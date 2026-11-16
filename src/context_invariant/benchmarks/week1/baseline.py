"""Verbatim relevance selection with metadata-matched hard constraints."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from context_invariant import ContextConstraintGraph, OptimizationPolicy
from context_invariant.benchmarks.week1.models import StudyInputs
from context_invariant.embeddings import DeterministicEmbeddingProvider, EmbeddingProvider
from context_invariant.errors import RequiredContextOverflow
from context_invariant.scoring import relevance_scores
from context_invariant.tokenization import Tokenizer
from context_invariant.trace import (
    BudgetAllocation,
    ItemTrace,
    OptimizationDecision,
    OptimizationTrace,
    OptimizedContext,
)


class MetadataMatchedSelector:
    """Rank legal optional bundles by relevance, skipping bundles that cannot fit."""

    name = "metadata_matched"

    def __init__(self, provider: EmbeddingProvider | None = None) -> None:
        self._provider = provider or DeterministicEmbeddingProvider()

    def optimize(
        self, inputs: StudyInputs, policy: OptimizationPolicy, tokenizer: Tokenizer
    ) -> OptimizedContext:
        started = perf_counter()
        policy.validate_static()
        items = [item.model_copy(deep=True) for item in inputs.items]
        for item in items:
            item.token_count = tokenizer.count_tokens(item.content)
        graph = ContextConstraintGraph(items, inputs.edges)
        rules = inputs.constraint_policy

        def resolve(ids: set[str]) -> set[str]:
            return set(
                graph.resolve(
                    sorted(ids),
                    conflict_policy=rules.conflict_policy,
                    conflict_winners=rules.conflict_winners,
                    retain_superseded=rules.retain_superseded,
                ).selected_item_ids
            )

        by_id = {item.id: item for item in items}
        legal = resolve(set(by_id))
        selected = resolve({item.id for item in items if item.mandatory})

        def tokens(ids: set[str]) -> int:
            return sum(by_id[item_id].token_count or 0 for item_id in ids)

        if tokens(selected) > policy.effective_budget:
            raise RequiredContextOverflow(
                required_item_ids=tuple(item.id for item in items if item.id in selected),
                required_tokens=tokens(selected),
                effective_budget=policy.effective_budget,
            )
        scores = relevance_scores(
            inputs.task, [item for item in items if item.id in legal], provider=self._provider
        )
        positions = {item.id: index for index, item in enumerate(items)}
        decisions: list[dict[str, Any]] = []
        reasons = {
            item.id: "excluded_by_declared_relations" for item in items if item.id not in legal
        }
        for item_id in sorted(legal, key=lambda key: (-scores[key], positions[key], key)):
            if item_id in selected:
                continue
            proposed = resolve(selected | {item_id})
            fits = tokens(proposed) <= policy.effective_budget
            decisions.append(
                {
                    "candidate": item_id,
                    "relevance": scores[item_id],
                    "bundle_ids": sorted(proposed - selected),
                    "proposed_total_tokens": tokens(proposed),
                    "decision": "accepted" if fits else "skipped_bundle_over_budget",
                }
            )
            if fits:
                selected = proposed
            else:
                reasons[item_id] = "optional_bundle_over_budget"

        chosen = [item for item in items if item.id in selected]
        removed = [item for item in items if item.id not in selected]
        final_positions = {item.id: index for index, item in enumerate(chosen)}
        original_tokens = sum(item.token_count or 0 for item in items)
        used = tokens(selected)
        mandatory_tokens = sum(item.token_count or 0 for item in items if item.mandatory)
        trace = OptimizationTrace(
            strategy=self.name,
            policy=policy,
            constraint_policy=rules,
            effective_budget=policy.effective_budget,
            mandatory_tokens=mandatory_tokens,
            optional_budget=policy.effective_budget - mandatory_tokens,
            original_tokens=original_tokens,
            final_tokens=used,
            reduction_ratio=0.0 if not original_tokens else 1 - used / original_tokens,
            stage_timings_ms={"metadata_matched_selection": (perf_counter() - started) * 1000},
            selected_count=len(chosen),
            removed_count=len(removed),
            compressed_count=0,
            items=[
                ItemTrace(
                    item_id=item.id,
                    initial_token_count=item.token_count or 0,
                    relevance_score=scores.get(item.id),
                    decision=(
                        OptimizationDecision.RETAINED
                        if item.id in selected
                        else OptimizationDecision.REMOVED
                    ),
                    decision_reason=(
                        "mandatory_or_selected_support_or_relevance"
                        if item.id in selected
                        else reasons.get(item.id, "not_selected")
                    ),
                    final_token_count=(item.token_count or 0) if item.id in selected else 0,
                    final_position=final_positions.get(item.id),
                    final_representation_type="original" if item.id in selected else None,
                )
                for item in items
            ],
        )
        return OptimizedContext(
            selected_items=chosen,
            removed_items=removed,
            original_token_count=original_tokens,
            final_token_count=used,
            budget_allocation=BudgetAllocation(
                effective_budget=policy.effective_budget,
                used_tokens=used,
                remaining_tokens=policy.effective_budget - used,
            ),
            trace=trace,
            metadata={"bundle_decisions": decisions},
        )
