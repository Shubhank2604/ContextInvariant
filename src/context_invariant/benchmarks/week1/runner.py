"""Offline metadata-matched pilot and checkpoint replay with explicit outcome accounting."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from context_invariant import ContextOptimizer, OptimizationPolicy
from context_invariant.benchmarks.bundles import capture_environment, write_benchmark_bundle
from context_invariant.benchmarks.week1.baseline import MetadataMatchedSelector
from context_invariant.benchmarks.week1.evaluator import (
    evaluate_failure,
    evaluate_output,
    required_certificate,
    validate_labels,
)
from context_invariant.benchmarks.week1.models import (
    BUDGET_PERCENTAGES,
    STARTING_COMMIT,
    Checklist,
    StudyCase,
    StudyInputs,
    content_hash,
    prepare_inputs,
    study_policy,
)
from context_invariant.embeddings import DeterministicEmbeddingProvider
from context_invariant.layout import PositionAwareLayout
from context_invariant.models import ContextItem
from context_invariant.scoring import ScoreBreakdown
from context_invariant.tokenization import TiktokenTokenizer, Tokenizer

METHODS = ("context_invariant_full", "metadata_matched")


class SelectionObserver:
    """Observe existing layout passes without re-executing or changing selection."""

    def __init__(self) -> None:
        self.passes: list[dict[str, Any]] = []

    def arrange(
        self,
        items: Sequence[ContextItem],
        *,
        scores: Mapping[str, ScoreBreakdown],
        original_positions: Mapping[str, int],
    ) -> list[ContextItem]:
        arranged = PositionAwareLayout().arrange(
            items, scores=scores, original_positions=original_positions
        )
        self.passes.append(
            {
                "selected_ids": [item.id for item in arranged],
                "selected_tokens": sum(item.token_count or 0 for item in arranged),
                "scores": {key: value.model_dump(mode="json") for key, value in scores.items()},
            }
        )
        return arranged


def load_cases(dataset: Path, checklists: Path) -> tuple[list[StudyCase], dict[str, Checklist]]:
    cases = [StudyCase.model_validate(value) for value in json.loads(dataset.read_text("utf-8"))]
    labels = {
        key: Checklist.model_validate(value)
        for key, value in json.loads(checklists.read_text("utf-8")).items()
    }
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)) or set(ids) != labels.keys():
        raise ValueError("case IDs must be unique and match the separate checklists")
    for case in cases:
        validate_labels(case.inputs, labels[case.id])
    return cases, labels


def run_pair(
    case: StudyCase,
    checklist: Checklist,
    percentage: int,
    tokenizer: Tokenizer,
    *,
    replay: bool = False,
) -> list[dict[str, Any]]:
    """Prepare one shared input/policy, then pass those exact objects to both methods."""
    inputs = prepare_inputs(case.inputs, tokenizer)
    validate_labels(inputs, checklist)
    original_tokens = sum(tokenizer.count_tokens(item.content) for item in inputs.items)
    policy = study_policy(original_tokens, percentage)
    certificate = required_certificate(inputs, policy, tokenizer)
    before = content_hash(inputs)
    rows: list[dict[str, Any]] = []
    for method in METHODS:
        row = execute_method(inputs, checklist, method, policy, tokenizer)
        if content_hash(inputs) != before:
            raise RuntimeError(f"{method} mutated the shared selector inputs")
        row.update(
            case_id=case.id,
            budget_percentage=percentage,
            effective_budget=policy.effective_budget,
            original_context_tokens=original_tokens,
            shared_inputs_sha256=before,
            policy=policy.model_dump(mode="json"),
            required_certificate=certificate,
            inputs_unchanged=True,
        )
        if replay and row["selected_items"] is not None:
            prompt = render_prompt(inputs, row["selected_items"])
            row.update(model_prompt=prompt, model_prompt_tokens=tokenizer.count_tokens(prompt))
        rows.append(row)
    return rows


def execute_method(
    inputs: StudyInputs,
    checklist: Checklist,
    method: str,
    policy: OptimizationPolicy,
    tokenizer: Tokenizer,
) -> dict[str, Any]:
    certificate = required_certificate(inputs, policy, tokenizer)
    observer = SelectionObserver()
    try:
        if method == "context_invariant_full":
            result = ContextOptimizer(
                tokenizer=tokenizer,
                edges=inputs.edges,
                constraint_policy=inputs.constraint_policy,
                embedding_provider=DeterministicEmbeddingProvider(),
                layout=observer,
            ).optimize(inputs.task, inputs.items, policy)
        elif method == "metadata_matched":
            result = MetadataMatchedSelector().optimize(inputs, policy, tokenizer)
        else:
            raise ValueError(f"unknown study method: {method}")
    except Exception as error:  # preserve unexpected failures as visible execution errors
        return {
            "method": method,
            **evaluate_failure(error, certificate),
            "selected_items": None,
            "trace": None,
            "method_metadata": {"preclosure_passes": observer.passes},
            "context_reduction": None,
        }
    evaluation = evaluate_output(inputs, checklist, result.selected_items, policy, tokenizer)
    actual_tokens = evaluation["context_tokens"]
    if actual_tokens != result.final_token_count:
        evaluation["violations"].append("reported_token_count_mismatch")
        evaluation["outcome"] = "invalid_context"
    original_tokens = sum(tokenizer.count_tokens(item.content) for item in inputs.items)
    return {
        "method": method,
        **evaluation,
        "failure_reason": None,
        "selected_items": [item.model_dump(mode="json") for item in result.selected_items],
        "trace": result.trace.model_dump(mode="json"),
        "method_metadata": {**result.metadata, "preclosure_passes": observer.passes},
        "context_reduction": 1 - actual_tokens / original_tokens if original_tokens else 0.0,
    }


def render_prompt(inputs: StudyInputs, selected: Sequence[dict[str, Any]]) -> str:
    context = "\n\n".join(
        f"[record {item['id']}; type={item['type']}]\n{item['content']}" for item in selected
    )
    return (
        f"Use the supplied records to complete the coding task.\n\n{context}\n\nTASK\n{inputs.task}"
    )


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    for percentage in sorted({row["budget_percentage"] for row in rows}):
        for method in METHODS:
            values = [
                row
                for row in rows
                if row["budget_percentage"] == percentage and row["method"] == method
            ]
            valid = [row for row in values if row["outcome"] == "valid_context"]
            returned = [row for row in values if row["outcome"] != "no_context"]
            recall = [row["useful_recall"] for row in valid if row["useful_recall"] is not None]
            counts = Counter(row["outcome"] for row in values)
            cells.append(
                {
                    "budget_percentage": percentage,
                    "method": method,
                    "total": len(values),
                    **{
                        key: counts[key]
                        for key in ("valid_context", "invalid_context", "no_context")
                    },
                    "no_context_reasons": dict(
                        Counter(
                            row["failure_reason"]
                            for row in values
                            if row["outcome"] == "no_context"
                        )
                    ),
                    "valid_context_token_total": sum(row["context_tokens"] for row in valid),
                    "mean_valid_context_tokens": mean(row["context_tokens"] for row in valid)
                    if valid
                    else None,
                    "mean_returned_context_tokens": mean(row["context_tokens"] for row in returned)
                    if returned
                    else None,
                    "mean_valid_useful_recall": mean(recall) if recall else None,
                }
            )
    paired: list[dict[str, Any]] = []
    for percentage in sorted({row["budget_percentage"] for row in rows}):
        group = [row for row in rows if row["budget_percentage"] == percentage]
        matched = {
            row["case_id"]
            for row in group
            if all(
                other["outcome"] == "valid_context"
                for other in group
                if other["case_id"] == row["case_id"]
            )
        }
        annotated = {
            row["case_id"]
            for row in group
            if row["case_id"] in matched and row.get("useful_spans_total", 0) > 0
        }
        paired.append(
            {
                "budget_percentage": percentage,
                "matched_valid_case_count": len(matched),
                "context_token_totals": {
                    method: sum(
                        row["context_tokens"]
                        for row in group
                        if row["case_id"] in matched and row["method"] == method
                    )
                    for method in METHODS
                },
                "matched_valid_annotated_case_count": len(annotated),
                "mean_useful_recall": {
                    method: mean(
                        row["useful_recall"]
                        for row in group
                        if row["case_id"] in annotated and row["method"] == method
                    )
                    if annotated
                    else None
                    for method in METHODS
                },
            }
        )
    return {"cells": cells, "matched_valid": paired, "evaluation_count": len(rows)}


def disagreements(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Retain every difference, including baseline wins, failures and layout-only changes."""
    results: list[dict[str, Any]] = []
    keys = sorted({(row["case_id"], row["budget_percentage"]) for row in rows})
    for case_id, percentage in keys:
        pair = {
            row["method"]: row
            for row in rows
            if row["case_id"] == case_id and row["budget_percentage"] == percentage
        }
        full, baseline = (pair[method] for method in METHODS)
        fields = ("outcome", "failure_reason", "context_tokens", "useful_recall", "violations")
        differences = [field for field in fields if full.get(field) != baseline.get(field)]
        full_text = {item["id"]: item["content"] for item in full["selected_items"] or []}
        base_text = {item["id"]: item["content"] for item in baseline["selected_items"] or []}
        if full_text != base_text:
            differences.append("selected_content")
        full_order = [item["id"] for item in full["selected_items"] or []]
        base_order = [item["id"] for item in baseline["selected_items"] or []]
        if full_order != base_order:
            differences.append("layout_or_selection_order")
        if not differences:
            continue
        changed = [
            {
                "item_id": item_id,
                "full_text": full_text.get(item_id),
                "baseline_text": base_text.get(item_id),
                "full_decision": next(
                    (
                        trace
                        for trace in (full["trace"] or {}).get("items", [])
                        if trace["item_id"] == item_id
                    ),
                    None,
                ),
            }
            for item_id in sorted(full_text.keys() | base_text.keys())
            if full_text.get(item_id) != base_text.get(item_id)
        ]
        results.append(
            {
                "case_id": case_id,
                "budget_percentage": percentage,
                "different_fields": differences,
                "full_outcome": full["outcome"],
                "baseline_outcome": baseline["outcome"],
                "full_failure": full.get("exception_message"),
                "baseline_bundle_decisions": (baseline["method_metadata"] or {}).get(
                    "bundle_decisions"
                ),
                "changed_records": changed,
                "full_order": full_order,
                "baseline_order": base_order,
            }
        )
    return results


