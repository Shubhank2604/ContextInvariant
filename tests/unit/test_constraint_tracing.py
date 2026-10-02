"""Phase 5H constraint-aware trace tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from context_invariant import (
    ConflictTraceStatus,
    ConstraintResolution,
    ConstraintTraceIndex,
    ContextEdge,
    ContextItem,
    ContextOptimizer,
    ContextType,
    DependencyRelation,
    OptimizationPolicy,
    OptimizedContext,
    PreservationContract,
    summarize_transformation_trace,
)
from context_invariant.errors import UnknownDependencyReference
from context_invariant.trace import OptimizationTrace
from context_invariant.validation import TransformationAttemptRecord, ValidatorOutcome

_NOW = datetime(2026, 9, 13, tzinfo=UTC)


class WordTokenizer:
    def count_tokens(self, text: str) -> int:
        return len(text.split())


def _item(item_id: str, content: str | None = None) -> ContextItem:
    value = content or item_id
    return ContextItem(
        id=item_id,
        content=value,
        type=ContextType.MEMORY,
        created_at=_NOW,
        updated_at=_NOW,
        importance=0.5,
        token_count=len(value.split()),
    )


def _edge(source: str, target: str, relation: DependencyRelation) -> ContextEdge:
    return ContextEdge(source_id=source, target_id=target, relation=relation, weight=1.0)


def test_constraint_trace_index_records_directional_reasoning() -> None:
    items = [
        _item(value) for value in ("operation", "middle", "source", "new", "old", "left", "right")
    ]
    edges = [
        _edge("operation", "middle", DependencyRelation.REQUIRES),
        _edge("middle", "source", DependencyRelation.REQUIRES),
        _edge("new", "old", DependencyRelation.SUPERSEDES),
        _edge("left", "right", DependencyRelation.CONTRADICTS),
    ]
    index = ConstraintTraceIndex(
        items,
        edges,
        selected_item_ids=("operation", "middle", "source", "new", "left", "right"),
    )

    operation = index.for_item("operation")
    source = index.for_item("source")
    new = index.for_item("new")
    left = index.for_item("left")

    assert operation.dependency_closure == ("middle", "source")
    assert [edge.relation for edge in operation.hard_constraints_triggered] == [
        DependencyRelation.REQUIRES
    ]
    assert source.required_by == ("middle",)
    assert new.superseded_items == ("old",)
    assert left.conflict_status is ConflictTraceStatus.CO_RETAINED
    assert operation.constraint_resolution_applied is False
    assert operation.would_have_been_removed_without_constraints is None


def test_constraint_trace_distinguishes_resolved_outcomes_and_counterfactuals() -> None:
    items = [_item(value) for value in ("operation", "dependency", "left", "right")]
    edges = [
        _edge("operation", "dependency", DependencyRelation.REQUIRES),
        _edge("left", "right", DependencyRelation.CONTRADICTS),
    ]
    resolution = ConstraintResolution(
        selected_item_ids=("operation", "dependency", "left"),
        represented_item_ids=("operation", "dependency", "left"),
        added_required_item_ids=("dependency",),
        removed_superseded_item_ids=(),
        removed_conflicting_item_ids=("right",),
        requirement_groups=(),
        unresolved_conflicts=(),
        derivation_relations=(),
        total_tokens=3,
    )
    index = ConstraintTraceIndex(
        items,
        edges,
        selected_item_ids=resolution.selected_item_ids,
        resolution=resolution,
    )

    dependency = index.for_item("dependency")
    right = index.for_item("right")
    assert dependency.constraint_resolution_applied is True
    assert dependency.would_have_been_removed_without_constraints is True
    assert dependency.required_by == ("operation",)
    assert right.conflict_status is ConflictTraceStatus.REMOVED_COUNTERPART_RETAINED
    assert right.would_have_been_removed_without_constraints is None


def test_constraint_trace_rejects_unknown_selection_and_lookup() -> None:
    item = _item("known")
    with pytest.raises(UnknownDependencyReference, match="trace selection"):
        ConstraintTraceIndex([item], [], selected_item_ids=("unknown",))

    index = ConstraintTraceIndex([item], [], selected_item_ids=("known",))
    with pytest.raises(UnknownDependencyReference, match="unknown trace item"):
        index.for_item("unknown")


def test_constraint_trace_rejects_mismatched_resolution_attestation() -> None:
    item = _item("known")
    resolution = ConstraintResolution(
        selected_item_ids=("known",),
        represented_item_ids=("known",),
        added_required_item_ids=(),
        removed_superseded_item_ids=(),
        removed_conflicting_item_ids=(),
        requirement_groups=(),
        unresolved_conflicts=(),
        derivation_relations=(),
        total_tokens=1,
    )

    with pytest.raises(ValueError, match="must match"):
        ConstraintTraceIndex(
            [item],
            [],
            selected_item_ids=(),
            resolution=resolution,
        )


def test_transformation_summary_preserves_each_validator_attempt() -> None:
    failed = ValidatorOutcome(
        validator="IdentifierPreservationValidator",
        passed=False,
        violations=("missing_identifier:usr_72B91",),
    )
    passed = ValidatorOutcome(
        validator="IdentifierPreservationValidator",
        passed=True,
    )
    attempts = [
        TransformationAttemptRecord(
            strategy="summary",
            representation_type="summary",
            succeeded=False,
            validator_outcomes=(failed,),
            violations=failed.violations,
            failure_reason="contract_validation_failed",
        ),
        TransformationAttemptRecord(
            strategy="extractive",
            representation_type="extractive",
            succeeded=True,
            validator_outcomes=(passed,),
        ),
    ]

    summary = summarize_transformation_trace(
        PreservationContract(preserve_identifiers=True),
        attempts,
        ("summary", "extractive"),
    )

    assert summary.transformation_attempted is True
    assert summary.validators_executed == ("IdentifierPreservationValidator",)
    assert summary.validator_results == (failed, passed)
    assert summary.fallback_used is True
    assert summary.would_have_been_compressed_without_contract is True


def test_optimizer_trace_is_complete_versioned_and_serializable() -> None:
    contract = PreservationContract(preserve_identifiers=True)
    source = _item("source", "Keep usr_72B91. filler filler filler filler.")
    source.contract = contract
    result = ContextOptimizer(tokenizer=WordTokenizer()).optimize(
        "Keep the user identifier",
        [source],
        OptimizationPolicy(
            max_input_tokens=3,
            compression_target_ratio=0.5,
            minimum_compressed_tokens=1,
            risk_aware_allocation=True,
        ),
    )

    trace = result.trace.items[0]
    assert result.trace.schema_version == "phase5h-v2"
    assert trace.preservation_contract == contract
    assert trace.omission_risk is not None
    assert trace.transformation_risk is not None
    assert trace.selection_value is not None
    assert trace.transformation_attempted is True
    assert trace.validators_executed == ["IdentifierPreservationValidator"]
    assert trace.validator_results[0].passed is True
    assert trace.fallback_used is False
    assert trace.final_representation_type == "extractive"
    assert trace.final_position == 0
    assert trace.would_have_been_compressed_without_contract is False
    assert trace.constraint_resolution_applied is False

    restored = OptimizationTrace.model_validate_json(result.trace.model_dump_json())
    assert restored == result.trace

    legacy_payload = result.trace.model_dump()
    legacy_payload["schema_version"] = "phase5h-v1"
    legacy_payload.pop("optimization_passes")
    legacy = OptimizationTrace.model_validate(legacy_payload)
    assert legacy.schema_version == "phase5h-v1"
    assert legacy.optimization_passes == 1


def test_trace_and_result_models_reject_inconsistent_accounting() -> None:
    source = _item("source", "one two three")
    result = ContextOptimizer(tokenizer=WordTokenizer()).optimize(
        "one",
        [source],
        OptimizationPolicy(max_input_tokens=3),
    )

    invalid_trace = result.trace.model_dump()
    invalid_trace["original_tokens"] = 4
    with pytest.raises(ValidationError, match="item tokens must equal original tokens"):
        OptimizationTrace.model_validate(invalid_trace)

    invalid_timing = result.trace.model_dump()
    invalid_timing["stage_timings_ms"]["trace"] = float("nan")
    with pytest.raises(ValidationError, match="finite and non-negative"):
        OptimizationTrace.model_validate(invalid_timing)

    invalid_result = result.model_dump()
    invalid_result["final_token_count"] = 2
    with pytest.raises(ValidationError, match="result and trace final token counts must match"):
        OptimizedContext.model_validate(invalid_result)
