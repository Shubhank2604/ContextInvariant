"""Explainable per-item and whole-run optimization traces."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from contextos.config import OptimizationPolicy
from contextos.constraints import ConstraintPolicy, ConstraintResolution
from contextos.contracts import PreservationContract
from contextos.errors import UnknownDependencyReference
from contextos.models import (
    ContextEdge,
    ContextItem,
    DependencyRelation,
    validate_unique_item_ids,
)
from contextos.validation import TransformationAttemptRecord, ValidatorOutcome


class OptimizationDecision(StrEnum):
    """Final disposition of a candidate context item."""

    RETAINED = "retained"
    REMOVED = "removed"
    COMPRESSED = "compressed"


class ConflictTraceStatus(StrEnum):
    """Observed final-selection state for an item involved in a contradiction."""

    NOT_INVOLVED = "not_involved"
    INACTIVE = "inactive"
    CO_RETAINED = "co_retained"
    RETAINED_COUNTERPART_REMOVED = "retained_counterpart_removed"
    REMOVED_COUNTERPART_RETAINED = "removed_counterpart_retained"
    UNRESOLVED = "unresolved"


class ConstraintTraceEvidence(BaseModel):
    """Constraint facts applicable to one item and one final selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hard_constraints_triggered: tuple[ContextEdge, ...] = ()
    required_by: tuple[str, ...] = ()
    dependency_closure: tuple[str, ...] = ()
    superseded_items: tuple[str, ...] = ()
    conflict_status: ConflictTraceStatus = ConflictTraceStatus.NOT_INVOLVED
    constraint_resolution_applied: bool = False
    would_have_been_removed_without_constraints: bool | None = None


