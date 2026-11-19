# ContextInvariant: Constraint-Preserving Context Construction and the Limits of Token Reduction

Shubhank Chandak

First manuscript draft — 19 November 2026

## Abstract

Long-running language-model agents must select bounded context from records containing instructions, dependencies, changing state, and exact evidence. ContextInvariant makes these obligations explicit through preservation contracts and directed relationships, then combines constrained selection with validated transformations and auditable failure reporting. We evaluate the system using several distinct evidence sources: a 90-case controlled development benchmark, a 100-example LongBench subset, a ten-case diagnostic pilot, and a new 30-case developer-curated offline comparison. The controlled benchmark recorded an 85.7% relative reduction in selection violations against frozen v0.4 at an 80% budget, but that result comes from development data and does not compare against a metadata-matched selector. The new comparison gives both methods the same records, requirements, relationships, tokenizer, and budgets. Across 90 evaluations per method, both returned 76 valid contexts and 14 certified infeasibilities, with no invalid contexts, avoidable refusals, or other failures. On matched-valid cases, ContextInvariant used approximately 6.2%, 10.0%, and 12.9% fewer context tokens at the 65%, 80%, and 100% budgets, respectively. Its mean annotated optional-evidence recall was lower at every budget. These findings establish neither equal-quality compression nor a validity advantage over the simpler baseline. The new dataset was prepared and checked with AI assistance, curated by the developer, and received no independent human review. Its 180 evaluations represent 30 cases at repeated budgets, and no downstream model-answer evaluation was performed. The evidence supports explicit context constraints as an engineering interface while showing that additional optimization mechanisms can reduce context size without improving measured reliability or evidence retention.

## 1. Introduction

A coding agent may need an earlier failing test after several tool calls, an operational assistant may need the current configuration rather than a superseded value, and an analysis assistant may need the qualifier that determines whether a numerical claim is applicable. These requirements are not captured completely by asking which text is most similar to the latest task. A short, relevant record can depend on a long supporting record. A useful diagnostic line can be buried inside an oversized tool result. A value can remain syntactically intact while losing the condition that makes it meaningful.

ContextInvariant treats context construction as selection under declared constraints. Applications supply typed records, preservation contracts, and relationships such as dependencies, supersession, and contradiction. The runtime constructs a bounded context and records its selection and transformation decisions. It can also return an explicit failure when it cannot construct a context consistent with the declared requirements. These mechanisms operate before a downstream model call; preserving an instruction in context does not guarantee that a model will obey it.

The empirical question is more demanding than whether this interface improves on an earlier implementation: **given identical inputs, declared requirements, and token budgets, what does ContextInvariant add over a simpler selector?** A baseline denied the relationships or mandatory-retention metadata available to the full system would confound information access with selection sophistication. We therefore distinguish the historical comparison against frozen v0.4 from a later metadata-matched comparison that gives both methods the same hard constraints.

The resulting evidence changes the interpretation of the system. Historical controlled experiments show a large reduction in recorded violations relative to frozen v0.4, but the benchmark co-evolved with the implementation. LongBench results are mixed. A diagnostic pilot reveals useful extraction behavior as well as a baseline-winning refusal case. Most centrally, the new developer-curated comparison finds a tie in validity and feasibility: ContextInvariant returns smaller contexts but retains less annotated optional evidence at every evaluated budget. Smaller contexts cannot therefore be presented as compression at equal measured evidence quality.

This paper contributes an explicit interface for constrained context construction, a metadata-matched comparison that separates requirements from selection strategy, and an evaluation account that retains failures and reports evidence retention alongside token use. It does not claim a new globally optimal selector, a component-level causal explanation, or general superiority over simpler context management. Its main conclusion is that reliable enforcement of the declared requirements was achievable by the simpler selector on the new dataset, while the full runtime changed the balance between context size and optional-evidence retention.

## 2. Related work

