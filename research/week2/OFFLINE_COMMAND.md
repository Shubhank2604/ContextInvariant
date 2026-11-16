# Offline Week 2 command

This is a separate entry point. The Week 1 runner still requires exactly ten pilot
cases. The new command accepts exactly 30 cases, ten per locked family, and produces
180 rows: two locked methods at 65%, 80% and 100%. There are no model calls.

The original study-lock.json remains pending and byte-identical to 8253d0d. A final
steward signs a separate seal binding its exact hash and the execution freeze; the
command never edits or marks the pending study lock as signed. The avoidable-refusal
candidate and compression ablation are excluded.

## Setup and synthetic dry run

From a committed checkout, install `.[dev,research]` in an isolated environment. The
research extra adds maintained Ed25519 verification and dependency-version parsing;
the base runtime's dependencies and behavior are unchanged. On PowerShell:

```powershell
python -m venv .venv-week2
$studyPython = Join-Path (Get-Location) '.venv-week2/Scripts/python.exe'
& $studyPython -m pip install -e '.[dev,research]'
& $studyPython -m context_invariant.benchmarks.week2 synthetic --output-directory out/week2-dry-data
& $studyPython -m context_invariant.benchmarks.week2 freeze --output out/week2-execution-freeze.json
& $studyPython -m context_invariant.benchmarks.week2 preflight --synthetic --inputs out/week2-dry-data/cases.json --keys out/week2-dry-data/keys.json --freeze out/week2-execution-freeze.json
& $studyPython -m context_invariant.benchmarks.week2 run --synthetic --inputs out/week2-dry-data/cases.json --keys out/week2-dry-data/keys.json --freeze out/week2-execution-freeze.json --output-directory out/week2-dry-results
```

The last command prints a timestamped bundle directory. Audit that exact directory
with `audit --bundle PATH` plus the same input/key/freeze arguments and `--synthetic`.
Creation commands refuse to overwrite files. Normal run commands create new bundles.
On POSIX use the virtual environment's `bin/python`.

Synthetic fixtures are three family-labelled copies of the ten already public Week 1
development cases, with distinct case IDs and explicit synthetic task prefixes. They
exercise family aggregation and all failure paths; they are not 30 independent scientific
observations or realistic held-out workloads. Keys are separate files and contain only
development labels. Synthetic mode refuses seal arguments and cannot claim signed final
evidence. Final mode refuses synthetic cases and development keys, even with a valid
test signature. No real final cases or genuine steward attestations were created here.

## Freeze identity

`freeze` requires committed source and configuration. It checks every original runtime
module against the lock's method revision and the two corrected Week 1 evaluator/auditor
modules against their fixed revision. It also freezes all current source modules,
pyproject.toml, the original lock, analysis plan and dependency constraints, plus the
installed transitive runtime/research dependency versions and Python version.

Use a full Git checkout, or fetch the recorded method/evaluator/execution revisions
before preflight. The Linux and Windows test jobs fetch full history so those checks
also run in CI. Missing Git objects are rejected rather than treated as verified.

Source-file hashes use LF-normalized bytes, matching Git's source convention. Data,
key, seal and freeze-file hashes cover exact bytes. `configuration_sha256` and canonical
data hashes use SHA-256 of UTF-8 JSON with sorted keys and compact separators, wrapped
as `{"document": VALUE}`; use the provided `canonical` helper rather than guessing the
serialization. The original analysis-plan hash is checked against the pending lock.

The steward creates the execution freeze in the actual approved environment after
installing/reviewing dependencies. Preflight rejects source, configuration, dependency,
lock or analysis changes relative to that freeze. A later checkout may add documentation
without changing the executing files. New method or evaluator behavior needs a new
approved freeze before final-case access. Hashes prove identity, not human independence
or semantic correctness of authored requirements.

## Steward data format and attestation

Final input is a list of extended case objects. Keep `inputs` unchanged from the authoring
schema and add envelope fields:

- `family`: `coding_agent`, `operations`, or `evidence_backed_analysis`.
- `data_kind`: `sealed_final` for genuine final data; never for a development fixture.
- `origin`: `authored` or `real_trace`. At least 15 cases must have reviewed real-trace
  provenance. The seal lists their IDs exactly.

