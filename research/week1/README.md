# Reproduce the metadata-matched Week 1 study

Read [the short report](report.md), [prespecified protocol](protocol.md),
[raw-record audit](manual-audit.md), and [Week 2 lock](week2-plan.md).
The implementation lives in `src/context_invariant/benchmarks/week1/`, isolated from
the frozen SDK behavior. The project-wide 85% coverage gate is retained.

Starting revision: `00a54b559f55a29bcdc61fc1663fa322d90fa466`.
Authoritative execution revision: `d91cb078d4c803a68bc0d9b956122c92468e1688`.
The later evidence/documentation commit does not change method behavior. For exact
source auditing, use a separate clone/checkout at the execution revision. Run the
commands below from this research branch, which also contains the retained artifacts
and environment constraints; its method source matches that execution revision. The
constraint and baseline inputs were committed at `ded0346d744f93dbc6047e025d659ba020559747`
before the first retained run. Protocol commit: `a506675`.

## Inputs and outputs

| Deliverable | Location |
|---|---|
| Ten pilot selector inputs | [inputs/pilot.json](inputs/pilot.json) |
| Separate development scoring checklists | [inputs/checklists.json](inputs/checklists.json) |
| Authoritative 60-run pilot | [evidence/20261116T051053.178379Z-metadata-matched-pilot-development](evidence/20261116T051053.178379Z-metadata-matched-pilot-development/report.md) |
| Three replay checkpoints plus stress probe | [inputs/replay.json](inputs/replay.json), [labels](inputs/replay-checklists.json) |
| Eight replay outputs, including exact prompts | [evidence/20261116T051053.904393Z-week1-replay-development](evidence/20261116T051053.904393Z-week1-replay-development/report.md) |
| Captured buggy/reference test execution | [inputs/task-test-capture.json](inputs/task-test-capture.json) |
| Task, reference and behavioral oracle | [workflow/task](workflow/README.md) |
| Machine-readable audit and evidence anchors | [verification.json](verification.json) |
| Observed dependency constraints | [environment-requirements.txt](environment-requirements.txt) |

Each evidence directory contains the established seven-file immutable bundle format.
`cases.jsonl` saves both original inputs and separately authored checklists; only the
input object reaches the selectors. `predictions.jsonl` has one row per case/method/budget.
Full configuration is in each row's policy and `config.json`; semantic input hashes,
source hashes, Git SHA and installed core dependency versions are retained. Timing
and run-directory timestamps may vary; selection content and outcome fields are
deterministic. A preliminary run is archived locally under ignored
`out/week1-preliminary/`; verification records exact selection/outcome agreement.

## Run from the repository root

The following uses PowerShell and a dedicated environment. The dependency constraints
capture the observed Python 3.13 Windows environment; they are not a claim that every
platform has been reproduced with exactly those wheels.

```powershell
python -m venv .venv-week1
$studyPython = Join-Path (Get-Location) '.venv-week1/Scripts/python.exe'
& $studyPython -m pip install -c research/week1/environment-requirements.txt -e '.[dev]'
& $studyPython -m context_invariant.benchmarks.week1.runner --inputs research/week1/inputs/pilot.json --checklists research/week1/inputs/checklists.json --output-directory out/week1-pilot
& $studyPython -m context_invariant.benchmarks.week1.runner --inputs research/week1/inputs/replay.json --checklists research/week1/inputs/replay-checklists.json --output-directory out/week1-replay --replay
```

On POSIX, use the environment's `bin/python` with the same module arguments.
No credentials, data downloads or model provider are required. The pilot always runs
10 × 2 × 3 = 60 evaluations at 65%, 80%, 100%; replay runs 4 × 2 at 80%. Budget
rounding and full policy values are fixed in the protocol and saved configuration.
The historical v0.4 comparison is deliberately excluded from these primary totals.

Recheck the retained bundles without running the methods:

```powershell
& $studyPython -m context_invariant.benchmarks.week1.audit --bundle research/week1/evidence/20261116T051053.178379Z-metadata-matched-pilot-development --inputs research/week1/inputs/pilot.json --checklists research/week1/inputs/checklists.json
& $studyPython -m context_invariant.benchmarks.week1.audit --bundle research/week1/evidence/20261116T051053.904393Z-week1-replay-development --inputs research/week1/inputs/replay.json --checklists research/week1/inputs/replay-checklists.json
```

To inspect a new rerun, replace `--bundle` with its printed output directory. The
auditor checks canonical input identity, raw cases, the exact evaluation grid, actual
selected text/tokens, no-output null accounting, infeasibility certificates, verbatim
baseline behavior, and aggregate recomputation. Unit tests include corrupted-result
detection and a missing-requirement output distinct from an explicit overflow.

## Validation commands used

The checkout's base interpreter already contained the dependencies. It required a
source path because the package was not installed in that interpreter:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -m pytest -o addopts= --no-cov tests/unit/test_week1_study.py --basetemp=.pytest-tmp-week1-focused-7 -q
python -m pytest --basetemp=.pytest-tmp-week1-full-1 -q
python -m pytest --basetemp=.pytest-tmp-week1-final -q --cov-report=term:skip-covered
ruff check .
ruff format --check .
mypy
git diff --exit-code 00a54b559f55a29bcdc61fc1663fa322d90fa466 -- benchmarks/results tests/fixtures/phase5_full_runtime_parity_v1.json
```

Focused tests: 16 passed. Final full suite: 413 passed, 90.59% coverage, above the unchanged 85% coverage
gate. The 540-record frozen parity test is included. Ruff lint/format and strict mypy
passed. All six retained v0.5 evidence tree IDs equal their starting-revision anchors;
no source behavior in the existing runtime, baselines, or historical experiment adapter
was changed. Existing user-owned untracked Markdown files were preserved and excluded
from these commits.
