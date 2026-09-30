"""Result and policy models for directed context constraints."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contextos.models import ContextEdge


class ConflictPolicy(StrEnum):
    """Explicit behavior when contradiction authority cannot be resolved."""

    ERROR = "error"
    RETAIN_BOTH = "retain_both"


class ValidatedRepresentation(BaseModel):
    """Caller attestation that one selected item represents another item safely."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_item_id: str
    representation_item_id: str
    validator_names: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_ids(self) -> ValidatedRepresentation:
        if not self.source_item_id.strip() or not self.representation_item_id.strip():
            raise ValueError("representation item IDs must not be blank")
        if any(not name.strip() for name in self.validator_names):
            raise ValueError("validator names must not be blank")
        return self


class ConstraintResolution(BaseModel):
    """Deterministic legal selection and the decisions used to obtain it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    selected_item_ids: tuple[str, ...]
    represented_item_ids: tuple[str, ...]
    added_required_item_ids: tuple[str, ...]
    removed_superseded_item_ids: tuple[str, ...]
    removed_conflicting_item_ids: tuple[str, ...]
    requirement_groups: tuple[tuple[str, ...], ...]
    unresolved_conflicts: tuple[tuple[str, str], ...]
    derivation_relations: tuple[ContextEdge, ...]
    total_tokens: int = Field(ge=0)
