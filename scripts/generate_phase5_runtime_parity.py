"""Generate the tracked Phase 5 runtime parity fixture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from context_invariant.benchmarks.constraint_benchmark import run_constraint_benchmark
from context_invariant.benchmarks.constraint_dataset import (
    PHASE5_BASELINE_SHA,
    generate_constraint_dataset,
)
from context_invariant.benchmarks.constraint_models import ConstraintMeasurement
from context_invariant.benchmarks.phase5_ablation import (
    BUDGET_RATIOS,
    Phase5BenchmarkStrategy,
    Phase5Variant,
    constraint_dataset_at_budget,
)
from context_invariant.tokenization import TiktokenTokenizer

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPOSITORY_ROOT / "tests/fixtures/phase5_full_runtime_parity_v1.json"
CAPTURED_FROM_GIT_SHA = "b50da2ffc66ca1b5df941d87435718c532c9bfba"


def _selected_context_sha256(measurement: ConstraintMeasurement) -> str:
    selected = [item.model_dump(mode="json") for item in measurement.benchmark.selected_items]
    payload = json.dumps(
        selected,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _record(
    budget_ratio: float,
    measurement: ConstraintMeasurement,
) -> dict[str, Any]:
    benchmark = measurement.benchmark
    return {
        "budget_ratio": budget_ratio,
        "case_id": benchmark.case_id,
        "category": measurement.category.value,
        "status": benchmark.status,
        "effective_budget": benchmark.effective_budget,
        "input_tokens": benchmark.input_tokens,
        "compressed_count": benchmark.compressed_count,
        "selected_item_ids": benchmark.selected_item_ids,
        "selected_context_sha256": _selected_context_sha256(measurement),
        "task_specific_score": benchmark.task_specific_score,
        "critical_information_recall": benchmark.critical_information_recall,
        "context_reduction": benchmark.context_reduction,
        "required_items_retained": benchmark.required_items_retained,
        "required_items_total": benchmark.required_items_total,
        "required_facts_retained": benchmark.required_facts_retained,
        "required_facts_total": benchmark.required_facts_total,
        "constraint_violation_rate": measurement.constraint_violation_rate,
        "dependency_closure_rate": measurement.dependency_closure_rate,
        "state_consistency_rate": measurement.state_consistency_rate,
        "contradiction_leakage_rate": measurement.contradiction_leakage_rate,
        "exact_value_preservation_rate": measurement.exact_value_preservation_rate,
        "identifier_preservation_rate": measurement.identifier_preservation_rate,
        "citation_preservation_rate": measurement.citation_preservation_rate,
    }


def main() -> None:
    """Regenerate the parity fixture from the pre-integration implementation."""
    tokenizer = TiktokenTokenizer()
    dataset = generate_constraint_dataset()
    strategy = Phase5BenchmarkStrategy(Phase5Variant.FULL)
    records: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    for budget_ratio in BUDGET_RATIOS:
        adjusted = constraint_dataset_at_budget(
            dataset,
            tokenizer,
            budget_ratio,
            case_limit=None,
        )
        _, measurements, _ = run_constraint_benchmark(
            adjusted,
            tokenizer=tokenizer,
            strategies=[strategy],
        )
        for measurement in measurements:
            records.append(_record(budget_ratio, measurement))
            status = measurement.benchmark.status
            status_counts[status] = status_counts.get(status, 0) + 1
    fixture = {
        "schema_version": "phase5-runtime-parity-v1",
        "strategy": Phase5Variant.FULL.value,
        "baseline_v040_sha": PHASE5_BASELINE_SHA,
        "captured_from_git_sha": CAPTURED_FROM_GIT_SHA,
        "generator_version": dataset.generator_version,
        "budget_ratios": list(BUDGET_RATIOS),
        "case_count": len(dataset.cases),
        "record_count": len(records),
        "status_counts": dict(sorted(status_counts.items())),
        "records": records,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(fixture, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
