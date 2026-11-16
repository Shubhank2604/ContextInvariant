"""Synthetic-only end-to-end and corruption tests for the locked offline command."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from context_invariant import ContextItem, ContextOptimizer, OptimizationPolicy
from context_invariant.benchmarks.bundles import load_benchmark_bundle
from context_invariant.benchmarks.week1 import runner as week1
from context_invariant.benchmarks.week1.baseline import MetadataMatchedSelector
from context_invariant.benchmarks.week1.models import StudyCase, StudyInputs
from context_invariant.benchmarks.week2 import preflight as checks
from context_invariant.benchmarks.week2.audit import audit_evaluation
from context_invariant.benchmarks.week2.models import FAMILIES, ExecutionFreeze
from context_invariant.benchmarks.week2.preflight import canonical, json_bytes, preflight, sha
from context_invariant.benchmarks.week2.runner import run_evaluation
from context_invariant.benchmarks.week2.synthetic import write_synthetic
from context_invariant.tokenization import TiktokenTokenizer, Tokenizer
from context_invariant.trace import OptimizedContext


@pytest.fixture(scope="module")
def development(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, Path, Path]:
    root = tmp_path_factory.mktemp("week2-development")
    write_synthetic(root)
    inputs, keys, freeze = root / "cases.json", root / "keys.json", root / "freeze.json"
    freeze.write_bytes(json_bytes(checks.make_freeze().model_dump(mode="json")))
    bundle = run_evaluation(inputs, keys, freeze, root / "results", mode="synthetic_development")
    return inputs, keys, freeze, bundle


def copy_fixture(
    development: tuple[Path, Path, Path, Path], target: Path
) -> tuple[Path, Path, Path, Path]:
    inputs, keys, freeze, bundle = development
    for file in (inputs, keys, freeze):
        shutil.copyfile(file, target / file.name)
    result = Path(shutil.copytree(bundle, target / "bundle"))
    return target / inputs.name, target / keys.name, target / freeze.name, result


def signed_protocol_fixture(
    inputs: Path,
    keys: Path,
    freeze: Path,
    target: Path,
    **changes: Any,
) -> dict[str, Any]:
    """Ephemeral test signature only. Data stay synthetic, so final execution must reject them."""
    frozen = ExecutionFreeze.model_validate_json(freeze.read_bytes())
    rows = json.loads(inputs.read_bytes())
    manifest = {
        "schema_version": "week2-offline-seal-v1",
        "status": "sealed_final",
        "author": "TEST ONLY, not a final-case author",
        "reviewers": ["TEST ONLY"],
        "data_steward": "TEST ONLY, not a real attestation",
        "authorship_description": "independently_authored",
        "provenance_and_permissions_review": "test rejection path",
        "review_disagreements_and_resolutions": "test rejection path",
        "access_log_reference": "temporary test fixture",
        "case_counts_by_family": {family: 10 for family in FAMILIES},
        "realistic_trace_case_ids": [row["id"] for row in rows[:15]],
        "input_file_sha256": sha(inputs.read_bytes()),
        "key_file_sha256": sha(keys.read_bytes()),
        "canonical_input_json_sha256": canonical(rows),
        "canonical_key_json_sha256": canonical(json.loads(keys.read_bytes())),
        "study_lock_sha256": frozen.study_lock_sha256,
        "execution_freeze_sha256": sha(freeze.read_bytes()),
        "analysis_plan_sha256": frozen.analysis_plan_sha256,
        "configuration_sha256": frozen.configuration_sha256,
        "method_freeze_timestamp_utc": frozen.created_at_utc.isoformat(),
        "sealed_at_utc": datetime.now(UTC).isoformat(),
        **changes,
    }
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    seal_path, signature_path, key_path = (
        target / "test-seal.json",
        target / "test-seal.sig",
        target / "test-public.pem",
    )
    raw = json_bytes(manifest)
    seal_path.write_bytes(raw)
    signature_path.write_bytes(key.sign(raw))
    key_path.write_bytes(public)
    return {
        "seal_path": seal_path,
        "signature_path": signature_path,
        "public_key_path": key_path,
        "trusted_key_sha256": sha(public),
    }


def test_complete_development_grid_and_read_only_audit(
    development: tuple[Path, Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs, keys, freeze, path = development
    bundle = load_benchmark_bundle(path)
    assert len(bundle.predictions) == 180
    assert bundle.metrics["evaluation_count"] == 180
    assert all(
        cell["total"] == 10
        for family in bundle.metrics["families"].values()
        for cell in family["cells"]
    )
    assert bundle.config["preflight"]["seal_verified"] is False
    assert bundle.config["mode"] == "synthetic_development"
    failures = [row for row in bundle.predictions if row["outcome"] == "no_context"]
    assert failures
    assert all(
        row["context_tokens"] is None and row["context_reduction"] is None for row in failures
    )
    assert any(row["outcome_class"] == "certified_infeasibility" for row in failures)
    assert any(
        row["outcome_class"] == "avoidable_selection_failure"
        and row["feasibility_witness"]["context_tokens"] == 30
        for row in failures
    )
    monkeypatch.setattr(
        week1, "execute_method", lambda *args, **kwargs: pytest.fail("audit reran a method")
    )
    assert (
        audit_evaluation(path, inputs, keys, freeze, mode="synthetic_development")[
            "checked_evaluations"
        ]
        == 180
    )


@pytest.mark.parametrize(
    "corruption", ["missing", "duplicate", "prompt", "outcome", "certificate", "witness", "family"]
)
def test_audit_rejects_corrupted_result_rows(
    development: tuple[Path, Path, Path, Path], tmp_path: Path, corruption: str
) -> None:
    inputs, keys, freeze, path = copy_fixture(development, tmp_path)
    rows = [json.loads(line) for line in (path / "predictions.jsonl").read_text().splitlines()]
    if corruption == "missing":
        rows.pop()
    elif corruption == "duplicate":
        rows[-1] = rows[0]
    elif corruption == "prompt":
        rows[0].update(model_prompt="scoring-key substitution", model_prompt_tokens=0)
    elif corruption == "outcome":
        rows[0]["outcome"] = "invalid_context"
    elif corruption == "certificate":
        rows[0]["required_certificate"]["lower_bound_tokens"] = 0
    elif corruption == "witness":
        row = next(row for row in rows if row["feasibility_witness"] is not None)
        row["feasibility_witness"]["context_tokens"] = 0
    else:
        rows[0]["family"] = "operations"
    (path / "predictions.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )
    with pytest.raises(ValueError):
        audit_evaluation(path, inputs, keys, freeze, mode="synthetic_development")


@pytest.mark.parametrize("changed", ["cases", "keys"])
def test_signed_preflight_rejects_changed_files_before_selection(
    development: tuple[Path, Path, Path, Path],
    tmp_path: Path,
    changed: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs, keys, freeze, _ = copy_fixture(development, tmp_path)
    evidence = signed_protocol_fixture(inputs, keys, freeze, tmp_path)
    path = inputs if changed == "cases" else keys
    path.write_bytes(path.read_bytes() + b"\n")
    monkeypatch.setattr(
        week1, "execute_method", lambda *args, **kwargs: pytest.fail("preflight ran a method")
    )
    with pytest.raises(ValueError, match="file_sha256 mismatch"):
        run_evaluation(inputs, keys, freeze, tmp_path / "rejected", mode="sealed_final", **evidence)
    assert not (tmp_path / "rejected").exists()


@pytest.mark.parametrize(
    "corruption", ["signature", "key", "unsigned", "blank-review", "timestamp"]
)
def test_invalid_or_missing_steward_evidence_is_rejected(
    development: tuple[Path, Path, Path, Path], tmp_path: Path, corruption: str
) -> None:
    inputs, keys, freeze, _ = copy_fixture(development, tmp_path)
    changes: dict[str, Any] = {}
    if corruption == "blank-review":
        changes["reviewers"] = []
    if corruption == "timestamp":
        changes["sealed_at_utc"] = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    evidence = signed_protocol_fixture(inputs, keys, freeze, tmp_path, **changes)
    if corruption == "signature":
        evidence["signature_path"].write_bytes(b"invalid")
    elif corruption == "key":
        evidence["trusted_key_sha256"] = "0" * 64
    elif corruption == "unsigned":
        evidence = {}
    with pytest.raises(ValueError):
        preflight(inputs, keys, freeze, mode="sealed_final", **evidence)


def test_authenticated_synthetic_data_still_cannot_be_run_as_final(
    development: tuple[Path, Path, Path, Path], tmp_path: Path
) -> None:
    inputs, keys, freeze, _ = copy_fixture(development, tmp_path)
    evidence = signed_protocol_fixture(inputs, keys, freeze, tmp_path)
    with pytest.raises(ValueError, match="must not be mixed"):
        preflight(inputs, keys, freeze, mode="sealed_final", **evidence)
    with pytest.raises(ValueError, match="cannot supply"):
        preflight(inputs, keys, freeze, mode="synthetic_development", **evidence)


@pytest.mark.parametrize("corruption", ["configuration", "source", "analysis", "dependencies"])
def test_frozen_execution_evidence_must_match(
    development: tuple[Path, Path, Path, Path], tmp_path: Path, corruption: str
) -> None:
    inputs, keys, freeze, _ = copy_fixture(development, tmp_path)
    value = json.loads(freeze.read_bytes())
    if corruption == "configuration":
        value["configuration_sha256"] = "0" * 64
    elif corruption == "source":
        value["files"]["src/context_invariant/optimizer.py"] = "0" * 64
    elif corruption == "analysis":
        value["analysis_plan_sha256"] = "0" * 64
    else:
        value["dependencies"]["numpy"] = "not-the-frozen-version"
    freeze.write_bytes(json_bytes(value))
    with pytest.raises(ValueError):
        preflight(inputs, keys, freeze, mode="synthetic_development")


@pytest.mark.parametrize("corruption", ["family", "key-correspondence", "hidden-exclusion"])
def test_preflight_requires_family_counts_and_matching_keys(
    development: tuple[Path, Path, Path, Path], tmp_path: Path, corruption: str
) -> None:
    inputs, keys, freeze, _ = copy_fixture(development, tmp_path)
    if corruption == "family":
        data = json.loads(inputs.read_bytes())
        data[0]["family"] = "operations"
        inputs.write_bytes(json_bytes(data))
    elif corruption == "key-correspondence":
        labels = json.loads(keys.read_bytes())
        del labels[next(iter(labels))]
        keys.write_bytes(json_bytes(labels))
    else:
        labels = json.loads(keys.read_bytes())
        labels[next(iter(labels))]["forbidden_ids"] = ["release"]
        keys.write_bytes(json_bytes(labels))
    with pytest.raises(ValueError):
        preflight(inputs, keys, freeze, mode="synthetic_development")


def test_week1_entry_point_remains_limited_to_ten_cases(
    development: tuple[Path, Path, Path, Path], tmp_path: Path
) -> None:
    cases, labels = checks.load_data(
        development[0].read_bytes(), development[1].read_bytes(), "synthetic_development"
    )
    inputs, keys = tmp_path / "week1-inputs.json", tmp_path / "week1-keys.json"
    inputs.write_bytes(
        json_bytes(
            [{"id": case.id, "inputs": case.inputs.model_dump(mode="json")} for case in cases]
        )
    )
    keys.write_bytes(
        json_bytes({key: value.model_dump(mode="json") for key, value in labels.items()})
    )
    with pytest.raises(ValueError, match="exactly ten"):
        week1.run_study(inputs, keys, tmp_path / "not-a-pilot")


def test_cli_preflight_and_audit_are_read_only(development: tuple[Path, Path, Path, Path]) -> None:
    inputs, keys, freeze, bundle = development
    for command, extra in (("preflight", []), ("audit", ["--bundle", str(bundle)])):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "context_invariant.benchmarks.week2",
                command,
                "--synthetic",
                "--inputs",
                str(inputs),
                "--keys",
                str(keys),
                "--freeze",
                str(freeze),
                *extra,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["status"] == "passed"


def test_actual_selector_calls_share_records_policy_and_tokenizer_without_keys(
    development: tuple[Path, Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases, labels = checks.load_data(
        development[0].read_bytes(), development[1].read_bytes(), "synthetic_development"
    )
    case = next(case for case in cases if case.id.endswith("diagnostic-log"))
    secret = "SCORING_KEY_SENTINEL_MUST_NEVER_REACH_SELECTORS_OR_PROMPTS"
    label = labels[case.id].model_copy(update={"purpose": secret})
    observed: list[tuple[object, ...]] = []
    original_full = ContextOptimizer.optimize
    original_baseline = MetadataMatchedSelector.optimize

    def full(
        self: ContextOptimizer, task: str, items: Sequence[ContextItem], policy: OptimizationPolicy
    ) -> OptimizedContext:
        observed.append(
            (id(items), id(policy), id(self._tokenizer), task, self._edges, self._constraint_policy)
        )
        assert secret not in task and all(secret not in item.content for item in items)
        return original_full(self, task, items, policy)

    def baseline(
        self: MetadataMatchedSelector,
        inputs: StudyInputs,
        policy: OptimizationPolicy,
        tokenizer: Tokenizer,
    ) -> OptimizedContext:
        observed.append(
            (
                id(inputs.items),
                id(policy),
                id(tokenizer),
                inputs.task,
                inputs.edges,
                inputs.constraint_policy,
            )
        )
        assert secret not in inputs.model_dump_json()
        return original_baseline(self, inputs, policy, tokenizer)

    monkeypatch.setattr(ContextOptimizer, "optimize", full)
    monkeypatch.setattr(MetadataMatchedSelector, "optimize", baseline)
    tokenizer = TiktokenTokenizer()
    for percentage in (65, 80, 100):
        rows = week1.run_pair(
            StudyCase(id=case.id, inputs=case.inputs), label, percentage, tokenizer
        )
        assert len(rows) == 2
    assert len(observed) == 6
    assert all(observed[index] == observed[index + 1] for index in range(0, 6, 2))
