"""Focused checks for the matched selector and independent outcome accounting."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from context_invariant import (
    ConstraintPolicy,
    ContextEdge,
    ContextItem,
    ContextType,
    DependencyReferenceRequirement,
    DependencyRelation,
    OptimizationPolicy,
    PreservationContract,
    RetentionPolicy,
)
from context_invariant.benchmarks.bundles import load_benchmark_bundle
from context_invariant.benchmarks.week1.baseline import MetadataMatchedSelector
from context_invariant.benchmarks.week1.evaluator import (
    evaluate_failure,
    evaluate_output,
    required_certificate,
    validate_labels,
)
from context_invariant.benchmarks.week1.models import (
    Checklist,
    SpanCheck,
    StudyCase,
    StudyInputs,
    content_hash,
    prepare_inputs,
    study_policy,
)
from context_invariant.benchmarks.week1.runner import (
    disagreements,
    load_cases,
    run_pair,
    run_study,
    summarize,
)
from context_invariant.errors import RequiredContextOverflow

ROOT = Path(__file__).parents[2]
NOW = datetime(2026, 11, 15, tzinfo=UTC)


class WordTokenizer:
    def count_tokens(self, text: str) -> int:
        return len(text.split())


def item(
    item_id: str, text: str, *, required: bool = False, canonical: bool = False
) -> ContextItem:
    return ContextItem(
        id=item_id,
        content=text,
        type=ContextType.MEMORY,
        created_at=NOW,
        updated_at=NOW,
        contract=PreservationContract(
            retention=RetentionPolicy.REQUIRED if required else RetentionPolicy.OPTIONAL
        ),
        metadata={"canonical": canonical},
    )


def relation(source: str, target: str, kind: DependencyRelation) -> ContextEdge:
    return ContextEdge(source_id=source, target_id=target, relation=kind, weight=1.0)


def checklist(*required: str, **kwargs: object) -> Checklist:
    return Checklist.model_validate(
        {
            "purpose": "test",
            "required": "test",
            "optional": "test",
            "failure": "test",
            "required_ids": required,
            **kwargs,
        }
    )


@pytest.mark.parametrize("budget", [5, 6])
def test_baseline_retains_required_chain_at_and_above_exact_boundary(budget: int) -> None:
    inputs = StudyInputs(
        task="irrelevant ranking",
        items=(item("a", "keep root", required=True), item("b", "keep support"), item("c", "leaf")),
        edges=(
            relation("a", "b", DependencyRelation.REQUIRES),
            relation("b", "c", DependencyRelation.REQUIRES),
        ),
    )
    before = content_hash(inputs)
    result = MetadataMatchedSelector().optimize(
        inputs, OptimizationPolicy(max_input_tokens=budget), WordTokenizer()
    )
    assert {value.id for value in result.selected_items} == {"a", "b", "c"}
    assert result.final_token_count == 5
    assert content_hash(inputs) == before
    assert [value.content for value in result.selected_items] == [
        value.content for value in inputs.items
    ]


def test_baseline_skips_expensive_optional_bundle_and_tries_next_candidate() -> None:
    inputs = StudyInputs(
        task="retry",
        items=(
            item("root", "policy", required=True),
            item("lead", "retry"),
            item("support", "irrelevant telemetry that is much too large"),
            item("alternative", "retry evidence"),
        ),
        edges=(relation("lead", "support", DependencyRelation.REQUIRES),),
    )
    result = MetadataMatchedSelector().optimize(
        inputs, OptimizationPolicy(max_input_tokens=3), WordTokenizer()
    )
    assert {value.id for value in result.selected_items} == {"root", "alternative"}
    assert result.metadata["bundle_decisions"][0]["decision"] == "skipped_bundle_over_budget"


@pytest.mark.parametrize("kind", [DependencyRelation.SUPERSEDES, DependencyRelation.CONTRADICTS])
def test_baseline_resolves_stale_state_and_authority_conflicts(kind: DependencyRelation) -> None:
    inputs = StudyInputs(
        task="old state",
        items=(item("new", "current state", canonical=True), item("old", "old state")),
        edges=(relation("new", "old", kind),),
    )
    result = MetadataMatchedSelector().optimize(
        inputs, OptimizationPolicy(max_input_tokens=20), WordTokenizer()
    )
    assert [value.id for value in result.selected_items] == ["new"]


def test_evaluator_detects_missing_requirement_as_invalid_return_not_no_context() -> None:
    inputs = prepare_inputs(
        StudyInputs(task="t", items=(item("root", "keep root", required=True),)), WordTokenizer()
    )
    policy = OptimizationPolicy(max_input_tokens=1)
    evaluation = evaluate_output(inputs, checklist("root"), [], policy, WordTokenizer())
    assert evaluation["outcome"] == "invalid_context"
    assert "missing_required:root" in evaluation["violations"]
    certificate = required_certificate(inputs, policy, WordTokenizer())
    failure = evaluate_failure(
        RequiredContextOverflow(required_item_ids=("root",), required_tokens=2, effective_budget=1),
        certificate,
    )
    assert failure["outcome"] == "no_context"
    assert failure["failure_reason"] == "budget_infeasible"
    assert failure["context_tokens"] is None


def test_overflow_is_not_global_infeasibility_without_a_lossless_lower_bound() -> None:
    inputs = StudyInputs(task="t", items=(item("root", "small", required=True),))
    certificate = required_certificate(
        inputs, OptimizationPolicy(max_input_tokens=2), WordTokenizer()
    )
    error = RequiredContextOverflow(
        required_item_ids=("optional",), required_tokens=5, effective_budget=2
    )
    assert evaluate_failure(error, certificate)["failure_reason"] == "selection_failure"
    assert (
        evaluate_failure(RuntimeError("test error"), certificate)["failure_reason"]
        == "execution_error"
    )


def test_evaluator_checks_support_budget_protected_text_and_unknown_ids() -> None:
    inputs = prepare_inputs(
        StudyInputs(
            task="t",
            items=(item("root", "keep root", required=True), item("support", "support")),
            edges=(relation("root", "support", DependencyRelation.REQUIRES),),
        ),
        WordTokenizer(),
    )
    changed = inputs.items[0].model_copy(update={"content": "bad changed content"})
    evaluation = evaluate_output(
        inputs,
        checklist("root", "support"),
        [changed, item("unknown", "extra")],
        OptimizationPolicy(max_input_tokens=1),
        WordTokenizer(),
    )
    assert evaluation["outcome"] == "invalid_context"
    assert "budget_exceeded" in evaluation["violations"]
    assert "missing_support:root->support" in evaluation["violations"]
    assert "changed_lossless_record:root" in evaluation["violations"]
    assert "unknown_record:unknown" in evaluation["violations"]


def test_qualifier_is_declared_input_not_a_hidden_scoring_requirement() -> None:
    inputs = StudyInputs(
        task="threshold",
        items=(item("value", "30 ms only for warm cache"),),
        constraint_policy=ConstraintPolicy.enforced(
            dependency_references=(
                DependencyReferenceRequirement(
                    item_id="value", references=("only for warm cache",)
                ),
            )
        ),
    )
    labels = checklist(conditional_spans=(SpanCheck(item_id="value", text="only for warm cache"),))
    validate_labels(inputs, labels)
    changed = inputs.items[0].model_copy(update={"content": "30 ms"})
    result = evaluate_output(
        inputs, labels, [changed], OptimizationPolicy(max_input_tokens=30), WordTokenizer()
    )
    assert result["outcome"] == "invalid_context"
    assert any("missing_qualifier" in issue for issue in result["violations"])
    with pytest.raises(ValueError, match="declared literal"):
        validate_labels(
            inputs.model_copy(update={"constraint_policy": ConstraintPolicy.enforced()}), labels
        )


def test_pair_shares_inputs_and_accounting_without_turning_refusal_into_compression() -> None:
    case = StudyCase(
        id="failure",
        inputs=StudyInputs(task="t", items=(item("root", "keep all these four", required=True),)),
    )
    rows = run_pair(case, checklist("root"), 65, WordTokenizer())
    assert len({row["shared_inputs_sha256"] for row in rows}) == 1
    assert all(row["outcome"] == "no_context" for row in rows)
    assert all(row["context_tokens"] is None and row["context_reduction"] is None for row in rows)
    assert all(cell["mean_valid_context_tokens"] is None for cell in summarize(rows)["cells"])
    assert disagreements(rows) == []


def test_prespecified_ten_case_pilot_writes_all_sixty_raw_evaluations(tmp_path: Path) -> None:
    dataset = ROOT / "research/week1/inputs/pilot.json"
    labels_path = ROOT / "research/week1/inputs/checklists.json"
    cases, labels = load_cases(dataset, labels_path)
    assert len(cases) == 10
    assert all(labels[case.id].development_only for case in cases)
    path = run_study(dataset, labels_path, tmp_path)
    bundle = load_benchmark_bundle(path)
    assert len(bundle.predictions) == 60
    assert len(bundle.cases) == 10
    assert sum(cell["total"] for cell in bundle.metrics["cells"]) == 60
    assert all(row["inputs_unchanged"] for row in bundle.predictions)
    assert (
        len(
            {
                (row["case_id"], row["method"], row["budget_percentage"])
                for row in bundle.predictions
            }
        )
        == 60
    )
    boundary = [
        row
        for row in bundle.predictions
        if row["case_id"] == "exact-boundary" and row["budget_percentage"] == 65
    ]
    assert all(
        row["outcome"] == "valid_context" and row["context_tokens"] == 65 for row in boundary
    )
    assert any(row["failure_reason"] == "budget_infeasible" for row in bundle.predictions)


def test_budget_rounding_is_fixed_and_rejects_unspecified_budget() -> None:
    assert study_policy(101, 65).effective_budget == 65
    with pytest.raises(ValueError, match="65, 80, and 100"):
        study_policy(100, 50)
