"""Execute exactly the locked 30-case, two-method, three-budget offline comparison."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from context_invariant.benchmarks.bundles import capture_environment, write_benchmark_bundle
from context_invariant.benchmarks.week1.models import BUDGET_PERCENTAGES, StudyCase
from context_invariant.benchmarks.week1.runner import METHODS, disagreements, run_pair, summarize
from context_invariant.benchmarks.week2.models import FAMILIES, Mode
from context_invariant.benchmarks.week2.preflight import canonical, preflight
from context_invariant.benchmarks.week2.prompts import (
    render_context_prompt as render_context_prompt,
)
from context_invariant.embeddings import DeterministicEmbeddingProvider
from context_invariant.tokenization import TiktokenTokenizer


def classify(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Only call a selection refusal avoidable when a peer returns a valid witness."""
    result: list[dict[str, Any]] = []
    for row in rows:
        witness = None
        if row["outcome"] != "no_context":
            category = row["outcome"]
        elif row["failure_reason"] == "budget_infeasible":
            category = "certified_infeasibility"
        elif row["failure_reason"] == "selection_failure":
            peer = next(
                (
                    other
                    for other in rows
                    if other["case_id"] == row["case_id"]
                    and other["budget_percentage"] == row["budget_percentage"]
                    and other["method"] != row["method"]
                    and other["outcome"] == "valid_context"
                ),
                None,
            )
            category = "avoidable_selection_failure" if peer else "unproven_selection_failure"
            if peer:
                witness = {
                    "method": peer["method"],
                    "context_tokens": peer["context_tokens"],
                    "selected_items_sha256": canonical(peer["selected_items"]),
                }
        else:
            category = row["failure_reason"]
        result.append({**row, "outcome_class": category, "feasibility_witness": witness})
    return result


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    overall = summarize(rows)
    families = {
        family: summarize([row for row in rows if row["family"] == family]) for family in FAMILIES
    }
    for family, summary in [("all", overall), *families.items()]:
        for cell in summary["cells"]:
            cell["family"] = family
            cell["outcome_classes"] = dict(
                Counter(
                    row["outcome_class"]
                    for row in rows
                    if row["method"] == cell["method"]
                    and row["budget_percentage"] == cell["budget_percentage"]
                    and (family == "all" or row["family"] == family)
                )
            )
    return {"evaluation_count": len(rows), "overall": overall, "families": families}


def report(metrics: dict[str, Any], mode: Mode) -> str:
    title = (
        "SYNTHETIC DEVELOPMENT DRY RUN — NOT FINAL EVIDENCE"
        if mode == "synthetic_development"
        else "Sealed offline Week 2 evaluation"
    )
    lines = [
        f"# {title}",
        "",
        "| Family | Budget | Method | Valid | Invalid | No context | Mean valid tokens |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for summary in [metrics["overall"], *metrics["families"].values()]:
        for cell in summary["cells"]:
            lines.append(
                f"| {cell['family']} | {cell['budget_percentage']}% | {cell['method']} | "
                f"{cell['valid_context']} | {cell['invalid_context']} | {cell['no_context']} | "
                f"{cell['mean_valid_context_tokens']} |"
            )
    lines.extend(
        [
            "",
            "All attempts remain in the denominators. "
            "No-output token use and useful recall are null.",
            "metrics.json reports certified, witnessed-avoidable and unproven failures separately,",
            "plus matched-valid tokens and optional evidence recall overall and by family.",
            "config.json includes preflight evidence and every disagreement. No live model calls.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_evaluation(
    inputs: Path,
    keys: Path,
    freeze: Path,
    output_directory: Path,
    *,
    mode: Mode,
    **seal_arguments: Any,
) -> Path:
    cases, labels, evidence = preflight(inputs, keys, freeze, mode=mode, **seal_arguments)
    tokenizer = TiktokenTokenizer()
    rows: list[dict[str, Any]] = []
    for case in cases:
        # Strip family/provenance and never put scoring labels in the input object.
        shared_case = StudyCase(id=case.id, inputs=case.inputs)
        for percentage in BUDGET_PERCENTAGES:
            for row in run_pair(shared_case, labels[case.id], percentage, tokenizer):
                row.update(family=case.family, data_kind=mode)
                if row["selected_items"] is not None:
                    prompt = render_context_prompt(case.inputs.task, row["selected_items"])
                    row.update(
                        model_prompt=prompt, model_prompt_tokens=tokenizer.count_tokens(prompt)
                    )
                rows.append(row)
    rows = classify(rows)
    metrics = aggregate(rows)
    recorded = datetime.now(UTC)
    metric_rows = [
        {
            key: value
            for key, value in cell.items()
            if key not in ("outcome_classes", "no_context_reasons")
        }
        for summary in [metrics["overall"], *metrics["families"].values()]
        for cell in summary["cells"]
    ]
    return write_benchmark_bundle(
        output_directory=output_directory,
        recorded_at_utc=recorded,
        strategy="week2-synthetic-dry-run" if mode == "synthetic_development" else "week2-sealed",
        profile="development" if mode == "synthetic_development" else "final",
        config={
            "protocol": "week2-offline-v1",
            "mode": mode,
            "preflight": evidence,
            "method_ids": list(METHODS),
            "expected_evaluations": 180,
            "disagreements": disagreements(rows),
        },
        environment=capture_environment(
            recorded_at_utc=recorded,
            embedding_provider="DeterministicEmbeddingProvider",
            embedding_model=DeterministicEmbeddingProvider.model_name,
            dependency_names=("cryptography", "packaging"),
        ),
        cases=[
            {
                "case": case.model_dump(mode="json"),
                "checklist": labels[case.id].model_dump(mode="json"),
            }
            for case in cases
        ],
        predictions=rows,
        metrics=metrics,
        metric_rows=metric_rows,
        report=report(metrics, mode),
    )
