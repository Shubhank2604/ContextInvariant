"""Phase 5G omission- and transformation-risk tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from contextos import ContextOptimizer
from contextos.budget import TokenBudgetAllocator
from contextos.config import OptimizationPolicy
from contextos.contracts import PreservationContract, RetentionPolicy
from contextos.errors import InvalidScore
from contextos.models import ContextEdge, ContextItem, ContextType, DependencyRelation
from contextos.scoring import ScoreBreakdown, assess_context_risk, composite_scores

_NOW = datetime(2026, 9, 13, tzinfo=UTC)


class WordTokenizer:
    def count_tokens(self, text: str) -> int:
        return len(text.split())


def _item(
    item_id: str,
    content: str,
    *,
    context_type: ContextType = ContextType.MEMORY,
    tokens: int = 5,
    contract: PreservationContract | None = None,
    metadata: dict[str, object] | None = None,
) -> ContextItem:
    return ContextItem(
        id=item_id,
        content=content,
        type=context_type,
        created_at=_NOW,
        updated_at=_NOW,
        importance=0.5,
        token_count=tokens,
        contract=contract,
        metadata=metadata or {},
    )


def _edge(source: str, target: str, relation: DependencyRelation) -> ContextEdge:
    return ContextEdge(source_id=source, target_id=target, relation=relation, weight=1.0)


def _score(
    utility: float,
    *,
    selection_value: float,
    transformed_value: float,
) -> ScoreBreakdown:
    return ScoreBreakdown(
        relevance=utility,
        importance=utility,
        recency=utility,
        novelty=utility,
        dependency=utility,
        type_priority=utility,
        composite_utility=utility,
        selection_value=selection_value,
        transformed_selection_value=transformed_value,
    )


def test_risk_assessment_is_deterministic_bounded_and_signal_driven() -> None:
    protected = _item(
        "protected",
        "Do NOT change account ACCT_927 or amount $1,947.36.",
        context_type=ContextType.TASK_STATE,
        contract=PreservationContract(
            retention=RetentionPolicy.REQUIRED_IF_REFERENCED,
            preserve_numbers=True,
            preserve_identifiers=True,
            preserve_negation=True,
        ),
        metadata={"current": True},
    )
    plain = _item("plain", "General conversational background.")
    edges = [
        _edge("plain", "protected", DependencyRelation.REQUIRES),
        _edge("plain", "protected", DependencyRelation.CONTRADICTS),
    ]

    first = assess_context_risk([protected, plain], edges)
    second = assess_context_risk([protected, plain], edges)

    assert first == second
    assert first["protected"].omission_risk > first["plain"].omission_risk
    assert first["protected"].transformation_risk > first["plain"].transformation_risk
    assert first["protected"].omission_signals["contract"] == 1.0
    assert first["protected"].omission_signals["current_state"] == 1.0
    assert all(
        0.0 <= score <= 1.0
        for assessment in first.values()
        for score in (assessment.omission_risk, assessment.transformation_risk)
    )


def test_risk_adjustment_has_documented_signs_and_can_be_disabled() -> None:
    item = _item("safe", "content")
    components = {name: {"safe": 0.5} for name in _COMPONENT_NAMES}
    enabled = composite_scores(
        [item],
        policy=OptimizationPolicy(
            max_input_tokens=10,
            risk_aware_allocation=True,
            omission_risk_weight=0.2,
            transformation_risk_weight=0.15,
        ),
        omission_risk={"safe": 0.8},
        transformation_risk={"safe": 0.6},
        **components,
    )["safe"]
    disabled = composite_scores(
        [item],
        policy=OptimizationPolicy(max_input_tokens=10),
        omission_risk={"safe": 0.8},
        transformation_risk={"safe": 0.6},
        **components,
    )["safe"]

    assert enabled.composite_utility == pytest.approx(0.5)
    assert enabled.selection_value == pytest.approx(0.55)
    assert enabled.transformed_selection_value == pytest.approx(0.46)
    assert disabled.selection_value == pytest.approx(0.5)
    assert disabled.transformed_selection_value == pytest.approx(0.5)


def test_risk_enabled_composite_requires_complete_risk_inputs() -> None:
    item = _item("safe", "content")
    components = {name: {"safe": 0.5} for name in _COMPONENT_NAMES}

    with pytest.raises(InvalidScore, match="requires both risk score mappings"):
        composite_scores(
            [item],
            policy=OptimizationPolicy(max_input_tokens=10, risk_aware_allocation=True),
            **components,
        )


def test_allocator_uses_omission_risk_for_raw_selection() -> None:
    items = [
        _item("safe", "safe", tokens=5),
        _item("fragile", "fragile", tokens=5),
    ]
    plan = TokenBudgetAllocator().allocate(
        items,
        scores={
            "safe": _score(0.6, selection_value=0.5, transformed_value=0.5),
            "fragile": _score(0.5, selection_value=0.7, transformed_value=0.4),
        },
        policy=OptimizationPolicy(
            max_input_tokens=5,
            compression_enabled=False,
            risk_aware_allocation=True,
        ),
    )

    assert [selection.item_id for selection in plan.direct_selected] == ["fragile"]
    assert plan.direct_selected[0].selection_value == 0.7


def test_allocator_uses_transformation_risk_only_for_compression_priority() -> None:
    items = [
        _item("safe", "safe", tokens=10),
        _item("fragile", "fragile", tokens=10),
    ]
    plan = TokenBudgetAllocator().allocate(
        items,
        scores={
            "safe": _score(0.5, selection_value=0.6, transformed_value=0.55),
            "fragile": _score(0.5, selection_value=0.6, transformed_value=0.2),
        },
        policy=OptimizationPolicy(
            max_input_tokens=5,
            compression_target_ratio=0.5,
            minimum_compressed_tokens=1,
            risk_aware_allocation=True,
        ),
    )

    assert [request.item_id for request in plan.compression_requests] == ["safe"]
    assert plan.compression_requests[0].selection_value == 0.55
    assert plan.rejection_reasons == {"fragile": "insufficient_compression_budget"}


def test_required_context_remains_outside_optional_risk_competition() -> None:
    required = _item(
        "required",
        "required",
        tokens=5,
        contract=PreservationContract(retention=RetentionPolicy.REQUIRED),
    )
    optional = _item("optional", "optional", tokens=5)
    plan = TokenBudgetAllocator().allocate(
        [required, optional],
        scores={"optional": _score(1.0, selection_value=1.0, transformed_value=1.0)},
        policy=OptimizationPolicy(
            max_input_tokens=5,
            compression_enabled=False,
            risk_aware_allocation=True,
        ),
    )

    assert plan.optional_budget == 0
    assert plan.candidate_item_ids == ["optional"]
    assert plan.rejected_item_ids == ["optional"]


def test_integrated_optimizer_changes_only_when_risk_is_enabled() -> None:
    plain = _item("a-plain", "ordinary background note", tokens=3)
    critical = _item(
        "z-critical",
        "active task state",
        context_type=ContextType.TASK_STATE,
        tokens=3,
        contract=PreservationContract(retention=RetentionPolicy.REQUIRED_IF_REFERENCED),
        metadata={"current": True},
    )
    common: dict[str, object] = {
        "max_input_tokens": 3,
        "compression_enabled": False,
        "semantic_dedup_enabled": False,
        "semantic_relevance_enabled": False,
        "position_aware_layout": False,
        "weight_relevance": 0,
        "weight_importance": 1,
        "weight_recency": 0,
        "weight_novelty": 0,
        "weight_dependency": 0,
        "weight_type_priority": 0,
    }
    optimizer = ContextOptimizer(tokenizer=WordTokenizer())

    legacy = optimizer.optimize(
        "task",
        [plain, critical],
        OptimizationPolicy.model_validate(common),
    )
    risk_aware = optimizer.optimize(
        "task",
        [plain, critical],
        OptimizationPolicy.model_validate({**common, "risk_aware_allocation": True}),
    )

    assert [item.id for item in legacy.selected_items] == ["a-plain"]
    assert [item.id for item in risk_aware.selected_items] == ["z-critical"]


_COMPONENT_NAMES = (
    "relevance",
    "importance",
    "recency",
    "novelty",
    "dependency",
    "type_priority",
)
