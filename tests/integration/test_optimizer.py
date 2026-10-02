"""End-to-end acceptance tests for the integrated v0.3 optimizer."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray
from pydantic import ValidationError

from context_invariant import (
    ConflictOverride,
    ConflictPolicy,
    ConstraintPolicy,
    ContextEdge,
    ContextItem,
    ContextOptimizer,
    ContextType,
    DependencyReferenceRequirement,
    OptimizationPolicy,
    ValidatedRepresentation,
)
from context_invariant.compression import CompressionExecutor, CompressionResult
from context_invariant.errors import (
    EmbeddingProviderError,
    MandatoryContextOverflow,
    RequiredContextOverflow,
    UnknownDependencyReference,
    UnresolvedConflict,
)
from context_invariant.models import DependencyRelation
from context_invariant.store import InMemoryContextStore, SQLiteContextStore


class WordTokenizer:
    def count_tokens(self, text: str) -> int:
        return len(text.split())


class UnavailableEmbeddingProvider:
    @property
    def identity(self) -> str:
        return "unavailable"

    def embed(self, texts: Sequence[str]) -> NDArray[np.float64]:
        del texts
        raise EmbeddingProviderError("offline")


class ConstantEmbeddingProvider:
    @property
    def identity(self) -> str:
        return "constant"

    def embed(self, texts: Sequence[str]) -> NDArray[np.float64]:
        return np.ones((len(texts), 3), dtype=np.float64)


class ReferenceDroppingCompressor:
    def compress(
        self,
        item: ContextItem,
        target_tokens: int,
        task: str,
    ) -> CompressionResult:
        del target_tokens, task
        return CompressionResult(
            content="short summary",
            original_tokens=item.token_count or 0,
            compressed_tokens=2,
            source_item_id=item.id,
            strategy="reference_dropping_test",
            provenance=(item.id,),
            lossy=True,
        )


def make_item(
    item_id: str,
    content: str,
    context_type: ContextType,
    position: int,
    *,
    mandatory: bool = False,
) -> ContextItem:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=position)
    return ContextItem(
        id=item_id,
        content=content,
        type=context_type,
        created_at=timestamp,
        updated_at=timestamp,
        mandatory=mandatory,
        evictable=not mandatory,
    )


def policy(budget: int) -> OptimizationPolicy:
    return OptimizationPolicy(
        max_input_tokens=budget,
        compression_target_ratio=0.4,
        minimum_compressed_tokens=2,
    )


def test_full_mixed_context_pipeline_is_deterministic_and_fully_traced() -> None:
    items = [
        make_item(
            "system",
            "Follow safety rules",
            ContextType.SYSTEM_INSTRUCTION,
            0,
            mandatory=True,
        ),
        make_item(
            "doc",
            "Authentication timeout is 37 seconds. Extra background.",
            ContextType.RETRIEVED_DOCUMENT,
            1,
        ),
        make_item("state", "Current task is timeout repair", ContextType.TASK_STATE, 2),
        make_item("noise", "Formatting completed normally", ContextType.TOOL_OUTPUT, 3),
    ]
    optimizer = ContextOptimizer(tokenizer=WordTokenizer())

    first = optimizer.optimize("repair authentication timeout", items, policy(12))
    second = optimizer.optimize("repair authentication timeout", items, policy(12))

    assert first.final_token_count <= 12
    assert first.selected_items[0].id == "system"
    assert [item.id for item in first.selected_items] == [item.id for item in second.selected_items]
    assert first.trace.items[0].final_position == 0
    assert set(first.trace.stage_timings_ms) == {
        "validate_policy",
        "tokenize",
        "reserve_mandatory",
        "exact_dedup",
        "semantic_dedup",
        "contextual_budget_validation",
        "relevance",
        "importance",
        "recency",
        "novelty",
        "dependencies",
        "composite_utility",
        "allocation_plan",
        "compression",
        "final_selection",
        "layout",
        "invariant_validation",
        "trace",
        "lifecycle_persistence",
    }


def test_sqlite_persistence_is_part_of_integrated_pipeline(tmp_path: Path) -> None:
    store = SQLiteContextStore(tmp_path / "optimizer.db")
    source = make_item("persisted", "durable optimizer input", ContextType.MEMORY, 0)
    ContextOptimizer(tokenizer=WordTokenizer(), store=store).optimize(
        "durability", [source], policy(10)
    )
    store.close()

    reopened = SQLiteContextStore(tmp_path / "optimizer.db")
    assert reopened.load_item("persisted").token_count == 3
    reopened.close()


def test_unavailable_semantic_provider_has_visible_offline_fallback() -> None:
    source = make_item("source", "offline provider context", ContextType.MEMORY, 0)
    result = ContextOptimizer(
        tokenizer=WordTokenizer(), embedding_provider=UnavailableEmbeddingProvider()
    ).optimize("task", [source], policy(10))

    assert "embedding_provider_unavailable:deterministic_fallback" in result.trace.warnings


def test_semantic_deduplication_can_be_explicitly_disabled_for_ablation() -> None:
    first = make_item("first", "alpha beta", ContextType.MEMORY, 0)
    second = make_item("second", "alpha beta extra", ContextType.MEMORY, 1)
    optimizer = ContextOptimizer(
        tokenizer=WordTokenizer(),
        embedding_provider=ConstantEmbeddingProvider(),
    )

    enabled = optimizer.optimize("alpha", [first, second], policy(20))
    disabled = optimizer.optimize(
        "alpha",
        [first, second],
        policy(20).model_copy(update={"semantic_dedup_enabled": False}),
    )

    assert len(enabled.selected_items) == 1
    assert {item.id for item in disabled.selected_items} == {"first", "second"}
    assert all(item.semantic_duplicate_of is None for item in disabled.trace.items)


def test_mandatory_overflow_fails_before_deduplication() -> None:
    mandatory = make_item(
        "mandatory", "one two three four", ContextType.SYSTEM_INSTRUCTION, 0, mandatory=True
    )
    with pytest.raises(MandatoryContextOverflow):
        ContextOptimizer(tokenizer=WordTokenizer()).optimize("task", [mandatory], policy(3))


def test_empty_optional_context_and_cyclic_dependencies_are_supported() -> None:
    mandatory = make_item("system", "required", ContextType.SYSTEM_INSTRUCTION, 0, mandatory=True)
    only_mandatory = ContextOptimizer(tokenizer=WordTokenizer()).optimize(
        "task", [mandatory], policy(5)
    )
    assert [item.id for item in only_mandatory.selected_items] == ["system"]

    first = make_item("first", "first dependency", ContextType.DECISION, 1)
    second = make_item("second", "second dependency", ContextType.PLAN, 2)
    edges = [
        ContextEdge(
            source_id="first",
            target_id="second",
            relation=DependencyRelation.REQUIRES,
            weight=1.0,
        ),
        ContextEdge(
            source_id="second",
            target_id="first",
            relation=DependencyRelation.RELATED_TO,
            weight=0.5,
        ),
    ]
    cyclic = ContextOptimizer(tokenizer=WordTokenizer(), edges=edges).optimize(
        "dependency", [first, second], policy(10)
    )
    assert {item.id for item in cyclic.selected_items} == {"first", "second"}


def test_large_tool_output_compresses_without_losing_error_line() -> None:
    log = make_item(
        "log",
        "start request\nnoise one two three four five\nERROR status=503 request_id=ABC-42\n"
        "more irrelevant output values here\nend request",
        ContextType.TOOL_OUTPUT,
        0,
    )
    result = ContextOptimizer(tokenizer=WordTokenizer()).optimize(
        "request failed", [log], policy(8)
    )

    selected = result.selected_items[0]
    assert selected.metadata["compression_strategy"] == "tool_output"
    assert "ERROR status=503 request_id=ABC-42" in selected.content
    assert result.final_token_count <= 8


def test_repeated_numeric_different_items_are_not_semantically_collapsed() -> None:
    first = make_item("timeout-30", "Timeout is 30 seconds.", ContextType.DECISION, 0)
    second = make_item("timeout-60", "Timeout is 60 seconds.", ContextType.DECISION, 1)
    result = ContextOptimizer(tokenizer=WordTokenizer()).optimize(
        "timeout", [first, second], policy(20)
    )

    assert {item.id for item in result.selected_items} == {"timeout-30", "timeout-60"}


def test_public_optimizer_enforces_constraints_only_when_explicitly_enabled() -> None:
    task = make_item(
        "task",
        "execute using current state",
        ContextType.USER_MESSAGE,
        0,
        mandatory=True,
    )
    obsolete = make_item("obsolete", "obsolete state", ContextType.TASK_STATE, 1)
    current = make_item("current", "authoritative current state", ContextType.TASK_STATE, 2)
    edges = [
        ContextEdge(
            source_id="task",
            target_id="current",
            relation=DependencyRelation.REQUIRES,
            weight=1.0,
        ),
        ContextEdge(
            source_id="current",
            target_id="obsolete",
            relation=DependencyRelation.SUPERSEDES,
            weight=1.0,
        ),
    ]
    items = [task, obsolete, current]
    legacy_policy = policy(9).model_copy(
        update={"semantic_dedup_enabled": False, "compression_enabled": False}
    )
    constrained_policy = legacy_policy.model_copy(update={"max_input_tokens": 7})
    store = InMemoryContextStore()

    default_result = ContextOptimizer(tokenizer=WordTokenizer(), edges=edges).optimize(
        "execute", items, legacy_policy
    )
    explicitly_disabled = ContextOptimizer(
        tokenizer=WordTokenizer(),
        edges=edges,
        constraint_policy=ConstraintPolicy(),
    ).optimize("execute", items, legacy_policy)
    enforced = ContextOptimizer(
        tokenizer=WordTokenizer(),
        edges=edges,
        store=store,
        constraint_policy=ConstraintPolicy.enforced(),
    ).optimize("execute", items, constrained_policy)

    assert [item.id for item in default_result.selected_items] == [
        item.id for item in explicitly_disabled.selected_items
    ]
    assert {item.id for item in default_result.selected_items} == {
        "task",
        "obsolete",
        "current",
    }
    assert {item.id for item in enforced.selected_items} == {"task", "current"}
    assert {item.id for item in enforced.removed_items} == {"obsolete"}
    assert enforced.constraint_resolution is not None
    assert set(enforced.constraint_resolution.selected_item_ids) == {"task", "current"}
    assert enforced.constraint_resolution.removed_superseded_item_ids == ("obsolete",)
    assert enforced.trace.strategy == "context_invariant_constraint_aware"
    assert enforced.trace.optimization_passes == 1
    assert enforced.trace.constraint_policy == ConstraintPolicy.enforced()
    assert [trace.item_id for trace in enforced.trace.items] == [
        "task",
        "obsolete",
        "current",
    ]
    obsolete_trace = next(trace for trace in enforced.trace.items if trace.item_id == "obsolete")
    assert obsolete_trace.decision_reason == "removed_by_supersession_constraint"
    assert all(trace.constraint_resolution_applied for trace in enforced.trace.items)
    assert [item.id for item in store.list_items()] == ["current", "obsolete", "task"]
    assert store.load_item("obsolete").token_count == 2
    assert {
        (edge.source_id, edge.target_id, edge.relation) for edge in store.load_dependencies()
    } == {(edge.source_id, edge.target_id, edge.relation) for edge in edges}
    assert items[0].token_count is None
    assert items[1].token_count is None
    assert items[2].token_count is None


def test_public_optimizer_exposes_explicit_unresolved_conflict_policy() -> None:
    left = make_item("left", "left", ContextType.TASK_STATE, 0, mandatory=True)
    right = make_item("right", "right", ContextType.TASK_STATE, 0)
    edge = ContextEdge(
        source_id="left",
        target_id="right",
        relation=DependencyRelation.CONTRADICTS,
        weight=1.0,
    )

    failed_store = InMemoryContextStore()
    with pytest.raises(UnresolvedConflict):
        ContextOptimizer(
            tokenizer=WordTokenizer(),
            edges=[edge],
            store=failed_store,
            constraint_policy=ConstraintPolicy.enforced(),
        ).optimize("resolve", [left, right], policy(2))
    assert failed_store.list_items() == []
    assert failed_store.load_dependencies() == []

    retain_both = ConstraintPolicy.enforced(conflict_policy=ConflictPolicy.RETAIN_BOTH)
    result = ContextOptimizer(
        tokenizer=WordTokenizer(),
        edges=[edge],
        constraint_policy=retain_both,
    ).optimize("resolve", [left, right], policy(2))

    assert {item.id for item in result.selected_items} == {"left", "right"}
    assert result.constraint_resolution is not None
    assert result.constraint_resolution.unresolved_conflicts == (("left", "right"),)
    assert ConstraintPolicy.model_validate_json(retain_both.model_dump_json()) == retain_both


def test_public_optimizer_reports_dependency_closure_overflow() -> None:
    operation = make_item(
        "operation",
        "execute operation",
        ContextType.USER_MESSAGE,
        0,
        mandatory=True,
    )
    dependency = make_item(
        "dependency",
        "required dependency has three tokens",
        ContextType.TASK_STATE,
        1,
    )
    edge = ContextEdge(
        source_id="operation",
        target_id="dependency",
        relation=DependencyRelation.REQUIRES,
        weight=1.0,
    )

    failed_store = InMemoryContextStore()
    with pytest.raises(RequiredContextOverflow) as error:
        ContextOptimizer(
            tokenizer=WordTokenizer(),
            edges=[edge],
            store=failed_store,
            constraint_policy=ConstraintPolicy.enforced(),
        ).optimize(
            "execute",
            [operation, dependency],
            policy(4).model_copy(update={"compression_enabled": False}),
        )

    assert error.value.required_item_ids == ("operation", "dependency")
    assert error.value.required_tokens == 7
    assert error.value.effective_budget == 4
    assert failed_store.list_items() == []
    assert failed_store.load_dependencies() == []


def test_public_optimizer_uses_validated_representation_for_required_source() -> None:
    operation = make_item(
        "operation",
        "execute",
        ContextType.USER_MESSAGE,
        0,
        mandatory=True,
    )
    source = make_item(
        "source",
        "large original dependency that cannot fit",
        ContextType.RETRIEVED_DOCUMENT,
        1,
    )
    compact = make_item("compact", "summary", ContextType.RETRIEVED_DOCUMENT, 2)
    compact.importance = 0.0
    decoy = make_item("decoy", "summary", ContextType.RETRIEVED_DOCUMENT, 3)
    decoy.importance = 1.0
    representation = ValidatedRepresentation(
        source_item_id="source",
        representation_item_id="compact",
        validator_names=("ContractValidationEngine",),
    )
    edge = ContextEdge(
        source_id="operation",
        target_id="source",
        relation=DependencyRelation.REQUIRES,
        weight=1.0,
    )
    constraint_policy = ConstraintPolicy.enforced(validated_representations=(representation,))

    result = ContextOptimizer(
        tokenizer=WordTokenizer(),
        edges=[edge],
        constraint_policy=constraint_policy,
    ).optimize(
        "execute",
        [operation, source, compact, decoy],
        policy(2).model_copy(
            update={
                "semantic_dedup_enabled": False,
                "semantic_relevance_enabled": False,
                "compression_enabled": False,
                "weight_relevance": 0.0,
                "weight_importance": 1.0,
                "weight_recency": 0.0,
                "weight_novelty": 0.0,
                "weight_dependency": 0.0,
                "weight_type_priority": 0.0,
            }
        ),
    )

    assert {item.id for item in result.selected_items} == {"operation", "compact"}
    assert result.constraint_resolution is not None
    assert set(result.constraint_resolution.represented_item_ids) == {
        "operation",
        "source",
        "compact",
    }
    assert result.constraint_resolution.added_required_item_ids == ("compact",)
    assert result.trace.optimization_passes == 2
    assert {
        "constraint_setup",
        "constraint_legal_universe",
        "constraint_candidate_filter",
        "constraint_required_preflight",
        "constraint_force_required",
        "constraint_resolution",
        "constraint_result_assembly",
        "constraint_trace_patch",
        "constraint_persistence",
    } <= result.trace.stage_timings_ms.keys()
    source_trace = next(trace for trace in result.trace.items if trace.item_id == "source")
    decoy_trace = next(trace for trace in result.trace.items if trace.item_id == "decoy")
    assert source_trace.decision_reason == "replaced_by_validated_representation"
    assert decoy_trace.exact_duplicate_of == "compact"
    assert ConstraintPolicy.model_validate_json(constraint_policy.model_dump_json()) == (
        constraint_policy
    )


def test_public_optimizer_applies_serializable_conflict_override() -> None:
    left = make_item("left", "left state", ContextType.TASK_STATE, 0)
    right = make_item("right", "right state", ContextType.TASK_STATE, 0)
    edge = ContextEdge(
        source_id="left",
        target_id="right",
        relation=DependencyRelation.CONTRADICTS,
        weight=1.0,
    )
    override = ConflictOverride(
        left_item_id="right",
        right_item_id="left",
        winner_item_id="right",
    )

    result = ContextOptimizer(
        tokenizer=WordTokenizer(),
        edges=[edge],
        constraint_policy=ConstraintPolicy.enforced(conflict_overrides=(override,)),
    ).optimize("resolve", [left, right], policy(4))

    assert [item.id for item in result.selected_items] == ["right"]
    assert result.constraint_resolution is not None
    assert result.constraint_resolution.removed_conflicting_item_ids == ("left",)


def test_constraint_policy_rejects_ambiguous_duplicate_rules() -> None:
    representation = ValidatedRepresentation(
        source_item_id="source",
        representation_item_id="compact-a",
        validator_names=("Validator",),
    )
    duplicate = representation.model_copy(update={"representation_item_id": "compact-b"})
    override = ConflictOverride(
        left_item_id="left",
        right_item_id="right",
        winner_item_id="left",
    )
    reversed_duplicate = ConflictOverride(
        left_item_id="right",
        right_item_id="left",
        winner_item_id="right",
    )

    with pytest.raises(ValidationError, match="unique source"):
        ConstraintPolicy.enforced(validated_representations=(representation, duplicate))
    with pytest.raises(ValidationError, match="unique endpoint pairs"):
        ConstraintPolicy.enforced(conflict_overrides=(override, reversed_duplicate))
    with pytest.raises(ValidationError, match="chains are not supported"):
        ConstraintPolicy.enforced(
            validated_representations=(
                representation,
                ValidatedRepresentation(
                    source_item_id="compact-a",
                    representation_item_id="compact-b",
                    validator_names=("Validator",),
                ),
            )
        )
    with pytest.raises(ValidationError, match="must differ"):
        ValidatedRepresentation(
            source_item_id="same",
            representation_item_id="same",
            validator_names=("Validator",),
        )
    with pytest.raises(ValidationError, match="winner must be one"):
        ConflictOverride(
            left_item_id="left",
            right_item_id="right",
            winner_item_id="third",
        )
    with pytest.raises(ValidationError, match="validator names must be unique"):
        ValidatedRepresentation(
            source_item_id="source",
            representation_item_id="compact",
            validator_names=("Validator", "Validator"),
        )
    with pytest.raises(ValidationError):
        ConstraintPolicy.model_validate({"enabled": 1})


def test_constraint_aware_compression_preserves_required_literal_references() -> None:
    source = make_item(
        "source",
        "Keep auth_001X. filler filler filler filler.",
        ContextType.MEMORY,
        0,
    )
    requirement = DependencyReferenceRequirement(
        item_id="source",
        references=("auth_001X",),
    )
    constraint_policy = ConstraintPolicy.enforced(dependency_references=(requirement,))

    result = ContextOptimizer(
        tokenizer=WordTokenizer(),
        compression_executor=CompressionExecutor(
            WordTokenizer(),
            type_aware=ReferenceDroppingCompressor(),
        ),
        constraint_policy=constraint_policy,
    ).optimize(
        "Keep the authentication reference",
        [source],
        policy(3).model_copy(update={"minimum_compressed_tokens": 1}),
    )

    assert result.selected_items[0].content == "Keep auth_001X."
    trace = result.trace.items[0]
    assert trace.fallback_path == ["reference_dropping_test", "extractive"]
    assert trace.transformation_attempts[0].violations == (
        "missing_dependency_reference:auth_001X",
    )
    assert any(
        outcome.validator == "DependencyReferenceValidator"
        for outcome in trace.transformation_attempts[1].validator_outcomes
    )
    assert result.trace.constraint_policy == constraint_policy
    assert ConstraintPolicy.model_validate_json(constraint_policy.model_dump_json()) == (
        constraint_policy
    )


def test_constraint_policy_rejects_invalid_dependency_reference_requirements() -> None:
    requirement = DependencyReferenceRequirement(
        item_id="source",
        references=("auth_001X",),
    )

    with pytest.raises(ValidationError, match="unique item IDs"):
        ConstraintPolicy.enforced(dependency_references=(requirement, requirement))
    with pytest.raises(ValidationError, match="must be unique"):
        DependencyReferenceRequirement(
            item_id="source",
            references=("auth_001X", "auth_001X"),
        )
    with pytest.raises(UnknownDependencyReference, match="missing"):
        ContextOptimizer(
            tokenizer=WordTokenizer(),
            constraint_policy=ConstraintPolicy.enforced(
                dependency_references=(
                    DependencyReferenceRequirement(
                        item_id="missing",
                        references=("auth_001X",),
                    ),
                )
            ),
        ).optimize("task", [make_item("known", "known", ContextType.MEMORY, 0)], policy(2))
