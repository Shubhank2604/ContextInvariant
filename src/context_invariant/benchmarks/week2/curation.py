"""Unsigned, explicitly developer-curated approval records; no independent-review claim."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from context_invariant.benchmarks.week2.models import SHA256, Family

AMENDMENT_PATH = "research/week2/amendments/developer-curated-v1.md"
REVIEW_ARRANGEMENT = "developer-curated, AI-assisted; no independent human review"
NonBlank = Annotated[str, Field(min_length=1, pattern=r"\S")]


class AccessEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    actor: NonBlank
    action: NonBlank
    at_utc: datetime

    @field_validator("at_utc")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("access timestamps must be timezone aware")
        return value


class CurationRecord(BaseModel):
    """Hash integrity and recorded approval, not cryptographic proof of human identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["week2-developer-curated-v1"]
    mode: Literal["developer_curated", "developer_curated_development"]
    review_arrangement: Literal["developer-curated, AI-assisted; no independent human review"]
    independent_human_review: Literal[False]
    independent_human_reviewers: tuple[str, ...] = Field(max_length=0)
    authors: tuple[NonBlank, ...] = Field(min_length=1)
    ai_assistance: NonBlank
    provenance_and_permissions: NonBlank
    cross_checks_and_inclusion_decisions: NonBlank
    access_history: tuple[AccessEvent, ...] = Field(min_length=1)
    approval_status: Literal["approved", "synthetic_test_only"]
    approved_by: NonBlank
    approved_at_utc: datetime
    approval_reference: NonBlank
    case_counts_by_family: dict[Family, int]
    realistic_trace_case_ids: tuple[str, ...]
    input_file_sha256: SHA256
    key_file_sha256: SHA256
    canonical_input_json_sha256: SHA256
    canonical_key_json_sha256: SHA256
    study_lock_sha256: SHA256
    execution_freeze_sha256: SHA256
    analysis_plan_sha256: SHA256
    configuration_sha256: SHA256
    amendment_sha256: SHA256
    method_freeze_timestamp_utc: datetime

    @field_validator("approved_at_utc", "method_freeze_timestamp_utc")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("curation timestamps must be timezone aware")
        return value
