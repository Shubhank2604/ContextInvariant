# Tokenization preflight correction

Corrected execution source: `7f2fed9a7ff97eb3c134d42049cc9159263bbcb3`.
The regression was reproduced against `d656130`: a control marker in the last
case's task or last record passed preflight and allowed selection to start.

The shared data validator now checks every task and record with the unchanged
`cl100k_base` tokenizer before either method runs. Failures identify case, field
and record ID where applicable, omit restricted content, and suppress the tokenizer
exception chain. All six new regressions pass: last-case task/record failures through
direct preflight, the runner, and CLI preflight. Runner checks prove no selector runs
and no result directory is created; CLI checks prove no traceback or content leaks.

Verification at the corrected source:

- All 465 repository tests passed; coverage 89.73%, above the unchanged 85% gate.
- Ruff lint, formatting and strict mypy passed.
- Fresh synthetic run and audit: 180 rows, 162 valid, zero invalid, 12 certified
  infeasibilities, six witnessed avoidable selection failures. All prediction fields
  match the retained run after omitting only `trace.stage_timings_ms`; metrics match
  exactly. The six avoidable refusals remain one development scenario repeated across
  three family labels and two budgets, not six independent research observations.
- The original 60 pilot and eight replay rows re-audit successfully.
- Week 1 code/evidence, tokenizer, runtime, retained synthetic data/freeze/results,
  study lock and analysis plan are unchanged. The pending study lock remains unsigned.

Exact local validation commands (PowerShell, from the repository root):

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
$studyPython = Join-Path (Get-Location) '.venv-week2-runner/Scripts/python.exe'
& $studyPython -m pytest --basetemp=.pytest-tmp-week2-tokenization-recorded -q --cov-report=term:skip-covered
& $studyPython -m ruff check .
& $studyPython -m ruff format --check .
& $studyPython -m mypy
& $studyPython -m context_invariant.benchmarks.week2 freeze --output out/week2-tokenization-check/execution-freeze.json
& $studyPython -m context_invariant.benchmarks.week2 run --synthetic --inputs research/week2/synthetic/cases.json --keys research/week2/synthetic/keys.json --freeze out/week2-tokenization-check/execution-freeze.json --output-directory out/week2-tokenization-check/results
& $studyPython -m context_invariant.benchmarks.week2 audit --synthetic --inputs research/week2/synthetic/cases.json --keys research/week2/synthetic/keys.json --freeze out/week2-tokenization-check/execution-freeze.json --bundle out/week2-tokenization-check/results/20261116T163800.552839Z-week2-synthetic-dry-run-development
& $studyPython -m context_invariant.benchmarks.week1.audit --inputs research/week1/inputs/pilot.json --checklists research/week1/inputs/checklists.json --bundle research/week1/evidence/20261116T051053.178379Z-metadata-matched-pilot-development
& $studyPython -m context_invariant.benchmarks.week1.audit --inputs research/week1/inputs/replay.json --checklists research/week1/inputs/replay-checklists.json --bundle research/week1/evidence/20261116T051053.904393Z-week1-replay-development
```

The fresh freeze, rerun and test log are local ignored verification files under
`out/week2-tokenization-check/`. For another run choose a new freeze filename and use
the bundle directory printed by `run` in `audit`. The retained synthetic evidence is
still bound to its original source and freeze; do not overwrite it to validate this
correction. The final steward must approve a fresh execution freeze before signing.

The authoring packet is ready for handoff; author/steward assignment remains pending.
Independently authored or reviewed data are the next research milestone. No final
cases were authored, opened or run, and no live model calls were made.

## Rendered header follow-up

Corrected source for the steward's new execution freeze:
`3e4419a760ef71404f3c2bd0e718541ca3db3cf6`. This also checks every original
record's rendered header, including ID and type, before either selector runs.
The renderer and preflight share the header formatter, preserving exact prompt
text. Header errors use case ID, zero-based record index and `field=header` rather
than exposing a potentially restricted record ID. Tokenizer behavior is unchanged.

The added regression puts `<|endoftext|>` in a required record ID in the last
development case and updates shared references and the separate scoring key. It
reproduces preflight acceptance on `b90b7cc`; with the correction, both preflight
and run reject it before any selection or result-directory creation, with no ID
text or exception-chain exposure.

All 466 repository tests passed with 89.75% coverage. Ruff lint, formatting and
strict mypy passed. Full-suite command:
`& $studyPython -m pytest --basetemp=.pytest-tmp-week2-header-full -q --cov-report=term:skip-covered`.

A fresh 180-row synthetic run and read-only audit passed. All predictions match the
retained run after omitting only trace timings; metrics match byte for byte: 162
valid, zero invalid, 12 certified infeasibilities and six avoidable refusals. Both
original Week 1 audits pass (60 pilot and eight replay rows). The fresh local freeze
and results are under ignored `out/week2-header-check/`; retained evidence, study
lock and analysis plan remain untouched. No final cases or live models were used.

```powershell
& $studyPython -m context_invariant.benchmarks.week2 freeze --output out/week2-header-check/execution-freeze.json
& $studyPython -m context_invariant.benchmarks.week2 run --synthetic --inputs research/week2/synthetic/cases.json --keys research/week2/synthetic/keys.json --freeze out/week2-header-check/execution-freeze.json --output-directory out/week2-header-check/results
& $studyPython -m context_invariant.benchmarks.week2 audit --synthetic --inputs research/week2/synthetic/cases.json --keys research/week2/synthetic/keys.json --freeze out/week2-header-check/execution-freeze.json --bundle out/week2-header-check/results/20261116T171620.280884Z-week2-synthetic-dry-run-development
```

Use a new freeze filename and the newly printed bundle path for subsequent runs.
Hand off the [authoring packet](authoring/README.md) now; the independent author or
steward can work privately while arranging review. Before sealing, validate tasks,
headers and content with the packet's private data-check instructions, then approve
a fresh execution freeze from this corrected source (or a documentation-only
descendant). Assignment and attestation remain pending; do not mark the study lock
signed or provide final data to the implementation team.
