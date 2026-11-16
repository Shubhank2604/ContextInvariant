"""Recheck retained raw outputs without invoking either selector."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from context_invariant import ContextItem
from context_invariant.benchmarks.bundles import load_benchmark_bundle
from context_invariant.benchmarks.week1.evaluator import evaluate_output, required_certificate
from context_invariant.benchmarks.week1.models import (
    BUDGET_PERCENTAGES,
    content_hash,
    prepare_inputs,
    study_policy,
)
from context_invariant.benchmarks.week1.runner import METHODS, load_cases, summarize
from context_invariant.tokenization import TiktokenTokenizer


def audit_bundle(bundle_path: Path, inputs_path: Path, checklists_path: Path) -> dict[str, Any]:
    bundle = load_benchmark_bundle(bundle_path)
    cases, labels = load_cases(inputs_path, checklists_path)
    if bundle.config["canonical_dataset_sha256"] != content_hash(
        {"cases": [case.model_dump(mode="json") for case in cases]}
    ):
        raise ValueError("saved input identity does not match the supplied dataset")
    if bundle.config["canonical_checklists_sha256"] != content_hash(
        {key: value.model_dump(mode="json") for key, value in labels.items()}
    ):
        raise ValueError("saved checklist identity does not match the supplied labels")
    expected_cases = [
        {"case": case.model_dump(mode="json"), "checklist": labels[case.id].model_dump(mode="json")}
        for case in cases
    ]
    if bundle.cases != expected_cases:
        raise ValueError("saved raw cases or checklists were changed")
    tokenizer = TiktokenTokenizer()
    by_id = {case.id: case for case in cases}
    percentages = (80,) if bundle.config["replay"] else BUDGET_PERCENTAGES
    expected = {
        (case.id, method, percentage)
        for case in cases
        for method in METHODS
        for percentage in percentages
    }
    actual = [
        (row["case_id"], row["method"], row["budget_percentage"]) for row in bundle.predictions
    ]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("raw outputs must cover the exact prespecified evaluation grid")
    for row in bundle.predictions:
        inputs = prepare_inputs(by_id[row["case_id"]].inputs, tokenizer)
        original_tokens = sum(tokenizer.count_tokens(item.content) for item in inputs.items)
        policy = study_policy(original_tokens, row["budget_percentage"])
        certificate = required_certificate(inputs, policy, tokenizer)
        if row["required_certificate"] != certificate:
            raise ValueError("saved infeasibility certificate is incorrect")
        if row["shared_inputs_sha256"] != content_hash(inputs):
            raise ValueError("selector inputs differ from the declared shared inputs")
        if row["effective_budget"] != policy.effective_budget or row["policy"] != policy.model_dump(
            mode="json"
        ):
            raise ValueError("saved policy or effective budget is incorrect")
        if row["outcome"] == "no_context":
            if any(
                row[field] is not None
                for field in (
                    "selected_items",
                    "context_tokens",
                    "context_reduction",
                    "useful_recall",
                )
            ):
                raise ValueError("a no-context outcome cannot contain output or token savings")
            if (
                row["failure_reason"] == "budget_infeasible"
                and not certificate["proves_budget_infeasible"]
            ):
                raise ValueError("budget infeasibility lacks a valid lower-bound certificate")
            if row["failure_reason"] == "execution_error":
                raise ValueError("unexpected execution error requires investigation")
        else:
            selected = [ContextItem.model_validate(item) for item in row["selected_items"]]
            evaluation = evaluate_output(
                inputs, labels[row["case_id"]], selected, policy, tokenizer
            )
            for field in ("outcome", "context_tokens", "violations", "useful_recall"):
                if evaluation[field] != row[field]:
                    raise ValueError(f"saved evaluation does not match raw text: {field}")
            if row["method"] == "metadata_matched":
                source = {item.id: item.content for item in inputs.items}
                if any(item.content != source[item.id] for item in selected):
                    raise ValueError("the verbatim baseline changed selected text")
    if summarize(bundle.predictions) != bundle.metrics:
        raise ValueError("aggregate metrics do not match the raw evaluations")
    return {
        "bundle": bundle_path.name,
        "execution_commit": bundle.config["execution_commit"],
        "checked_evaluations": len(bundle.predictions),
        "shared_input_identity": "passed",
        "raw_text_and_token_recheck": "passed",
        "no_output_accounting": "passed",
        "infeasibility_certificates": "passed",
        "verbatim_baseline": "passed",
        "aggregate_recomputation": "passed",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--checklists", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit_bundle(args.bundle, args.inputs, args.checklists), indent=2))


if __name__ == "__main__":
    main()
