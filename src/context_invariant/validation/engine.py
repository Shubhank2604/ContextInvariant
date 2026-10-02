"""Composition engine for deterministic preservation validators."""

from __future__ import annotations

from collections.abc import Sequence

from context_invariant.contracts import PreservationContract
from context_invariant.models import ContextItem
from context_invariant.validation.models import ValidationResult, ValidatorOutcome
from context_invariant.validation.validators import (
    CitationPreservationValidator,
    DatePreservationValidator,
    DependencyReferenceValidator,
    IdentifierPreservationValidator,
    NegationPreservationValidator,
    NumericPreservationValidator,
    StructuredFieldValidator,
)


class ContractValidationEngine:
    """Run every applicable validator and preserve all observed violations."""

    def __init__(self) -> None:
        self._contract_validators = (
            NumericPreservationValidator(),
            DatePreservationValidator(),
            IdentifierPreservationValidator(),
            CitationPreservationValidator(),
            NegationPreservationValidator(),
            StructuredFieldValidator(),
        )
        self._dependency_validator = DependencyReferenceValidator()

    def validate(
        self,
        source: ContextItem,
        transformed: str,
        *,
        required_references: Sequence[str] = (),
    ) -> ValidationResult:
        """Validate transformed text against its contract and required references."""
        contract = source.contract or PreservationContract()
        outcomes: list[ValidatorOutcome] = []
        for validator in self._contract_validators:
            outcome = validator.validate(source, transformed, contract)
            if outcome is not None:
                outcomes.append(outcome)
        dependency_outcome = self._dependency_validator.validate(
            transformed,
            required_references,
        )
        if dependency_outcome is not None:
            outcomes.append(dependency_outcome)
        violations = tuple(violation for outcome in outcomes for violation in outcome.violations)
        return ValidationResult(
            passed=not violations,
            violations=violations,
            outcomes=tuple(outcomes),
        )
