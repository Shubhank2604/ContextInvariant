"""Result and policy models for directed context constraints."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from contextos.models import ContextEdge


class ConflictPolicy(StrEnum):
    """Explicit behavior when contradiction authority cannot be resolved."""

    ERROR = "error"
    RETAIN_BOTH = "retain_both"


class ConflictOverride(BaseModel):
    """Serializable caller decision for one otherwise ambiguous contradiction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    left_item_id: str
    right_item_id: str
    winner_item_id: str

    @field_validator("left_item_id", "right_item_id", "winner_item_id")
    @classmethod
    def reject_blank_ids(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("conflict override item IDs must not be blank")
        return value

    @model_validator(mode="after")
    def validate_winner(self) -> ConflictOverride:
        if self.left_item_id == self.right_item_id:
            raise ValueError("conflict override endpoints must be distinct")
        if self.winner_item_id not in {self.left_item_id, self.right_item_id}:
            raise ValueError("conflict override winner must be one of its endpoints")
        return self

    @property
    def pair(self) -> tuple[str, str]:
        """Return the canonical unordered conflict pair."""
        left, right = sorted((self.left_item_id, self.right_item_id))
        return left, right


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
        if self.source_item_id == self.representation_item_id:
            raise ValueError("representation item must differ from its source item")
        if any(not name.strip() for name in self.validator_names):
            raise ValueError("validator names must not be blank")
        if len(self.validator_names) != len(set(self.validator_names)):
            raise ValueError("validator names must be unique")
        return self


class DependencyReferenceRequirement(BaseModel):
    """Literal references that must survive transformation of one context item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    references: tuple[str, ...] = Field(min_length=1)

    @field_validator("item_id")
    @classmethod
    def reject_blank_item_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("dependency reference item ID must not be blank")
        return value

    @field_validator("references")
    @classmethod
    def validate_references(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("dependency references must not be blank")
        if len(values) != len(set(values)):
            raise ValueError("dependency references must be unique")
        return values


class ConstraintPolicy(BaseModel):
    """Serializable opt-in policy for directed hard-constraint enforcement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: StrictBool = False
    conflict_policy: ConflictPolicy = ConflictPolicy.ERROR
    retain_superseded: StrictBool = False
    validated_representations: tuple[ValidatedRepresentation, ...] = ()
    conflict_overrides: tuple[ConflictOverride, ...] = ()
    dependency_references: tuple[DependencyReferenceRequirement, ...] = ()

    @model_validator(mode="after")
    def validate_unique_rules(self) -> ConstraintPolicy:
        representation_sources = [
            representation.source_item_id for representation in self.validated_representations
        ]
        if len(representation_sources) != len(set(representation_sources)):
            raise ValueError("validated representations must have unique source item IDs")
        representation_targets = {
            representation.representation_item_id
            for representation in self.validated_representations
        }
        if set(representation_sources) & representation_targets:
            raise ValueError("validated representation chains are not supported")
        conflict_pairs = [override.pair for override in self.conflict_overrides]
        if len(conflict_pairs) != len(set(conflict_pairs)):
            raise ValueError("conflict overrides must have unique endpoint pairs")
        reference_item_ids = [requirement.item_id for requirement in self.dependency_references]
        if len(reference_item_ids) != len(set(reference_item_ids)):
            raise ValueError("dependency reference requirements must have unique item IDs")
        return self

    @classmethod
    def enforced(
        cls,
        *,
        conflict_policy: ConflictPolicy = ConflictPolicy.ERROR,
        retain_superseded: bool = False,
        validated_representations: tuple[ValidatedRepresentation, ...] = (),
        conflict_overrides: tuple[ConflictOverride, ...] = (),
        dependency_references: tuple[DependencyReferenceRequirement, ...] = (),
    ) -> ConstraintPolicy:
        """Return an enabled policy with explicit conflict semantics."""
        return cls(
            enabled=True,
            conflict_policy=conflict_policy,
            retain_superseded=retain_superseded,
            validated_representations=validated_representations,
            conflict_overrides=conflict_overrides,
            dependency_references=dependency_references,
        )

    @property
    def conflict_winners(self) -> dict[tuple[str, str], str]:
        """Return normalized winner choices for the constraint resolver."""
        return {override.pair: override.winner_item_id for override in self.conflict_overrides}

    @property
    def required_references(self) -> dict[str, tuple[str, ...]]:
        """Return per-item literal references for transformation validation."""
        return {
            requirement.item_id: requirement.references
            for requirement in self.dependency_references
        }


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
