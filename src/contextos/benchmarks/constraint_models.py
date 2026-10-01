"""Schemas for the Phase 5 constraint-sensitive benchmark track."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contextos.benchmarks.models import (
    BenchmarkMeasurement,
    BenchmarkRun,
    ContextOSBenchCase,
    PairedMetricComparison,
)
from contextos.models import ContextEdge


class ConstraintCategory(StrEnum):
    """Deterministically scored preservation failure families."""

    DEPENDENCY = "dependency"
    SUPERSESSION = "supersession"
    CONTRADICTION = "contradiction"
    EXACT_NUMERIC = "exact_numeric"
    IDENTIFIER = "identifier"
    NEGATION_POLICY = "negation_policy"
    TOOL_STATE = "tool_state"
    CITATION_EVIDENCE = "citation_evidence"
    MULTI_HOP = "multi_hop"


class ConstraintGroundTruth(BaseModel):
    """Machine-readable legal-state requirements for one case."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: ConstraintCategory
    critical_item_ids: list[str]
    relations: list[ContextEdge] = Field(default_factory=list)
    required_exact_values: list[str] = Field(default_factory=list)
    required_identifiers: list[str] = Field(default_factory=list)
    required_citations: list[str] = Field(default_factory=list)
    forbidden_output_values: list[str] = Field(default_factory=list)
    forbidden_item_combinations: list[tuple[str, ...]] = Field(default_factory=list)
    expected_current_state: dict[str, str] = Field(default_factory=dict)
    stale_item_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ground_truth(self) -> ConstraintGroundTruth:
        if not self.critical_item_ids:
            raise ValueError("constraint cases require critical item IDs")
        if any(len(group) < 2 for group in self.forbidden_item_combinations):
            raise ValueError("forbidden item combinations require at least two items")
        if any(not value.strip() for value in self.forbidden_output_values):
            raise ValueError("forbidden output values must not be blank")
        return self


class ConstraintBenchmarkCase(ContextOSBenchCase):
    """A ContextOS-Bench-compatible case with preservation ground truth."""

    schema_version: str = "2.0"
    constraints: ConstraintGroundTruth

    @model_validator(mode="after")
    def validate_constraints(self) -> ConstraintBenchmarkCase:
        item_ids = {item.id for item in self.context_items}
        referenced = set(self.constraints.critical_item_ids)
        referenced.update(self.constraints.stale_item_ids)
        referenced.update(
            item_id for group in self.constraints.forbidden_item_combinations for item_id in group
        )
        referenced.update(
            endpoint
            for edge in self.constraints.relations
            for endpoint in (edge.source_id, edge.target_id)
        )
        unknown = sorted(referenced - item_ids)
        if unknown:
            raise ValueError(f"constraint annotations reference unknown items: {unknown}")
        return self


class ConstraintBenchmarkDataset(BaseModel):
    """Separate Phase 5 benchmark track; does not replace ContextOS-Bench."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "2.0"
    name: str
    generator_version: str
    generation_seed: int = Field(ge=0)
    cases: list[ConstraintBenchmarkCase]

    @model_validator(mode="after")
    def validate_dataset(self) -> ConstraintBenchmarkDataset:
        case_ids = [case.id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("constraint benchmark case IDs must be unique")
        return self


class ConstraintMeasurement(BaseModel):
    """Per-case constraint metrics alongside the unchanged v0.4 measurement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    benchmark: BenchmarkMeasurement
    category: ConstraintCategory
    constraint_violation_rate: float = Field(ge=0.0, le=1.0)
    dependency_closure_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    state_consistency_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    contradiction_leakage_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    exact_value_preservation_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    identifier_preservation_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    citation_preservation_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class ConstraintAggregate(BaseModel):
    """Strategy-level means for the constraint-specific metrics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy: str
    case_count: int = Field(ge=0)
    constraint_violation_rate: float = Field(ge=0.0, le=1.0)
    dependency_closure_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    state_consistency_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    contradiction_leakage_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    exact_value_preservation_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    identifier_preservation_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    citation_preservation_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class Phase5SweepMeasurement(BaseModel):
    """One constraint measurement at one declared budget frontier point."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    budget_ratio: float = Field(gt=0.0, le=1.0)
    measurement: ConstraintMeasurement


