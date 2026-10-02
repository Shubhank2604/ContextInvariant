"""Deterministic omission and transformation risk assessment."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from context_invariant.contracts import RetentionPolicy
from context_invariant.dependency import DependencyGraph
from context_invariant.models import (
    ContextEdge,
    ContextItem,
    ContextType,
    DependencyRelation,
    validate_unique_item_ids,
)

_EXACT_VALUE = re.compile(
    r"(?:https?://\S+|\b10\.\d{4,9}/\S+|\b[A-Za-z_]+\d+[A-Za-z0-9_-]*\b|"
    r"\b[A-Z]{2,}[A-Z0-9_-]*\b|(?<![\w.])[$€£]?[+-]?\d+(?:[,.]\d+)*%?)"
)
_NEGATION = re.compile(
    r"\b(?:not|no|never|none|without|cannot|can't|won't|isn't|aren't|"
    r"disabled|false|except|unless)\b",
    re.IGNORECASE,
)
_CURRENT_MARKERS = ("active", "canonical", "current", "is_current")

_CRITICAL_STATE_TYPES = {
    ContextType.SYSTEM_INSTRUCTION,
    ContextType.TASK_STATE,
    ContextType.ERROR,
    ContextType.DECISION,
}
_OPERATIONAL_TYPES = {
    ContextType.TOOL_OUTPUT,
    ContextType.CODE,
    ContextType.TOOL_DEFINITION,
}
_EVIDENCE_TYPES = {
    ContextType.USER_MESSAGE,
    ContextType.PLAN,
    ContextType.RETRIEVED_DOCUMENT,
}


class RiskAssessment(BaseModel):
    """Normalized deterministic signals for one context item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    omission_risk: float = Field(ge=0.0, le=1.0)
    transformation_risk: float = Field(ge=0.0, le=1.0)
    omission_signals: dict[str, float]
    transformation_signals: dict[str, float]


def _contract_signal(item: ContextItem) -> float:
    contract = item.contract
    if contract is None:
        return 0.0
    preservation_flags = (
        contract.preserve_numbers,
        contract.preserve_dates,
        contract.preserve_identifiers,
        contract.preserve_citations,
        contract.preserve_negation,
        contract.preserve_structure,
    )
    feature_risk = sum(preservation_flags) / len(preservation_flags)
    retention_risk = float(contract.retention is not RetentionPolicy.OPTIONAL)
    return max(feature_risk, retention_risk)


def _exact_value_density(item: ContextItem) -> float:
    word_count = max(len(item.content.split()), 1)
    matches = len(_EXACT_VALUE.findall(item.content))
    return min(matches / max(word_count * 0.25, 1.0), 1.0)


def _omission_type_risk(context_type: ContextType) -> float:
    if context_type in _CRITICAL_STATE_TYPES:
        return 1.0
    if context_type in _OPERATIONAL_TYPES:
        return 0.75
    if context_type in _EVIDENCE_TYPES:
        return 0.5
    return 0.25


def _transformation_type_risk(context_type: ContextType) -> float:
    if context_type in {ContextType.SYSTEM_INSTRUCTION, ContextType.TASK_STATE}:
        return 1.0
    if context_type in _OPERATIONAL_TYPES | {ContextType.ERROR, ContextType.DECISION}:
        return 0.75
    if context_type in {ContextType.PLAN, ContextType.RETRIEVED_DOCUMENT}:
        return 0.5
    return 0.25


def _mean(signals: dict[str, float]) -> float:
    return sum(signals.values()) / len(signals)


def assess_context_risk(
    items: Sequence[ContextItem],
    edges: Sequence[ContextEdge],
) -> dict[str, RiskAssessment]:
    """Assess soft omission/transformation risk without resolving hard constraints."""
    validate_unique_item_ids(items)
    graph = DependencyGraph([item.id for item in items], edges)
    requirement_exposure: Counter[str] = Counter()
    for edge in edges:
        if edge.relation is DependencyRelation.REQUIRES:
            requirement_exposure.update((edge.source_id, edge.target_id))
    results: dict[str, RiskAssessment] = {}
    for item in items:
        relations = graph.edges_for(item.id)
        relation_risk = float(
            any(
                edge.relation in {DependencyRelation.CONTRADICTS, DependencyRelation.SUPERSEDES}
                for edge in relations
            )
        )
        omission_signals = {
            "contract": _contract_signal(item),
            "dependency_exposure": min(requirement_exposure[item.id] / 3.0, 1.0),
            "context_type": _omission_type_risk(item.type),
            "current_state": float(any(bool(item.metadata.get(key)) for key in _CURRENT_MARKERS)),
            "relational_conflict": relation_risk,
        }
        transformation_signals = {
            "lossy_candidate": float(item.compressible),
            "exact_value_density": _exact_value_density(item),
            "negation": float(bool(_NEGATION.search(item.content))),
            "structured_contract": float(
                item.contract is not None and item.contract.preserve_structure
            ),
            "context_type": _transformation_type_risk(item.type),
        }
        results[item.id] = RiskAssessment(
            omission_risk=_mean(omission_signals),
            transformation_risk=_mean(transformation_signals),
            omission_signals=omission_signals,
            transformation_signals=transformation_signals,
        )
    return results
