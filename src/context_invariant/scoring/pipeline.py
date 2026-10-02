"""End-to-end deterministic scoring composition for Phase 3B."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from context_invariant.config import OptimizationPolicy
from context_invariant.dependency import DependencyGraph
from context_invariant.embeddings import CachedEmbeddingProvider
from context_invariant.embeddings.base import EmbeddingProvider
from context_invariant.models import ContextEdge, ContextItem, validate_unique_item_ids
from context_invariant.scoring.composite import ScoreBreakdown, composite_scores
from context_invariant.scoring.importance import importance_scores
from context_invariant.scoring.novelty import novelty_scores
from context_invariant.scoring.recency import recency_scores
from context_invariant.scoring.relevance import relevance_scores
from context_invariant.scoring.risk import assess_context_risk
from context_invariant.scoring.type_priority import type_priority_scores


def score_context_items(
    task: str,
    items: Sequence[ContextItem],
    *,
    edges: Sequence[ContextEdge],
    policy: OptimizationPolicy,
    provider: EmbeddingProvider,
    reference_time: datetime | None = None,
) -> dict[str, ScoreBreakdown]:
    """Calculate every Phase 3B component and deterministic composite score."""
    policy.validate_static()
    validate_unique_item_ids(items)
    cached_provider = (
        provider
        if isinstance(provider, CachedEmbeddingProvider)
        else CachedEmbeddingProvider(provider)
    )
    relevance = (
        relevance_scores(task, items, provider=cached_provider)
        if policy.semantic_relevance_enabled
        else {item.id: 0.0 for item in items}
    )
    importance = importance_scores(items)
    recency = recency_scores(
        items,
        half_life_seconds=policy.recency_half_life_seconds,
        reference_time=reference_time,
    )
    novelty = novelty_scores(items, provider=cached_provider)
    for item in items:
        if item.mandatory:
            novelty[item.id] = 1.0
    graph = DependencyGraph([item.id for item in items], edges)
    dependency = graph.propagate_scores(
        {item.id: max(relevance[item.id], importance[item.id]) for item in items},
        max_depth=policy.dependency_max_depth,
    )
    type_priority = type_priority_scores(items, priorities=policy.type_priorities)
    risk = assess_context_risk(items, edges) if policy.risk_aware_allocation else {}
    return composite_scores(
        items,
        policy=policy,
        relevance=relevance,
        importance=importance,
        recency=recency,
        novelty=novelty,
        dependency=dependency,
        type_priority=type_priority,
        omission_risk={item_id: value.omission_risk for item_id, value in risk.items()},
        transformation_risk={item_id: value.transformation_risk for item_id, value in risk.items()},
    )