def source_manifest(root: Path) -> dict[str, Any]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", "src", "scripts", "tests", "research/week1/inputs"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    hashes = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for folder in ("src", "scripts", "research/week1/workflow/task")
        for pattern in ("*.py", "*.json")
        for path in sorted((root / folder).rglob(pattern))
    }
    return {"execution_commit": revision, "study_source_status": status, "source_sha256": hashes}


def run_study(
    dataset: Path,
    checklists: Path,
    output_directory: Path,
    *,
    replay: bool = False,
) -> Path:
    cases, labels = load_cases(dataset, checklists)
    if not replay and len(cases) != 10:
        raise ValueError("the prespecified pilot has exactly ten cases")
    tokenizer = TiktokenTokenizer()
    percentages = (80,) if replay else BUDGET_PERCENTAGES
    rows = [
        row
        for case in cases
        for percentage in percentages
        for row in run_pair(case, labels[case.id], percentage, tokenizer, replay=replay)
    ]
    summary = summarize(rows)
    changes = disagreements(rows)
    recorded = datetime.now(UTC)
    root = Path(__file__).resolve().parents[4]
    config = {
        "protocol": "week1-metadata-matched-v1",
        "starting_commit": STARTING_COMMIT,
        **source_manifest(root),
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "checklists_sha256": hashlib.sha256(checklists.read_bytes()).hexdigest(),
        "canonical_dataset_sha256": content_hash(
            {"cases": [case.model_dump(mode="json") for case in cases]}
        ),
        "canonical_checklists_sha256": content_hash(
            {key: value.model_dump(mode="json") for key, value in labels.items()}
        ),
        "budget_percentages": percentages,
        "budget_rounding": "floor(sum(original record tokens) * percentage / 100)",
        "tokenizer": "cl100k_base",
        "methods": METHODS,
        "development_only": True,
        "replay": replay,
        "disagreements": changes,
    }
    report = "# Offline development replay\n" if replay else "# Offline development pilot\n"
    report += "\n| Budget | Method | Valid | Invalid | No context | Mean valid tokens |\n"
    report += "|---|---|---|---|---|---|\n"
    for cell in summary["cells"]:
        report += (
            f"| {cell['budget_percentage']}% | {cell['method']} | {cell['valid_context']} | "
            f"{cell['invalid_context']} | {cell['no_context']} | "
            f"{cell['mean_valid_context_tokens']} |\n"
        )
    report += (
        "\nNo-output runs have null token use and are visible in totals. "
        "See metrics.json for matched-valid token totals and failure reasons, config.json "
        "for every disagreement, and predictions.jsonl for text, traces and certificates. "
        "This development pilot makes no held-out or downstream-success claim.\n"
    )
    return write_benchmark_bundle(
        output_directory=output_directory,
        recorded_at_utc=recorded,
        strategy="week1-replay" if replay else "metadata-matched-pilot",
        profile="development",
        config=config,
        environment=capture_environment(
            recorded_at_utc=recorded,
            embedding_provider="DeterministicEmbeddingProvider",
            embedding_model=DeterministicEmbeddingProvider.model_name,
        ),
        cases=[
            {
                "case": case.model_dump(mode="json"),
                "checklist": labels[case.id].model_dump(mode="json"),
            }
            for case in cases
        ],
        predictions=rows,
        metrics=summary,
        metric_rows=[
            {key: value for key, value in cell.items() if key != "no_context_reasons"}
            for cell in summary["cells"]
        ],
        report=report,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--checklists", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    print(run_study(args.inputs, args.checklists, args.output_directory, replay=args.replay))


if __name__ == "__main__":
    main()