Keys are a separate object mapping case IDs to checklists with `development_only=false`.
All hard requirements must be supplied to both methods. The fixed evaluator rejects
private prohibitions and mismatched labels. Source text, keys and transcripts remain
in the steward's restricted location, outside implementation-team access.

[command-seal-template.json](authoring/command-seal-template.json) documents the executable
seal schema; the older packet manifest remains an unsigned planning template. Replace
all null/draft fields only after independent authorship/review and permission checks.
The signed seal must contain exact data/key hashes, canonical data/key hashes, lock,
freeze, configuration and analysis hashes, family counts, realistic-trace IDs, author,
reviewer and steward identities, provenance/review/access references, and timezone-aware
timestamps. Its freeze timestamp must equal the execution freeze timestamp; sealing
must follow freezing and precede execution. Prior implementation-team final access is
not accepted by this gate.

The steward signs the exact UTF-8 manifest bytes with an Ed25519 private key held outside
the checkout. Store the raw detached 64-byte signature separately; supply the public key
as PEM SubjectPublicKeyInfo. A trusted reviewer verifies the steward's identity and public
key through an independent channel and supplies SHA-256 of those exact PEM bytes through
`--trusted-key-sha256`. Do not take that fingerprint from the untrusted seal itself.
The command verifies the detached signature and all its bindings; a signature-shaped
string or a nonempty signature field is not accepted as authentication. See the
[cryptography signing API](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/).

For example, in the steward's isolated signing environment (not run by the implementation
team), an existing encrypted PEM private key can sign the final manifest with
`serialization.load_pem_private_key(...).sign(manifest_bytes)`. Use a password prompt or
the steward's secret store. Never put the private key, password, final cases or keys in
this repository. The public fingerprint and detached signature are not secret. Review
and sign the actual execution freeze and manifest, not just the filenames.

The steward can check everything without running either selector:

```powershell
& $studyPython -m context_invariant.benchmarks.week2 preflight --inputs STEWARD_CASES.json --keys STEWARD_KEYS.json --freeze APPROVED_FREEZE.json --seal SIGNED_SEAL.json --signature SEAL.sig --public-key STEWARD_PUBLIC.pem --trusted-key-sha256 TRUSTED_PEM_SHA256
```

Only after preflight passes should the steward invoke `run` with those same arguments
and `--output-directory STEWARD_RESULTS`. Omit `--synthetic` for sealed mode. Keep the
result bundle restricted: its raw cases include keys for auditability, even though
neither selector nor any saved model-facing prompt receives them. This command makes
no live calls and grants no implementation-team access to final content.

## Outcomes and audit

Every attempt has a case/method/budget row, exact input identity, family, policy, selected
records, original and final token counts, available trace/pass evidence, and a failure
reason/exception where applicable. Returned context is either valid or invalid. No
output has null context tokens, reduction and useful recall, and no prompt fields.

Required-budget infeasibility needs the fixed lossless lower-bound certificate. A
selection refusal is marked avoidable only when the other method supplies a valid
context at that budget; the row stores its token count and selected-context hash as a
feasibility witness. Other selection refusals remain unproven. Conflict and execution
failures remain distinct and visible. All totals retain failures.

JSON/CSV/report views show method × budget × family counts, reasons and valid-output
token means. Matched-valid pairs report token totals and optional useful-evidence recall
with their own denominators. The ten-case family strata are descriptive, and the synthetic
copies must never be treated as independent samples for inference. No-output savings
are not compression. Every disagreement is retained in config.json.

`audit` repeats preflight and checks exact input/key snapshots, all 180 unique grid
identities, actual selected text and tokens, certificates, no-output nulls, failure
classes and feasibility witnesses, prompt reconstruction/counts, verbatim baseline
behavior, aggregate metrics, CSV, report and disagreement evidence. It never invokes
either method. Supply the original input/key/freeze and, for sealed runs, the original
signature evidence plus independently trusted key fingerprint. A changed file, invalid
seal, missing row or duplicate row is rejected. Keep original and amended artifacts
separate if a later defect is discovered.
