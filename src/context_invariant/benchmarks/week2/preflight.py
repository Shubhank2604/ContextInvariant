"""Read-only source freeze, shared-data checks and detached steward authentication."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement

from context_invariant.benchmarks.week1.evaluator import validate_labels
from context_invariant.benchmarks.week1.models import Checklist, content_hash, study_policy
from context_invariant.benchmarks.week1.runner import METHODS
from context_invariant.benchmarks.week2.models import (
    FAMILIES,
    LOCK_SHA,
    ExecutionFreeze,
    Mode,
    Seal,
    Week2Case,
)
from context_invariant.errors import TokenizerError
from context_invariant.tokenization import TiktokenTokenizer

ROOT = Path(__file__).resolve().parents[4]
LOCK_PATH = "research/week2/study-lock.json"
EXTRA_FILES = (
    LOCK_PATH,
    "research/week2/analysis-plan.md",
    "research/week1/environment-requirements.txt",
    "pyproject.toml",
)
DEPENDENCIES = ("numpy", "pydantic", "tiktoken", "typer", "cryptography", "packaging")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def canonical(value: Any) -> str:
    return content_hash({"document": value})


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=root, check=False, capture_output=True)
    if result.returncode:
        raise ValueError("unable to verify frozen Git revision or source")
    return result.stdout


def git_files(root: Path, revision: str, names: list[str]) -> dict[str, bytes]:
    """Read immutable Git blobs in one process, including exact binary boundaries."""
    requests = "".join(f"{revision}:{name}\n" for name in names).encode()
    result = subprocess.run(
        ["git", "cat-file", "--batch"],
        input=requests,
        cwd=root,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        raise ValueError("unable to read frozen source blobs")
    position = 0
    blobs: dict[str, bytes] = {}
    for name in names:
        end = result.stdout.find(b"\n", position)
        header = result.stdout[position:end].split()
        if end < 0 or len(header) != 3 or header[1] != b"blob":
            raise ValueError(f"missing frozen source blob: {name}")
        size = int(header[2])
        position = end + 1
        blobs[name] = result.stdout[position : position + size]
        position += size
        if len(blobs[name]) != size or result.stdout[position : position + 1] != b"\n":
            raise ValueError("invalid frozen Git blob response")
        position += 1
    return blobs


def source_bytes(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n")


def locked_configuration(lock: dict[str, Any]) -> dict[str, Any]:
    policy = study_policy(100, 65).model_dump(mode="json")
    policy["max_input_tokens"] = "computed from each original context and budget percentage"
    if lock["full_policy"] != policy or lock["method_ids"] != list(METHODS):
        raise ValueError("locked methods or policy do not match the implemented comparison")
    if lock["budget_percentages"] != [65, 80, 100] or lock["case_count"] != 30:
        raise ValueError("unexpected locked grid")
    return {
        key: lock[key]
        for key in (
            "method_ids",
            "method_source_commit",
            "evaluator_and_auditor_source_commit",
            "case_count",
            "case_families",
            "minimum_realistic_trace_cases",
            "budget_percentages",
            "budget_formula",
            "tokenizer",
            "representation_rule",
            "full_policy",
        )
    }


def read_lock(root: Path) -> dict[str, Any]:
    raw = (root / LOCK_PATH).read_bytes()
    if sha(raw) != LOCK_SHA:
        raise ValueError("study lock differs from the prespecified 8253d0d document")
    lock: dict[str, Any] = json.loads(raw)
    locked_configuration(lock)
    for file_key, hash_key in (
        ("analysis_plan", "analysis_plan_sha256"),
        ("dependency_constraints", "dependency_constraints_sha256"),
    ):
        if sha((root / lock[file_key]).read_bytes()) != lock[hash_key]:
            raise ValueError(f"locked {file_key} hash mismatch")
    return lock


def verify_original_sources(root: Path, lock: dict[str, Any]) -> None:
    """Compare all original runtime modules to Git, not just the two selector files."""
    revision = lock["method_source_commit"]
    names = git(root, "ls-tree", "-r", "--name-only", revision, "--", "src").decode().splitlines()
    patched = {
        "src/context_invariant/benchmarks/week1/evaluator.py",
        "src/context_invariant/benchmarks/week1/audit.py",
    }
    for expected_revision, selected in (
        (revision, [name for name in names if name.endswith(".py") and name not in patched]),
        (lock["evaluator_and_auditor_source_commit"], sorted(patched)),
    ):
        for name, expected in git_files(root, expected_revision, selected).items():
            if source_bytes((root / name).read_bytes()) != source_bytes(expected):
                raise ValueError(f"frozen method/evaluator source mismatch: {name}")


def file_manifest(root: Path) -> dict[str, str]:
    paths = sorted(path.relative_to(root).as_posix() for path in (root / "src").rglob("*.py"))
    return {name: sha(source_bytes((root / name).read_bytes())) for name in [*paths, *EXTRA_FILES]}


def dependency_manifest() -> dict[str, str]:
    pending = list(DEPENDENCIES)
    versions = {"python": sys.version.split()[0]}
    while pending:
        distribution = importlib.metadata.distribution(pending.pop())
        name = str(distribution.metadata["Name"]).lower().replace("_", "-")
        if name in versions:
            continue
        versions[name] = distribution.version
        for declaration in distribution.requires or ():
            requirement = Requirement(declaration)
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                pending.append(requirement.name)
    return dict(sorted(versions.items()))


def make_freeze(root: Path = ROOT) -> ExecutionFreeze:
    lock = read_lock(root)
    verify_original_sources(root, lock)
    files = file_manifest(root)
    revision = git(root, "rev-parse", "HEAD").decode().strip()
    committed = git_files(root, revision, list(files))
    for name, digest in files.items():
        if sha(source_bytes(committed[name])) != digest:
            raise ValueError(f"commit source/configuration before freezing: {name}")
    return ExecutionFreeze(
        source_commit=revision,
        created_at_utc=datetime.now(UTC),
        study_lock_sha256=LOCK_SHA,
        analysis_plan_sha256=lock["analysis_plan_sha256"],
        configuration_sha256=canonical(locked_configuration(lock)),
        files=files,
        dependencies=dependency_manifest(),
    )


def verify_freeze(raw: bytes, root: Path = ROOT) -> tuple[ExecutionFreeze, dict[str, Any]]:
    freeze = ExecutionFreeze.model_validate_json(raw)
    lock = read_lock(root)
    verify_original_sources(root, lock)
    if (
        freeze.study_lock_sha256 != LOCK_SHA
        or freeze.analysis_plan_sha256 != lock["analysis_plan_sha256"]
    ):
        raise ValueError("execution freeze lock/analysis hash mismatch")
    if freeze.configuration_sha256 != canonical(locked_configuration(lock)):
        raise ValueError("execution freeze configuration mismatch")
    if freeze.files != file_manifest(root):
        raise ValueError("executing source/configuration differs from execution freeze")
    committed = git_files(root, freeze.source_commit, list(freeze.files))
    for name, digest in freeze.files.items():
        if sha(source_bytes(committed[name])) != digest:
            raise ValueError(f"execution freeze does not match its source commit: {name}")
    if freeze.dependencies != dependency_manifest():
        raise ValueError("installed dependencies differ from execution freeze")
    return freeze, lock


def verify_signature(
    manifest: bytes, signature: bytes, public_key: bytes, trusted_sha256: str
) -> None:
    """Trust the independently supplied key fingerprint, never a key inside the seal."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    if sha(public_key) != trusted_sha256:
        raise ValueError("steward public key does not match the independently trusted fingerprint")
    try:
        key = serialization.load_pem_public_key(public_key)
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError("steward key must be Ed25519")
        key.verify(signature, manifest)
    except (InvalidSignature, ValueError) as error:
        raise ValueError("invalid steward seal signature or public key") from error


