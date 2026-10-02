# Resume evidence ledger

This ledger maps concise resume language to retained, reviewable artifacts. Raw cases,
predictions, configurations, environments, and metrics are committed under
`benchmarks/results/`; the
[research-readiness report](../benchmarks/reports/v0.5.0-research-readiness.md) records the
complete interpretation.

## Approved primary claim

**Claim:** Constraint-aware ContextOS materially reduces structural and answer-level failures
under token pressure versus the frozen v0.4 runtime.

**Measured result:** At an 80% budget, selection violations fall from 77.78% to 11.11%, an
85.7% relative reduction. Answer violations fall from 22.22% to 11.11% on GPT-5.4-mini and
from 33.33% to 11.11% on GPT-5.4, relative reductions of 50.0% and 66.7%.

**Artifacts:**

- `20261002T011212.526789Z-constraint-model-full`
- `20261002T012723.643351Z-constraint-model-full`

**Scope:** 90 controlled development cases across nine failure families; three strategies and
270 predictions per model snapshot; temperature zero; deterministic required-value and
forbidden-value scoring without an LLM judge.

**Limitations:** The benchmark co-evolved with the implementation. Full Phase 5 explicitly
rejects ten infeasible multi-hop cases at this budget. The GPT-5.4-mini answer-violation delta
CI includes zero; the GPT-5.4 interval excludes zero.

**Safe to use on a resume:** Yes, when identified as a 90-case controlled benchmark and not as
a production or general long-context result.

## Approved efficiency claim

**Claim:** Full Phase 5 increases controlled context reduction while preserving required values
on feasible executions.

**Measured result:** At the 80% budget, mean context reduction increases from 27.20% for frozen
v0.4 to 32.38% for Full Phase 5. All 80 feasible Phase 5 cases preserve their required values;
ten multi-hop cases report explicit overflow.

**Artifact:** `20261002T011212.526789Z-constraint-model-full` and its GPT-5.4 replication
`20261002T012723.643351Z-constraint-model-full`.

**Safe to use on a resume:** Yes, provided the wording does not imply 100% success across all
90 cases.

## External LongBench claim

**Measured result:** Across 98 matched successful cases, Full Phase 5 uses 687,678 context
tokens versus 1,005,038 for Full Context, a 31.58% reduction. Dataset quality is mixed:
2WikiMQA `+0.0760`, HotpotQA `-0.1753`, Passage Retrieval `-0.1200`, and RepoBench-P
`+0.0026` versus Full Context. Only the recorded HotpotQA degradation has a paired interval
excluding zero.

**Artifact:** `20261002T021250.312800Z-comparison-standard`.

**Safe to use on a resume:** The existence and scale of the evaluation suite are safe to cite.
Do not claim universal quality retention, superiority, or a combined LongBench quality score.

## Positional claim

**Measured result:** GPT-5.4-mini achieves 100% exact match and zero positional gap for all
three layouts at 4K, 8K, 16K, and 32K tokens.

**Artifact:** `20261002T032213.979841Z-layout-comparison-full`.

**Safe to use on a resume:** Only as a controlled positional evaluation with a ceiling-effect
null result. Do not claim reproduction or mitigation of *Lost in the Middle*.

## Optimizer-overhead claim

**Measured result:** Full Phase 5 p95 optimizer latency is 5.74 ms at the deterministic 80%
budget frontier and 4.28-4.43 ms in the model-backed constraint runs. On LongBench's larger
contexts, per-dataset p95 ranges from 187.95 to 325.05 ms.

**Artifacts:** `20261002T032535.450250Z-phase5-ablation-full`, the two 80% model-backed
constraint artifacts, and `20261002T021250.312800Z-comparison-standard`.

**Safe to use on a resume:** Prefer omitting latency. A universal sub-10-ms claim is not safe.

## Recommended resume section

- Engineered a model-agnostic LLM context runtime with preservation contracts, dependency and
  state-consistency constraints, omission-risk-aware allocation, validated type-aware
  transformations, explicit infeasibility, and auditable optimization traces.
- Reduced context-selection violations from **77.8% to 11.1%** (**85.7% relative**) on a
  90-case controlled benchmark at an 80% token budget; reduced model-answer violations by
  **50.0% on GPT-5.4-mini** and **66.7% on GPT-5.4** while reducing context by **32.4%**.
- Built a reproducible evaluation framework spanning a six-budget constraint frontier, a
  100-case LongBench subset, and a 4K-32K positional study, with paired bootstrap intervals,
  immutable raw artifacts, and token/latency telemetry.

The second bullet is the strongest measured result. In an interview, disclose the controlled
development-set scope, ten explicit overflows, mixed LongBench result, and positional null.
