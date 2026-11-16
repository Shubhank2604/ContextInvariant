# Week 2 validation and authoring handoff

Starting point: `51bb4f0794c49702078821d301f821597a8e22ee`.
Validation fix revision: `809843ed2fe41006d86359cbf1de4798792b4aec`.
Branch: `research/week2-validation-preflight`.

Two validation defects reported after Week 1 are fixed:

- A checklist could forbid a legal optional record without either selector receiving
  that prohibition. Now each forbidden ID must follow from a shared supersession rule
  with history retention disabled, or be the loser of a declared contradiction resolved
  by supplied authority/override. A tied conflict cannot justify an evaluator-only
  winner. Direct evaluation validates labels too. Actual hard-exclusion failures come
  from the input relationships, independently of checklist preferences; optional useful
  evidence remains a separate recall score.
- Replay auditing checked selected records but ignored the stored model prompt. Now it
  rebuilds the exact prompt from the saved selected records and verified shared inputs,
  compares its text and tiktoken count, requires both fields for returned replay context,
  and rejects either field on no-context rows, including null-valued fields.

The new corruption tests reproduce the failures against the original code. Under the
fixed evaluator/auditor, the unchanged 60 pilot rows and eight replay rows pass. All
31 tracked files under `research/week1/` remain identical to the starting revision;
the [new verification record](preflight-verification.json) is stored here rather than
rewriting the recorded Week 1 evidence or its report.

## Authoring may proceed independently

Per the maintainer's choice, prepare the packet now and assign the independent author
or data steward later. No final cases have been authored or opened by the method
implementation team in this change. The packet contains:

- [Authoring, review and sealing instructions](authoring/README.md).
- [Input template](authoring/case-template.json) and [checklist template](authoring/checklist-template.json).
- [Three explicit Week 1 development examples](authoring/development-examples.json):
  a tie, declared stale-state removal, and conditional qualifier preservation.
- [Blank reviewer/steward manifest](authoring/sealing-manifest-template.json).
- [Analysis plan](analysis-plan.md), with its fixed source/configuration identity in
  [study-lock.json](study-lock.json).

The preferred final status is independently authored and stewarded by someone who did
not tune either method. If the collaborator can only review, record independently
reviewed instead, and disclose who authored the cases. No collaborator is assigned or
contacted by this change. The methods, evaluator, budgets and analysis must be frozen
and their manifest signed before the implementation team can access final inputs or keys.

## Avoidable-refusal follow-up

The highest-priority runtime candidate is selection that considers an optional record
and its complete required support before committing to that record. Develop it only on
development cases, including the saved valid 30-token witness at budgets 87 and 108.
Retain the original refusal outcome. Any implementation must have a new method ID
(proposed `context_invariant_bundle_skip_v1`), a distinct source SHA, paired development
results and a frozen configuration. It must not silently replace `context_invariant_full`.
The candidate is not implemented or included in the current locked comparison. To
include it, publish a revised method/analysis freeze before final-case access; otherwise
defer it to a subsequent study. This patch changes no selection or compression behavior.

## Verify without rerunning selection

From the repository root with the development dependencies installed:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -m pytest -o addopts= --no-cov tests/unit/test_week1_study.py tests/unit/test_week2_preflight.py --basetemp=.pytest-tmp-week2-preflight-focused -q
python -m context_invariant.benchmarks.week1.audit --bundle research/week1/evidence/20261116T051053.178379Z-metadata-matched-pilot-development --inputs research/week1/inputs/pilot.json --checklists research/week1/inputs/checklists.json
python -m context_invariant.benchmarks.week1.audit --bundle research/week1/evidence/20261116T051053.904393Z-week1-replay-development --inputs research/week1/inputs/replay.json --checklists research/week1/inputs/replay-checklists.json
python -m pytest --basetemp=.pytest-tmp-week2-preflight-full -q --cov-report=term:skip-covered
ruff check .
ruff format --check .
mypy
```
