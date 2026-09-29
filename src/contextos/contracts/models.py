"""Validated preservation contracts for context items."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RetentionPolicy(StrEnum):
    """When an item must remain representable in final model context."""

    OPTIONAL = "optional"
    REQUIRED = "required"
    REQUIRED_IF_REFERENCED = "required_if_referenced"


class PreservationContract(BaseModel):
    """Deterministic features that a valid item representation must preserve."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    retention: RetentionPolicy = RetentionPolicy.OPTIONAL
    preserve_numbers: bool = False
    preserve_dates: bool = False
    preserve_identifiers: bool = False
    preserve_citations: bool = False
    preserve_negation: bool = False
    preserve_structure: bool = False
    required_keys: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("required_keys")
    @classmethod
    def validate_required_keys(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Require stable, nonblank, unique structured-field names."""
        if any(not key.strip() for key in value):
            raise ValueError("required structured keys must not be blank")
        if any(key != key.strip() for key in value):
            raise ValueError("required structured keys must not contain surrounding whitespace")
        if len(value) != len(set(value)):
            raise ValueError("required structured keys must be unique")
        return value

    @model_validator(mode="after")
    def validate_structure_configuration(self) -> PreservationContract:
        """Reject structure settings without a deterministic key contract."""
        if self.preserve_structure != bool(self.required_keys):
            raise ValueError("preserve_structure and required_keys must be configured together")
        return self
