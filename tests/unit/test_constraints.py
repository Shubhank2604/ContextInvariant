"""Phase 5D directed hard-constraint tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from contextos import (
    ConflictPolicy,
    ContextConstraintGraph,
    ContextEdge,
    ContextItem,
    ContextType,
    DependencyRelation,
    PreservationContract,
    RetentionPolicy,
    ValidatedRepresentation,
)
from contextos.errors import (
    ConstraintUnsatisfiable,
    RequiredContextOverflow,
    UnknownDependencyReference,
    UnresolvedConflict,
)

_NOW = datetime(2026, 9, 12, tzinfo=UTC)


def _item(
    item_id: str,
    *,
    tokens: int = 1,
    offset: int = 0,
    metadata: dict[str, object] | None = None,
    contract: PreservationContract | None = None,
) -> ContextItem:
    timestamp = _NOW + timedelta(seconds=offset)
    return ContextItem(
        id=item_id,
        content=f"content for {item_id}",
        type=ContextType.TASK_STATE,
        created_at=timestamp,
        updated_at=timestamp,
        token_count=tokens,
        metadata=metadata or {},
        contract=contract,
    )


def _edge(source: str, target: str, relation: DependencyRelation) -> ContextEdge:
    return ContextEdge(source_id=source, target_id=target, relation=relation, weight=1.0)


def test_single_requires_is_directional() -> None:
    graph = ContextConstraintGraph(
        [_item("dependency"), _item("operation")],
        [_edge("operation", "dependency", DependencyRelation.REQUIRES)],
    )

    assert graph.resolve(["operation"]).selected_item_ids == ("dependency", "operation")
    assert graph.resolve(["dependency"]).selected_item_ids == ("dependency",)


def test_multi_hop_requires_builds_complete_closure() -> None:
    graph = ContextConstraintGraph(
        [_item("root"), _item("middle"), _item("leaf")],
        [
            _edge("leaf", "middle", DependencyRelation.REQUIRES),
            _edge("middle", "root", DependencyRelation.REQUIRES),
        ],
    )

    result = graph.resolve(["leaf"])

    assert result.selected_item_ids == ("root", "middle", "leaf")
    assert result.added_required_item_ids == ("root", "middle")


def test_requirement_cycle_is_an_atomic_group() -> None:
    graph = ContextConstraintGraph(
        [_item("a"), _item("b"), _item("other")],
        [
            _edge("a", "b", DependencyRelation.REQUIRES),
            _edge("b", "a", DependencyRelation.REQUIRES),
        ],
    )

    result = graph.resolve(["a"])

    assert result.selected_item_ids == ("a", "b")
    assert result.requirement_groups == (("a", "b"),)


def test_requirement_cycle_detection_handles_deep_graphs_without_recursion() -> None:
    item_count = 1_200
    items = [_item(f"item-{index:04d}") for index in range(item_count)]
    edges = [
        _edge(
            f"item-{index:04d}",
            f"item-{index - 1:04d}",
            DependencyRelation.REQUIRES,
        )
        for index in range(1, item_count)
    ]

    assert ContextConstraintGraph(items, edges).requirement_groups() == ()


def test_supersession_replaces_obsolete_selected_state() -> None:
    graph = ContextConstraintGraph(
        [_item("old"), _item("current")],
        [_edge("current", "old", DependencyRelation.SUPERSEDES)],
    )

    result = graph.resolve(["old"])

    assert result.selected_item_ids == ("current",)
    assert result.removed_superseded_item_ids == ("old",)


def test_supersession_cycle_is_explicitly_unsatisfiable() -> None:
    graph = ContextConstraintGraph(
        [_item("a"), _item("b")],
        [
            _edge("a", "b", DependencyRelation.SUPERSEDES),
            _edge("b", "a", DependencyRelation.SUPERSEDES),
        ],
    )

    with pytest.raises(ConstraintUnsatisfiable, match="supersession_cycle:a->b->a"):
        graph.resolve(["a", "b"])


def test_unresolved_contradiction_fails_explicitly() -> None:
    graph = ContextConstraintGraph(
        [_item("left"), _item("right")],
        [_edge("left", "right", DependencyRelation.CONTRADICTS)],
    )

    with pytest.raises(UnresolvedConflict) as error:
        graph.resolve(["left"])

    assert error.value.conflicts == (("left", "right"),)


def test_unresolved_contradiction_can_be_retained_only_by_explicit_policy() -> None:
    graph = ContextConstraintGraph(
        [_item("left"), _item("right")],
        [_edge("left", "right", DependencyRelation.CONTRADICTS)],
    )

    result = graph.resolve(["left"], conflict_policy=ConflictPolicy.RETAIN_BOTH)

    assert result.selected_item_ids == ("left", "right")
    assert result.unresolved_conflicts == (("left", "right"),)


def test_unknown_relation_reference_is_rejected() -> None:
    with pytest.raises(UnknownDependencyReference, match="missing"):
        ContextConstraintGraph(
            [_item("known")],
            [_edge("known", "missing", DependencyRelation.REQUIRES)],
        )


def test_dependency_closure_over_budget_has_typed_failure() -> None:
    graph = ContextConstraintGraph(
        [_item("dependency", tokens=3), _item("operation", tokens=2)],
        [_edge("operation", "dependency", DependencyRelation.REQUIRES)],
    )

    with pytest.raises(RequiredContextOverflow) as error:
        graph.resolve(["operation"], effective_budget=4)

    assert error.value.required_item_ids == ("dependency", "operation")
    assert error.value.required_tokens == 5
    assert error.value.effective_budget == 4


def test_validated_compressed_representation_satisfies_dependency() -> None:
    graph = ContextConstraintGraph(
        [_item("source", tokens=10), _item("compressed", tokens=2), _item("operation")],
        [_edge("operation", "source", DependencyRelation.REQUIRES)],
    )
    representation = ValidatedRepresentation(
        source_item_id="source",
        representation_item_id="compressed",
        validator_names=("NumericPreservationValidator",),
    )

    result = graph.resolve(
        ["compressed", "operation"],
        effective_budget=3,
        representations=[representation],
    )

    assert result.selected_item_ids == ("compressed", "operation")
    assert result.represented_item_ids == ("source", "compressed", "operation")
    assert result.added_required_item_ids == ()


def test_validated_representation_is_added_as_required_dependency() -> None:
    graph = ContextConstraintGraph(
        [_item("source", tokens=10), _item("compact", tokens=2), _item("operation")],
        [_edge("operation", "source", DependencyRelation.REQUIRES)],
    )
    representation = ValidatedRepresentation(
        source_item_id="source",
        representation_item_id="compact",
        validator_names=("NumericPreservationValidator",),
    )

    result = graph.resolve(
        ["operation"],
        effective_budget=3,
        representations=[representation],
    )

    assert result.selected_item_ids == ("compact", "operation")
    assert result.represented_item_ids == ("source", "compact", "operation")
    assert result.added_required_item_ids == ("compact",)


def test_validated_representation_satisfies_required_retention() -> None:
    required = PreservationContract(retention=RetentionPolicy.REQUIRED)
    graph = ContextConstraintGraph(
        [_item("source", tokens=10, contract=required), _item("compressed", tokens=2)],
        [],
    )
    representation = ValidatedRepresentation(
        source_item_id="source",
        representation_item_id="compressed",
        validator_names=("ContractValidator",),
    )

    result = graph.resolve(
        ["compressed"],
        effective_budget=2,
        representations=[representation],
    )

    assert result.selected_item_ids == ("compressed",)
    assert result.represented_item_ids == ("source", "compressed")


def test_deterministic_metadata_resolves_contradiction() -> None:
    graph = ContextConstraintGraph(
        [_item("draft"), _item("canonical", metadata={"canonical": True})],
        [_edge("draft", "canonical", DependencyRelation.CONTRADICTS)],
    )

    result = graph.resolve(["draft"])

    assert result.selected_item_ids == ("canonical",)
    assert result.removed_conflicting_item_ids == ("draft",)


def test_non_finite_authority_metadata_is_not_used_as_conflict_evidence() -> None:
    graph = ContextConstraintGraph(
        [
            _item("newer", offset=1, metadata={"authority_rank": float("nan")}),
            _item("older", offset=0),
        ],
        [_edge("newer", "older", DependencyRelation.CONTRADICTS)],
    )

    result = graph.resolve(["older"])

    assert result.selected_item_ids == ("newer",)


def test_caller_can_resolve_otherwise_ambiguous_conflict() -> None:
    graph = ContextConstraintGraph(
        [_item("left"), _item("right")],
        [_edge("left", "right", DependencyRelation.CONTRADICTS)],
    )

    result = graph.resolve(
        ["left"],
        conflict_winners={("left", "right"): "right"},
    )

    assert result.selected_item_ids == ("right",)


def test_conflict_override_must_match_a_known_contradiction() -> None:
    graph = ContextConstraintGraph([_item("left"), _item("right")], [])

    with pytest.raises(ConstraintUnsatisfiable, match="conflict_override_has_no_relation"):
        graph.resolve(
            ["left"],
            conflict_winners={("left", "right"): "right"},
        )


def test_constraint_inputs_reject_unknown_representation_ids() -> None:
    graph = ContextConstraintGraph([_item("source")], [])
    representation = ValidatedRepresentation(
        source_item_id="source",
        representation_item_id="missing",
        validator_names=("Validator",),
    )

    with pytest.raises(UnknownDependencyReference, match="missing"):
        graph.resolve([], representations=[representation])


def test_required_superseded_item_is_unsatisfiable() -> None:
    required = PreservationContract(retention=RetentionPolicy.REQUIRED)
    graph = ContextConstraintGraph(
        [_item("old", contract=required), _item("current")],
        [_edge("current", "old", DependencyRelation.SUPERSEDES)],
    )

    with pytest.raises(ConstraintUnsatisfiable, match="superseded_item_is_required"):
        graph.resolve(["old"])


def test_omitted_required_contract_root_is_added() -> None:
    required = PreservationContract(retention=RetentionPolicy.REQUIRED)
    graph = ContextConstraintGraph(
        [_item("required", contract=required), _item("optional")],
        [],
    )

    result = graph.resolve(["optional"])

    assert result.selected_item_ids == ("required", "optional")
    assert result.added_required_item_ids == ("required",)


def test_supersession_removes_obsolete_validated_representation() -> None:
    graph = ContextConstraintGraph(
        [_item("old"), _item("compressed-old"), _item("current")],
        [_edge("current", "old", DependencyRelation.SUPERSEDES)],
    )
    representation = ValidatedRepresentation(
        source_item_id="old",
        representation_item_id="compressed-old",
        validator_names=("StateValidator",),
    )

    result = graph.resolve(["compressed-old"], representations=[representation])

    assert result.selected_item_ids == ("current",)
    assert result.removed_superseded_item_ids == ("old",)


def test_derived_from_relation_is_preserved_as_provenance() -> None:
    edge = _edge("summary", "source", DependencyRelation.DERIVED_FROM)
    graph = ContextConstraintGraph([_item("source"), _item("summary")], [edge])

    result = graph.resolve(["summary"])

    assert result.derivation_relations == (edge,)
