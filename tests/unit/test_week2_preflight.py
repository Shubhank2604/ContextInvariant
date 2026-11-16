"""Regression checks for input-grounded exclusions and saved replay prompt integrity."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from context_invariant import ConflictOverride, ConflictPolicy, ConstraintPolicy, OptimizationPolicy
from context_invariant.benchmarks.week1.audit import audit_bundle
from context_invariant.benchmarks.week1.evaluator import evaluate_output, validate_labels
from context_invariant.benchmarks.week1.models import SpanCheck, StudyInputs
from context_invariant.models import DependencyRelation
from tests.unit.test_week1_study import WordTokenizer, checklist, item, relation

ROOT = Path(__file__).parents[2]
STUDY = ROOT / "research/week1"
PILOT = STUDY / "evidence/20261116T051053.178379Z-metadata-matched-pilot-development"
REPLAY = STUDY / "evidence/20261116T051053.904393Z-week1-replay-development"


@pytest.mark.parametrize("entry_point", ["validate_labels", "evaluate_output"])
def test_checklist_only_prohibition_is_rejected(entry_point: str) -> None:
    inputs = StudyInputs(task="review", items=(item("optional", "legal useful evidence"),))
    labels = checklist(forbidden_ids=("optional",))
    with pytest.raises(ValueError, match="declared exclusion"):
        if entry_point == "validate_labels":
            validate_labels(inputs, labels)
        else:
            evaluate_output(
                inputs,
                labels,
                inputs.items,
                OptimizationPolicy(max_input_tokens=10),
                WordTokenizer(),
            )


@pytest.mark.parametrize("retain", [False, True])
def test_supersession_exclusion_respects_the_supplied_policy(retain: bool) -> None:
    inputs = StudyInputs(
        task="current state",
        items=(item("new", "current state"), item("old", "earlier state")),
        edges=(relation("new", "old", DependencyRelation.SUPERSEDES),),
        constraint_policy=ConstraintPolicy.enforced(retain_superseded=retain),
    )
    labels = checklist(forbidden_ids=("old",))
    if retain:
        with pytest.raises(ValueError, match="declared exclusion"):
            validate_labels(inputs, labels)
    else:
        validate_labels(inputs, labels)
        evaluation = evaluate_output(
            inputs,
            checklist(),
            [inputs.items[1]],
            OptimizationPolicy(max_input_tokens=10),
            WordTokenizer(),
        )
        assert evaluation["outcome"] == "invalid_context"
        assert "stale_record:old" in evaluation["violations"]


@pytest.mark.parametrize("override", [False, True])
def test_conflict_exclusion_follows_declared_authority_or_override(override: bool) -> None:
    inputs = StudyInputs(
        task="authoritative state",
        items=(item("canonical", "approved state", canonical=True), item("other", "other state")),
        edges=(relation("canonical", "other", DependencyRelation.CONTRADICTS),),
        constraint_policy=ConstraintPolicy.enforced(
            conflict_overrides=(
                ConflictOverride(
                    left_item_id="canonical", right_item_id="other", winner_item_id="other"
                ),
            )
            if override
            else (),
        ),
    )
    winner, loser = ("other", "canonical") if override else ("canonical", "other")
    validate_labels(inputs, checklist(forbidden_ids=(loser,)))
    with pytest.raises(ValueError, match="declared exclusion"):
        validate_labels(inputs, checklist(forbidden_ids=(winner,)))


@pytest.mark.parametrize("policy", [ConflictPolicy.ERROR, ConflictPolicy.RETAIN_BOTH])
def test_ambiguous_conflict_does_not_justify_a_hidden_winner(policy: ConflictPolicy) -> None:
    inputs = StudyInputs(
        task="state",
        items=(item("a", "first state"), item("b", "other state")),
        edges=(relation("a", "b", DependencyRelation.CONTRADICTS),),
        constraint_policy=ConstraintPolicy.enforced(conflict_policy=policy),
    )
    for item_id in ("a", "b"):
        with pytest.raises(ValueError, match="declared exclusion"):
            validate_labels(inputs, checklist(forbidden_ids=(item_id,)))


def test_optional_usefulness_changes_score_without_changing_legality() -> None:
    inputs = StudyInputs(task="review", items=(item("optional", "useful evidence"),))
    labels = checklist(useful_spans=(SpanCheck(item_id="optional", text="useful evidence"),))
    policy = OptimizationPolicy(max_input_tokens=10)
    retained = evaluate_output(inputs, labels, inputs.items, policy, WordTokenizer())
    omitted = evaluate_output(inputs, labels, [], policy, WordTokenizer())
    assert retained["outcome"] == omitted["outcome"] == "valid_context"
    assert retained["useful_recall"] == 1.0 and omitted["useful_recall"] == 0.0


def _rewrite_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    (path / "predictions.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("model_prompt", "unrelated replacement text"),
        ("model_prompt_tokens", 0),
        ("model_prompt_tokens", True),
        ("model_prompt", None),
        ("model_prompt_tokens", None),
    ],
)
def test_replay_auditor_rejects_changed_or_missing_prompt_fields(
    tmp_path: Path, field: str, value: str | int | bool | None
) -> None:
    path = Path(shutil.copytree(REPLAY, tmp_path / "replay"))
    rows = [json.loads(line) for line in (path / "predictions.jsonl").read_text().splitlines()]
    row = next(row for row in rows if row["outcome"] == "valid_context")
    if value is None:
        del row[field]
    else:
        row[field] = value
    _rewrite_rows(path, rows)
    with pytest.raises(ValueError, match="prompt"):
        audit_bundle(path, STUDY / "inputs/replay.json", STUDY / "inputs/replay-checklists.json")


def test_replay_auditor_rejects_the_two_field_prompt_corruption(tmp_path: Path) -> None:
    path = Path(shutil.copytree(REPLAY, tmp_path / "replay"))
    rows = [json.loads(line) for line in (path / "predictions.jsonl").read_text().splitlines()]
    rows[0].update(model_prompt="unrelated text", model_prompt_tokens=0)
    _rewrite_rows(path, rows)
    with pytest.raises(ValueError, match="prompt"):
        audit_bundle(path, STUDY / "inputs/replay.json", STUDY / "inputs/replay-checklists.json")


@pytest.mark.parametrize("replay", [False, True])
@pytest.mark.parametrize("field", ["model_prompt", "model_prompt_tokens"])
def test_no_context_row_cannot_contain_either_prompt_field(
    tmp_path: Path, replay: bool, field: str
) -> None:
    path = Path(shutil.copytree(REPLAY if replay else PILOT, tmp_path / "bundle"))
    rows = [json.loads(line) for line in (path / "predictions.jsonl").read_text().splitlines()]
    row = next(row for row in rows if row["outcome"] == "no_context")
    row[field] = None
    _rewrite_rows(path, rows)
    prefix = "replay" if replay else "pilot"
    label_file = "replay-checklists.json" if replay else "checklists.json"
    with pytest.raises(ValueError, match="prompt"):
        audit_bundle(path, STUDY / f"inputs/{prefix}.json", STUDY / "inputs" / label_file)


def test_unchanged_recorded_pilot_and_replay_pass_the_stricter_auditor() -> None:
    pilot = audit_bundle(PILOT, STUDY / "inputs/pilot.json", STUDY / "inputs/checklists.json")
    replay = audit_bundle(
        REPLAY, STUDY / "inputs/replay.json", STUDY / "inputs/replay-checklists.json"
    )
    assert pilot["checked_evaluations"] == 60
    assert replay["checked_evaluations"] == 8
    assert replay["saved_replay_prompts"] == "passed"
