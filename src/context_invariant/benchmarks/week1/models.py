"""Separate selector inputs and evaluator-only development labels."""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field, model_validator

from context_invariant import ConstraintPolicy, ContextEdge, ContextItem, OptimizationPolicy
from context_invariant.models import DependencyRelation, validate_unique_item_ids
from context_invariant.tokenization import Tokenizer

STARTING_COMMIT = "00a54b559f55a29bcdc61fc1663fa322d90fa466"
BUDGET_PERCENTAGES = (65, 80, 100)


class StudyInputs(BaseModel):
    """The complete information available to either method; contains no answer key."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    task: str
    items: tuple[ContextItem, ...]
    edges: tuple[ContextEdge, ...] = ()
    constraint_policy: ConstraintPolicy = Field(default_factory=ConstraintPolicy.enforced)

    @model_validator(mode="after")
    def validate_study_scope(self) -> StudyInputs:
        validate_unique_item_ids(self.items)
        known = {item.id for item in self.items}
        if any({edge.source_id, edge.target_id} - known for edge in self.edges):
            raise ValueError("study edges must reference supplied records")
        if not self.constraint_policy.enabled:
            raise ValueError("the metadata-matched study requires enforced constraints")
        if self.constraint_policy.validated_representations:
            raise ValueError("representation substitutions are excluded from Week 1")
        if set(self.constraint_policy.required_references) - known:
            raise ValueError("literal references must target supplied records")
        return self


class StudyCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    inputs: StudyInputs


class SpanCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    item_id: str
    text: str = Field(min_length=1)


class Checklist(BaseModel):
    """Authored before execution and never supplied to a selector."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    purpose: str
    required: str
    optional: str
    failure: str
    required_ids: tuple[str, ...] = ()
    forbidden_ids: tuple[str, ...] = ()
    required_spans: tuple[SpanCheck, ...] = ()
    conditional_spans: tuple[SpanCheck, ...] = ()
    useful_spans: tuple[SpanCheck, ...] = ()
    development_only: bool = True


def content_hash(value: BaseModel | dict[str, object]) -> str:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def required_ids(inputs: StudyInputs) -> tuple[str, ...]:
    """Compute mandatory directed closure without using evaluator labels."""
    selected = {item.id for item in inputs.items if item.mandatory}
    while True:
        additions = {
            edge.target_id
            for edge in inputs.edges
            if edge.relation is DependencyRelation.REQUIRES and edge.source_id in selected
        }
        if additions <= selected:
            return tuple(item.id for item in inputs.items if item.id in selected)
        selected.update(additions)


def prepare_inputs(inputs: StudyInputs, tokenizer: Tokenizer) -> StudyInputs:
    """Prepare shared isolated records once, making required closure explicitly lossless."""
    protected = set(required_ids(inputs))
    items: list[ContextItem] = []
    for original in inputs.items:
        item = original.model_copy(deep=True)
        item.token_count = tokenizer.count_tokens(item.content)
        if item.id in protected:
            item.compressible = False
        items.append(item)
    return inputs.model_copy(update={"items": tuple(items)})


def study_policy(original_tokens: int, percentage: int) -> OptimizationPolicy:
    if percentage not in BUDGET_PERCENTAGES:
        raise ValueError("Week 1 budgets are 65, 80, and 100 percent")
    return OptimizationPolicy.balanced(
        max_input_tokens=max(original_tokens * percentage // 100, 1),
        minimum_compressed_tokens=8,
        risk_aware_allocation=True,
    )