Prompt compression seeks to reduce the amount of text supplied to a language model while preserving information useful to inference. Selective Context identifies and prunes redundancy in input context [Li et al., 2023](https://aclanthology.org/2023.emnlp-main.391/). LLMLingua combines budget control with coarse-to-fine prompt compression [Jiang et al., 2023](https://aclanthology.org/2023.emnlp-main.825/). LLMLingua-2 uses data distillation and a token-classification formulation for task-agnostic compression [Pan et al., 2024](https://aclanthology.org/2024.findings-acl.57/). These works motivate evaluating compression through retained information and downstream behavior, rather than token reduction alone. ContextInvariant instead exposes application-declared record obligations and checks supported transformations against those obligations. This is a description of the implemented interface, not a claim that preservation or faithful compression originated with this system.

Agent memory systems address a related but broader problem: maintaining useful state over interactions longer than a model's immediate context. MemGPT manages information across memory tiers and uses model-directed control flow to move information into and out of the active context [Packer et al., 2023](https://arxiv.org/abs/2310.08560). ContextInvariant is a context-construction component rather than an evaluated autonomous memory agent. Its present offline comparison does not measure whether a model subsequently retrieves the right record, makes a correct edit, or completes an extended workflow.

The position of relevant evidence also matters. Liu et al. found that language-model performance can depend strongly on where relevant information occurs in long contexts [Liu et al., 2024](https://aclanthology.org/2024.tacl-1.9/). ContextInvariant includes a position-aware layout policy, but the retained positional experiment described below reaches a ceiling for all tested layouts. We therefore do not claim to reproduce or mitigate the degradation reported in that work.

LongBench supplies a standardized collection of long-context tasks with task-specific evaluation [Bai et al., 2024](https://aclanthology.org/2024.acl-long.172/). Our retained evaluation uses only four datasets and 100 examples from that collection. It provides evidence about model answers on an external task distribution, whereas the new developer-curated study measures the legality and annotated evidence content of selected context without generating answers. Those evaluations answer different questions and are not combined into one quality score.

We did not run the cited compression or memory systems as baselines in the experiments reported here. Their inclusion situates the research question; it does not establish a measured ranking against them. The metadata-matched baseline is deliberately narrower: it tests whether the full runtime improves upon a relevance selector that already knows the same mandatory records and relationships.

## 3. System design

### 3.1 Records, requirements, and legal context

The application supplies a task and typed records representing instructions, messages, code, tool outputs, retrieved documents, decisions, errors, memory, or task state. Records have stable identifiers, timestamps, retention flags, and optional preservation contracts. Contracts can require retention or protect numbers, dates, identifiers, citations, negation, and structured keys. Their interpretation is explicit and limited to supported validators; they are not a general semantic correctness oracle.

Directed relationships provide additional obligations. If record B `REQUIRES` record A, retaining B requires its declared support. `SUPERSEDES` identifies obsolete state unless history retention is explicitly enabled. `CONTRADICTS` requires the configured authority rule, an application-supplied winner, or an explicit retain-both policy. Derivation relationships preserve provenance. Traversal is cycle-safe, and unresolved conflicts can produce typed failures. In particular, an arbitrary identifier is not treated as semantic authority.

The constraint-enabled path resolves the legal candidate universe before applying the stable optimization pipeline. This opt-in behavior is distinct from the compatibility path that preserves the earlier unconstrained optimizer. The system operates on copies of caller-owned records and checks the final token budget. Its legality guarantee is relative to the supplied requirements and implemented checks. Incorrect metadata, absent requirements, or incomplete annotations remain possible application errors.

### 3.2 Full ContextInvariant selection and transformation

The full runtime reserves mandatory content, performs exact and guarded semantic deduplication, and computes relevance, importance, recency, novelty, dependency, and type-priority scores. Optional omission and transformation risks influence allocation. A deterministic greedy allocator considers original and transformable representations under the available budget; it is not claimed to solve a global constrained optimum.

Transformations depend on record type. The implementation supports conservative code-line extraction, structured pruning for eligible tool or state records, and verbatim evidence or sentence extraction. Mandatory and explicitly noncompressible content remains unchanged. System instructions and tool definitions are handled losslessly. Lossy candidates are provisional until the configured validators check protected details and declared literal references. Rejection can lead to an eligible extractive fallback, original-text fallback if it fits, omission of an optional record, or a typed failure for required content. The optional model-based summarizer is not part of the evaluated offline comparison.

After selection, the constraint wrapper checks directed closure. Newly required support can be forced into a subsequent optimizer pass until the selection reaches a fixed point or the runtime raises an overflow. This procedure matters for interpreting failure: once an expensive optional root has been selected, forcing its support can cause a refusal even though some alternative valid context would fit. A runtime overflow is therefore not by itself a proof that the case is globally infeasible. The Week 1 pilot contains such an example.

Layout changes order without changing selected text. Traces record selected and removed items, available score and allocation evidence, transformations, validator outcomes, fallback decisions, relationships, token counts, and positions. Traces make concrete decisions inspectable; they do not establish what an unexecuted component ablation would have done. The [architecture description](../docs/architecture.md) documents these boundaries and implementation details.

### 3.3 Metadata-matched relevance baseline

The baseline receives the same task, records, contracts, relationships, tokenizer, and effective budget as the full runtime. It reuses low-level relationship resolution and relevance scoring, but does not use ContextInvariant's risk-aware allocation or compression. First it resolves declared supersession and conflicts and retains mandatory records with their required support. It then considers legal optional candidates in descending relevance order, with deterministic tie handling. Each proposed addition includes its supporting closure. If that bundle does not fit, the baseline skips it and tries the next candidate. Selected text remains unchanged, and output follows original record order.

This baseline is simple but not metadata-blind. Its hard-constraint handling is intentional: both methods must be given the information needed to satisfy the application contract. Because it shares low-level utilities with the full method, a tie does not prove that a separately implemented constraint engine would behave identically. It does directly test whether the full selection and transformation pipeline adds measurable value over this simpler selection rule when requirements are held constant.

## 4. Experimental setup

### 4.1 Distinct evidence sources

Table 1 separates the experiments by dataset and measured outcome. Historical artifacts retain the former project name ContextOS and strategy identifiers such as `phase5_full` and `phase5_v040`; they are not evidence of experiments rerun after the rename. The [evidence inventory](../benchmarks/results/README.md) records the retained bundles and integrity anchors.

**Table 1. Evidence sources and their scope. Counts of evaluations are repeated observations of the listed cases or conditions.**

| Experiment | Cases or conditions | Comparison and scope | Downstream answers? |
|---|---|---|---|
| Controlled development benchmark | 90 generated cases in nine failure families | Six-budget deterministic sweep; separate model-backed runs against frozen v0.4 and Full Context | Yes, in the model-backed runs |
| LongBench subset | 100 examples: 25 from each of four datasets | Full Context, frozen v0.4, full ContextInvariant; 300 attempted predictions | Yes |
| Positional diagnostic | 20 length/position conditions | Three layouts; 60 predictions | Yes, exact retrieval |
| Week 1 diagnostic pilot | Ten development cases | Two methods, three budgets; 60 evaluations | No |
| Week 1 workflow replay | Three normal checkpoints and one stress probe | Two methods; eight evaluations | No model-generated solution |
| New developer-curated study | 30 cases, ten per family | Two methods, three budgets; 180 evaluations | No |

The new study is also distinct from the 30 synthetic integration fixtures used to verify the Week 2 runner. Those fixtures repeated public pilot scenarios under family labels and were infrastructure tests, not the final developer-curated dataset. Their results are not substituted for the new study anywhere in this paper.

### 4.2 Historical controlled and external experiments

The 90-case development benchmark covers dependency, supersession, contradiction, exact numeric values, identifiers, negation/policy, tool state, citation evidence, and multi-hop requirements. It was generated and used during system development. The retained deterministic sweep evaluates 11 strategies at 25%, 35%, 50%, 65%, 80%, and 100% budgets, including cumulative variants of the constraint-aware system. Frozen v0.4 is the historical optimizer baseline, not the later metadata-matched baseline. Full Context is an unbounded selection reference rather than an equal-budget constrained method.

The model-backed controlled experiments use the recorded snapshots `gpt-5.4-mini-2026-03-17` and `gpt-5.4-2026-03-05` at temperature zero. Both have retained 80%-budget runs; the mini snapshot also has a 100%-budget run. Outputs are scored using deterministic required-value recall and forbidden-value leakage, not an LLM judge. The historical aggregates count failed executions as violations, while task scores and context-use summaries can condition on successful executions. We state those denominators explicitly rather than treating a conditional score of one as success on all 90 cases.

The LongBench subset uses sampling seed 404 and source revision `5e628be`, with 25 examples each from 2WikiMQA, HotpotQA, PassageRetrieval-en, and RepoBench-P. The recorded configuration uses an 8,000-token context budget for bounded methods, chunks of at most 256 tokens, and a 32,000-token maximum context setting. The provider is `gpt-5.4-mini-2026-03-17` at temperature zero. Dataset metrics are QA F1, retrieval score, and code similarity. We report them separately. Existing 95% percentile-bootstrap intervals use 1,000 resamples and paired strategy comparisons where at least 20 paired cases are available. We quote retained intervals rather than computing new tests or intervals for this draft.

### 4.3 Pilot and developer-curated comparison

The ten-case Week 1 pilot was designed for diagnosis and implementation checks, separately from the 90-case benchmark. Its cases include straightforward ties, optional evidence competing for space, dependency chains, stale state, exact budget boundaries, protected qualifiers, and a genuinely overflowing required closure. It retains baseline wins and mutual failures. It does not estimate performance on an independently sampled task population.

The new study contains ten coding cases, ten operations cases, and ten evidence-backed analysis cases. Fifteen are trace-derived: all ten coding cases and five operations cases. The other 15 are authored. Preparation and cross-checking used a separate Data Codex session, with Shubhank Chandak responsible for final inclusion decisions. There was **no independent human review**. The original independent-review protocol was preserved, and an explicit [developer-curated amendment](../research/week2/amendments/developer-curated-v1.md) disclosed the changed arrangement before method execution. Separate AI-assisted preparation is not presented as independent human validation.

The reported execution commit is `e59b6b194109d102773cb8417dff046c917e4006`. According to the supplied study and audit summary, neither method was run during dataset preparation, the frozen final comparison ran once, and approved hashes and the execution freeze were unchanged before and after execution. The developer-curated approval record binds source/configuration and dataset/key identities without claiming an independently authenticated signature. The scientific settings remain those of the fixed comparison; the avoidable-refusal variant and compression ablation are not included.

For each case-budget pair, the runner constructs shared prepared selector inputs and passes them to both methods. Scoring keys remain separate from selector inputs and model-facing prompts. Mandatory roots and their transitive supporting records are explicitly lossless in this comparison. Optional text may be transformed by the full method, while all baseline text is unchanged. The tokenizer is `cl100k_base`; output reservation is zero. The full policy retains the recorded risk settings, compression target ratio 0.5, minimum compressed size eight tokens, and default position-aware layout. These settings are not retuned on the new cases.

Let the original content-token count of case i be T_i, computed as the sum of token counts of individual record contents. For budget fraction b in {0.65, 0.80, 1.00}, the effective budget is:

```text
B(i, b) = max(1, floor(b × T_i)).
```

The 30 cases produce 30 × 2 × 3 = 180 method–case–budget evaluations, or 90 per method. The same case appears at three budgets, and the two methods are paired on each input. Thus there are 30 cases, not 180 independent cases. No model answers, patches, downstream task successes, or live model calls were evaluated in this new study.

### 4.4 Outcome definitions, token accounting, and audit

A **valid context** is returned text that passes the common checks for budget, mandatory retention, supporting closure, declared state consistency, and protected content. An **invalid context** is returned text that fails those checks. **No context** is recorded separately, with its reason. A no-context result is certified budget-infeasible only when the required records and their declared supporting records demonstrably cannot fit under the allowed representation rules. In the lossless required-closure setting, the certificate uses the sum of their original content-token counts as a lower bound. An avoidable selection failure requires evidence that a valid output can fit, such as the other method's valid context. Unproven selection failures, conflicts, and execution errors remain visible as other failure categories.

Hard exclusions in scoring must follow rules supplied to both selectors. Whether an optional record is useful is a separate question. A legal omission may lower useful-evidence recall without invalidating context. For each annotated case, useful recall is the proportion of annotated optional spans retained literally in their associated selected record. The reported mean is a mean of per-case recall, not a pooled fraction over all spans. Cases without useful-evidence annotations are excluded from that mean, not assigned perfect recall or zero recall.

Token comparisons condition on cases for which both methods return valid context at the given budget. Recall further conditions on that matched-valid subset having annotations. No-output token counts and useful recall remain null; refusing a case does not produce zero-token compression. Context-token counts sum record content only. Task text, record headers, and prompt scaffolding are outside that selection budget; rendered prompt text and its token count are retained and checked separately. Consequently, context-token savings are not automatically full-request token savings, latency reductions, or monetary savings.

Preflight checks record identity, source/configuration freeze, data/key correspondence, mode-specific approval evidence, counts, and tokenizability before selection. The read-only auditor verifies complete unique coverage, saved selections, token accounting, prompt reconstruction, explicit failures, and derived metrics without invoking either selector. The supplied new-study audit summary reports a pass for all 180 unique evaluations. This manuscript uses that aggregate report and audit summary; its preparation did not reopen or independently re-audit the restricted cases, keys, prompts, or raw bundles.

## 5. Results

### 5.1 Controlled development results against frozen v0.4

At an 80% budget on the 90-case development benchmark, the recorded selection-violation rate falls from 70/90 (77.78%) for frozen v0.4 to 10/90 (11.11%) for full ContextInvariant. The relative reduction is (70 − 10)/70 = 85.7%. This is a **development-benchmark result against frozen v0.4**, not an improvement over the metadata-matched baseline and not an 85.7% reduction in tokens or downstream error on the new dataset.

**Table 2. Retained 80%-budget controlled results. Full ContextInvariant completes 80 of 90 cases; frozen v0.4 completes 90. Answer-violation rates include failed executions.**

| Measure | Frozen v0.4 | Full ContextInvariant |
|---|---:|---:|
| Successful executions | 90/90 | 80/90 |
| Selection violations | 70/90 (77.78%) | 10/90 (11.11%) |
| Answer violations, mini snapshot | 20/90 (22.22%) | 10/90 (11.11%) |
| Answer violations, larger snapshot | 30/90 (33.33%) | 10/90 (11.11%) |
| Recorded mean context reduction on successful outputs | 27.20% | 32.38% |

Sources: retained [mini-model metrics](../benchmarks/results/20261002T011212.526789Z-constraint-model-full/metrics.json) and [larger-model metrics](../benchmarks/results/20261002T012723.643351Z-constraint-model-full/metrics.json).

The ten full-method failures are the multi-hop cases identified in the historical evidence as having protected closures that do not fit at 80%. On the 80 cases where both methods complete, the mini model's required-value task-score difference is +0.2458, with retained 95% interval [0.1542, 0.3375]. The corresponding larger-model difference is +0.3125 [0.2248, 0.4125]. These are conditional comparisons. All-attempt answer-violation differences are −0.1111 [−0.2222, 0.0111] and −0.2222 [−0.3444, −0.0889], respectively. The first interval includes zero. These recorded intervals do not remove development-set bias or establish effects against a metadata-matched baseline.

The retained deterministic sweep reports full-method successful-output counts of 0/90 at 25%, 35%, and 50%; 40/90 at 65%; 80/90 at 80%; and 90/90 at 100%. At 100%, the recorded selection-violation rate is zero and mean context reduction is 8.12%. Cumulative variants tie on the main 65%, 80%, and 100% outcome and retention measures. These ties do not isolate the causal contribution of contracts, relationship enforcement, transformation validation, or risk scoring. We also do not reinterpret every historical runtime overflow as a newly certified global infeasibility; the later comparison uses a more explicit outcome-accounting framework.

There is a retained reporting discrepancy: the research-readiness narrative says 50/90 successful cases at 65%, whereas both the [sweep metrics](../benchmarks/results/20261002T032535.450250Z-phase5-ablation-full/metrics.json) and generated report say 40/90. We use 40/90 here and preserve the original files. This discrepancy does not affect the 80%-budget 85.7% calculation.

### 5.2 LongBench: fewer context tokens, mixed answer quality

The retained LongBench run has 298 successful predictions among 300 attempts. Two Full Context RepoBench-P requests overflow; the bounded methods complete all 25 examples in that dataset. The resumed-run metadata retains provenance for 28 retried transient provider failures. The results do not support a universal quality-preservation claim.

**Table 3. LongBench mean task scores and retained paired differences for full ContextInvariant minus Full Context. Metrics differ across datasets and must not be averaged into one quality score.**

| Dataset and metric | Full Context | Frozen v0.4 | ContextInvariant | Paired cases | Mean difference [recorded 95% interval] |
|---|---:|---:|---:|---:|---|
| 2WikiMQA, QA F1 | 0.5844 | 0.6284 | 0.6604 | 25 | +0.0760 [−0.0360, 0.2000] |
| HotpotQA, QA F1 | 0.7470 | 0.6430 | 0.5716 | 25 | −0.1753 [−0.3400, −0.0386] |
| PassageRetrieval-en, retrieval score | 1.0000 | 0.8400 | 0.8800 | 25 | −0.1200 [−0.2410, 0.0000] |
| RepoBench-P, code similarity | 0.0578 | 0.0460 | 0.0592 | 23 | +0.0026 [−0.0509, 0.0574] |

Source: retained [LongBench report](../benchmarks/results/20261002T021250.312800Z-comparison-standard/report.md) and [metrics](../benchmarks/results/20261002T021250.312800Z-comparison-standard/metrics.json). RepoBench-P marginal means use 23 successful Full Context cases and 25 cases for each bounded method; its paired difference uses only the 23 matched cases and therefore need not equal the difference between the displayed marginal means.

On the 98 cases where Full Context and ContextInvariant both complete, ContextInvariant uses 687,678 context tokens versus 1,005,038, a 31.58% reduction. That reduction accompanies a HotpotQA decline whose recorded paired interval excludes zero. The 2WikiMQA and RepoBench-P differences do not exclude zero; the Passage Retrieval interval reaches zero. No retained ContextInvariant-versus-v0.4 task-score interval excludes zero. We report these existing intervals without adding new significance tests, multiplicity corrections, or claims about an overall benchmark winner.

Optimizer overhead is workload-dependent. The retained model-backed controlled runs report full-method p95 optimizer times of approximately 4.28–4.43 ms at 80%, while the LongBench per-dataset p95 values range from approximately 188 to 325 ms. These are local optimizer measurements, not demonstrated end-to-end speedups. Provider caching, run order, and latency variation also prevent interpreting observed token reduction as a controlled cost or latency effect.

The separate positional experiment records 100% exact retrieval in all 60 predictions across three layouts, five evidence positions, and 4K, 8K, 16K, and 32K token targets. With one observation per cell and all layouts at ceiling, it is a nondiscriminating null result. It demonstrates no measured positional advantage.

### 5.3 Week 1 pilot: extraction differences and an avoidable refusal

The Week 1 pilot contains 60 evaluations on ten development cases. At 65% and 80%, the full method returns eight valid contexts and two no-context outcomes; the baseline returns nine valid contexts and one no-context outcome. Neither returns invalid context. At each of those budgets, both methods have one certified required-budget infeasibility, and only the full method has the additional selection failure. At 100%, both return ten valid contexts.

**Table 4. Pilot token and optional-evidence comparisons on matched-valid cases. Token columns are totals, unlike the means reported for the new study in Table 6.**

| Budget | Matched-valid cases | ContextInvariant tokens | Baseline tokens | Annotated matched-valid cases | ContextInvariant mean useful recall | Baseline mean useful recall |
|---|---:|---:|---:|---:|---:|---:|
| 65% | 8 | 304 | 149 | 4 | 75% | 25% |
| 80% | 8 | 304 | 149 | 4 | 75% | 25% |
| 100% | 10 | 955 | 1,020 | 5 | 80% | 100% |

Source: retained [pilot metrics](../research/week1/evidence/20261116T051053.178379Z-metadata-matched-pilot-development/metrics.json) and [worked report](../research/week1/report.md).

The public development examples explain why these aggregate differences should not be reduced to one compression ratio. In the diagnostic-log case at 65%, the original context is 188 tokens and the budget is 122. The baseline cannot retain the unchanged 181-token optional log, so it keeps only the seven-token required policy. ContextInvariant returns 97 tokens: the policy and a 90-token verbatim excerpt containing the error code E503 and request ID `req_A17`. The full runtime retains useful optional evidence by spending more tokens than the baseline. This is neither a validity gain nor an observed downstream-answer improvement.

In the optional-bundle case, the required policy costs ten tokens. A five-token optional lead needs 100 tokens of support. At budgets 87 and 108, the baseline skips that bundle and retains a separate 20-token alternative, producing a valid 30-token context. The full runtime selects the lead and subsequently forces expensive support, then refuses. Its mandatory lower bound is only ten tokens, and the baseline's 30-token output is a concrete feasibility witness. This failure is avoidable selection failure, not certified global infeasibility. It remains part of the pilot evidence; the frozen runtime was not changed to remove it before the final comparison.

The qualifier-sensitive case illustrates the boundary of validation. A candidate preserves a latency value but loses its warm-cache qualifier. The declared literal-reference check rejects it, the original optional record does not fit at the smaller budgets, and both methods omit the record. The tie preserves legality under the specified checks without establishing that either output is sufficient for every downstream use. Other pilot differences involve repeated padding affecting semantic deduplication, which limits their realism and prevents broad component claims.

The workflow replay provides an additional implementation check, not an agent-success result. Both methods return valid context at three normal checkpoints, preserve earlier required records, and remove stale state. Both fail the stress probe with a certified requirement exceeding budget. The local buggy and reference implementations were checked against a development oracle, but no model-generated solution was evaluated. The retained audit covers 60 pilot rows and eight replay rows.

### 5.4 New developer-curated study: validity and feasibility tie

We compared ContextInvariant with the metadata-matched relevance baseline on 30 developer-curated cases spanning coding, operations, and evidence-backed analysis. Fifteen cases were derived from recorded execution traces. Dataset preparation and checking used AI assistance without independent human review. Each case was evaluated at three token budgets, producing 180 method–case–budget evaluations. The supplied subsequent audit verified the complete grid without rerunning either selector, and reported unchanged approved hashes and freeze before and after execution.

Both methods returned **76 valid contexts and 14 certified infeasibilities across their respective 90 evaluations**. Neither returned an invalid context, exhibited an avoidable refusal, or encountered another recorded failure. Across both methods, this is 152 valid contexts and 28 certified no-context outcomes among 180 evaluations. Validity and feasibility tied across the tested budgets. An observed tie on this sample is not a statistical equivalence or noninferiority result.

**Table 5. New-study valid contexts / certified infeasibilities. Every entry applies identically to both methods. Each family-budget cell contains ten attempted cases per method. Invalid contexts, avoidable refusals, and other failures are zero in every cell.**

| Family | 65% budget | 80% budget | 100% budget |
|---|---:|---:|---:|
| Coding | 8 / 2 | 10 / 0 | 10 / 0 |
| Operations | 7 / 3 | 9 / 1 | 10 / 0 |
| Evidence-backed analysis | 2 / 8 | 10 / 0 | 10 / 0 |
| Total per method | 17 / 13 | 29 / 1 | 30 / 0 |

The 14 infeasibilities per method are repeated case-budget outcomes: 13 occur at 65% and one at 80%; none occurs at 100%. They must not be described as 14 distinct cases that cannot be solved at any budget. The family counts show where the smaller budgets exclude valid outputs under the declared representation rules, but the shared aggregate does not support a record-level explanation for each private case.

### 5.5 New study: smaller contexts retain less annotated optional evidence

On matched-valid cases, ContextInvariant uses fewer record-content tokens at every budget, while retaining a smaller proportion of annotated optional evidence. Table 6 preserves the distinct denominators for tokens and recall.

**Table 6. New-study matched-valid token use and mean per-case useful recall. Cases without useful annotations are excluded from recall only. Token reductions are approximate because they are calculated from the supplied rounded means.**

| Budget | Matched-valid cases | Mean context tokens, ContextInvariant | Mean context tokens, baseline | Approximate reduction vs baseline | Annotated cases | Mean useful recall, ContextInvariant | Mean useful recall, baseline |
|---|---:|---:|---:|---:|---:|---:|---:|
| 65% | 17 | 4,830.0 | 5,148.8 | 6.2% | 17 | 23.53% | 46.08% |
| 80% | 29 | 3,517.2 | 3,908.8 | 10.0% | 28 | 39.88% | 52.38% |
| 100% | 30 | 4,170.0 | 4,790.1 | 12.9% | 29 | 91.95% | 100% |

Source for Tables 5 and 6: aggregate report and audit summary supplied by the separate Data Codex session through the study author during preparation of this manuscript. These are the new final-study aggregates, not the synthetic runner-verification results.

The reported token reductions correspond to one minus the ratio of the two displayed means. We do not reconstruct exact totals or additional precision from rounded means. The matched-valid set changes across budgets: 17 cases contribute at 65%, 29 at 80%, and 30 at 100%. Therefore, the lower mean token count at 80% than at 65% is not evidence that relaxing a budget reduces context size on a fixed set of cases. It is a comparison of different eligible subsets.

Mean useful recall is lower for ContextInvariant at every budget: 23.53% versus 46.08%, 39.88% versus 52.38%, and 91.95% versus 100%. At the full original-content budget, all 30 cases return valid contexts, but only 29 have useful-evidence annotations; the baseline retains all annotated useful spans on those cases, while ContextInvariant's mean recall remains below one. At the smaller budgets, neither method retains all annotated optional evidence.

These descriptive findings show reduced input size accompanied by reduced retention of annotated optional evidence. They do not establish equal-quality compression, improved downstream answers, or overall superiority. Optional-evidence recall is itself a proxy: the study does not demonstrate that each omitted span changes an answer, or that each retained span improves one. It does establish that the available evidence-retention measure does not remain equal as token use falls. No new significance tests or uncertainty intervals are reported for this comparison. Family-level token and recall breakdowns were not supplied and are not inferred from the aggregate means.

## 6. Discussion

### 6.1 What the metadata-matched comparison changes

The distinction between historical v0.4 and the metadata-matched baseline is central. The development comparison shows what happened when the full constraint-aware system was compared with an older optimizer that did not enforce the same hard-constraint interface. It does not establish that elaborate optimization is needed to enforce those requirements. The new baseline already retains mandatory records, follows dependencies, and resolves declared state relationships. Given that information, it ties the full runtime on validity and feasibility in the developer-curated sample.

This finding supports a narrower account of ContextInvariant's contribution. The explicit representation of context obligations, checks, traces, and failure reasons provides an engineering interface. The full selection and transformation mechanisms are an additional design choice whose benefit must be demonstrated separately. On the new dataset, the observed difference is a size–evidence trade-off, not better compliance. Developers should therefore consider the simpler selector a substantive reference point rather than assume that relevance selection necessarily violates constraints.

### 6.2 Token reduction is conditional on what survives

The pilot and final study show why token reduction alone is an incomplete objective. In the pilot's diagnostic case, extraction retains useful text that the verbatim baseline cannot afford, and the full method spends more tokens to do so. In the new study, the full method spends fewer tokens but has lower annotated optional-evidence recall at every budget. Both observations are compatible: the mechanisms can make different choices on different inputs, and the aggregate direction depends on the dataset and budget.

The correct interpretation is not that compression always helps or always harms. It is that legality, useful-evidence retention, and downstream task quality are separate outcomes. Requirements define a minimum acceptable context under a particular application contract; optional evidence may still matter to an answer. Conversely, a literal recall annotation may reward evidence whose omission has no practical consequence. Without downstream evaluation in the new study, neither a task-quality gain nor a task-quality loss is established.

The comparison also does not measure an optimal trade-off frontier. A relevance baseline that fills available space and an optimizer that deduplicates or transforms optional text need not use the same number of tokens. Comparing the two packaged methods under the same maximum budget is fair for the stated deployment question, but it does not isolate compression at equal token use or establish which method would be best at a matched evidence-retention target.

### 6.3 Failure accounting remains part of the result

A refusal must be judged against feasible alternatives. The Week 1 optional-bundle refusal was avoidable because the baseline produced a valid output within the same budget. The new study records only certified infeasibilities and no avoidable refusals. Because the runtime behavior remained frozen, this absence does not show that the known selection failure was fixed or cannot recur. It shows that the final sample did not record that failure.

Reporting token means on valid outputs and recording no-output values as null prevents refusals from appearing to be perfect compression. The same discipline applies to the historical controlled result: perfect scores on 80 completed cases should appear alongside ten failures, rather than being promoted to a 90-case success claim. These denominator distinctions are necessary to compare systems that can explicitly decline to return context.

### 6.4 Attribution and interpretation boundaries

ContextInvariant differs from the metadata-matched baseline in several linked mechanisms, including utility/risk allocation, deduplication, transformations, closure behavior, and layout. The final aggregate report does not identify which mechanism caused the token or recall differences. The historical cumulative variants also fail to distinguish their main outcome measures at the important budget points. Neither source supports component-level causal attribution.

Likewise, the external HotpotQA decline cannot be assigned to a specific component from the retained aggregate alone. A record-level account or targeted ablation would require additional evidence, not a stronger narrative. We preserve the existing methods and dataset and do not use the paper-writing process to tune the runtime or initiate such experiments.

## 7. Limitations

The new evaluation is developer-curated and AI-assisted, with no independent human review. The developer makes final inclusion decisions, and AI-assisted generation or checking can share assumptions with the evaluated implementation and annotation rules. Recording this arrangement truthfully does not eliminate selection bias, label bias, or missing requirements. The separation between Data Codex preparation and implementation work should not be interpreted as an independent human audit of scientific validity.

The sample contains only 30 cases and three ten-case families. Fifteen trace-derived cases broaden the source material beyond authored examples, but trace provenance alone does not establish representativeness or independence. The shared report does not specify whether cases share source episodes or workflows. Repeating cases at three budgets and evaluating two methods does not increase the number of independent cases to 180. The results are descriptive; a sample tie is not proof of population equivalence.

The new study evaluates returned context using declared constraints and annotated literal spans, not model answers or successful agent actions. It contains no downstream model-answer evaluation, no live model calls, and no measured end-to-end task improvement. Deterministic validators cannot guarantee preservation of all meaning, correctness of unstated requirements, resistance to prompt injection, or compliance by a downstream model. Optional-evidence recall is an annotation-dependent proxy rather than a complete measure of utility.

The older 90-case benchmark co-evolved with system development and uses generated failure families. Its 85.7% relative reduction is therefore a development result against frozen v0.4, not held-out confirmation against the metadata-matched baseline. Week 1 cases are development diagnostics and include padding-sensitive behavior. The workflow replay uses a local reference solution rather than a model-generated patch. These experiments should not be pooled into a single effectiveness estimate.

LongBench covers only 100 examples from four datasets and one model snapshot, with two Full Context overflows and recorded provider retries. Historical controlled answer experiments use two snapshots from the same provider/model family. Existing bootstrap intervals are retained experimental summaries, not evidence of broad cross-model generalization. Positional results are at ceiling, and provider caching and execution order limit causal cost or latency interpretation. LongBench-derived records also remain subject to upstream data terms.

Finally, the new-study report supplied to this writing session does not include family-specific token/recall results, exact unrounded token totals, the private bundle identifier, freeze timestamp, approved hash values, detailed trace provenance, annotation instructions beyond the protocol, or per-case selection traces. Those details are not invented here, and private records were not opened to recover them. The author-supplied audit summary reports integrity and coverage, but this manuscript preparation did not independently reproduce the final audit. Availability of a nonrevealing public provenance and hash record remains a documentation requirement for a more complete reproducibility package.

## 8. Conclusion

ContextInvariant makes context obligations explicit and couples bounded selection with transformation checks, traces, and explicit failure reporting. Its historical development benchmark records substantially fewer violations than frozen v0.4, while external model-answer results remain mixed. A later diagnostic pilot demonstrates both useful extraction and an avoidable refusal.

The new developer-curated comparison provides the most direct answer to the paper's central question. When a simpler selector receives the same records, declared requirements, relationships, and budgets, it matches ContextInvariant's observed validity and feasibility: 76 valid contexts and 14 certified infeasibilities per method, with no invalid contexts or other failures. ContextInvariant uses fewer tokens, but retains less annotated optional evidence at every budget. The study therefore supports neither an observed reliability advantage over that baseline nor equal-quality compression. Its contribution is a reproducible account of constrained context construction and its trade-offs, with the limits of the evidence kept explicit.

## References

Li, Yucheng, et al. 2023. [Compressing Context to Enhance Inference Efficiency of Large Language Models](https://aclanthology.org/2023.emnlp-main.391/). *Proceedings of EMNLP 2023*, pp. 6342–6353. DOI: 10.18653/v1/2023.emnlp-main.391.

Jiang, Huiqiang, et al. 2023. [LLMLingua: Compressing Prompts for Accelerated Inference of Large Language Models](https://aclanthology.org/2023.emnlp-main.825/). *Proceedings of EMNLP 2023*, pp. 13358–13376. DOI: 10.18653/v1/2023.emnlp-main.825.

Pan, Zhuoshi, et al. 2024. [LLMLingua-2: Data Distillation for Efficient and Faithful Task-Agnostic Prompt Compression](https://aclanthology.org/2024.findings-acl.57/). *Findings of ACL 2024*, pp. 963–981. DOI: 10.18653/v1/2024.findings-acl.57.

Packer, Charles, et al. 2023. [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560). arXiv:2310.08560. First submitted in 2023; the linked record includes a February 2024 revision.

Liu, Nelson F., et al. 2024. [Lost in the Middle: How Language Models Use Long Contexts](https://aclanthology.org/2024.tacl-1.9/). *Transactions of the Association for Computational Linguistics*, 12:157–173. DOI: 10.1162/tacl_a_00638.

Bai, Yushi, et al. 2024. [LongBench: A Bilingual, Multitask Benchmark for Long Context Understanding](https://aclanthology.org/2024.acl-long.172/). *Proceedings of ACL 2024, Volume 1: Long Papers*, pp. 3119–3137. DOI: 10.18653/v1/2024.acl-long.172.

## Appendix A. Evidence provenance and reproducibility

The manuscript was prepared from retained public evidence and the new aggregate report supplied by the study author. Bibliographic titles, authorship, years, venues, identifiers, and the related-work descriptions were checked against ACL Anthology records or the original arXiv record on 19 November 2026. No new selection run, model call, or significance test was performed to write the manuscript.

The historical implementation is identified as `f1e92ff39212ee4996273949e21d2f9caa375c20`; the frozen v0.4 reference is `4fdd88391300c56ad17af5458897ccdd08d6f7bf`. Retained artifact reports and metrics are:

- [Controlled deterministic sweep and cumulative variants](../benchmarks/results/20261002T032535.450250Z-phase5-ablation-full/report.md).
- [Mini-model controlled run, 100% budget](../benchmarks/results/20261002T010620.923753Z-constraint-model-full/report.md).
- [Mini-model controlled run, 80% budget](../benchmarks/results/20261002T011212.526789Z-constraint-model-full/report.md).
- [Larger-model controlled run, 80% budget](../benchmarks/results/20261002T012723.643351Z-constraint-model-full/report.md).
- [LongBench subset](../benchmarks/results/20261002T021250.312800Z-comparison-standard/report.md).
- [Positional diagnostic](../benchmarks/results/20261002T032213.979841Z-layout-comparison-full/report.md).

The Week 1 pilot execution commit is `d91cb078d4c803a68bc0d9b956122c92468e1688`. The [pilot report](../research/week1/report.md), [pilot metrics](../research/week1/evidence/20261116T051053.178379Z-metadata-matched-pilot-development/metrics.json), [replay report](../research/week1/evidence/20261116T051053.904393Z-week1-replay-development/report.md), and [verification record](../research/week1/verification.json) retain the development evidence. Later fixed evaluator/auditor behavior is identified by `809843ed2fe41006d86359cbf1de4798792b4aec` in the preserved Week 2 lock.

The new study reports execution commit `e59b6b194109d102773cb8417dff046c917e4006`. Its [original study lock](../research/week2/study-lock.json) and [analysis plan](../research/week2/analysis-plan.md) remain preserved alongside the [developer-curated amendment](../research/week2/amendments/developer-curated-v1.md) and [execution instructions](../research/week2/DEVELOPER_CURATED_COMMAND.md). The supplied audit summary reports 180 unique evaluations, unchanged approved hashes/freeze, and no selector reruns during audit. Exact private artifact identifiers and hashes were not included in the shared summary, so no fabricated identifiers or public download claims are supplied. Private inputs, scoring keys, rendered prompts, and raw bundles remain in steward-controlled storage.

## Appendix B. Disclosure and draft information gaps

Dataset preparation and cross-checking for the new study used AI assistance in a separate Data Codex session. Shubhank Chandak made final inclusion decisions. There was no independent human review. This first manuscript was also drafted with AI assistance; its claims and interpretation require author verification before submission. AI assistance does not constitute a human reviewer or an additional scientific author.

Family-level validity and infeasibility counts are available and appear in Table 5. Family-level token/recall breakdowns, unrounded totals, more detailed annotation/provenance documentation, and a shareable record of the actual execution freeze and approved hashes were not supplied. They remain explicit information gaps rather than reasons to substitute synthetic results, infer private details, or initiate further experiments. Affiliation, correspondence details, funding, conflicts-of-interest information, and any required institutional or data-governance statements have not been supplied for this draft.
