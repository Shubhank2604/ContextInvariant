"""Phase 5J model-backed constraint validation acceptance tests."""

from __future__ import annotations

import json
from pathlib import Path

from contextos.benchmarks.bundles import REQUIRED_BUNDLE_FILES
from contextos.benchmarks.constraint_dataset import generate_constraint_dataset
from contextos.benchmarks.constraint_model import (
    run_model_constraint_benchmark,
    write_model_constraint_artifact,
)
from contextos.benchmarks.constraint_models import ConstraintBenchmarkDataset, ModelPricing
from contextos.benchmarks.phase5_ablation import Phase5Variant
from contextos.errors import LLMProviderError
from contextos.providers.base import ProviderResponse
from contextos.tokenization import TiktokenTokenizer


class ConflictSensitiveProvider:
    """Expose whether stale state survived into the model-visible prompt."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def complete(self, prompt: str, *, max_output_tokens: int) -> ProviderResponse:
        self.calls.append((prompt, max_output_tokens))
        current = "region-west-001"
        stale = "region-east-001"
        answer = f"{current} {stale}" if stale in prompt else current
        return ProviderResponse(
            text=answer,
            input_tokens=len(prompt.split()),
            output_tokens=len(answer.split()),
            cached_tokens=2,
            ttft_ms=0.5,
            model="fixture-v1",
        )


class FailingProvider:
    def complete(self, prompt: str, *, max_output_tokens: int) -> ProviderResponse:
        raise LLMProviderError("fixture provider unavailable")


def _supersession_dataset() -> ConstraintBenchmarkDataset:
    dataset = generate_constraint_dataset()
    return dataset.model_copy(update={"cases": [dataset.cases[10]]})


def test_same_model_comparison_translates_context_legality_to_answer_legality() -> None:
    provider = ConflictSensitiveProvider()
    pricing = ModelPricing(
        input_usd_per_million=1.0,
        output_usd_per_million=2.0,
        cached_input_usd_per_million=0.5,
    )
    _, run = run_model_constraint_benchmark(
        _supersession_dataset(),
        provider=provider,
        provider_name="fixture",
        provider_model="fixture-v1",
        tokenizer=TiktokenTokenizer(),
        pricing=pricing,
    )

    assert len(provider.calls) == 3
    assert {max_tokens for _, max_tokens in provider.calls} == {96}
    predictions = {value.strategy: value for value in run.predictions}
    assert predictions["full_context"].answer_constraint_violation is True
    assert predictions[Phase5Variant.V040.value].answer_constraint_violation is True
    assert predictions[Phase5Variant.FULL.value].answer_constraint_violation is False
    assert predictions[Phase5Variant.FULL.value].task_score == 1.0
    assert predictions[Phase5Variant.FULL.value].estimated_cost_usd is not None
    assert all(value.provider == "fixture" for value in run.predictions)
    assert all(value.model == "fixture-v1" for value in run.predictions)
    assert all(value.prompt_input_tokens is not None for value in run.predictions)
    assert all(value.provider_latency_ms is not None for value in run.predictions)
    assert all(value.model_ttft_ms == 0.5 for value in run.predictions)
    assert len(run.aggregates) == 6
    assert len(run.paired_comparisons) == 8


def test_provider_failures_remain_raw_unscored_violations() -> None:
    _, run = run_model_constraint_benchmark(
        _supersession_dataset(),
        provider=FailingProvider(),
        provider_name="fixture",
        provider_model="fixture-v1",
        tokenizer=TiktokenTokenizer(),
    )

    assert all(value.status == "provider_error" for value in run.predictions)
    assert all(value.task_score is None for value in run.predictions)
    assert all(value.answer_constraint_violation for value in run.predictions)
    assert all("fixture provider unavailable" in value.warnings for value in run.predictions)


def test_model_constraint_bundle_captures_phase5_and_provider_provenance(
    tmp_path: Path,
) -> None:
    dataset, run = run_model_constraint_benchmark(
        _supersession_dataset(),
        provider=ConflictSensitiveProvider(),
        provider_name="fixture",
        provider_model="fixture-v1",
        tokenizer=TiktokenTokenizer(),
    )
    artifact = write_model_constraint_artifact(
        tmp_path,
        dataset=dataset,
        run=run,
        profile="test",
    )

    assert {entry.name for entry in artifact.iterdir()} == REQUIRED_BUNDLE_FILES
    config = json.loads((artifact / "config.json").read_text(encoding="utf-8"))
    metrics = json.loads((artifact / "metrics.json").read_text(encoding="utf-8"))
    assert config["generator_version"] == "1.3.0"
    assert config["prompt_version"] == "phase5j-constraint-prompt-v1"
    assert config["phase5_components"]["constraint_resolver_version"] == "phase5d-v1"
    assert config["execution"]["temperature"] == 0.0
    assert metrics["status_counts"] == {"ok": 3}
    assert len((artifact / "predictions.jsonl").read_text(encoding="utf-8").splitlines()) == 3


def test_budget_ratio_validation_precedes_provider_calls() -> None:
    provider = ConflictSensitiveProvider()

    try:
        run_model_constraint_benchmark(
            _supersession_dataset(),
            provider=provider,
            provider_name="fixture",
            provider_model="fixture-v1",
            tokenizer=TiktokenTokenizer(),
            budget_ratio=0.0,
        )
    except ValueError as exc:
        assert "budget ratio" in str(exc)
    else:
        raise AssertionError("invalid budget ratio was accepted")
    assert provider.calls == []
