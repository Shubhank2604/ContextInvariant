"""Property checks for the public constraint-aware optimizer boundary."""

from __future__ import annotations

from datetime import UTC, datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from contextos import (
    ConstraintPolicy,
    ContextEdge,
    ContextItem,
    ContextOptimizer,
    ContextType,
    DependencyRelation,
    OptimizationPolicy,
)
from contextos.errors import RequiredContextOverflow

_NOW = datetime(2026, 10, 1, tzinfo=UTC)


class WordTokenizer:
    def count_tokens(self, text: str) -> int:
        return len(text.split())


@settings(max_examples=40, deadline=None)
@given(
    token_counts=st.lists(st.integers(min_value=1, max_value=8), min_size=1, max_size=7),
    budget=st.integers(min_value=1, max_value=35),
)
def test_constraint_optimizer_preserves_every_selected_requirement_or_fails_explicitly(
    token_counts: list[int],
    budget: int,
) -> None:
    items = [
        ContextItem(
            id=f"item-{index}",
            content=" ".join([f"token-{index}"] * count),
            type=ContextType.TASK_STATE,
            created_at=_NOW,
            updated_at=_NOW,
            importance=(index + 1) / len(token_counts),
        )
        for index, count in enumerate(token_counts)
    ]
    edges = [
        ContextEdge(
            source_id=f"item-{index}",
            target_id=f"item-{index - 1}",
            relation=DependencyRelation.REQUIRES,
            weight=1.0,
        )
        for index in range(1, len(items))
    ]
    optimizer = ContextOptimizer(
        tokenizer=WordTokenizer(),
        edges=edges,
        constraint_policy=ConstraintPolicy.enforced(),
    )
    policy = OptimizationPolicy(
        max_input_tokens=budget,
        semantic_dedup_enabled=False,
        semantic_relevance_enabled=False,
        compression_enabled=False,
        position_aware_layout=False,
    )

    try:
        result = optimizer.optimize("retain dependencies", items, policy)
    except RequiredContextOverflow as error:
        assert error.required_tokens > error.effective_budget
        return

    selected = {item.id for item in result.selected_items}
    for edge in edges:
        if edge.source_id in selected:
            assert edge.target_id in selected
    assert result.final_token_count <= policy.effective_budget
    assert result.constraint_resolution is not None
    assert set(result.constraint_resolution.selected_item_ids) == selected
