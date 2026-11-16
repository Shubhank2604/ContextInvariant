"""Week 2 data envelopes and signed steward evidence, separate from selector inputs."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from context_invariant.benchmarks.week1.models import StudyCase

Family = Literal["coding_agent", "operations", "evidence_backed_analysis"]
Mode = Literal["synthetic_development", "sealed_final"]
SHA256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
FAMILIES: tuple[Family, ...] = ("coding_agent", "operations", "evidence_backed_analysis")
START = "8253d0db550b071f05ce23d51f71a9fcb74a32dd"
LOCK_SHA = "e5d5cb5c0ad04374c1720ca000e146da27c7342b140d3e6fe4361b63473217ee"


class Week2Case(StudyCase):
    """Family and provenance never enter StudyInputs or the model-facing prompt."""

    family: Family
    data_kind: Mode
    origin: Literal["synthetic", "authored", "real_trace"]


class ExecutionFreeze(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["week2-execution-freeze-v1"] = "week2-execution-freeze-v1"
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    created_at_utc: datetime
    study_lock_sha256: SHA256
    analysis_plan_sha256: SHA256
    configuration_sha256: SHA256
    files: dict[str, SHA256]
    dependencies: dict[str, str]

    @field_validator("created_at_utc")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("freeze timestamps must be timezone aware")
        return value


class Seal(BaseModel):
    """Sign exact UTF-8 bytes of this manifest with a detached Ed25519 signature."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["week2-offline-seal-v1"]
    status: Literal["sealed_final"]
    author: str = Field(min_length=1)
    reviewers: tuple[str, ...] = Field(min_length=1)
    data_steward: str = Field(min_length=1)
    authorship_description: Literal["independently_authored", "independently_reviewed"]
    provenance_and_permissions_review: str = Field(min_length=1)
    review_disagreements_and_resolutions: str = Field(min_length=1)
    access_log_reference: str = Field(min_length=1)
    case_counts_by_family: dict[Family, int]
    realistic_trace_case_ids: tuple[str, ...] = Field(min_length=15)
    input_file_sha256: SHA256
    key_file_sha256: SHA256
    canonical_input_json_sha256: SHA256
    canonical_key_json_sha256: SHA256
    study_lock_sha256: SHA256
    execution_freeze_sha256: SHA256
    analysis_plan_sha256: SHA256
    configuration_sha256: SHA256
    method_freeze_timestamp_utc: datetime
    sealed_at_utc: datetime
    implementation_team_first_final_access_utc: None = None

    @field_validator("method_freeze_timestamp_utc", "sealed_at_utc")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("seal timestamps must be timezone aware")
        return value

    @field_validator(
        "author",
        "data_steward",
        "provenance_and_permissions_review",
        "review_disagreements_and_resolutions",
        "access_log_reference",
    )
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("attestation evidence must not be blank")
        return value

    @field_validator("reviewers")
    @classmethod
    def reviewers_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not person.strip() for person in value):
            raise ValueError("reviewer identities must not be blank")
        return value
