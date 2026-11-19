# Week 1 result: metadata-matched comparison

The comparison is operational and auditable. It does **not** establish a general win
for ContextInvariant: validated extraction retains useful optional evidence in two
cases under pressure, while the simpler selector has better coverage in one case.
Neither method returns an invalid context in this pilot.

Starting commit: `00a54b559f55a29bcdc61fc1663fa322d90fa466`.
Execution commit: `d91cb078d4c803a68bc0d9b956122c92468e1688`.
Branch: `research/metadata-matched-week1`. The [protocol](protocol.md) preceded
implementation. [Selector inputs](inputs/pilot.json) and [scoring checklists](inputs/checklists.json)
were authored separately; the ten cases are development data, separate from the 90-case
benchmark and the future held-out set. The runtime and historical evidence are unchanged.

The authoritative [pilot bundle](evidence/20261116T051053.178379Z-metadata-matched-pilot-development/report.md)
has 60 evaluations. Its [raw outputs](evidence/20261116T051053.178379Z-metadata-matched-pilot-development/predictions.jsonl)
contain complete selected text, token counts, failure reasons, certificates, available
traces, and observed pre-closure passes. [Configuration](evidence/20261116T051053.178379Z-metadata-matched-pilot-development/config.json)
contains source hashes, input hashes and all 14 differing pairs. No failed or baseline-winning
case was removed. A preliminary run was archived locally; its 60 selections and outcomes
match the final instrumentation rerun exactly.

## Comparison table

Every row includes all ten attempted cases. Mean tokens uses valid outputs only;
no-context runs have null token use, not zero-token compression.

| Budget | Method | Valid | Invalid | No context | Certified budget infeasible | Selection failure | Mean valid tokens |
|---|---|---:|---:|---:|---:|---:|---:|
| 65% | Full ContextInvariant | 8 | 0 | 2 | 1 | 1 | 38.00 |
| 65% | Metadata-matched | 9 | 0 | 1 | 1 | 0 | 19.89 |
| 80% | Full ContextInvariant | 8 | 0 | 2 | 1 | 1 | 38.00 |
| 80% | Metadata-matched | 9 | 0 | 1 | 1 | 0 | 19.89 |
| 100% | Full ContextInvariant | 10 | 0 | 0 | 0 | 0 | 95.50 |
| 100% | Metadata-matched | 10 | 0 | 0 | 0 | 0 | 102.00 |

On the eight matched-valid cases at 65% and 80%, full uses 304 tokens versus 149 for
the baseline. On the four matched-valid cases with useful-evidence labels, mean useful
recall is 0.75 versus 0.25. The full method spends more tokens to retain evidence.
At 100%, all ten cases are valid: 955 versus 1,020 tokens, but useful recall across
the five annotated cases is 0.80 versus 1.00. The smaller total includes lost optional
evidence and must not be presented as equal-quality compression efficiency.
These descriptive development measurements have no inferential significance claim.

## Walkthrough: a tie, a failure, and a disagreement

**Tie — `simple-tie`, 65%.** Original context has 22 tokens; floor(22 × .65) is 14.
Both keep the exact same `policy` and `release` text using exactly 14 tokens:
“Preserve approved release behavior.” and “The approved release is ready for review.”
Both omit unrelated formatting output. Full ContextInvariant adds no measured value here.

**Failure — `required-overflow`, 65%.** Original context is exactly 100 tokens. The
required decision is 20 tokens and its declared supporting transcript is 70. Both are
explicitly lossless, so every valid context requires at least 90 tokens. Both methods
return no context at budget 65 (also at 80). The saved certificate proves infeasibility;
there is no selected text or compression score. At 100% both return valid context.

**Disagreement — `diagnostic-log`, 65%.** Original context is 188 tokens, budget 122.
The unchanged log alone is 181 tokens, so the baseline skips it and keeps only the
seven-token required policy. The full runtime keeps the policy plus a 90-token,
12-line verbatim excerpt, 97 tokens total. The excerpt contains:

```text
error E503 request_id=req_A17: retry needs jitter.
```

The trace records `tool_output`, successful identifier and literal-reference checks,
and `compressed_to_fit_budget`. The whole request ID and error code survive. This
is an optional useful-evidence difference, not a validity difference, model-answer
improvement, or reduction versus the baseline's seven tokens.

