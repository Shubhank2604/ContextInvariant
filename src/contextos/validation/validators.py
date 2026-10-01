"""Reusable deterministic preservation validators."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Sequence

from contextos.contracts import PreservationContract
from contextos.models import ContextItem
from contextos.validation.models import ValidatorOutcome

_NUMBER = re.compile(r"(?<![\w.])(?:[$€£])?[+-]?\d+(?:,\d{3})*(?:\.\d+)?%?")
_DATE = re.compile(
    r"\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{4})?)\b",
    re.IGNORECASE,
)
_IDENTIFIER = re.compile(
    r"(?:\b[A-Za-z_][A-Za-z0-9_]*\(\)|\b(?:[A-Z]{2,}[A-Z0-9_-]*|"
    r"[A-Za-z]+\d+[A-Za-z0-9_-]*|[A-Za-z]+_[A-Za-z0-9_]+|"
    r"[a-z]+(?:[A-Z][A-Za-z0-9]*)+)\b)"
)
_NEGATION = re.compile(
    r"\b(?:not|no|never|none|without|cannot|can't|won't|isn't|aren't|"
    r"disabled|false|except|unless)\b",
    re.IGNORECASE,
)
_CITATION = re.compile(
    r"(?:https?://[^\s<>'\"]+|\b10\.\d{4,9}/[-._;()/:A-Z0-9]+|"
    r"\b(?:SRC|REF|DOC)-[A-Za-z0-9_-]+|\[(?:\d+|[A-Za-z][A-Za-z0-9_-]*)\])",
    re.IGNORECASE,
)


def _missing_values(pattern: re.Pattern[str], source: str, transformed: str) -> tuple[str, ...]:
    expected = Counter(match.group(0) for match in pattern.finditer(source))
    actual = Counter(match.group(0) for match in pattern.finditer(transformed))
    return tuple(
        value for value in sorted(expected) for _ in range(max(expected[value] - actual[value], 0))
    )


class NumericPreservationValidator:
    name = "NumericPreservationValidator"

    def validate(
        self,
        source: ContextItem,
        transformed: str,
        contract: PreservationContract,
    ) -> ValidatorOutcome | None:
        if not contract.preserve_numbers:
            return None
        violations = tuple(
            f"missing_number:{value}"
            for value in _missing_values(_NUMBER, source.content, transformed)
        )
        return ValidatorOutcome(validator=self.name, passed=not violations, violations=violations)


class DatePreservationValidator:
    name = "DatePreservationValidator"

    def validate(
        self,
        source: ContextItem,
        transformed: str,
        contract: PreservationContract,
    ) -> ValidatorOutcome | None:
        if not contract.preserve_dates:
            return None
        violations = tuple(
            f"missing_date:{value}" for value in _missing_values(_DATE, source.content, transformed)
        )
        return ValidatorOutcome(validator=self.name, passed=not violations, violations=violations)


class IdentifierPreservationValidator:
    name = "IdentifierPreservationValidator"

    def validate(
        self,
        source: ContextItem,
        transformed: str,
        contract: PreservationContract,
    ) -> ValidatorOutcome | None:
        if not contract.preserve_identifiers:
            return None
        violations = tuple(
            f"missing_identifier:{value}"
            for value in _missing_values(_IDENTIFIER, source.content, transformed)
        )
        return ValidatorOutcome(validator=self.name, passed=not violations, violations=violations)


class NegationPreservationValidator:
    name = "NegationPreservationValidator"

    def validate(
        self,
        source: ContextItem,
        transformed: str,
        contract: PreservationContract,
    ) -> ValidatorOutcome | None:
        if not contract.preserve_negation:
            return None
        missing = _missing_values(_NEGATION, source.content.casefold(), transformed.casefold())
        violations = tuple(f"missing_negation:{value}" for value in missing)
        return ValidatorOutcome(validator=self.name, passed=not violations, violations=violations)


class CitationPreservationValidator:
    name = "CitationPreservationValidator"

    def validate(
        self,
        source: ContextItem,
        transformed: str,
        contract: PreservationContract,
    ) -> ValidatorOutcome | None:
        if not contract.preserve_citations:
            return None
        violations = tuple(
            f"missing_citation:{value}"
            for value in _missing_values(_CITATION, source.content, transformed)
        )
        return ValidatorOutcome(validator=self.name, passed=not violations, violations=violations)


class StructuredFieldValidator:
    name = "StructuredFieldValidator"

    def validate(
        self,
        source: ContextItem,
        transformed: str,
        contract: PreservationContract,
    ) -> ValidatorOutcome | None:
        if not contract.preserve_structure:
            return None
        violations: list[str] = []
        try:
            source_payload = json.loads(source.content)
        except (TypeError, json.JSONDecodeError):
            source_payload = None
        try:
            transformed_payload = json.loads(transformed)
        except (TypeError, json.JSONDecodeError):
            transformed_payload = None
        if not isinstance(source_payload, dict):
            violations.append("invalid_source_structure")
        if not isinstance(transformed_payload, dict):
            violations.append("invalid_transformed_structure")
        if isinstance(source_payload, dict) and isinstance(transformed_payload, dict):
            for key in contract.required_keys:
                if key not in source_payload:
                    violations.append(f"source_missing_required_key:{key}")
                elif key not in transformed_payload:
                    violations.append(f"missing_structured_key:{key}")
                elif transformed_payload[key] != source_payload[key]:
                    violations.append(f"changed_structured_value:{key}")
        return ValidatorOutcome(
            validator=self.name,
            passed=not violations,
            violations=tuple(violations),
        )


class DependencyReferenceValidator:
    name = "DependencyReferenceValidator"

    def validate(self, transformed: str, references: Sequence[str]) -> ValidatorOutcome | None:
        if not references:
            return None
        violations = tuple(
            f"missing_dependency_reference:{reference}"
            for reference in references
            if reference not in transformed
        )
        return ValidatorOutcome(validator=self.name, passed=not violations, violations=violations)
