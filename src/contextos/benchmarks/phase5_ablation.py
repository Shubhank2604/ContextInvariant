"""Controlled cumulative Phase 5 ablations across a fixed token-budget frontier."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from statistics import mean

from contextos.baselines import (
    FullContextBaseline,
    LastNTokensBaseline,
    NaiveExtractiveBaseline,
    RelevanceOnlyBaseline,
    SlidingWindowBaseline,
)
from contextos.benchmarks.bundles import capture_environment, write_benchmark_bundle
from contextos.benchmarks.constraint_benchmark import (
    aggregate_constraints,
    evaluate_constraints,
)
from contextos.benchmarks.constraint_dataset import PHASE5_BASELINE_SHA
from contextos.benchmarks.constraint_models import (
    ConstraintBenchmarkCase,
    ConstraintBenchmarkDataset,
    ConstraintMeasurement,
    Phase5AblationResult,
    Phase5BudgetResult,
    Phase5SweepMeasurement,
)
from contextos.benchmarks.metrics import (
    MIN_BOOTSTRAP_SAMPLE_SIZE,
    bootstrap_mean_ci,
    paired_metric_comparisons,
)
from contextos.benchmarks.models import (
    ContextOSBenchCase,
    ContextOSBenchDataset,
    PairedMetricComparison,
)
from contextos.benchmarks.runner import (
    BaselineBenchmarkStrategy,
    BenchmarkStrategy,
    run_contextos_bench,
)
from contextos.budget import AllocationPlan
from contextos.compression import (
    CompressionAttempt,
    CompressionExecution,
    CompressionResult,
    Compressor,
    ExtractiveCompressor,
    NoneCompressor,
    ToolOutputCompressor,
)
from contextos.config import OptimizationPolicy
from contextos.constraints import ConstraintPolicy
from contextos.contracts import PreservationContract, RetentionPolicy
from contextos.embeddings import DeterministicEmbeddingProvider
from contextos.models import ContextItem, ContextType, DependencyRelation
from contextos.optimizer import ContextOptimizer
from contextos.tokenization import Tokenizer
from contextos.trace import OptimizedContext

BUDGET_RATIOS: tuple[float, ...] = (0.25, 0.35, 0.50, 0.65, 0.80, 1.00)

_TOOL_TYPES = {ContextType.TOOL_OUTPUT, ContextType.ERROR}
_PROTECTED_TYPES = {
    ContextType.SYSTEM_INSTRUCTION,
    ContextType.TOOL_DEFINITION,
    ContextType.CODE,
}


class Phase5Variant(StrEnum):
    """Stable names for the required cumulative ablation sequence."""

    V040 = "phase5_v040"
    HARD_RELATIONS = "phase5_hard_relations"
    PRESERVATION_CONTRACTS = "phase5_preservation_contracts"
    VALIDATED_TRANSFORMATIONS = "phase5_validated_transformations"
    OMISSION_RISK = "phase5_omission_risk"
    FULL = "phase5_full"


class FrozenV040CompressionExecutor:
    """Benchmark-local reproduction of compression behavior at the frozen v0.4 SHA."""

    def __init__(self, tokenizer: Tokenizer) -> None:
        self._extractive = ExtractiveCompressor(tokenizer)
        self._tool_output = ToolOutputCompressor(tokenizer)
        self._none = NoneCompressor(tokenizer)

    def execute(
        self,
        plan: AllocationPlan,
        items: Sequence[ContextItem],
        *,
        task: str,
        policy: OptimizationPolicy,
        required_references: Mapping[str, Sequence[str]] | None = None,
    ) -> CompressionExecution:
        """Execute the allocation using the exact v0.4 type router and checks."""
        del required_references
        by_id = {item.id: item for item in items}
        direct_by_type: dict[ContextType, int] = defaultdict(int)
        for selection in plan.direct_selected:
            direct_by_type[by_id[selection.item_id].type] += selection.allocated_tokens

        used_by_type = dict(direct_by_type)
        used_tokens = 0
        attempts: list[CompressionAttempt] = []
        successes: dict[str, CompressionResult] = {}
        for item_id in plan.compression_candidate_order:
            item = by_id[item_id]
            target = plan.compression_candidate_targets[item_id]
            available = plan.compression_budget - used_tokens
            maximum = policy.class_maximum_tokens.get(item.type)
            if target > available:
                attempts.append(
                    CompressionAttempt(
                        item_id=item_id,
                        target_tokens=target,
                        attempted=False,
                        reason="insufficient_compression_budget",
                    )
                )
                continue
            if maximum is not None and used_by_type.get(item.type, 0) + target > maximum:
                attempts.append(
                    CompressionAttempt(
                        item_id=item_id,
                        target_tokens=target,
                        attempted=False,
                        reason="class_maximum_exceeded",
                    )
                )
                continue
            compressor = self._compressor_for(item)
            try:
                result = compressor.compress(item, target, task)
            except Exception as exc:  # frozen compressor boundary
                attempts.append(
                    CompressionAttempt(
                        item_id=item_id,
                        target_tokens=target,
                        attempted=True,
                        reason=f"compressor_error:{type(exc).__name__}",
                    )
                )
                continue
            invalid_reason = self._validate_result(item, target, result)
            if invalid_reason is not None:
                attempts.append(
                    CompressionAttempt(
                        item_id=item_id,
                        target_tokens=target,
                        attempted=True,
                        result=result,
                        reason=invalid_reason,
                    )
                )
                continue
            successes[item_id] = result
            used_tokens += result.compressed_tokens
            used_by_type[item.type] = used_by_type.get(item.type, 0) + result.compressed_tokens
            attempts.append(
                CompressionAttempt(
                    item_id=item_id,
                    target_tokens=target,
                    attempted=True,
                    result=result,
                )
            )
        return CompressionExecution(
            attempts=attempts,
            successful_results=successes,
            used_tokens=used_tokens,
            returned_tokens=plan.compression_budget - used_tokens,
        )

    def _compressor_for(self, item: ContextItem) -> Compressor:
        if item.mandatory or not item.compressible or item.type in _PROTECTED_TYPES:
            return self._none
        if item.type in _TOOL_TYPES:
            return self._tool_output
        return self._extractive

    @staticmethod
    def _validate_result(
        item: ContextItem,
        target_tokens: int,
        result: CompressionResult,
    ) -> str | None:
        if not result.succeeded:
            return result.failure_reason or "compression_failed"
        if result.source_item_id != item.id or item.id not in result.provenance:
            return "invalid_provenance"
        if result.content is None or not result.content.strip():
            return "empty_result"
        if result.compressed_tokens > target_tokens:
            return "target_overflow"
        if result.compressed_tokens >= result.original_tokens:
            return "compression_not_beneficial"
        return None


def _contract_for(case: ConstraintBenchmarkCase, item: ContextItem) -> PreservationContract | None:
    truth = case.constraints
    if item.id not in truth.critical_item_ids:
        return None
    required_targets = {
        edge.target_id for edge in truth.relations if edge.relation is DependencyRelation.REQUIRES
    }
    exact_values = [value for value in truth.required_exact_values if value in item.content]
    identifiers = [value for value in truth.required_identifiers if value in item.content]
    citations = [value for value in truth.required_citations if value in item.content]
    required_keys: tuple[str, ...] = ()
    if item.type is ContextType.TOOL_OUTPUT:
        try:
            payload = json.loads(item.content)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            required_keys = tuple(sorted(str(key) for key in payload))
    return PreservationContract(
        retention=(
            RetentionPolicy.REQUIRED_IF_REFERENCED
            if item.id in required_targets
            else RetentionPolicy.REQUIRED
        ),
        preserve_numbers=bool(exact_values),
        preserve_dates=any(
            len(value) == 10 and value[4:5] == "-" and value[7:8] == "-" for value in exact_values
        ),
        preserve_identifiers=bool(identifiers),
        preserve_citations=bool(citations),
        preserve_negation=any("NOT" in value.upper() for value in exact_values),
        preserve_structure=bool(required_keys),
        required_keys=required_keys,
    )


def _with_contracts(case: ConstraintBenchmarkCase) -> list[ContextItem]:
    items: list[ContextItem] = []
    for item in case.context_items:
        copied = item.model_copy(deep=True)
        contract = _contract_for(case, copied)
        if contract is not None:
            if contract.retention is RetentionPolicy.REQUIRED:
                copied.evictable = False
                copied.mandatory = True
            copied.contract = contract
        items.append(copied)
    return items


class Phase5BenchmarkStrategy:
    """Execute one cumulative Phase 5 research variant."""

    def __init__(self, variant: Phase5Variant) -> None:
        self._variant = variant

    @property
    def name(self) -> str:
        return self._variant.value

    def optimize(self, case: ContextOSBenchCase, tokenizer: Tokenizer) -> OptimizedContext:
        if not isinstance(case, ConstraintBenchmarkCase):
            raise TypeError("Phase 5 strategies require ConstraintBenchmarkCase inputs")
        uses_relations = self._variant is not Phase5Variant.V040
        uses_contracts = self._variant in {
            Phase5Variant.PRESERVATION_CONTRACTS,
            Phase5Variant.VALIDATED_TRANSFORMATIONS,
            Phase5Variant.OMISSION_RISK,
            Phase5Variant.FULL,
        }
        uses_validated_transformations = self._variant in {
            Phase5Variant.VALIDATED_TRANSFORMATIONS,
            Phase5Variant.OMISSION_RISK,
            Phase5Variant.FULL,
        }
        uses_risk = self._variant in {Phase5Variant.OMISSION_RISK, Phase5Variant.FULL}
        items = (
            _with_contracts(case)
            if uses_contracts
            else [item.model_copy(deep=True) for item in case.context_items]
        )
        policy = case.policy.model_copy(update={"risk_aware_allocation": uses_risk})
        legacy = (
            None if uses_validated_transformations else FrozenV040CompressionExecutor(tokenizer)
        )
        if not uses_relations:
            return ContextOptimizer(
                tokenizer=tokenizer,
                edges=case.edges,
                compression_executor=legacy,
            ).optimize(case.task, items, policy)
        return ContextOptimizer(
            tokenizer=tokenizer,
            edges=case.edges,
            compression_executor=legacy,
            constraint_policy=ConstraintPolicy.enforced(),
        ).optimize(case.task, items, policy)


def phase5_ablation_strategies() -> list[BenchmarkStrategy]:
    """Return required simple baselines followed by cumulative Phase 5 variants."""
    baselines: list[BenchmarkStrategy] = [
        BaselineBenchmarkStrategy(FullContextBaseline(), full_context_reference=True),
        BaselineBenchmarkStrategy(LastNTokensBaseline()),
        BaselineBenchmarkStrategy(SlidingWindowBaseline(window_seconds=7 * 86_400)),
        BaselineBenchmarkStrategy(RelevanceOnlyBaseline()),
        BaselineBenchmarkStrategy(NaiveExtractiveBaseline()),
    ]
    return baselines + [Phase5BenchmarkStrategy(variant) for variant in Phase5Variant]


def constraint_dataset_at_budget(
    dataset: ConstraintBenchmarkDataset,
    tokenizer: Tokenizer,
    ratio: float,
    *,
    case_limit: int | None,
) -> ConstraintBenchmarkDataset:
    """Copy constraint cases with an effective budget at the requested source ratio."""
    if not 0.0 < ratio <= 1.0:
        raise ValueError("budget ratio must be between zero and one")
    if case_limit is not None and case_limit <= 0:
        raise ValueError("case limit must be positive")
    cases = dataset.cases[:case_limit] if case_limit is not None else dataset.cases
    adjusted: list[ConstraintBenchmarkCase] = []
    for case in cases:
        original_tokens = sum(tokenizer.count_tokens(item.content) for item in case.context_items)
        effective_budget = max(1, math.ceil(original_tokens * ratio))
        adjusted.append(
            case.model_copy(
                update={
                    "policy": case.policy.model_copy(
                        update={
                            "max_input_tokens": effective_budget + case.policy.reserve_output_tokens
                        }
                    )
                }
            )
        )
    return dataset.model_copy(update={"cases": adjusted})


_CONSTRAINT_METRICS = (
    "constraint_violation_rate",
    "dependency_closure_rate",
    "state_consistency_rate",
    "contradiction_leakage_rate",
    "exact_value_preservation_rate",
    "identifier_preservation_rate",
    "citation_preservation_rate",
)


def constraint_paired_comparisons(
    measurements: Sequence[ConstraintMeasurement],
    *,
    reference_strategy: str,
    candidate_strategies: Sequence[str],
    bootstrap_seed: int,
) -> list[PairedMetricComparison]:
    """Reuse Phase 4 seeded bootstrap rules for paired constraint-metric deltas."""
    reference = {
        measurement.benchmark.case_id: measurement
        for measurement in measurements
        if measurement.benchmark.strategy == reference_strategy
    }
    comparisons: list[PairedMetricComparison] = []
    for candidate in candidate_strategies:
        candidate_by_case = {
            measurement.benchmark.case_id: measurement
            for measurement in measurements
            if measurement.benchmark.strategy == candidate
        }
        shared_ids = sorted(set(reference) & set(candidate_by_case))
        for metric_index, metric in enumerate(_CONSTRAINT_METRICS):
            pairs = [
                (getattr(reference[case_id], metric), getattr(candidate_by_case[case_id], metric))
                for case_id in shared_ids
            ]
            deltas = [
                float(right) - float(left)
                for left, right in pairs
                if left is not None and right is not None
            ]
            if not deltas:
                continue
            material = f"{reference_strategy}|{candidate}|{metric}".encode()
            seed = bootstrap_seed + int.from_bytes(hashlib.sha256(material).digest()[:4], "big")
            comparisons.append(
                PairedMetricComparison(
                    reference_strategy=reference_strategy,
                    candidate_strategy=candidate,
                    metric=metric,
                    case_count=len(deltas),
                    mean_delta=mean(deltas),
                    delta_ci95=(
                        bootstrap_mean_ci(deltas, seed=seed + metric_index)
                        if len(deltas) >= MIN_BOOTSTRAP_SAMPLE_SIZE
                        else None
                    ),
                )
            )
    return comparisons


def run_phase5_ablation(
    dataset: ConstraintBenchmarkDataset,
    *,
    tokenizer: Tokenizer,
    budget_ratios: Sequence[float] = BUDGET_RATIOS,
    case_limit: int | None = None,
) -> Phase5AblationResult:
    """Run every strategy on identical cases at every declared budget ratio."""
    ratios = tuple(float(value) for value in budget_ratios)
    if not ratios or any(not 0.0 < value <= 1.0 for value in ratios):
        raise ValueError("budget ratios must be non-empty and between zero and one")
    if len(ratios) != len(set(ratios)):
        raise ValueError("budget ratios must be unique")
    strategies = phase5_ablation_strategies()
    names = tuple(strategy.name for strategy in strategies)
    candidates = tuple(name for name in names if name != Phase5Variant.V040.value)
    results: list[Phase5BudgetResult] = []
    for ratio_index, ratio in enumerate(ratios):
        adjusted = constraint_dataset_at_budget(dataset, tokenizer, ratio, case_limit=case_limit)
        compatible = ContextOSBenchDataset(
            name=adjusted.name,
            generator_version=adjusted.generator_version,
            generation_seed=adjusted.generation_seed,
            cases=list(adjusted.cases),
        )
        run = run_contextos_bench(compatible, tokenizer=tokenizer, strategies=strategies)
        task_pairs = paired_metric_comparisons(
            run.measurements,
            reference_strategy=Phase5Variant.V040.value,
            candidate_strategies=candidates,
            bootstrap_seed=dataset.generation_seed + ratio_index,
        )
        run = run.model_copy(update={"paired_comparisons": task_pairs})
        constraint_measurements = evaluate_constraints(adjusted, run)
        constraint_aggregates = aggregate_constraints(constraint_measurements)
        results.append(
            Phase5BudgetResult(
                budget_ratio=ratio,
                run=run,
                constraint_measurements=constraint_measurements,
                constraint_aggregates=constraint_aggregates,
                constraint_paired_comparisons=constraint_paired_comparisons(
                    constraint_measurements,
                    reference_strategy=Phase5Variant.V040.value,
                    candidate_strategies=candidates,
                    bootstrap_seed=dataset.generation_seed + ratio_index,
                ),
            )
        )
    return Phase5AblationResult(
        baseline_v040_sha=PHASE5_BASELINE_SHA,
        budget_ratios=ratios,
        strategies=names,
        budget_results=results,
    )


def _optional(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _report(result: Phase5AblationResult, *, current_sha: str) -> str:
    lines = [
        "# Phase 5 Cumulative Ablation and Budget Sweep",
        "",
        f"- Frozen v0.4 baseline SHA: `{result.baseline_v040_sha}`",
        f"- Current research SHA: `{current_sha}`",
        "- Budget ratios: " + ", ".join(f"{value:.0%}" for value in result.budget_ratios),
        "",
        "| Budget | Strategy | Success | Task | CIR | Reduction | Violations | Closure | "
        "State | Leakage | Exact | IDs | Citations | p50 ms | p95 ms |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for budget in result.budget_results:
        benchmark = {value.strategy: value for value in budget.run.aggregates}
        for constraint in budget.constraint_aggregates:
            aggregate = benchmark[constraint.strategy]
            lines.append(
                f"| {budget.budget_ratio:.0%} | {constraint.strategy} | "
                f"{aggregate.successful_case_count}/{aggregate.case_count} | "
                f"{aggregate.mean_task_specific_score:.4f} | "
                f"{aggregate.mean_critical_information_recall:.4f} | "
                f"{aggregate.mean_context_reduction:.4f} | "
                f"{constraint.constraint_violation_rate:.4f} | "
                f"{_optional(constraint.dependency_closure_rate)} | "
                f"{_optional(constraint.state_consistency_rate)} | "
                f"{_optional(constraint.contradiction_leakage_rate)} | "
                f"{_optional(constraint.exact_value_preservation_rate)} | "
                f"{_optional(constraint.identifier_preservation_rate)} | "
                f"{_optional(constraint.citation_preservation_rate)} | "
                f"{aggregate.p50_optimizer_latency_ms:.3f} | "
                f"{aggregate.p95_optimizer_latency_ms:.3f} |"
            )
    lines.extend(
        [
            "",
            "All constrained strategies at a given row group receive the same effective token "
            "budget. Full Context is an explicitly unbounded quality-reference baseline.",
            "",
            "A zero-success frontier point denotes a legal budget infeasibility; it is retained "
            "rather than silently relaxing mandatory or hard relational requirements.",
            "",
            "`phase5_full` adds Phase 5H tracing to the omission-risk variant. Their selected "
            "contexts should therefore be behaviorally equivalent.",
        ]
    )
    return "\n".join(lines)


def write_phase5_ablation_artifact(
    output_directory: Path,
    *,
    dataset: ConstraintBenchmarkDataset,
    result: Phase5AblationResult,
    profile: str,
) -> Path:
    """Write an immutable seven-file Phase 5I evidence bundle."""
    if not result.budget_results:
        raise ValueError("Phase 5 ablation result contains no budget runs")
    recorded_at = result.budget_results[0].run.recorded_at_utc
    embedding = DeterministicEmbeddingProvider()
    environment = capture_environment(
        recorded_at_utc=recorded_at,
        embedding_provider="deterministic",
        embedding_model=embedding.model_name,
    )
    selected_ids = {
        measurement.benchmark.case_id
        for budget in result.budget_results
        for measurement in budget.constraint_measurements
    }
    cases = [case for case in dataset.cases if case.id in selected_ids]
    predictions = [
        Phase5SweepMeasurement(
            budget_ratio=budget.budget_ratio,
            measurement=measurement,
        )
        for budget in result.budget_results
        for measurement in budget.constraint_measurements
    ]
    metric_rows: list[dict[str, object]] = []
    for budget in result.budget_results:
        benchmark = {value.strategy: value for value in budget.run.aggregates}
        for constraint in budget.constraint_aggregates:
            metric_rows.append(
                {
                    "budget_ratio": budget.budget_ratio,
                    **benchmark[constraint.strategy].model_dump(mode="json"),
                    **constraint.model_dump(mode="json", exclude={"strategy", "case_count"}),
                }
            )
    config = {
        "schema_version": result.schema_version,
        "benchmark": "phase5-cumulative-ablation",
        "baseline_v040_sha": result.baseline_v040_sha,
        "current_research_sha": environment.git_sha,
        "generator_version": dataset.generator_version,
        "profile": profile,
        "budget_ratios": result.budget_ratios,
        "strategies": result.strategies,
        "case_count": len(cases),
        "fair_comparison": {
            "same_cases": True,
            "same_budget_within_ratio": True,
            "same_evaluator": True,
            "same_provider": "deterministic",
            "full_context_is_unbounded_reference": True,
        },
    }
    metrics = {
        "schema_version": result.schema_version,
        "baseline_v040_sha": result.baseline_v040_sha,
        "current_research_sha": environment.git_sha,
        "budget_results": [
            {
                "budget_ratio": budget.budget_ratio,
                "benchmark_aggregates": [
                    value.model_dump(mode="json") for value in budget.run.aggregates
                ],
                "constraint_aggregates": [
                    value.model_dump(mode="json") for value in budget.constraint_aggregates
                ],
                "paired_comparisons": [
                    value.model_dump(mode="json") for value in budget.run.paired_comparisons
                ],
                "constraint_paired_comparisons": [
                    value.model_dump(mode="json") for value in budget.constraint_paired_comparisons
                ],
            }
            for budget in result.budget_results
        ],
    }
    return write_benchmark_bundle(
        output_directory=output_directory,
        recorded_at_utc=recorded_at,
        strategy="phase5-ablation",
        profile=profile,
        config=config,
        environment=environment,
        cases=cases,
        predictions=predictions,
        metrics=metrics,
        metric_rows=metric_rows,
        report=_report(result, current_sha=environment.git_sha),
    )


__all__ = [
    "BUDGET_RATIOS",
    "FrozenV040CompressionExecutor",
    "Phase5BenchmarkStrategy",
    "Phase5Variant",
    "constraint_dataset_at_budget",
    "constraint_paired_comparisons",
    "phase5_ablation_strategies",
    "run_phase5_ablation",
    "write_phase5_ablation_artifact",
]
