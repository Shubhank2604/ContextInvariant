"""Audit the entire Week 2 grid and saved evidence without executing selectors."""

from __future__ import annotations

from collections import Counter
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
from context_invariant.benchmarks.week1.runner import METHODS, disagreements
from context_invariant.benchmarks.week2.models import Mode
from context_invariant.benchmarks.week2.preflight import preflight
from context_invariant.benchmarks.week2.runner import (
    aggregate,
    classify,
    render_context_prompt,
    report,
)
from context_invariant.tokenization import TiktokenTokenizer


def audit_evaluation(
    bundle_path: Path,
    inputs: Path,
    keys: Path,
    freeze: Path,
    *,
    mode: Mode,
    **seal_arguments: Any,
) -> dict[str, Any]:
    cases, labels, evidence = preflight(inputs, keys, freeze, mode=mode, **seal_arguments)
    bundle = load_benchmark_bundle(bundle_path)
    if (
        bundle.config.get("protocol") != "week2-offline-v1"
        or bundle.config.get("mode") != mode
        or bundle.config.get("preflight") != evidence
        or bundle.config.get("method_ids") != list(METHODS)
        or bundle.config.get("expected_evaluations") != 180
    ):
        raise ValueError("saved preflight/data/freeze/configuration evidence mismatch")
    expected_cases = [
        {"case": case.model_dump(mode="json"), "checklist": labels[case.id].model_dump(mode="json")}
        for case in cases
    ]
    if bundle.cases != expected_cases:
        raise ValueError("saved cases or keys differ from authenticated inputs")
    expected = {
        (case.id, method, percentage)
        for case in cases
        for method in METHODS
        for percentage in BUDGET_PERCENTAGES
    }
    rows = bundle.predictions
    identities = [(row["case_id"], row["method"], row["budget_percentage"]) for row in rows]
    if len(identities) != len(set(identities)) or set(identities) != expected:
        raise ValueError("missing, duplicate or unexpected result row in the 180-evaluation grid")
    by_id = {case.id: case for case in cases}
    tokenizer = TiktokenTokenizer()
    for row in rows:
        case = by_id[row["case_id"]]
        shared = prepare_inputs(case.inputs, tokenizer)
        original_tokens = sum(tokenizer.count_tokens(item.content) for item in shared.items)
        policy = study_policy(original_tokens, row["budget_percentage"])
        if (
            row["family"] != case.family
            or row["data_kind"] != mode
            or row["shared_inputs_sha256"] != content_hash(shared)
            or row["inputs_unchanged"] is not True
            or row["original_context_tokens"] != original_tokens
            or row["effective_budget"] != policy.effective_budget
            or row["policy"] != policy.model_dump(mode="json")
        ):
            raise ValueError(
                "row shared-input identity, family, token accounting or policy mismatch"
            )
        certificate = required_certificate(shared, policy, tokenizer)
        if row["required_certificate"] != certificate:
            raise ValueError("invalid required-budget certificate")
        if row["outcome"] == "no_context":
            if any(
                field not in row or row[field] is not None
                for field in (
                    "selected_items",
                    "context_tokens",
                    "context_reduction",
                    "useful_recall",
                    "trace",
                )
            ):
                raise ValueError("no-context rows must have null output/token/recall fields")
            if "model_prompt" in row or "model_prompt_tokens" in row:
                raise ValueError("no-context rows must not contain prompts")
            if (
                not row.get("exception_type")
                or not row.get("exception_message")
                or row["violations"]
            ):
                raise ValueError("failure rows require an exception type and reason")
            overflow = row["exception_type"] in (
                "MandatoryContextOverflow",
                "RequiredContextOverflow",
            )
            reason = (
                (
                    "budget_infeasible"
                    if certificate["proves_budget_infeasible"]
                    else "selection_failure"
                )
                if overflow
                else "constraint_conflict"
                if row["exception_type"] in ("ConstraintUnsatisfiable", "UnresolvedConflict")
                else "execution_error"
            )
            if row["failure_reason"] != reason:
                raise ValueError("failure reason misclassifies a certified or avoidable failure")
        else:
            if (
                row["outcome"] not in ("valid_context", "invalid_context")
                or row["selected_items"] is None
            ):
                raise ValueError("unknown outcome or missing returned context")
            selected = [ContextItem.model_validate(value) for value in row["selected_items"]]
            evaluation = evaluate_output(shared, labels[case.id], selected, policy, tokenizer)
            if row["trace"]["final_tokens"] != evaluation["context_tokens"]:
                evaluation["violations"].append("reported_token_count_mismatch")
                evaluation["outcome"] = "invalid_context"
            for field, value in evaluation.items():
                if row.get(field) != value:
                    raise ValueError(f"raw selected text/evaluation mismatch: {field}")
            expected_reduction = 1 - evaluation["context_tokens"] / original_tokens
            if row["context_reduction"] != expected_reduction or row["failure_reason"] is not None:
                raise ValueError("returned context accounting mismatch")
            prompt = render_context_prompt(shared.task, row["selected_items"])
            if (
                row.get("model_prompt") != prompt
                or type(row.get("model_prompt_tokens")) is not int
                or row["model_prompt_tokens"] != tokenizer.count_tokens(prompt)
            ):
                raise ValueError("saved prompt text or token count mismatch")
            if row["method"] == "metadata_matched":
                source = {item.id: item.content for item in shared.items}
                if any(source.get(item.id) != item.content for item in selected):
                    raise ValueError("metadata-matched selector violated unchanged-text rule")
    expected_classes = classify(rows)
    for actual, derived in zip(rows, expected_classes, strict=True):
        if (
            actual["outcome_class"] != derived["outcome_class"]
            or actual["feasibility_witness"] != derived["feasibility_witness"]
        ):
            raise ValueError("failure class or feasibility witness mismatch")
    metrics = aggregate(rows)
    if bundle.metrics != metrics or bundle.report != report(metrics, mode):
        raise ValueError("saved aggregate metrics or report mismatch")
    expected_csv = [
        {
            key: "" if value is None else str(value)
            for key, value in cell.items()
            if key not in ("outcome_classes", "no_context_reasons")
        }
        for summary in [metrics["overall"], *metrics["families"].values()]
        for cell in summary["cells"]
    ]
    if bundle.metric_rows != expected_csv or bundle.config["disagreements"] != disagreements(rows):
        raise ValueError("derived CSV or disagreement evidence mismatch")
    return {
        "audit_version": "week2-offline-v1",
        "mode": mode,
        "seal_verified": evidence["seal_verified"],
        "checked_evaluations": len(rows),
        "status": "passed",
        "selectors_rerun": False,
        "outcome_counts": dict(Counter(row["outcome_class"] for row in rows)),
    }
