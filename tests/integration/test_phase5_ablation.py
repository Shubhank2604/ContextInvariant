"""Phase 5I cumulative-ablation and budget-frontier acceptance tests."""

from __future__ import annotations

import json
import math
from pathlib import Path

from contextos.benchmarks.bundles import REQUIRED_BUNDLE_FILES
from contextos.benchmarks.constraint_dataset import (
    PHASE5_BASELINE_SHA,
    generate_constraint_dataset,
)
from contextos.benchmarks.phase5_ablation import (
    BUDGET_RATIOS,
    Phase5Variant,
    phase5_ablation_strategies,
    run_phase5_ablation,
    write_phase5_ablation_artifact,
)
from contextos.tokenization import TiktokenTokenizer

EXPECTED_STRATEGIES = (
    "full_context",
    "last_n",
    "sliding_window",
    "relevance_only",
    "naive_extractive",
    "phase5_v040",
    "phase5_hard_relations",
    "phase5_preservation_contracts",
    "phase5_validated_transformations",
    "phase5_omission_risk",
    "phase5_full",
)


def test_phase5_matrix_runs_every_strategy_at_every_budget() -> None:
    dataset = generate_constraint_dataset()
    tokenizer = TiktokenTokenizer()
    result = run_phase5_ablation(dataset, tokenizer=tokenizer, case_limit=1)

    assert result.baseline_v040_sha == PHASE5_BASELINE_SHA
    assert result.budget_ratios == BUDGET_RATIOS
    assert result.strategies == EXPECTED_STRATEGIES
    assert len(result.budget_results) == len(BUDGET_RATIOS)
    for budget in result.budget_results:
        assert budget.run.strategies == list(EXPECTED_STRATEGIES)
        assert len(budget.run.measurements) == len(EXPECTED_STRATEGIES)
        case = dataset.cases[0]
        original = sum(tokenizer.count_tokens(item.content) for item in case.context_items)
        expected_budget = math.ceil(original * budget.budget_ratio)
        constrained = [
            measurement
            for measurement in budget.run.measurements
            if measurement.strategy != "full_context"
        ]
        assert {measurement.effective_budget for measurement in constrained} == {expected_budget}
        assert all(
            comparison.reference_strategy == Phase5Variant.V040.value
            for comparison in budget.run.paired_comparisons
        )


def test_full_variant_adds_tracing_without_changing_omission_risk_selection() -> None:
    dataset = generate_constraint_dataset()
    result = run_phase5_ablation(
        dataset,
        tokenizer=TiktokenTokenizer(),
        budget_ratios=(1.0,),
        case_limit=1,
    )
    measurements = {value.strategy: value for value in result.budget_results[0].run.measurements}

    risk = measurements[Phase5Variant.OMISSION_RISK.value]
    full = measurements[Phase5Variant.FULL.value]
    assert risk.selected_item_ids == full.selected_item_ids
    assert risk.input_tokens == full.input_tokens
    assert full.status == "ok"


def test_contracts_add_retention_beyond_hard_relations() -> None:
    dataset = generate_constraint_dataset()
    supersession = dataset.model_copy(update={"cases": [dataset.cases[10]]})
    result = run_phase5_ablation(
        supersession,
        tokenizer=TiktokenTokenizer(),
        budget_ratios=(0.5,),
    )
    measurements = {value.strategy: value for value in result.budget_results[0].run.measurements}

    hard = measurements[Phase5Variant.HARD_RELATIONS.value]
    contracts = measurements[Phase5Variant.PRESERVATION_CONTRACTS.value]
    assert hard.status == "ok"
    assert hard.critical_information_recall == 0.0
    assert contracts.status == "overflow"
    assert "mandatory context requires" in contracts.warnings[0]


def test_full_variant_has_no_constraint_violations_at_full_budget() -> None:
    dataset = generate_constraint_dataset()
    result = run_phase5_ablation(
        dataset,
        tokenizer=TiktokenTokenizer(),
        budget_ratios=(1.0,),
    )
    aggregate = next(
        value
        for value in result.budget_results[0].constraint_aggregates
        if value.strategy == Phase5Variant.FULL.value
    )

    assert aggregate.case_count == 90
    assert aggregate.constraint_violation_rate == 0.0


def test_phase5_artifact_is_immutable_seven_file_evidence_bundle(tmp_path: Path) -> None:
    dataset = generate_constraint_dataset()
    result = run_phase5_ablation(
        dataset,
        tokenizer=TiktokenTokenizer(),
        budget_ratios=(0.8, 1.0),
        case_limit=1,
    )

    artifact = write_phase5_ablation_artifact(
        tmp_path,
        dataset=dataset,
        result=result,
        profile="test",
    )

    assert {entry.name for entry in artifact.iterdir()} == REQUIRED_BUNDLE_FILES
    config = json.loads((artifact / "config.json").read_text(encoding="utf-8"))
    metrics = json.loads((artifact / "metrics.json").read_text(encoding="utf-8"))
    assert config["baseline_v040_sha"] == PHASE5_BASELINE_SHA
    assert config["budget_ratios"] == [0.8, 1.0]
    assert config["strategies"] == list(EXPECTED_STRATEGIES)
    assert len(metrics["budget_results"]) == 2
    assert "phase5_full" in (artifact / "report.md").read_text(encoding="utf-8")


def test_strategy_factory_has_one_entry_for_each_cumulative_variant() -> None:
    strategies = phase5_ablation_strategies()

    assert tuple(strategy.name for strategy in strategies) == EXPECTED_STRATEGIES
    assert tuple(variant.value for variant in Phase5Variant) == EXPECTED_STRATEGIES[-6:]
