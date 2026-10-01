"""Model-backed validation for constraint-sensitive ContextOS cases."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from time import perf_counter

from contextos.baselines import FullContextBaseline
from contextos.benchmarks.bundles import capture_environment, write_benchmark_bundle
from contextos.benchmarks.constraint_benchmark import evaluate_constraints
from contextos.benchmarks.constraint_dataset import PHASE5_BASELINE_SHA
from contextos.benchmarks.constraint_models import (
    ConstraintBenchmarkCase,
    ConstraintBenchmarkDataset,
    ConstraintCategory,
    ConstraintMeasurement,
    ConstraintModelAggregate,
    ConstraintModelPrediction,
    ConstraintModelRun,
    ModelPricing,
)
from contextos.benchmarks.metrics import (
    MIN_BOOTSTRAP_SAMPLE_SIZE,
    bootstrap_mean_ci,
    percentile,
)
from contextos.benchmarks.models import (
    ContextOSBenchDataset,
    PairedMetricComparison,
)
from contextos.benchmarks.phase5_ablation import (
    Phase5BenchmarkStrategy,
    Phase5Variant,
    constraint_dataset_at_budget,
)
from contextos.benchmarks.runner import (
    BaselineBenchmarkStrategy,
    BenchmarkStrategy,
    run_contextos_bench,
)
from contextos.embeddings import DeterministicEmbeddingProvider
from contextos.errors import ContextOSError
from contextos.providers import LLMProvider
from contextos.providers.base import ProviderResponse
from contextos.tokenization import Tokenizer

MODEL_CONSTRAINT_PROMPT_VERSION = "phase5j-constraint-prompt-v1"


def default_model_constraint_strategies() -> list[BenchmarkStrategy]:
    """Return the unbounded reference and two critical same-budget comparisons."""
    return [
        BaselineBenchmarkStrategy(FullContextBaseline(), full_context_reference=True),
        Phase5BenchmarkStrategy(Phase5Variant.V040),
        Phase5BenchmarkStrategy(Phase5Variant.FULL),
    ]


def render_constraint_model_prompt(
    case: ConstraintBenchmarkCase,
    measurement: ConstraintMeasurement,
) -> str:
    """Render one stable prompt without exposing benchmark answer annotations."""
    visible = "\n\n".join(
        f"[context item {index}; type={item.type.value}]\n{item.content}"
        for index, item in enumerate(measurement.benchmark.selected_items, start=1)
    )
    return (
        "Use only the supplied context to answer the task. Preserve the exact spelling of "
        "requested values, identifiers, dates, citations, and negation. When the context "
        "explicitly identifies current, canonical, or superseding state, do not report stale "
        "or conflicting state. Give a concise answer and no analysis.\n\n"
        f"CONTEXT\n{visible}\n\nTASK\n{case.task}\n\nANSWER"
    )


def _normalized(value: str) -> str:
    return " ".join(value.split()).casefold()


def _required_values(case: ConstraintBenchmarkCase) -> tuple[str, ...]:
    values = [fact.value for fact in case.answer_key.required_facts]
    values.extend(case.constraints.expected_current_state.values())
    return tuple(dict.fromkeys(values))


def _exact_values(case: ConstraintBenchmarkCase) -> tuple[str, ...]:
    truth = case.constraints
    return tuple(
        dict.fromkeys(
            [
                *truth.required_exact_values,
                *truth.required_identifiers,
                *truth.required_citations,
            ]
        )
    )


def _presence_rate(values: Sequence[str], output: str, *, exact: bool) -> float | None:
    if not values:
        return None
    if exact:
        return sum(value in output for value in values) / len(values)
    normalized_output = _normalized(output)
    return sum(_normalized(value) in normalized_output for value in values) / len(values)


def _estimated_cost(
    response: ProviderResponse,
    pricing: ModelPricing | None,
) -> float | None:
    if pricing is None or response.input_tokens is None or response.output_tokens is None:
        return None
    cached = min(response.cached_tokens or 0, response.input_tokens)
    uncached = response.input_tokens - cached
    return (
        uncached * pricing.input_usd_per_million
        + cached * pricing.cached_input_usd_per_million
        + response.output_tokens * pricing.output_usd_per_million
    ) / 1_000_000


def _prediction_from_failure(
    case: ConstraintBenchmarkCase,
    selection: ConstraintMeasurement,
    *,
    provider_name: str,
    provider_model: str,
) -> ConstraintModelPrediction:
    benchmark = selection.benchmark
    return ConstraintModelPrediction(
        case_id=case.id,
        category=case.constraints.category,
        strategy=benchmark.strategy,
        status=benchmark.status,
        raw_prediction="",
        answer_constraint_violation=True,
        required_values=_required_values(case),
        forbidden_output_values=tuple(case.constraints.forbidden_output_values),
        missing_required_values=_required_values(case),
        original_context_tokens=benchmark.original_tokens,
        input_context_tokens=benchmark.input_tokens,
        context_reduction=benchmark.context_reduction,
        optimizer_latency_ms=benchmark.optimizer_wall_time_ms,
        embedding_time_ms=benchmark.embedding_time_ms,
        compression_time_ms=benchmark.compression_time_ms,
        provider=provider_name,
        model=provider_model,
        selected_item_ids=tuple(benchmark.selected_item_ids),
        warnings=tuple(benchmark.warnings),
        selection=selection,
    )


def _prediction_from_response(
    case: ConstraintBenchmarkCase,
    selection: ConstraintMeasurement,
    response: ProviderResponse,
    *,
    provider_name: str,
    provider_model: str,
    prompt: str,
    tokenizer: Tokenizer,
    provider_latency_ms: float,
    pricing: ModelPricing | None,
) -> ConstraintModelPrediction:
    benchmark = selection.benchmark
    required = _required_values(case)
    normalized_output = _normalized(response.text)
    missing = tuple(value for value in required if _normalized(value) not in normalized_output)
    forbidden = tuple(case.constraints.forbidden_output_values)
    leaked = tuple(value for value in forbidden if _normalized(value) in normalized_output)
    selected_context = "\n".join(item.content for item in benchmark.selected_items)
    return ConstraintModelPrediction(
        case_id=case.id,
        category=case.constraints.category,
        strategy=benchmark.strategy,
        status="ok",
        raw_prediction=response.text,
        task_score=_presence_rate(required, response.text, exact=False),
        exact_value_preservation_rate=_presence_rate(
            _exact_values(case), response.text, exact=True
        ),
        answer_constraint_violation=bool(missing or leaked),
        required_values=required,
        forbidden_output_values=forbidden,
        missing_required_values=missing,
        leaked_forbidden_values=leaked,
        original_context_tokens=benchmark.original_tokens,
        input_context_tokens=benchmark.input_tokens,
        prompt_input_tokens=tokenizer.count_tokens(prompt),
        provider_input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cached_tokens=response.cached_tokens,
        context_reduction=benchmark.context_reduction,
        optimizer_latency_ms=benchmark.optimizer_wall_time_ms,
        embedding_time_ms=benchmark.embedding_time_ms,
        compression_time_ms=benchmark.compression_time_ms,
        provider_latency_ms=provider_latency_ms,
        model_ttft_ms=response.ttft_ms,
        estimated_cost_usd=_estimated_cost(response, pricing),
        provider=provider_name,
        model=provider_model,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        selected_context_sha256=hashlib.sha256(selected_context.encode("utf-8")).hexdigest(),
        selected_item_ids=tuple(benchmark.selected_item_ids),
        warnings=tuple(benchmark.warnings),
        selection=selection,
    )


def _aggregate_group(
    values: Sequence[ConstraintModelPrediction],
    *,
    category: ConstraintCategory | None,
) -> ConstraintModelAggregate:
    successful = [value for value in values if value.status == "ok"]
    task_scores = [value.task_score for value in successful if value.task_score is not None]
    exact_scores = [
        value.exact_value_preservation_rate
        for value in successful
        if value.exact_value_preservation_rate is not None
    ]
    optimizer_latencies = [value.optimizer_latency_ms for value in values]
    provider_latencies = [
        value.provider_latency_ms for value in values if value.provider_latency_ms is not None
    ]
    ttfts = [value.model_ttft_ms for value in successful if value.model_ttft_ms is not None]
    output_tokens = [value.output_tokens for value in successful if value.output_tokens is not None]
    cached_tokens = [value.cached_tokens for value in successful if value.cached_tokens is not None]
    costs = [
        value.estimated_cost_usd for value in successful if value.estimated_cost_usd is not None
    ]
    return ConstraintModelAggregate(
        strategy=values[0].strategy,
        category=category,
        case_count=len(values),
        successful_case_count=len(successful),
        mean_task_score=mean(task_scores) if task_scores else None,
        mean_exact_value_preservation_rate=mean(exact_scores) if exact_scores else None,
        answer_constraint_violation_rate=mean(
            float(value.answer_constraint_violation) for value in values
        ),
        selection_constraint_violation_rate=mean(
            value.selection.constraint_violation_rate for value in values
        ),
        mean_input_context_tokens=(
            mean(value.input_context_tokens for value in successful) if successful else None
        ),
        mean_context_reduction=(
            mean(value.context_reduction for value in successful) if successful else None
        ),
        p50_optimizer_latency_ms=percentile(optimizer_latencies, 0.5),
        p95_optimizer_latency_ms=percentile(optimizer_latencies, 0.95),
        mean_embedding_time_ms=mean(value.embedding_time_ms for value in values),
        mean_compression_time_ms=mean(value.compression_time_ms for value in values),
        total_provider_latency_ms=sum(provider_latencies) if provider_latencies else None,
        p50_provider_latency_ms=(
            percentile(provider_latencies, 0.5) if provider_latencies else None
        ),
        p95_provider_latency_ms=(
            percentile(provider_latencies, 0.95) if provider_latencies else None
        ),
        mean_model_ttft_ms=mean(ttfts) if ttfts else None,
        total_output_tokens=sum(output_tokens) if output_tokens else None,
        total_cached_tokens=sum(cached_tokens) if cached_tokens else None,
        total_estimated_cost_usd=(
            sum(costs) if successful and len(costs) == len(successful) else None
        ),
    )


def aggregate_model_constraint_predictions(
    predictions: Sequence[ConstraintModelPrediction],
) -> list[ConstraintModelAggregate]:
    """Aggregate overall and per-category cells without hiding failure families."""
    aggregates: list[ConstraintModelAggregate] = []
    for strategy in sorted({value.strategy for value in predictions}):
        strategy_values = [value for value in predictions if value.strategy == strategy]
        aggregates.append(_aggregate_group(strategy_values, category=None))
        for category in ConstraintCategory:
            category_values = [value for value in strategy_values if value.category is category]
            if category_values:
                aggregates.append(_aggregate_group(category_values, category=category))
    return aggregates


def _paired_comparisons(
    predictions: Sequence[ConstraintModelPrediction],
    *,
    bootstrap_seed: int,
) -> list[PairedMetricComparison]:
    pairs = (
        (Phase5Variant.V040.value, Phase5Variant.FULL.value),
        ("full_context", Phase5Variant.FULL.value),
    )
    metrics = (
        "task_score",
        "answer_constraint_violation",
        "input_context_tokens",
        "estimated_cost_usd",
    )
    comparisons: list[PairedMetricComparison] = []
    for reference_name, candidate_name in pairs:
        reference = {
            value.case_id: value for value in predictions if value.strategy == reference_name
        }
        candidate = {
            value.case_id: value for value in predictions if value.strategy == candidate_name
        }
        for metric_index, metric in enumerate(metrics):
            deltas: list[float] = []
            for case_id in sorted(set(reference) & set(candidate)):
                left = reference[case_id]
                right = candidate[case_id]
                if metric != "answer_constraint_violation" and (
                    left.status != "ok" or right.status != "ok"
                ):
                    continue
                left_value = getattr(left, metric)
                right_value = getattr(right, metric)
                if left_value is None or right_value is None:
                    continue
                deltas.append(float(right_value) - float(left_value))
            if not deltas:
                continue
            seed_material = f"{reference_name}|{candidate_name}|{metric}".encode()
            seed = bootstrap_seed + int.from_bytes(
                hashlib.sha256(seed_material).digest()[:4], "big"
            )
            comparisons.append(
                PairedMetricComparison(
                    reference_strategy=reference_name,
                    candidate_strategy=candidate_name,
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


def run_model_constraint_benchmark(
    dataset: ConstraintBenchmarkDataset,
    *,
    provider: LLMProvider,
    provider_name: str,
    provider_model: str,
    tokenizer: Tokenizer,
    budget_ratio: float = 1.0,
    max_output_tokens: int = 96,
    temperature: float | None = 0.0,
    pricing: ModelPricing | None = None,
    case_limit: int | None = None,
    strategies: Sequence[BenchmarkStrategy] | None = None,
) -> tuple[ConstraintBenchmarkDataset, ConstraintModelRun]:
    """Optimize once per strategy, call one model, and score answers deterministically."""
    if not provider_name.strip() or not provider_model.strip():
        raise ValueError("provider name and model must not be blank")
    if max_output_tokens <= 0:
        raise ValueError("max output tokens must be positive")
    adjusted = constraint_dataset_at_budget(
        dataset,
        tokenizer,
        budget_ratio,
        case_limit=case_limit,
    )
    selected_strategies = list(strategies or default_model_constraint_strategies())
    compatible = ContextOSBenchDataset(
        name=adjusted.name,
        generator_version=adjusted.generator_version,
        generation_seed=adjusted.generation_seed,
        cases=list(adjusted.cases),
    )
    benchmark_run = run_contextos_bench(
        compatible,
        tokenizer=tokenizer,
        strategies=selected_strategies,
    )
    selections = evaluate_constraints(adjusted, benchmark_run)
    cases = {case.id: case for case in adjusted.cases}
    predictions: list[ConstraintModelPrediction] = []
    for selection in selections:
        case = cases[selection.benchmark.case_id]
        if selection.benchmark.status != "ok":
            predictions.append(
                _prediction_from_failure(
                    case,
                    selection,
                    provider_name=provider_name,
                    provider_model=provider_model,
                )
            )
            continue
        prompt = render_constraint_model_prompt(case, selection)
        started = perf_counter()
        try:
            response = provider.complete(prompt, max_output_tokens=max_output_tokens)
        except ContextOSError as exc:
            elapsed = (perf_counter() - started) * 1_000
            failed = _prediction_from_failure(
                case,
                selection,
                provider_name=provider_name,
                provider_model=provider_model,
            )
            predictions.append(
                failed.model_copy(
                    update={
                        "status": "provider_error",
                        "provider_latency_ms": elapsed,
                        "prompt_input_tokens": tokenizer.count_tokens(prompt),
                        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                        "warnings": (*failed.warnings, str(exc)),
                    }
                )
            )
            continue
        predictions.append(
            _prediction_from_response(
                case,
                selection,
                response,
                provider_name=provider_name,
                provider_model=provider_model,
                prompt=prompt,
                tokenizer=tokenizer,
                provider_latency_ms=(perf_counter() - started) * 1_000,
                pricing=pricing,
            )
        )
    return adjusted, ConstraintModelRun(
        recorded_at_utc=datetime.now(UTC),
        provider=provider_name,
        model=provider_model,
        tokenizer=type(tokenizer).__name__,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        budget_ratio=budget_ratio,
        baseline_v040_sha=PHASE5_BASELINE_SHA,
        predictions=predictions,
        aggregates=aggregate_model_constraint_predictions(predictions),
        paired_comparisons=_paired_comparisons(
            predictions,
            bootstrap_seed=dataset.generation_seed,
        ),
        pricing=pricing,
    )


def _display(value: float | int | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _report(run: ConstraintModelRun) -> str:
    overall = [value for value in run.aggregates if value.category is None]
    categorized = [value for value in run.aggregates if value.category is not None]
    lines = [
        "# Phase 5 Model-Backed Constraint Report",
        "",
        f"- Provider/model: `{run.provider}/{run.model}`",
        f"- Budget ratio: `{run.budget_ratio:.0%}`",
        f"- Temperature: `{run.temperature}`",
        f"- Predictions: {len(run.predictions)}",
        "",
        "## Overall results",
        "",
        "| Strategy | Successful | Task | Exact values | Answer violations | "
        "Selection violations | Mean context tokens | Reduction | Optimizer p95 ms | "
        "Provider p95 ms | Cost USD |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for value in overall:
        lines.append(
            f"| {value.strategy} | {value.successful_case_count}/{value.case_count} | "
            f"{_display(value.mean_task_score)} | "
            f"{_display(value.mean_exact_value_preservation_rate)} | "
            f"{value.answer_constraint_violation_rate:.4f} | "
            f"{value.selection_constraint_violation_rate:.4f} | "
            f"{_display(value.mean_input_context_tokens)} | "
            f"{_display(value.mean_context_reduction)} | "
            f"{_display(value.p95_optimizer_latency_ms)} | "
            f"{_display(value.p95_provider_latency_ms)} | "
            f"{_display(value.total_estimated_cost_usd)} |"
        )
    lines.extend(
        [
            "",
            "## Results by failure family",
            "",
            "| Category | Strategy | Successful | Task | Answer violations | "
            "Selection violations |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for value in categorized:
        assert value.category is not None
        lines.append(
            f"| {value.category.value} | {value.strategy} | "
            f"{value.successful_case_count}/{value.case_count} | "
            f"{_display(value.mean_task_score)} | "
            f"{value.answer_constraint_violation_rate:.4f} | "
            f"{value.selection_constraint_violation_rate:.4f} |"
        )
    lines.extend(
        [
            "",
            "Outputs are scored by deterministic required-value recall and forbidden-value "
            "leakage. No LLM judge is used. Failed or infeasible executions count as answer "
            "violations and are never assigned invented task scores.",
            "",
            "Raw `cases.jsonl` and `predictions.jsonl` are authoritative; this report is derived.",
        ]
    )
    return "\n".join(lines)


def write_model_constraint_artifact(
    output_directory: Path,
    *,
    dataset: ConstraintBenchmarkDataset,
    run: ConstraintModelRun,
    profile: str,
) -> Path:
    """Write one provider/model execution as an immutable seven-file bundle."""
    embedding = DeterministicEmbeddingProvider()
    environment = capture_environment(
        recorded_at_utc=run.recorded_at_utc,
        embedding_provider="deterministic",
        embedding_model=embedding.model_name,
        llm_provider=run.provider,
        llm_model=run.model,
        dependency_names=("openai",),
    )
    first_policy = dataset.cases[0].policy
    config = {
        "schema_version": run.schema_version,
        "benchmark": "contextos-bench-constraints-model",
        "profile": profile,
        "generator_version": dataset.generator_version,
        "generation_seed": dataset.generation_seed,
        "baseline_v040_sha": run.baseline_v040_sha,
        "current_research_sha": environment.git_sha,
        "provider": run.provider,
        "model": run.model,
        "prompt_version": MODEL_CONSTRAINT_PROMPT_VERSION,
        "strategies": sorted({value.strategy for value in run.predictions}),
        "case_count": len(dataset.cases),
        "execution": {
            "budget_ratio": run.budget_ratio,
            "temperature": run.temperature,
            "max_output_tokens": run.max_output_tokens,
            "tokenizer": run.tokenizer,
            "embedding_provider": "deterministic",
        },
        "phase5_components": {
            "contract_schema_version": "phase5c-v1",
            "constraint_resolver_version": "phase5d-v1",
            "validator_version": "phase5f-v1",
            "trace_schema_version": "phase5h-v1",
            "risk_aware_allocation": True,
            "omission_risk_weight": first_policy.omission_risk_weight,
            "transformation_risk_weight": first_policy.transformation_risk_weight,
        },
        "pricing": run.pricing.model_dump(mode="json") if run.pricing is not None else None,
        "statistics": {
            "method": "percentile bootstrap; paired for strategy deltas",
            "confidence_level": 0.95,
            "minimum_sample_size": MIN_BOOTSTRAP_SAMPLE_SIZE,
            "repeat_policy": "each repeat must be a separate immutable bundle",
        },
    }
    metrics = {
        "schema_version": run.schema_version,
        "aggregates": [value.model_dump(mode="json") for value in run.aggregates],
        "paired_comparisons": [value.model_dump(mode="json") for value in run.paired_comparisons],
        "status_counts": {
            status: sum(value.status == status for value in run.predictions)
            for status in sorted({value.status for value in run.predictions})
        },
    }
    rows = [
        {
            "category": value.category.value if value.category is not None else "all",
            **value.model_dump(mode="json", exclude={"category"}),
        }
        for value in run.aggregates
    ]
    return write_benchmark_bundle(
        output_directory=output_directory,
        recorded_at_utc=run.recorded_at_utc,
        strategy="constraint-model",
        profile=profile,
        config=config,
        environment=environment,
        cases=dataset.cases,
        predictions=run.predictions,
        metrics=metrics,
        metric_rows=rows,
        report=_report(run),
    )


__all__ = [
    "MODEL_CONSTRAINT_PROMPT_VERSION",
    "aggregate_model_constraint_predictions",
    "default_model_constraint_strategies",
    "render_constraint_model_prompt",
    "run_model_constraint_benchmark",
    "write_model_constraint_artifact",
]
