# Research foundation

ContextInvariant tests the hypothesis that treating long context as structured runtime state can
reduce critical-information and state-consistency failures under a token budget. The Phase 5
formulation combines preservation contracts, directed hard relations, omission risk, validated
transformations, and explicit infeasibility with the v0.4 scoring and allocation baseline.

## Current finding

The narrow constraint-preservation hypothesis is supported on the controlled development
benchmark. At an 80% budget, Full Phase 5 reduces selection violations from 77.78% to 11.11%
versus frozen v0.4. Model-backed answer violations fall by 50.0% on GPT-5.4-mini and 66.7% on
GPT-5.4. Context reduction improves from 27.20% to 32.38%, and every feasible Phase 5 execution
preserves its required values.

The result is not evidence that ContextInvariant is a universal context compressor. Ten multi-hop
cases are explicitly infeasible at the 80% budget, the benchmark co-evolved with the algorithm,
and external task behavior is mixed.

## External validation

[LongBench](https://aclanthology.org/2024.acl-long.172/) supplies the external task distribution.
The retained standard subset contains 25 examples each from 2WikiMQA, HotpotQA,
PassageRetrieval-en, and RepoBench-P at pinned source revision `5e628be`.

Across the 98 cases where Full Context and Full Phase 5 both succeed, Phase 5 uses 31.58% fewer
context tokens. Quality changes vary by dataset: it is numerically higher on 2WikiMQA and
RepoBench-P, lower on Passage Retrieval, and significantly lower on HotpotQA versus Full
Context. Unlike task metrics are never collapsed into one aggregate quality number.

## Positional sensitivity

The controlled experiment is inspired by *Lost in the Middle: How Language Models Use Long
Contexts* (TACL 2024, DOI `10.1162/tacl_a_00638`) but does not reproduce the paper's full
methodology. It varies exact key-value evidence across five positions and four context lengths
for original, relevance-descending, and position-aware layouts.

GPT-5.4-mini achieves 100% exact match in all 60 cells from 4K through 32K tokens. This is a
ceiling-effect null result: position-aware layout does not regress retrieval, but the experiment
does not demonstrate positional degradation or mitigation.

## Readiness decision

The evidence supports a research-preview software release, not a paper submission. The next
scientific steps are a frozen held-out constraint set, a realistic evolving-agent workload,
another provider/model family, stronger equal-budget baselines, targeted component ablations,
counterbalanced provider execution, and structured error analysis.

The complete artifact inventory, confidence intervals, supported claims, and unsupported
claims are in the
[v0.5.0 research-readiness report](../benchmarks/reports/v0.5.0-research-readiness.md).