class ConstraintTraceIndex:
    """Build deterministic per-item constraint evidence without changing selection."""

    def __init__(
        self,
        items: Sequence[ContextItem],
        edges: Sequence[ContextEdge],
        *,
        selected_item_ids: Sequence[str],
        resolution: ConstraintResolution | None = None,
    ) -> None:
        validate_unique_item_ids(items)
        item_ids = {item.id for item in items}
        selected = set(selected_item_ids)
        unknown_selected = sorted(selected - item_ids)
        if unknown_selected:
            raise UnknownDependencyReference(
                "trace selection references unknown item IDs: " + ", ".join(unknown_selected)
            )
        if resolution is not None and set(resolution.selected_item_ids) != selected:
            raise ValueError("trace selection must match the supplied constraint resolution")
        if resolution is not None and not set(resolution.added_required_item_ids) <= selected:
            raise ValueError("resolved required additions must be present in the trace selection")
        self._item_ids = item_ids
        self._edges = tuple(
            sorted(
                edges,
                key=lambda edge: (
                    edge.source_id,
                    edge.target_id,
                    edge.relation.value,
                    edge.weight,
                ),
            )
        )
        for edge in self._edges:
            unknown = sorted({edge.source_id, edge.target_id} - item_ids)
            if unknown:
                raise UnknownDependencyReference(
                    "trace constraint references unknown item IDs: " + ", ".join(unknown)
                )
        self._selected = selected
        self._resolution = resolution
        self._requires: dict[str, list[str]] = defaultdict(list)
        for edge in self._edges:
            if edge.relation is DependencyRelation.REQUIRES:
                self._requires[edge.source_id].append(edge.target_id)
        for targets in self._requires.values():
            targets.sort()

    def for_item(self, item_id: str) -> ConstraintTraceEvidence:
        """Return factual constraint evidence for one known item."""
        if item_id not in self._item_ids:
            raise UnknownDependencyReference(f"unknown trace item ID: {item_id}")
        involved = [
            edge
            for edge in self._edges
            if item_id in {edge.source_id, edge.target_id}
            and edge.relation is not DependencyRelation.RELATED_TO
        ]
        if not involved and item_id not in self._selected:
            return ConstraintTraceEvidence(
                constraint_resolution_applied=self._resolution is not None,
                would_have_been_removed_without_constraints=self._counterfactual(item_id),
            )
        triggered = tuple(edge for edge in involved if self._is_triggered(edge))
        required_by = tuple(
            sorted(
                edge.source_id
                for edge in self._edges
                if edge.relation is DependencyRelation.REQUIRES
                and edge.target_id == item_id
                and edge.source_id in self._selected
            )
        )
        superseded_items = tuple(
            sorted(
                edge.target_id
                for edge in self._edges
                if edge.relation is DependencyRelation.SUPERSEDES
                and edge.source_id == item_id
                and edge.source_id in self._selected
            )
        )
        return ConstraintTraceEvidence(
            hard_constraints_triggered=triggered,
            required_by=required_by,
            dependency_closure=self._dependency_closure(item_id),
            superseded_items=superseded_items,
            conflict_status=self._conflict_status(item_id),
            constraint_resolution_applied=self._resolution is not None,
            would_have_been_removed_without_constraints=self._counterfactual(item_id),
        )

    def _is_triggered(self, edge: ContextEdge) -> bool:
        if edge.relation in {
            DependencyRelation.REQUIRES,
            DependencyRelation.SUPERSEDES,
            DependencyRelation.DERIVED_FROM,
        }:
            return edge.source_id in self._selected
        if edge.relation is DependencyRelation.CONTRADICTS:
            return bool({edge.source_id, edge.target_id} & self._selected)
        return False

    def _dependency_closure(self, item_id: str) -> tuple[str, ...]:
        if item_id not in self._selected:
            return ()
        closure: set[str] = set()
        pending = list(reversed(self._requires.get(item_id, ())))
        while pending:
            target = pending.pop()
            if target == item_id or target in closure:
                continue
            closure.add(target)
            pending.extend(reversed(self._requires.get(target, ())))
        return tuple(sorted(closure))

    def _conflict_status(self, item_id: str) -> ConflictTraceStatus:
        pairs = [
            tuple(sorted((edge.source_id, edge.target_id)))
            for edge in self._edges
            if edge.relation is DependencyRelation.CONTRADICTS
            and item_id in {edge.source_id, edge.target_id}
        ]
        if not pairs:
            return ConflictTraceStatus.NOT_INVOLVED
        unresolved = set(self._resolution.unresolved_conflicts) if self._resolution else set()
        if any(pair in unresolved for pair in pairs):
            return ConflictTraceStatus.UNRESOLVED
        counterpart_ids = {pair[0] if pair[1] == item_id else pair[1] for pair in pairs}
        item_selected = item_id in self._selected
        selected_counterparts = counterpart_ids & self._selected
        if item_selected and selected_counterparts:
            return ConflictTraceStatus.CO_RETAINED
        if item_selected:
            return ConflictTraceStatus.RETAINED_COUNTERPART_REMOVED
        if selected_counterparts:
            return ConflictTraceStatus.REMOVED_COUNTERPART_RETAINED
        return ConflictTraceStatus.INACTIVE

    def _counterfactual(self, item_id: str) -> bool | None:
        if self._resolution is None:
            return None
        if item_id in self._resolution.added_required_item_ids:
            return True
        return None


