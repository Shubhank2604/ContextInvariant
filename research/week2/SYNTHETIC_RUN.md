# Week 2 offline command: synthetic dry-run result

Execution source: `9cb0ab019bcdd13978a1fb671195ef645a7f8a09`, building on `8253d0d`.
The [execution freeze](synthetic/execution-freeze.json) binds source, configuration,
analysis and dependency identity. The [original study lock](study-lock.json) remains
pending and unchanged. No real seal was created or verified for this dry run.

Thirty explicitly synthetic, family-labelled fixtures produced all 180 evaluations:
ten per family, two original methods, and 65/80/100% budgets. These are three labelled
copies of public Week 1 development scenarios, not independent held-out observations.
The avoidable-refusal variant and compression ablation were not included.

| Budget | Method | Valid | Invalid | No context | Certified infeasible | Witnessed avoidable refusal |
|---|---|---:|---:|---:|---:|---:|
| 65% | Full ContextInvariant | 24 | 0 | 6 | 3 | 3 |
| 65% | Metadata-matched | 27 | 0 | 3 | 3 | 0 |
| 80% | Full ContextInvariant | 24 | 0 | 6 | 3 | 3 |
| 80% | Metadata-matched | 27 | 0 | 3 | 3 | 0 |
| 100% | Full ContextInvariant | 30 | 0 | 0 | 0 | 0 |
| 100% | Metadata-matched | 30 | 0 | 0 | 0 | 0 |

Total: 162 valid contexts, zero invalid contexts, 12 certified infeasibilities and
six selection refusals with a valid peer witness. No no-output row is counted as
zero-token compression. The peer witnesses use 30 tokens in the optional-bundle cases.

Each family independently has 8 versus 9 valid outputs at 65% and 80%, and 10 versus
10 at 100%. At 65% and 80%, the 24 matched-valid cases use 912 full-method tokens
versus 447 baseline tokens; useful recall on the 12 matched annotated cases is .75
versus .25. At 100%, totals are 2,865 versus 3,060 tokens and useful recall on 15
annotated cases is .80 versus 1.00. This is pipeline verification, not a scientific
effect estimate or an equal-quality compression result.

The [saved bundle](synthetic/evidence/20261116T082640.842497Z-week2-synthetic-dry-run-development/report.md)
contains exact inputs/keys, all selected records, prompts, counts, traces, failure
certificates, feasibility witnesses, family metrics and disagreements. The read-only
auditor passes all 180 rows without invoking either method. The preliminary run's
selections and outcomes agree with the final run; its files were preserved locally
under ignored `out/week2-offline-preliminary/`.

## Exact exercised commands

The workspace environment used Python 3.13.9 with the research extra installed in
`.venv-week2-runner`. From the repository root:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
$studyPython = Join-Path (Get-Location) '.venv-week2-runner/Scripts/python.exe'
& $studyPython -m context_invariant.benchmarks.week2 run --synthetic --inputs research/week2/synthetic/cases.json --keys research/week2/synthetic/keys.json --freeze research/week2/synthetic/execution-freeze.json --output-directory out/week2-offline-rerun
& $studyPython -m context_invariant.benchmarks.week2 audit --synthetic --inputs research/week2/synthetic/cases.json --keys research/week2/synthetic/keys.json --freeze research/week2/synthetic/execution-freeze.json --bundle research/week2/synthetic/evidence/20261116T082640.842497Z-week2-synthetic-dry-run-development
```

The first command creates a new bundle; replace the audit's `--bundle` with that printed
path to audit the rerun instead of the retained bundle. A different environment must
install the recorded dependency/Python versions to audit this exact freeze, or create
its own committed execution freeze for a separately identified synthetic run. See
[OFFLINE_COMMAND.md](OFFLINE_COMMAND.md) for fresh-environment setup and freeze commands.

## Verification and remaining final-run requirements

All 459 repository tests passed with 89.69% coverage, above the unchanged 85% gate.
The 26 new tests cover the complete grid, actual shared selector inputs, key isolation,
changed case/key files, invalid or missing seals, wrong source/configuration/dependency
evidence, family/key correspondence, prompt tampering, and missing/duplicate result rows.
Lint, formatting and strict mypy passed. The original 60 pilot rows and eight replay
rows re-audited successfully. Week 1 artifacts and runtime behavior are unchanged.
[verification.json](synthetic/verification.json) records these checks.

Before a final run the steward still needs to supply independently authored/reviewed
30-case inputs and separate keys, 10 per family with at least 15 reviewed real traces;
an approved committed execution freeze in the actual environment; a complete reviewed
seal binding all file/configuration/analysis hashes and access chronology; a detached
Ed25519 signature; and a public key with an independently authenticated fingerprint.
Use `preflight` first, then `run`, then `audit`, in the steward's restricted environment.
Human provenance and independence claims require real review; signature verification
authenticates the manifest but does not prove those claims. No final cases were authored,
opened or run by the implementation team, and no live model calls were made.
