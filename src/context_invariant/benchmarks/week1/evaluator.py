"""Symmetric outcome checks; no selection decisions and no repair of returned context."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from context_invariant import ContextItem, ContextType, OptimizationPolicy
from context_invariant.benchmarks.week1.models import Checklist, StudyInputs, required_ids
from context_invariant.constraints import ConflictPolicy
from context_invariant.errors import (
    ConstraintUnsatisfiable,
    MandatoryContextOverflow,
    RequiredContextOverflow,
    UnresolvedConflict,
)
from context_invariant.models import DependencyRelation
from context_invariant.tokenization import Tokenizer
from context_invariant.validation import ContractValidationEngine


def validate_labels(inputs: StudyInputs, checklist: Checklist) -> None:
    """Reject malformed labels before either method is invoked."""
    by_id = {item.id: item for item in inputs.items}
    if set(checklist.required_ids) != set(required_ids(inputs)):
        raise ValueError("required checklist IDs must match declared mandatory closure")
    if set(checklist.forbidden_ids) - by_id.keys():
        raise ValueError("forbidden checklist IDs must exist")
    if set(checklist.forbidden_ids) & set(checklist.required_ids):
        raise ValueError("a required record cannot also be forbidden")
    for span in (*checklist.required_spans, *checklist.conditional_spans, *checklist.useful_spans):
        if span.item_id not in by_id or span.text not in by_id[span.item_id].content:
            raise ValueError("checklist spans must occur in their annotated source record")
    if any(span.item_id not in checklist.required_ids for span in checklist.required_spans):
        raise ValueError("required spans must belong to required records")
    for span in checklist.conditional_spans:
        if span.text not in inputs.constraint_policy.required_references.get(span.item_id, ()):
            raise ValueError("conditional span must also be a declared literal requirement")


def _authority(item: ContextItem) -> tuple[float, ...]:
    """Independent implementation of the documented authority ordering for auditing."""
    values = [1.0 if item.metadata.get("canonical") is True else 0.0]
    for key in ("authority_rank", "version", "source_priority"):
        value = item.metadata.get(key)
        values.append(
            float(value)
            if isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            else -math.inf
        )
    return (*values, item.updated_at.timestamp())


def evaluate_output(
    inputs: StudyInputs,
    checklist: Checklist,
    selected: Sequence[ContextItem],
    policy: OptimizationPolicy,
    tokenizer: Tokenizer,
) -> dict[str, Any]:
    """Check actual returned text identically for both methods, without trusting traces."""
    source = {item.id: item for item in inputs.items}
    chosen = {item.id: item for item in selected}
    issues: list[str] = []
    if len(chosen) != len(selected):
        issues.append("duplicate_selected_ids")
    used = sum(tokenizer.count_tokens(item.content) for item in selected)
    if used > policy.effective_budget:
        issues.append("budget_exceeded")
    for item_id in checklist.required_ids:
        if item_id not in chosen:
            issues.append(f"missing_required:{item_id}")
    for item_id in checklist.forbidden_ids:
        if item_id in chosen:
            issues.append(f"forbidden_record:{item_id}")
    for edge in inputs.edges:
        if edge.relation is DependencyRelation.REQUIRES:
            if edge.source_id in chosen and edge.target_id not in chosen:
                issues.append(f"missing_support:{edge.source_id}->{edge.target_id}")
        elif edge.relation is DependencyRelation.SUPERSEDES:
            if edge.target_id in chosen and not inputs.constraint_policy.retain_superseded:
                issues.append(f"stale_record:{edge.target_id}")
        elif edge.relation is DependencyRelation.CONTRADICTS:
            left, right = sorted((edge.source_id, edge.target_id))
            if not {left, right} & chosen.keys():
                continue
            winner = inputs.constraint_policy.conflict_winners.get((left, right))
            if winner is None:
                a, b = _authority(source[left]), _authority(source[right])
                winner = left if a > b else right if b > a else None
            if winner is None:
                if (
                    inputs.constraint_policy.conflict_policy is not ConflictPolicy.RETAIN_BOTH
                    or not {left, right} <= chosen.keys()
                ):
                    issues.append(f"unresolved_conflict:{left}:{right}")
            else:
                loser = right if winner == left else left
                if winner not in chosen or loser in chosen:
                    issues.append(f"incorrect_conflict_winner:{winner}")
    validator = ContractValidationEngine()
    for item in selected:
        original = source.get(item.id)
        if original is None:
            issues.append(f"unknown_record:{item.id}")
            continue
        if item.type is not original.type:
            issues.append(f"changed_type:{item.id}")
        if (
            original.mandatory
            or not original.compressible
            or original.type in {ContextType.SYSTEM_INSTRUCTION, ContextType.TOOL_DEFINITION}
        ) and item.content != original.content:
            issues.append(f"changed_lossless_record:{item.id}")
        validation = validator.validate(
            original,
            item.content,
            required_references=inputs.constraint_policy.required_references.get(item.id, ()),
        )
        issues.extend(f"{item.id}:{violation}" for violation in validation.violations)
    for span in checklist.required_spans:
        if span.item_id not in chosen or span.text not in chosen[span.item_id].content:
            issues.append(f"missing_required_span:{span.item_id}:{span.text}")
    for span in checklist.conditional_spans:
        if span.item_id in chosen and span.text not in chosen[span.item_id].content:
            issues.append(f"missing_qualifier:{span.item_id}:{span.text}")
    useful = [
        span.model_dump()
        for span in checklist.useful_spans
        if span.item_id in chosen and span.text in chosen[span.item_id].content
    ]
    return {
        "outcome": "invalid_context" if issues else "valid_context",
        "violations": sorted(set(issues)),
        "context_tokens": used,
        "useful_spans_retained": useful,
        "useful_spans_total": len(checklist.useful_spans),
        "useful_recall": len(useful) / len(checklist.useful_spans)
        if checklist.useful_spans
        else None,
    }


def required_certificate(
    inputs: StudyInputs, policy: OptimizationPolicy, tokenizer: Tokenizer
) -> dict[str, Any]:
    """A lower bound only when every mandatory supporting record is explicitly lossless."""
    required = set(required_ids(inputs))
    records = [item for item in inputs.items if item.id in required]
    lossless = all(not item.compressible for item in records)
    counts = {item.id: tokenizer.count_tokens(item.content) for item in records}
    lower_bound = sum(counts.values()) if lossless else None
    return {
        "required_ids": [item.id for item in records],
        "record_tokens": counts,
        "representation_rule": "unchanged mandatory roots and transitive supporting records",
        "all_explicitly_lossless": lossless,
        "lower_bound_tokens": lower_bound,
        "effective_budget": policy.effective_budget,
        "proves_budget_infeasible": lower_bound is not None
        and lower_bound > policy.effective_budget,
    }


def evaluate_failure(error: Exception, certificate: dict[str, Any]) -> dict[str, Any]:
    overflow = isinstance(error, (MandatoryContextOverflow, RequiredContextOverflow))
    if overflow:
        reason = (
            "budget_infeasible" if certificate["proves_budget_infeasible"] else "selection_failure"
        )
    elif isinstance(error, (ConstraintUnsatisfiable, UnresolvedConflict)):
        reason = "constraint_conflict"
    else:
        reason = "execution_error"
    return {
        "outcome": "no_context",
        "failure_reason": reason,
        "exception_type": type(error).__name__,
        "exception_message": str(error),
        "context_tokens": None,
        "useful_recall": None,
        "violations": [],
    }