class TransformationTraceEvidence(BaseModel):
    """Flattened validator and fallback evidence for one item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    transformation_attempted: bool
    validators_executed: tuple[str, ...] = ()
    validator_results: tuple[ValidatorOutcome, ...] = ()
    fallback_used: bool
    would_have_been_compressed_without_contract: bool | None = None


def summarize_transformation_trace(
    contract: PreservationContract | None,
    attempts: Sequence[TransformationAttemptRecord],
    fallback_path: Sequence[str],
) -> TransformationTraceEvidence:
    """Build a lossless trace summary without rerunning any transformation."""
    results = tuple(
        outcome for transformation in attempts for outcome in transformation.validator_outcomes
    )
    validators = tuple(dict.fromkeys(outcome.validator for outcome in results))
    contract_results = tuple(
        outcome for outcome in results if outcome.validator != "DependencyReferenceValidator"
    )
    without_contract: bool | None = None
    if contract is not None and contract_results:
        without_contract = any(not outcome.passed for outcome in contract_results)
    return TransformationTraceEvidence(
        transformation_attempted=bool(attempts),
        validators_executed=validators,
        validator_results=results,
        fallback_used=len(fallback_path) > 1,
        would_have_been_compressed_without_contract=without_contract,
    )


class ItemTrace(BaseModel):
    """All currently available evidence for one item decision."""

    model_config = ConfigDict(extra="forbid")

    item_id: str
    initial_token_count: int = Field(ge=0)

    exact_duplicate_of: str | None = None
    semantic_duplicate_of: str | None = None
    semantic_similarity: float | None = Field(default=None, ge=0.0, le=1.0)

    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0)
    importance_score: float | None = Field(default=None, ge=0.0, le=1.0)
    recency_score: float | None = Field(default=None, ge=0.0, le=1.0)
    novelty_score: float | None = Field(default=None, ge=0.0, le=1.0)
    dependency_score: float | None = Field(default=None, ge=0.0, le=1.0)
    type_priority: float | None = Field(default=None, ge=0.0, le=1.0)
    composite_utility: float | None = Field(default=None, ge=0.0, le=1.0)
    omission_risk: float | None = Field(default=None, ge=0.0, le=1.0)
    transformation_risk: float | None = Field(default=None, ge=0.0, le=1.0)
    selection_value: float | None = Field(default=None, ge=0.0, le=1.0)
    transformed_selection_value: float | None = Field(default=None, ge=0.0, le=1.0)
    value_density: float | None = Field(default=None, ge=0.0)

    preservation_contract: PreservationContract | None = None
    hard_constraints_triggered: list[ContextEdge] = Field(default_factory=list)
    required_by: list[str] = Field(default_factory=list)
    dependency_closure: list[str] = Field(default_factory=list)
    superseded_items: list[str] = Field(default_factory=list)
    conflict_status: ConflictTraceStatus = ConflictTraceStatus.NOT_INVOLVED
    constraint_resolution_applied: bool = False
    would_have_been_removed_without_constraints: bool | None = None

    decision: OptimizationDecision
    decision_reason: str

    final_token_count: int = Field(ge=0)
    final_position: int | None = Field(default=None, ge=0)
    compression_strategy: str | None = None
    provenance: list[str] = Field(default_factory=list)
    transformation_attempted: bool = False
    transformation_attempts: list[TransformationAttemptRecord] = Field(default_factory=list)
    validators_executed: list[str] = Field(default_factory=list)
    validator_results: list[ValidatorOutcome] = Field(default_factory=list)
    fallback_path: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    final_representation_type: str | None = None
    would_have_been_compressed_without_contract: bool | None = None


class OptimizationTrace(BaseModel):
    """Whole-run budget, timing, warning, and item-decision record."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "phase5h-v1"
    strategy: str
    policy: OptimizationPolicy
    constraint_policy: ConstraintPolicy | None = None
    effective_budget: int = Field(gt=0)
    mandatory_tokens: int = Field(ge=0)
    optional_budget: int = Field(ge=0)
    original_tokens: int = Field(ge=0)
    final_tokens: int = Field(ge=0)
    reduction_ratio: float = Field(ge=0.0, le=1.0)
    stage_timings_ms: dict[str, float]
    selected_count: int = Field(ge=0)
    removed_count: int = Field(ge=0)
    compressed_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    items: list[ItemTrace]


class BudgetAllocation(BaseModel):
    """Budget use for an optimized context result."""

    model_config = ConfigDict(extra="forbid")

    effective_budget: int = Field(gt=0)
    used_tokens: int = Field(ge=0)
    remaining_tokens: int = Field(ge=0)


class OptimizedContext(BaseModel):
    """Selected context plus removals, budget accounting, and trace."""

    model_config = ConfigDict(extra="forbid")

    selected_items: list[ContextItem]
    removed_items: list[ContextItem]
    original_token_count: int = Field(ge=0)
    final_token_count: int = Field(ge=0)
    budget_allocation: BudgetAllocation
    trace: OptimizationTrace
    constraint_resolution: ConstraintResolution | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
