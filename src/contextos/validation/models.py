"""Auditable results from contract validation and transformation attempts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class ValidatorOutcome(BaseModel):
    """Outcome from one named deterministic validator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    validator: str
    passed: bool
    violations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_outcome(self) -> ValidatorOutcome:
        if self.passed == bool(self.violations):
            raise ValueError("validator pass state must agree with violations")
        return self


class ValidationResult(BaseModel):
    """Combined contract-validation result for one candidate representation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    passed: bool
    violations: tuple[str, ...] = ()
    outcomes: tuple[ValidatorOutcome, ...] = ()

    @model_validator(mode="after")
    def validate_result(self) -> ValidationResult:
        if self.passed == bool(self.violations):
            raise ValueError("validation pass state must agree with violations")
        return self


class TransformationAttemptRecord(BaseModel):
    """Trace record for one preferred or fallback representation attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy: str
    representation_type: str
    succeeded: bool
    validator_outcomes: tuple[ValidatorOutcome, ...] = ()
    violations: tuple[str, ...] = ()
    failure_reason: str | None = None

    @model_validator(mode="after")
    def validate_attempt(self) -> TransformationAttemptRecord:
        if self.succeeded and (self.failure_reason is not None or self.violations):
            raise ValueError("successful transformation cannot contain failures")
        if not self.succeeded and self.failure_reason is None:
            raise ValueError("failed transformation requires a failure reason")
        return self