def load_data(
    inputs_raw: bytes, keys_raw: bytes, mode: Mode
) -> tuple[list[Week2Case], dict[str, Checklist]]:
    cases = [Week2Case.model_validate(value) for value in json.loads(inputs_raw)]
    labels = {key: Checklist.model_validate(value) for key, value in json.loads(keys_raw).items()}
    ids = [case.id for case in cases]
    if len(ids) != 30 or len(set(ids)) != 30 or set(ids) != labels.keys():
        raise ValueError("expected 30 unique cases with exactly corresponding scoring keys")
    if Counter(case.family for case in cases) != {family: 10 for family in FAMILIES}:
        raise ValueError("expected ten cases per locked family")
    for case in cases:
        if case.data_kind != mode or labels[case.id].development_only != (
            mode == "synthetic_development"
        ):
            raise ValueError("synthetic and sealed data/keys must not be mixed")
        if mode == "synthetic_development" and case.origin != "synthetic":
            raise ValueError("dry-run cases must explicitly have synthetic origin")
        if mode == "sealed_final" and (
            case.origin == "synthetic"
            or "REPLACE_" in case.model_dump_json()
            or "__TEMPLATE_ONLY__" in case.id
        ):
            raise ValueError("final inputs contain synthetic data or unreplaced template markers")
        if not case.inputs.items or not case.inputs.task.strip():
            raise ValueError("cases require nonempty tasks and records")
        validate_labels(case.inputs, labels[case.id])
    validate_tokenization(cases)
    return cases, labels


