"""Normalized weighted composite-utility scoring."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from contextos.config import OptimizationPolicy
from contextos.errors import InvalidScore
from contextos.models import ContextItem


class ScoreBreakdown(BaseModel):
    """All normalized scoring evidence for one item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relevance: float = Field(ge=0.0, le=1.0)
    importance: float = Field(ge=0.0, le=1.0)
    recency: float = Field(ge=0.0, le=1.0)
    novelty: float = Field(ge=0.0, le=1.0)
    dependency: float = Field(ge=0.0, le=1.0)
    type_priority: float = Field(ge=0.0, le=1.0)
    composite_utility: float = Field(ge=0.0, le=1.0)
    omission_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    transformation_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    selection_value: float | None = Field(default=None, ge=0.0, le=1.0)
    transformed_selection_value: float | None = Field(default=None, ge=0.0, le=1.0)


def _score_for(component: str, item_id: str, scores: Mapping[str, float]) -> float:
    try:
        score = scores[item_id]
    except KeyError as exc:
        raise InvalidScore(f"{component} score missing for item {item_id}") from exc
    if not 0.0 <= score <= 1.0:
        raise InvalidScore(f"{component} score for {item_id} must be between 0 and 1")
    return score


def composite_scores(
    items: Sequence[ContextItem],
    *,
    policy: OptimizationPolicy,
    relevance: Mapping[str, float],
    importance: Mapping[str, float],
    recency: Mapping[str, float],
    novelty: Mapping[str, float],
    dependency: Mapping[str, float],
    type_priority: Mapping[str, float],
    omission_risk: Mapping[str, float] | None = None,
    transformation_risk: Mapping[str, float] | None = None,
) -> dict[str, ScoreBreakdown]:
    """Combine every component using statically validated normalized weights."""
    if policy.risk_aware_allocation and (omission_risk is None or transformation_risk is None):
        raise InvalidScore("risk-aware allocation requires both risk score mappings")
    weights = policy.normalized_weights
    results: dict[str, ScoreBreakdown] = {}
    for item in items:
        values = {
            "relevance": _score_for("relevance", item.id, relevance),
            "importance": _score_for("importance", item.id, importance),
            "recency": _score_for("recency", item.id, recency),
            "novelty": _score_for("novelty", item.id, novelty),
            "dependency": _score_for("dependency", item.id, dependency),
            "type_priority": _score_for("type_priority", item.id, type_priority),
        }
        utility = sum(weights[name] * score for name, score in values.items())
        utility = min(max(utility, 0.0), 1.0)
        omission = (
            _score_for("omission_risk", item.id, omission_risk or {}) if omission_risk else 0.0
        )
        transformation = (
            _score_for("transformation_risk", item.id, transformation_risk or {})
            if transformation_risk
            else 0.0
        )
        if policy.risk_aware_allocation:
            selection_value = (utility + policy.omission_risk_weight * omission) / (
                1.0 + policy.omission_risk_weight
            )
            transformed_value = max(
                0.0,
                selection_value - policy.transformation_risk_weight * transformation,
            )
        else:
            selection_value = utility
            transformed_value = utility
        results[item.id] = ScoreBreakdown(
            **values,
            composite_utility=utility,
            omission_risk=omission,
            transformation_risk=transformation,
            selection_value=selection_value,
            transformed_selection_value=transformed_value,
        )
    return results