**Baseline win — `optional-bundle`, 65% and 80%.** A five-token lead requires a
100-token support record; mandatory policy is ten tokens. The baseline tests the
115-token bundle, skips it at budgets 87 and 108, then keeps the policy and independent
20-token alternative (30 total). The full method's observed initial pass selects
`policy` and `lead`; forcing support subsequently requires 110 tokens before even
reconsidering the optional lead. The runtime raises `RequiredContextOverflow`.
Its independently computed mandatory lower bound is only ten tokens, and the baseline
has constructed a valid 30-token witness. This is a selection failure, **not** proved
global budget infeasibility. The preserved runtime deliberately refuses an overflowing
chosen closure; the baseline's bundle-skipping rule is a substantive algorithm difference.

## Every disagreement and the remaining null results

| Case | Budgets | Concrete decision and interpretation |
|---|---|---|
| `stale-state` | 65%, 80% | Both remove `old`. Full compresses unrelated noise and uses 19 tokens; baseline omits it and uses 14. No useful-evidence improvement is annotated. |
| `stale-state` | 100% | Same content and 59 tokens; default full layout places state differently. Order-only difference, not a measured quality gain. |
| `canonical-conflict` | 65%, 80% | Both retain canonical state and remove the rumor. Full adds a five-token noise excerpt (16 total); baseline uses 11. No annotated utility gain. |
| `diagnostic-log` | 65%, 80% | Full retains the diagnostic via validated extraction; baseline skips the unchanged oversized log. Both are valid; full spends 97 versus 7 tokens. |
| `exact-evidence` | 65%, 80% | Full keeps the exact limit 64, tenant_B42 and policy citation in a verbatim excerpt (63 total); baseline omits the document (8 total). Contracts pass for retained identifiers, numbers and citation. |
| `optional-bundle` | 65%, 80% | Full returns no context after forcing support; baseline skips the expensive optional bundle and returns a valid alternative. Selection failure, not global infeasibility. |
| `optional-bundle` | 100% | Full removes the useful alternative as `semantic_duplicate_of_mandatory: support` (115 tokens, useful recall 0); baseline keeps all records (135 tokens, recall 1). Repeated padding drives an artificial similarity trap. |
| `exact-boundary` | 100% | Full removes noise as a semantic duplicate of forced `state` (65 tokens); baseline retains noise (100). Repeated padding affects deduplication; no utility gain is established. |
| `required-overflow` | 100% | Full removes noise as a semantic duplicate of forced `transcript` (90 tokens); baseline retains it (100). Again a padding-driven token-only difference. |

Those groups cover all 14 differing case/budget pairs, including the order-only pair.
Sixteen pairs have identical outputs or mutual failure. `dependency-chain` is a tie at
all three budgets; `exact-boundary` is an exact 65-token tie at the 65% boundary.
`qualifier-sensitive` also ties: at 65% and 80%, the full runtime's candidate preserves
30 ms but loses “This threshold applies only to warm-cache requests.” The declared
literal-reference validator rejects it; original fallback cannot fit, so the optional
record is omitted. The baseline also omits it. Neither returns a misleading unqualified
value. At 100% both retain the original. No invalid returned context is hidden by this tie.

## Workflow, verification, and recommendation

The [offline replay](workflow/README.md) has three chronological coding checkpoints and
one explicit budget stress probe, eight evaluations total. Both methods return valid
context at the normal checkpoints, using 288/315, 310/342 and 329/357 record tokens.
They preserve the earlier failing test, original no-429 rule and current limit 2 while
removing stale limit 1. Rendered prompts cost 351, 378 and 409 tokens respectively.
The stress probe requires at least 587 lossless tokens with budget 479; both return
certified overflow. The [saved prompts and traces](evidence/20261116T051053.904393Z-week1-replay-development/predictions.jsonl)
show exactly what would reach a model. The buggy task fails and the reference passes
the 12-check local oracle; these are not model task-success results. No live run occurred.

The read-only audit revalidated all 68 outputs and recomputed aggregates; [verification](verification.json)
records the checks. Six historical evidence trees and the frozen parity fixture remain
unchanged. Repository tests, lint, formatting, and strict types pass; exact commands are
in the [run instructions](README.md), and worked raw-record checks are in the
[manual audit](manual-audit.md).

Proceed to the [Week 2 plan](week2-plan.md), with independently authored/reviewed sealed
cases, natural diverse text, explicit representation rules, and realistic task oracles.
The targeted ablation is full ContextInvariant with compression disabled, holding
everything else fixed. It tests whether the diagnostic/citation evidence difference
depends on extraction. Keep coverage and optional-bundle failure as primary concerns;
the current study supports a fair next experiment, not a claim of general superiority.
