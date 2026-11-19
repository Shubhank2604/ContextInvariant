"""Developer-curated amendment checks using public synthetic data only."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from context_invariant.benchmarks.bundles import load_benchmark_bundle
from context_invariant.benchmarks.week1 import runner as week1
from context_invariant.benchmarks.week2 import preflight as checks
from context_invariant.benchmarks.week2.audit import audit_evaluation
from context_invariant.benchmarks.week2.curation import AMENDMENT_PATH, REVIEW_ARRANGEMENT
from context_invariant.benchmarks.week2.models import FAMILIES
from context_invariant.benchmarks.week2.runner import run_evaluation
from context_invariant.benchmarks.week2.synthetic import write_synthetic


def stable_trace_values(value: Any) -> Any:
    """Normalize diagnostic score rounding across Python/NumPy versions."""
    if isinstance(value, float):
        return round(value, 12)
    if isinstance(value, dict):
        return {key: stable_trace_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [stable_trace_values(item) for item in value]
    return value


def synthetic_record(inputs: Path, keys: Path, freeze: Path) -> dict[str, Any]:
    frozen = json.loads(freeze.read_bytes())
    return {
        "schema_version": "week2-developer-curated-v1",
        "mode": "developer_curated_development",
        "review_arrangement": REVIEW_ARRANGEMENT,
        "independent_human_review": False,
        "independent_human_reviewers": [],
        "authors": ["SYNTHETIC TEST FIXTURE, not a dataset author"],
        "ai_assistance": "SYNTHETIC TEST ONLY; no actual dataset preparation claim",
        "provenance_and_permissions": "Public development fixtures; not eligible real traces",
        "cross_checks_and_inclusion_decisions": "TEST ONLY; not human inclusion decisions",
        "access_history": [
            {
                "actor": "TEST FIXTURE",
                "action": "synthetic fixture creation",
                "at_utc": frozen["created_at_utc"],
            }
        ],
        "approval_status": "synthetic_test_only",
        "approved_by": "TEST FIXTURE; not Shubhank Chandak's approval",
        "approved_at_utc": datetime.now(UTC).isoformat(),
        "approval_reference": "SYNTHETIC TEST ONLY; no real approval",
        "case_counts_by_family": {family: 10 for family in FAMILIES},
        "realistic_trace_case_ids": [],
        "input_file_sha256": checks.sha(inputs.read_bytes()),
        "key_file_sha256": checks.sha(keys.read_bytes()),
        "canonical_input_json_sha256": checks.canonical(json.loads(inputs.read_bytes())),
        "canonical_key_json_sha256": checks.canonical(json.loads(keys.read_bytes())),
        "study_lock_sha256": frozen["study_lock_sha256"],
        "execution_freeze_sha256": checks.sha(freeze.read_bytes()),
        "analysis_plan_sha256": frozen["analysis_plan_sha256"],
        "configuration_sha256": frozen["configuration_sha256"],
        "amendment_sha256": frozen["files"][AMENDMENT_PATH],
        "method_freeze_timestamp_utc": frozen["created_at_utc"],
    }


@pytest.fixture(scope="module")
def curated(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, Path, Path, Path]:
    root = tmp_path_factory.mktemp("curated-synthetic-only")
    write_synthetic(root, developer_curated=True)
    inputs, keys, freeze = (root / name for name in ("cases.json", "keys.json", "freeze.json"))
    freeze.write_bytes(checks.json_bytes(checks.make_freeze().model_dump(mode="json")))
    record = root / "SYNTHETIC-TEST-ONLY.json"
    record.write_bytes(checks.json_bytes(synthetic_record(inputs, keys, freeze)))
    bundle = run_evaluation(
        inputs,
        keys,
        freeze,
        root / "results",
        mode="developer_curated_development",
        curation_path=record,
    )
    return inputs, keys, freeze, record, bundle


def test_curated_synthetic_grid_has_same_scientific_results_and_read_only_audit(
    curated: tuple[Path, Path, Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs, keys, freeze, record, bundle = curated
    observed = load_benchmark_bundle(bundle)
    old = load_benchmark_bundle(
        checks.ROOT / "research/week2/synthetic/evidence/"
        "20261116T082640.842497Z-week2-synthetic-dry-run-development"
    )
    assert observed.metrics == old.metrics
    for current, previous in zip(observed.predictions, old.predictions, strict=True):
        current, previous = dict(current), dict(previous)
        for row in (current, previous):
            row.pop("data_kind")
            if row["trace"] is not None:
                row["trace"] = dict(row["trace"])
                row["trace"].pop("stage_timings_ms")
            # Keep exact assertions for selected text, prompts, tokens and metrics.
            for field in ("trace", "method_metadata"):
                row[field] = stable_trace_values(row.get(field))
        assert current == previous
    assert REVIEW_ARRANGEMENT in observed.report
    assert "NOT FINAL EVIDENCE" in observed.report
    monkeypatch.setattr(
        week1, "execute_method", lambda *a, **kw: pytest.fail("audit executed a method")
    )
    result = audit_evaluation(
        bundle,
        inputs,
        keys,
        freeze,
        mode="developer_curated_development",
        curation_path=record,
    )
    assert result["checked_evaluations"] == 180
    assert result["status"] == "passed"
    assert result["seal_verified"] is False
    assert result["independent_human_review"] is False
    assert result["developer_approval_recorded"] is False


@pytest.mark.parametrize(
    "field",
    [
        "input_file_sha256",
        "key_file_sha256",
        "canonical_input_json_sha256",
        "canonical_key_json_sha256",
        "study_lock_sha256",
        "execution_freeze_sha256",
        "analysis_plan_sha256",
        "configuration_sha256",
        "amendment_sha256",
        "independent_human_review",
        "independent_human_reviewers",
        "approval_status",
        "authors",
        "ai_assistance",
        "access_history",
        "approved_at_utc",
        "method_freeze_timestamp_utc",
        "approval_reference",
        "case_counts_by_family",
        "realistic_trace_case_ids",
        "mode",
    ],
)
def test_curated_record_rejects_missing_or_changed_evidence_before_selection(
    curated: tuple[Path, Path, Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    inputs, keys, freeze, record, _ = curated
    value = json.loads(record.read_bytes())
    changes: dict[str, Any] = {
        "independent_human_review": True,
        "independent_human_reviewers": ["invented reviewer"],
        "approval_status": "approved",
        "authors": [],
        "ai_assistance": " ",
        "access_history": [],
        "approved_at_utc": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "method_freeze_timestamp_utc": datetime.now(UTC).isoformat(),
        "approval_reference": "",
        "case_counts_by_family": {family: 9 for family in FAMILIES},
        "realistic_trace_case_ids": ["not a real trace"],
        "mode": "developer_curated",
    }
    value[field] = changes.get(field, "0" * 64)
    changed = tmp_path / "changed-record.json"
    changed.write_bytes(checks.json_bytes(value))
    monkeypatch.setattr(
        week1, "execute_method", lambda *a, **kw: pytest.fail("selection preceded preflight")
    )
    output = tmp_path / "must-not-exist"
    with pytest.raises(ValueError):
        run_evaluation(
            inputs,
            keys,
            freeze,
            output,
            mode="developer_curated_development",
            curation_path=changed,
        )
    assert not output.exists()


@pytest.mark.parametrize(
    "target", ["cases", "keys", "record", "missing-row", "duplicate-row", "prompt"]
)
def test_curated_audit_rejects_tampering(
    curated: tuple[Path, Path, Path, Path, Path],
    tmp_path: Path,
    target: str,
) -> None:
    inputs, keys, freeze, record, bundle = curated
    if target in ("cases", "keys", "record"):
        source = {"cases": inputs, "keys": keys, "record": record}[target]
        changed = tmp_path / source.name
        changed.write_bytes(source.read_bytes() + b"\n")
        if target == "cases":
            inputs = changed
        elif target == "keys":
            keys = changed
        else:
            record = changed
    else:
        bundle = Path(shutil.copytree(bundle, tmp_path / "bundle"))
        predictions = bundle / "predictions.jsonl"
        rows = [json.loads(line) for line in predictions.read_text().splitlines()]
        if target == "missing-row":
            rows.pop()
        elif target == "duplicate-row":
            rows.append(rows[0])
        else:
            next(row for row in rows if "model_prompt" in row)["model_prompt"] = "unrelated"
        predictions.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        audit_evaluation(
            bundle, inputs, keys, freeze, mode="developer_curated_development", curation_path=record
        )


def test_modes_cannot_mix_or_claim_synthetic_approval_as_final(
    curated: tuple[Path, Path, Path, Path, Path],
) -> None:
    inputs, keys, freeze, record, _ = curated
    with pytest.raises(ValueError, match="requires a completed"):
        checks.preflight(inputs, keys, freeze, mode="developer_curated_development")
    with pytest.raises(ValueError, match="explicit developer-curated"):
        checks.preflight(inputs, keys, freeze, mode="synthetic_development", curation_path=record)
    with pytest.raises(ValueError, match="independent seal"):
        checks.preflight(
            inputs,
            keys,
            freeze,
            mode="developer_curated_development",
            curation_path=record,
            trusted_key_sha256="0" * 64,
        )
    with pytest.raises(ValueError):
        checks.preflight(inputs, keys, freeze, mode="developer_curated", curation_path=record)
    with pytest.raises(ValueError, match="sealed runs require"):
        checks.preflight(inputs, keys, freeze, mode="sealed_final")


def test_curated_cli_preflight_and_read_only_audit(
    curated: tuple[Path, Path, Path, Path, Path],
) -> None:
    inputs, keys, freeze, record, bundle = curated
    for command, extra in (("preflight", []), ("audit", ["--bundle", str(bundle)])):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "context_invariant.benchmarks.week2",
                command,
                "--developer-curated",
                "--synthetic",
                "--inputs",
                str(inputs),
                "--keys",
                str(keys),
                "--freeze",
                str(freeze),
                "--curation-record",
                str(record),
                *extra,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        summary = json.loads(result.stdout)
        assert summary["mode"] == "developer_curated_development"
        assert summary["seal_verified"] is False
        assert summary["independent_human_review"] is False