def validate_tokenization(cases: Sequence[Week2Case]) -> None:
    """Reject untokenizable fields before selection, without exposing their contents."""
    tokenizer = TiktokenTokenizer()
    for case in cases:
        fields = [("field=task", case.inputs.task)]
        fields.extend(
            (f"record_id={json.dumps(item.id)} field=content", item.content)
            for item in case.inputs.items
        )
        for field, content in fields:
            try:
                tokenizer.count_tokens(content)
            except TokenizerError:
                raise ValueError(
                    f"case_id={json.dumps(case.id)} {field} cannot be tokenized"
                ) from None


def preflight(
    inputs_path: Path,
    keys_path: Path,
    freeze_path: Path,
    *,
    mode: Mode,
    seal_path: Path | None = None,
    signature_path: Path | None = None,
    public_key_path: Path | None = None,
    trusted_key_sha256: str | None = None,
    root: Path = ROOT,
) -> tuple[list[Week2Case], dict[str, Checklist], dict[str, Any]]:
    """Finish every evidence check before selection. Synthetic mode cannot assert a seal."""
    freeze_raw = freeze_path.read_bytes()
    freeze, lock = verify_freeze(freeze_raw, root)
    inputs_raw, keys_raw = inputs_path.read_bytes(), keys_path.read_bytes()
    seal_raw = b""
    evidence_paths = (seal_path, signature_path, public_key_path, trusted_key_sha256)
    seal: Seal | None = None
    if mode == "sealed_final":
        if any(value is None for value in evidence_paths):
            raise ValueError(
                "sealed runs require seal, detached signature, public key and trusted fingerprint"
            )
        assert seal_path and signature_path and public_key_path and trusted_key_sha256
        seal_raw = seal_path.read_bytes()
        verify_signature(
            seal_raw, signature_path.read_bytes(), public_key_path.read_bytes(), trusted_key_sha256
        )
        seal = Seal.model_validate_json(seal_raw)
        checks = {
            "input_file_sha256": sha(inputs_raw),
            "key_file_sha256": sha(keys_raw),
            "study_lock_sha256": LOCK_SHA,
            "execution_freeze_sha256": sha(freeze_raw),
            "analysis_plan_sha256": freeze.analysis_plan_sha256,
            "configuration_sha256": freeze.configuration_sha256,
        }
        for name, expected in checks.items():
            if getattr(seal, name) != expected:
                raise ValueError(f"seal {name} mismatch")
        if seal.method_freeze_timestamp_utc != freeze.created_at_utc or not (
            freeze.created_at_utc <= seal.sealed_at_utc <= datetime.now(UTC)
        ):
            raise ValueError(
                "seal timestamps must follow the actual source freeze and precede execution"
            )
    elif any(value is not None for value in evidence_paths):
        raise ValueError("synthetic dry runs cannot supply or claim a signed seal")
    cases, labels = load_data(inputs_raw, keys_raw, mode)
    raw_cases = json.loads(inputs_raw)
    raw_keys = json.loads(keys_raw)
    if seal is not None:
        if seal.canonical_input_json_sha256 != canonical(
            raw_cases
        ) or seal.canonical_key_json_sha256 != canonical(raw_keys):
            raise ValueError("seal canonical data/key hash mismatch")
        if seal.case_counts_by_family != lock["case_families"]:
            raise ValueError("sealed family counts differ from the locked comparison")
        real_ids = {case.id for case in cases if case.origin == "real_trace"}
        if (
            len(real_ids) < 15
            or set(seal.realistic_trace_case_ids) != real_ids
            or len(set(seal.realistic_trace_case_ids)) != len(seal.realistic_trace_case_ids)
        ):
            raise ValueError("seal must identify at least fifteen actual realistic trace cases")
    evidence = {
        "mode": mode,
        "seal_verified": seal is not None,
        "steward": seal.data_steward if seal else None,
        "seal_sha256": sha(seal_raw) if seal else None,
        "trusted_key_sha256": trusted_key_sha256,
        "input_file_sha256": sha(inputs_raw),
        "key_file_sha256": sha(keys_raw),
        "canonical_input_sha256": canonical(raw_cases),
        "canonical_key_sha256": canonical(raw_keys),
        "execution_freeze_sha256": sha(freeze_raw),
        "execution_freeze": freeze.model_dump(mode="json"),
        "configuration": locked_configuration(lock),
    }
    return cases, labels, evidence
