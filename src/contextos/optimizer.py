"""Authoritative integrated ContextOS optimization pipeline."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from time import perf_counter
from typing import Protocol, TypeVar

from contextos.budget import AllocationPlan, TokenBudgetAllocator, validate_contextual_budget
from contextos.compression import CompressionExecution, CompressionExecutor
from contextos.config import OptimizationPolicy
from contextos.constraints import ConstraintPolicy, ConstraintResolution, ContextConstraintGraph
from contextos.dedup import exact_deduplicate, semantic_deduplicate
from contextos.dedup.base import DeduplicationResult, DuplicateMatch
from contextos.dependency import DependencyGraph
from contextos.embeddings import (
    CachedEmbeddingProvider,
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
)
from contextos.errors import EmbeddingProviderError, MandatoryContextOverflow
from contextos.layout import LayoutStrategy, OriginalOrderLayout, PositionAwareLayout
from contextos.models import ContextEdge, ContextItem, validate_unique_item_ids
from contextos.scoring import ScoreBreakdown
from contextos.scoring.composite import composite_scores
from contextos.scoring.importance import importance_scores
from contextos.scoring.novelty import novelty_scores
from contextos.scoring.recency import recency_scores
from contextos.scoring.relevance import relevance_scores
from contextos.scoring.risk import RiskAssessment, assess_context_risk
from contextos.scoring.type_priority import type_priority_scores
from contextos.store import ContextStore
from contextos.tokenization import TiktokenTokenizer, Tokenizer
from contextos.trace import (
    BudgetAllocation,
    ConstraintTraceIndex,
    ItemTrace,
    OptimizationDecision,
    OptimizationTrace,
    OptimizedContext,
    summarize_transformation_trace,
)

T = TypeVar("T")


class CompressionExecutionEngine(Protocol):
    """Structural boundary used by research runs to freeze compression behavior."""

    def execute(
        self,
        plan: AllocationPlan,
        items: Sequence[ContextItem],
        *,
        task: str,
        policy: OptimizationPolicy,
    ) -> CompressionExecution:
        """Execute a previously constructed allocation plan."""
        ...


class ContextOptimizer:
    """Construct final model context as the sole token-budget authority."""

    def __init__(
        self,
        *,
        tokenizer: Tokenizer | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        edges: Sequence[ContextEdge] = (),
        layout: LayoutStrategy | None = None,
        store: ContextStore | None = None,
        compression_executor: CompressionExecutionEngine | None = None,
        constraint_policy: ConstraintPolicy | None = None,
    ) -> None:
        self._tokenizer = tokenizer or TiktokenTokenizer()
        self._provider = embedding_provider or DeterministicEmbeddingProvider()
        self._edges = tuple(edges)
        self._layout = layout
        self._store = store
        self._compression_executor = compression_executor or CompressionExecutor(self._tokenizer)
        self._constraint_policy = constraint_policy or ConstraintPolicy()

    def optimize(
        self,
        task: str,
        items: Sequence[ContextItem],
        policy: OptimizationPolicy,
    ) -> OptimizedContext:
        """Construct context through the legacy or opt-in constraint-aware pipeline."""
        if self._constraint_policy.enabled:
            return self._optimize_with_constraints(task, items, policy)
        return self._optimize_unconstrained(task, items, policy)

    def _optimize_unconstrained(
        self,
        task: str,
        items: Sequence[ContextItem],
        policy: OptimizationPolicy,
    ) -> OptimizedContext:
        """Execute the backwards-compatible integrated optimization pipeline."""
        timings: dict[str, float] = {}
        warnings: list[str] = []

        def stage(name: str, operation: Callable[[], T]) -> T:
            started = perf_counter()
            try:
                return operation()
            finally:
                timings[name] = (perf_counter() - started) * 1000

        stage("validate_policy", policy.validate_static)
        original_positions = {item.id: index for index, item in enumerate(items)}

        def tokenize() -> list[ContextItem]:
            validate_unique_item_ids(items)
            tokenized: list[ContextItem] = []
            for item in items:
                copied = item.model_copy(deep=True)
                copied.token_count = self._tokenizer.count_tokens(copied.content)
                tokenized.append(copied)
            return tokenized

        tokenized = stage("tokenize", tokenize)
        original_tokens = sum(item.token_count or 0 for item in tokenized)

        def reserve_mandatory() -> int:
            mandatory_tokens = sum(item.token_count or 0 for item in tokenized if item.mandatory)
            if mandatory_tokens > policy.effective_budget:
                raise MandatoryContextOverflow(
                    mandatory_tokens=mandatory_tokens,
                    effective_budget=policy.effective_budget,
                )
            return mandatory_tokens

        stage("reserve_mandatory", reserve_mandatory)
        exact = stage("exact_dedup", lambda: exact_deduplicate(tokenized))
        warnings.extend(exact.warnings)

        provider: EmbeddingProvider = CachedEmbeddingProvider(self._provider)

        def run_semantic() -> DeduplicationResult:
            return semantic_deduplicate(
                exact.items,
                provider=provider,
                threshold=policy.semantic_dedup_threshold,
            )

        if policy.semantic_dedup_enabled:
            try:
                semantic = stage("semantic_dedup", run_semantic)
            except EmbeddingProviderError:
                warnings.append("embedding_provider_unavailable:deterministic_fallback")
                provider = CachedEmbeddingProvider(DeterministicEmbeddingProvider())
                semantic = stage("semantic_dedup", run_semantic)
        else:
            semantic = stage(
                "semantic_dedup",
                lambda: DeduplicationResult(items=exact.items),
            )
        warnings.extend(semantic.warnings)
        survivors = semantic.items
        contextual = stage(
            "contextual_budget_validation",
            lambda: validate_contextual_budget(survivors, policy=policy),
        )

        relevance = stage(
            "relevance",
            lambda: (
                relevance_scores(task, survivors, provider=provider)
                if policy.semantic_relevance_enabled
                else {item.id: 0.0 for item in survivors}
            ),
        )
        importance = stage("importance", lambda: importance_scores(survivors))
        recency = stage(
            "recency",
            lambda: (
                recency_scores(
                    survivors,
                    half_life_seconds=policy.recency_half_life_seconds,
                )
                if policy.weight_recency > 0
                else {item.id: 0.0 for item in survivors}
            ),
        )
        novelty = stage("novelty", lambda: novelty_scores(survivors, provider=provider))
        for item in survivors:
            if item.mandatory:
                novelty[item.id] = 1.0

        survivor_ids = {item.id for item in survivors}
        survivor_edges = [
            edge
            for edge in self._edges
            if edge.source_id in survivor_ids and edge.target_id in survivor_ids
        ]

        def dependency_stage() -> dict[str, float]:
            if policy.weight_dependency == 0:
                return {item.id: 0.0 for item in survivors}
            DependencyGraph([item.id for item in tokenized], self._edges)
            graph = DependencyGraph(list(survivor_ids), survivor_edges)
            return graph.propagate_scores(
                {item.id: max(relevance[item.id], importance[item.id]) for item in survivors},
                max_depth=policy.dependency_max_depth,
            )

        dependency = stage("dependencies", dependency_stage)
        type_priority = type_priority_scores(survivors, priorities=policy.type_priorities)

        def risk_stage() -> dict[str, RiskAssessment]:
            DependencyGraph([item.id for item in tokenized], self._edges)
            return assess_context_risk(survivors, survivor_edges)

        risk = stage("risk_assessment", risk_stage) if policy.risk_aware_allocation else {}
        scores = stage(
            "composite_utility",
            lambda: composite_scores(
                survivors,
                policy=policy,
                relevance=relevance,
                importance=importance,
                recency=recency,
                novelty=novelty,
                dependency=dependency,
                type_priority=type_priority,
                omission_risk={item_id: value.omission_risk for item_id, value in risk.items()},
                transformation_risk={
                    item_id: value.transformation_risk for item_id, value in risk.items()
                },
            ),
        )
        plan = stage(
            "allocation_plan",
            lambda: TokenBudgetAllocator().allocate(survivors, scores=scores, policy=policy),
        )
        compression = stage(
            "compression",
            lambda: self._compression_executor.execute(
                plan,
                survivors,
                task=task,
                policy=policy,
            ),
        )

        def final_selection() -> list[ContextItem]:
            survivor_by_id = {item.id: item for item in survivors}
            selected = [item.model_copy(deep=True) for item in survivors if item.mandatory]
            selected.extend(
                survivor_by_id[selection.item_id].model_copy(deep=True)
                for selection in plan.direct_selected
            )
            for item_id, result in compression.successful_results.items():
                source = survivor_by_id[item_id].model_copy(deep=True)
                source.content = result.content or source.content
                source.token_count = result.compressed_tokens
                source.metadata = {
                    **source.metadata,
                    "compression_strategy": result.strategy,
                    "compression_provenance": list(result.provenance),
                    "compression_lossy": result.lossy,
                }
                selected.append(source)
            return selected

        selected = stage("final_selection", final_selection)
        strategy = self._layout or (
            PositionAwareLayout() if policy.position_aware_layout else OriginalOrderLayout()
        )
        laid_out = stage(
            "layout",
            lambda: strategy.arrange(
                selected,
                scores=scores,
                original_positions=original_positions,
            ),
        )

        def validate_invariants() -> int:
            validate_unique_item_ids(laid_out)
            selected_ids = {item.id for item in laid_out}
            missing_mandatory = sorted(
                item.id for item in survivors if item.mandatory and item.id not in selected_ids
            )
            if missing_mandatory:
                raise AssertionError("mandatory context was removed")
            final_tokens = sum(item.token_count or 0 for item in laid_out)
            if final_tokens > policy.effective_budget:
                raise AssertionError("integrated optimizer exceeded the effective budget")
            return final_tokens

        final_tokens = stage("invariant_validation", validate_invariants)
        exact_matches = exact.matches_by_item_id
        semantic_matches = semantic.matches_by_item_id
        traces = stage(
            "trace",
            lambda: self._build_item_traces(
                tokenized,
                laid_out,
                scores,
                plan,
                compression,
                exact_matches,
                semantic_matches,
                policy,
                self._edges,
            ),
        )

        def persist() -> None:
            if self._store is None:
                return
            for item in tokenized:
                self._store.save_item(item)
            for edge in self._edges:
                self._store.save_edge(edge)

        stage("lifecycle_persistence", persist)
        selected_ids = {item.id for item in laid_out}
        removed = [item for item in tokenized if item.id not in selected_ids]
        reduction = (
            0.0 if original_tokens == 0 else (original_tokens - final_tokens) / original_tokens
        )
        trace = OptimizationTrace(
            strategy="contextos",
            policy=policy,
            effective_budget=policy.effective_budget,
            mandatory_tokens=contextual.mandatory_tokens,
            optional_budget=contextual.optional_budget,
            original_tokens=original_tokens,
            final_tokens=final_tokens,
            reduction_ratio=max(0.0, min(reduction, 1.0)),
            stage_timings_ms=timings,
            selected_count=len(laid_out),
            removed_count=len(removed),
            compressed_count=sum(
                result.lossy for result in compression.successful_results.values()
            ),
            warnings=sorted(set(warnings)),
            items=traces,
        )
        return OptimizedContext(
            selected_items=laid_out,
            removed_items=removed,
            original_token_count=original_tokens,
            final_token_count=final_tokens,
            budget_allocation=BudgetAllocation(
                effective_budget=policy.effective_budget,
                used_tokens=final_tokens,
                remaining_tokens=policy.effective_budget - final_tokens,
            ),
            trace=trace,
            metadata={"layout": type(strategy).__name__},
        )

    def _optimize_with_constraints(
        self,
        task: str,
        items: Sequence[ContextItem],
        policy: OptimizationPolicy,
    ) -> OptimizedContext:
        """Enforce directed hard constraints around the stable optimization pipeline."""
        tokenized = self._tokenize_items(items)
        by_id = {item.id: item for item in tokenized}
        graph = ContextConstraintGraph(tokenized, self._edges)
        representations = self._constraint_policy.validated_representations
        conflict_winners = self._constraint_policy.conflict_winners
        representation_map = {
            representation.source_item_id: representation.representation_item_id
            for representation in representations
        }
        universe_seeds = tuple(item_id for item_id in by_id if item_id not in representation_map)
        legal_universe = graph.resolve(
            universe_seeds,
            representations=representations,
            conflict_policy=self._constraint_policy.conflict_policy,
            conflict_winners=conflict_winners,
            retain_superseded=self._constraint_policy.retain_superseded,
        )
        legal_ids = set(legal_universe.selected_item_ids)
        candidates = [item for item in tokenized if item.id in legal_ids]
        candidate_edges = [
            edge
            for edge in self._edges
            if edge.source_id in legal_ids and edge.target_id in legal_ids
        ]
        forced: set[str] = set()
        first_resolution: ConstraintResolution | None = None
        final_resolution: ConstraintResolution | None = None
        result: OptimizedContext | None = None
        for _ in range(len(candidates) + 1):
            if forced:
                required_seeds = {
                    representation_map.get(item.id, item.id) for item in tokenized if item.mandatory
                } | forced
                graph.resolve(
                    tuple(required_seeds),
                    effective_budget=policy.effective_budget,
                    representations=representations,
                    conflict_policy=self._constraint_policy.conflict_policy,
                    conflict_winners=conflict_winners,
                    retain_superseded=self._constraint_policy.retain_superseded,
                )
            prepared = self._force_required(candidates, forced)
            result = ContextOptimizer(
                tokenizer=self._tokenizer,
                embedding_provider=self._provider,
                edges=candidate_edges,
                layout=self._layout,
                compression_executor=self._compression_executor,
            ).optimize(task, prepared, policy)
            resolution = graph.resolve(
                tuple(item.id for item in result.selected_items),
                representations=representations,
                conflict_policy=self._constraint_policy.conflict_policy,
                conflict_winners=conflict_winners,
                retain_superseded=self._constraint_policy.retain_superseded,
            )
            final_resolution = resolution
            if first_resolution is None:
                first_resolution = resolution
            additions = set(resolution.selected_item_ids) - {
                item.id for item in result.selected_items
            }
            if not additions:
                break
            forced.update(additions)
        else:
            raise AssertionError("constraint-enforced optimization did not converge")
        assert result is not None and first_resolution is not None and final_resolution is not None
        trace_resolution = final_resolution.model_copy(
            update={
                "added_required_item_ids": first_resolution.added_required_item_ids,
                "removed_superseded_item_ids": tuple(
                    dict.fromkeys(
                        (
                            *legal_universe.removed_superseded_item_ids,
                            *final_resolution.removed_superseded_item_ids,
                        )
                    )
                ),
                "removed_conflicting_item_ids": tuple(
                    dict.fromkeys(
                        (
                            *legal_universe.removed_conflicting_item_ids,
                            *final_resolution.removed_conflicting_item_ids,
                        )
                    )
                ),
            }
        )

        full_original_tokens = sum(item.token_count or 0 for item in tokenized)
        filtered_out = [item for item in tokenized if item.id not in legal_ids]
        selected_ids = {item.id for item in result.selected_items}
        removed = [item for item in tokenized if item.id not in selected_ids]
        reduction = (
            0.0
            if full_original_tokens == 0
            else (full_original_tokens - result.final_token_count) / full_original_tokens
        )
        updated_trace = result.trace.model_copy(
            update={
                "constraint_policy": self._constraint_policy,
                "original_tokens": full_original_tokens,
                "reduction_ratio": max(0.0, min(reduction, 1.0)),
                "removed_count": len(removed),
                "warnings": sorted(
                    set(result.trace.warnings)
                    | ({"hard_constraints_filtered_items"} if filtered_out else set())
                ),
            }
        )
        result = result.model_copy(
            update={
                "original_token_count": full_original_tokens,
                "removed_items": removed,
                "trace": updated_trace,
                "constraint_resolution": trace_resolution,
                "metadata": {
                    **result.metadata,
                    "constraint_policy": self._constraint_policy.model_dump(mode="json"),
                    "constraint_resolution": trace_resolution.model_dump(mode="json"),
                },
            }
        )
        result = self._patch_constraint_trace(
            result,
            original_items=tokenized,
            resolution=trace_resolution,
        )
        if self._store is not None:
            for item in tokenized:
                self._store.save_item(item)
            for edge in self._edges:
                self._store.save_edge(edge)
        return result

    def _tokenize_items(self, items: Sequence[ContextItem]) -> list[ContextItem]:
        validate_unique_item_ids(items)
        tokenized: list[ContextItem] = []
        for item in items:
            copied = item.model_copy(deep=True)
            copied.token_count = self._tokenizer.count_tokens(copied.content)
            tokenized.append(copied)
        return tokenized

    @staticmethod
    def _force_required(
        items: Sequence[ContextItem],
        item_ids: set[str],
    ) -> list[ContextItem]:
        prepared: list[ContextItem] = []
        for item in items:
            copied = item.model_copy(deep=True)
            if item.id in item_ids:
                copied.evictable = False
                copied.mandatory = True
            prepared.append(copied)
        return prepared

    def _patch_constraint_trace(
        self,
        result: OptimizedContext,
        *,
        original_items: Sequence[ContextItem],
        resolution: ConstraintResolution,
    ) -> OptimizedContext:
        index = ConstraintTraceIndex(
            original_items,
            self._edges,
            selected_item_ids=tuple(item.id for item in result.selected_items),
            resolution=resolution,
        )
        traces_by_id: dict[str, ItemTrace] = {}
        for trace in result.trace.items:
            evidence = index.for_item(trace.item_id)
            traces_by_id[trace.item_id] = trace.model_copy(
                update={
                    "hard_constraints_triggered": list(evidence.hard_constraints_triggered),
                    "required_by": list(evidence.required_by),
                    "dependency_closure": list(evidence.dependency_closure),
                    "superseded_items": list(evidence.superseded_items),
                    "conflict_status": evidence.conflict_status,
                    "constraint_resolution_applied": True,
                    "would_have_been_removed_without_constraints": (
                        evidence.would_have_been_removed_without_constraints
                    ),
                }
            )

        removed_superseded = set(resolution.removed_superseded_item_ids)
        removed_conflicting = set(resolution.removed_conflicting_item_ids)
        represented_sources = set(resolution.represented_item_ids) - set(
            resolution.selected_item_ids
        )
        for item in original_items:
            if item.id in traces_by_id:
                continue
            evidence = index.for_item(item.id)
            if item.id in removed_superseded:
                reason = "removed_by_supersession_constraint"
            elif item.id in removed_conflicting:
                reason = "removed_by_conflict_constraint"
            elif item.id in represented_sources:
                reason = "replaced_by_validated_representation"
            else:
                reason = "removed_by_hard_constraint"
            traces_by_id[item.id] = ItemTrace(
                item_id=item.id,
                initial_token_count=item.token_count or 0,
                preservation_contract=item.contract,
                hard_constraints_triggered=list(evidence.hard_constraints_triggered),
                required_by=list(evidence.required_by),
                dependency_closure=list(evidence.dependency_closure),
                superseded_items=list(evidence.superseded_items),
                conflict_status=evidence.conflict_status,
                constraint_resolution_applied=True,
                would_have_been_removed_without_constraints=(
                    evidence.would_have_been_removed_without_constraints
                ),
                decision=OptimizationDecision.REMOVED,
                decision_reason=reason,
                final_token_count=0,
            )
        traces = [traces_by_id[item.id] for item in original_items]
        return result.model_copy(
            update={"trace": result.trace.model_copy(update={"items": traces})}
        )

    @staticmethod
    def _build_item_traces(
        original: Sequence[ContextItem],
        selected: Sequence[ContextItem],
        scores: Mapping[str, ScoreBreakdown],
        plan: AllocationPlan,
        compression: CompressionExecution,
        exact_matches: Mapping[str, DuplicateMatch],
        semantic_matches: Mapping[str, DuplicateMatch],
        policy: OptimizationPolicy,
        edges: Sequence[ContextEdge],
    ) -> list[ItemTrace]:
        selected_by_id = {item.id: item for item in selected}
        positions = {item.id: index for index, item in enumerate(selected)}
        attempts = {attempt.item_id: attempt for attempt in compression.attempts}
        direct_allocations = {value.item_id: value for value in plan.direct_selected}
        compression_allocations = {value.item_id: value for value in plan.compression_requests}
        constraint_evidence = ConstraintTraceIndex(
            original,
            edges,
            selected_item_ids=tuple(selected_by_id),
        )
        traces: list[ItemTrace] = []
        for item in original:
            exact = exact_matches.get(item.id)
            semantic = semantic_matches.get(item.id)
            score = scores.get(item.id)
            final = selected_by_id.get(item.id)
            result = compression.successful_results.get(item.id)
            attempt = attempts.get(item.id)
            allocation = direct_allocations.get(item.id) or compression_allocations.get(item.id)
            constraint = constraint_evidence.for_item(item.id)
            transformation_attempts = list(attempt.transformation_attempts) if attempt else []
            transformation = summarize_transformation_trace(
                item.contract,
                transformation_attempts,
                attempt.fallback_path if attempt else (),
            )
            if exact is not None:
                decision = OptimizationDecision.REMOVED
                reason = exact.reason
            elif semantic is not None:
                decision = OptimizationDecision.REMOVED
                reason = semantic.reason
            elif result is not None:
                decision = (
                    OptimizationDecision.COMPRESSED
                    if result.lossy
                    else OptimizationDecision.RETAINED
                )
                reason = (
                    "compressed_to_fit_budget"
                    if result.lossy
                    else "retained_after_transformation_fallback"
                )
            elif final is not None:
                decision = OptimizationDecision.RETAINED
                reason = "mandatory" if item.mandatory else "allocated_without_compression"
            else:
                decision = OptimizationDecision.REMOVED
                reason = (
                    attempt.reason
                    if attempt is not None and attempt.reason is not None
                    else plan.rejection_reasons.get(item.id, "not_selected")
                )
            selection_value = (
                allocation.selection_value
                if allocation is not None and allocation.selection_value is not None
                else score.selection_value
                if score is not None
                else None
            )
            value_density = (
                allocation.value_density
                if allocation is not None
                else selection_value / max(item.token_count or 0, 1)
                if selection_value is not None
                else None
            )
            traces.append(
                ItemTrace(
                    item_id=item.id,
                    initial_token_count=item.token_count or 0,
                    exact_duplicate_of=exact.duplicate_of if exact else None,
                    semantic_duplicate_of=semantic.duplicate_of if semantic else None,
                    semantic_similarity=semantic.similarity if semantic else None,
                    relevance_score=score.relevance if score else None,
                    importance_score=score.importance if score else None,
                    recency_score=score.recency if score else None,
                    novelty_score=score.novelty if score else None,
                    dependency_score=score.dependency if score else None,
                    type_priority=score.type_priority if score else None,
                    composite_utility=score.composite_utility if score else None,
                    omission_risk=(
                        score.omission_risk if score and policy.risk_aware_allocation else None
                    ),
                    transformation_risk=(
                        score.transformation_risk
                        if score and policy.risk_aware_allocation
                        else None
                    ),
                    selection_value=selection_value,
                    transformed_selection_value=(
                        score.transformed_selection_value if score else None
                    ),
                    value_density=value_density,
                    preservation_contract=item.contract,
                    hard_constraints_triggered=list(constraint.hard_constraints_triggered),
                    required_by=list(constraint.required_by),
                    dependency_closure=list(constraint.dependency_closure),
                    superseded_items=list(constraint.superseded_items),
                    conflict_status=constraint.conflict_status,
                    constraint_resolution_applied=constraint.constraint_resolution_applied,
                    would_have_been_removed_without_constraints=(
                        constraint.would_have_been_removed_without_constraints
                    ),
                    decision=decision,
                    decision_reason=reason,
                    final_token_count=final.token_count or 0 if final else 0,
                    final_position=positions.get(item.id),
                    compression_strategy=result.strategy if result else None,
                    provenance=list(result.provenance) if result else [],
                    transformation_attempted=transformation.transformation_attempted,
                    transformation_attempts=transformation_attempts,
                    validators_executed=list(transformation.validators_executed),
                    validator_results=list(transformation.validator_results),
                    fallback_path=list(attempt.fallback_path) if attempt else [],
                    fallback_used=transformation.fallback_used,
                    final_representation_type=(
                        attempt.final_representation_type
                        if attempt and attempt.final_representation_type is not None
                        else "original"
                        if final is not None
                        else None
                    ),
                    would_have_been_compressed_without_contract=(
                        transformation.would_have_been_compressed_without_contract
                    ),
                )
            )
        return traces