class Phase5BudgetResult(BaseModel):
    """All raw and aggregate outputs for one budget ratio."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    budget_ratio: float = Field(gt=0.0, le=1.0)
    run: BenchmarkRun
    constraint_measurements: list[ConstraintMeasurement]
    constraint_aggregates: list[ConstraintAggregate]
    constraint_paired_comparisons: list[PairedMetricComparison]


class Phase5AblationResult(BaseModel):
    """Complete cumulative Phase 5 ablation and budget-sweep result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "phase5i-v1"
    baseline_v040_sha: str
    budget_ratios: tuple[float, ...]
    strategies: tuple[str, ...]
    budget_results: list[Phase5BudgetResult]


class ModelPricing(BaseModel):
    """Caller-supplied token prices used only when provider usage is available."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_usd_per_million: float = Field(ge=0.0)
    output_usd_per_million: float = Field(ge=0.0)
    cached_input_usd_per_million: float = Field(ge=0.0)


class ConstraintModelPrediction(BaseModel):
    """Raw model answer and deterministic output score for one strategy-case pair."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    category: ConstraintCategory
    strategy: str
    status: str
    raw_prediction: str
    task_score: float | None = Field(default=None, ge=0.0, le=1.0)
    exact_value_preservation_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    answer_constraint_violation: bool
    required_values: tuple[str, ...]
    forbidden_output_values: tuple[str, ...]
    missing_required_values: tuple[str, ...] = ()
    leaked_forbidden_values: tuple[str, ...] = ()
    original_context_tokens: int = Field(ge=0)
    input_context_tokens: int = Field(ge=0)
    prompt_input_tokens: int | None = Field(default=None, ge=0)
    provider_input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cached_tokens: int | None = Field(default=None, ge=0)
    context_reduction: float = Field(ge=0.0, le=1.0)
    optimizer_latency_ms: float = Field(ge=0.0)
    embedding_time_ms: float = Field(ge=0.0)
    compression_time_ms: float = Field(ge=0.0)
    provider_latency_ms: float | None = Field(default=None, ge=0.0)
    model_ttft_ms: float | None = Field(default=None, ge=0.0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    provider: str
    model: str
    prompt_sha256: str | None = None
    selected_context_sha256: str | None = None
    selected_item_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    selection: ConstraintMeasurement


class ConstraintModelAggregate(BaseModel):
    """Model-answer and systems metrics for one strategy and optional category."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy: str
    category: ConstraintCategory | None = None
    case_count: int = Field(gt=0)
    successful_case_count: int = Field(ge=0)
    mean_task_score: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_exact_value_preservation_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    answer_constraint_violation_rate: float = Field(ge=0.0, le=1.0)
    selection_constraint_violation_rate: float = Field(ge=0.0, le=1.0)
    mean_input_context_tokens: float | None = Field(default=None, ge=0.0)
    mean_context_reduction: float | None = Field(default=None, ge=0.0, le=1.0)
    p50_optimizer_latency_ms: float | None = Field(default=None, ge=0.0)
    p95_optimizer_latency_ms: float | None = Field(default=None, ge=0.0)
    mean_embedding_time_ms: float | None = Field(default=None, ge=0.0)
    mean_compression_time_ms: float | None = Field(default=None, ge=0.0)
    total_provider_latency_ms: float | None = Field(default=None, ge=0.0)
    p50_provider_latency_ms: float | None = Field(default=None, ge=0.0)
    p95_provider_latency_ms: float | None = Field(default=None, ge=0.0)
    mean_model_ttft_ms: float | None = Field(default=None, ge=0.0)
    total_output_tokens: int | None = Field(default=None, ge=0)
    total_cached_tokens: int | None = Field(default=None, ge=0)
    total_estimated_cost_usd: float | None = Field(default=None, ge=0.0)


class ConstraintModelRun(BaseModel):
    """Complete model-backed constraint validation result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "phase5j-v1"
    recorded_at_utc: datetime
    provider: str
    model: str
    tokenizer: str
    temperature: float | None = None
    max_output_tokens: int = Field(gt=0)
    budget_ratio: float = Field(gt=0.0, le=1.0)
    baseline_v040_sha: str
    predictions: list[ConstraintModelPrediction]
    aggregates: list[ConstraintModelAggregate]
    paired_comparisons: list[PairedMetricComparison]
    pricing: ModelPricing | None = None
