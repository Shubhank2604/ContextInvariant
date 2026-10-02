# ContextInvariant benchmarks

ContextInvariant keeps research evaluation separate from the runtime API. Offline deterministic tracks
validate selection, constraints, artifacts, and evaluator behavior. Provider-backed tracks run
only when a user explicitly installs the required dependency, supplies credentials, selects a
model, and invokes the command.

Normal tests and CI never download LongBench data or spend API credits.

## Quick offline smoke test

```bash
context-invariant benchmark --profile quick
```

This runs one fixed mixed-context case through Full Context, Last-N, Sliding Window, Relevance
Only, Naive Extractive, and the integrated ContextInvariant optimizer. Selection and token outcomes are
deterministic; wall-clock timing is intentionally excluded from equality checks.

## ContextInvariant-Bench

`datasets/context_invariant_bench.json` contains 50 deterministic templated cases:

- 18 coding-agent cases;
- 16 research-agent cases;
- 16 support/operations cases.

Cases contain annotated required facts, dates, identifiers, changed-number and negation traps,
old critical evidence, recent noise, duplicate paraphrases, supersession, contradictions, and
one-/two-hop dependencies.

```bash
context-invariant benchmark run --input benchmarks/datasets/context_invariant_bench.json --output-directory out/context_invariant-bench
context-invariant benchmark ablation --input benchmarks/datasets/context_invariant_bench.json --output-directory out/phase4-ablation
context-invariant benchmark dedup --input benchmarks/datasets/deduplication_cases.json --output-directory out/dedup
```

The main runner compares the six strategies under the same case definitions. Metrics include
task-specific required-fact score, Critical Information Recall, quality retention where a valid
Full Context reference exists, input tokens, context reduction, compression, decision reasons,
and stage/runtime telemetry.

The Phase 4 ablation runs Full ContextInvariant and five single-component removals: semantic
deduplication, recency, dependency scoring, compression, and position-aware layout. Its current
deterministic result is diagnostic; the templated cases do not distinguish every component.

Regenerate the canonical dataset only when intentionally changing its versioned source:

```bash
python -m context_invariant.benchmarks.dataset --output benchmarks/datasets/context_invariant_bench.json
pytest --no-cov tests/unit/test_benchmark_schema.py
```

## Constraint-sensitive development benchmark

The Phase 5 track contains 90 deterministic cases, ten from each category:

1. dependency closure;
2. supersession;
3. contradiction;
4. exact numeric preservation;
5. identifier preservation;
6. negation and policy preservation;
7. tool state;
8. citation and evidence provenance;
9. multi-hop relations.

Every case carries machine-readable critical IDs, relations, required values, forbidden
combinations, current/stale state, identifiers, and citations as applicable. The evaluator adds
constraint violation, dependency closure, state consistency, contradiction leakage, exact-value,
identifier, and citation-preservation metrics without using an LLM judge.

```bash
context-invariant benchmark constraints --output-directory out/constraints
context-invariant benchmark phase5-ablation --output-directory out/phase5-ablation
```

The cumulative Phase 5 ablation runs the fixed 25%, 35%, 50%, 65%, 80%, and 100% budget
frontier. Zero-success points are retained as legal infeasibility; contracts are never relaxed
to manufacture coverage.

The final retained deterministic sweep is
`results/20261002T032535.450250Z-phase5-ablation-full`.

## Model-backed constraint evaluation

Install the optional provider dependency and expose `OPENAI_API_KEY` only in the process
environment or an ignored local `.env` loader. Never place a real key in `.env.example`.

```bash
python -m pip install -e ".[openai]"
context-invariant benchmark constraints-model --model MODEL_ID --budget-ratio 0.8 --output-directory out/constraint-model
```

The command compares Full Context, frozen v0.4, and Full Phase 5 through one temperature-zero
model configuration. Failed and infeasible executions remain in raw predictions, count as answer
violations, and receive no invented task score. Optional price arguments record estimated cost;
they do not affect provider billing.

The retained 80% runs are:

- `results/20261002T011212.526789Z-constraint-model-full` — GPT-5.4-mini;
- `results/20261002T012723.643351Z-constraint-model-full` — GPT-5.4.

The retained 100% GPT-5.4-mini run is
`results/20261002T010620.923753Z-constraint-model-full`.

## LongBench

`config/longbench_subset.json` pins source revision `5e628be` of `zai-org/LongBench` and selects:

- `hotpotqa` and `2wikimqa`, scored with normalized English token F1;
- `passage_retrieval_en`, scored with paragraph-number precision;
- `repobench-p`, scored with first uncommented code-line similarity.

Profiles preserve upstream IDs and are deterministic:

- `quick`: 2 cases per task, 8 total;
- `standard`: 25 cases per task, 100 total;
- `full`: every exposed row from the four configurations.

Prepare external cases explicitly:

```bash
python -m pip install -e ".[benchmark]"
context-invariant benchmark longbench prepare --config benchmarks/config/longbench_subset.json --profile standard --output out/longbench/prepared-standard.json
```

Run the Phase 5 comparison only with an explicit model and context limits:

```bash
context-invariant benchmark longbench phase5-run --prepared out/longbench/prepared-standard.json --output out/longbench-comparison --model MODEL_ID --context-budget-tokens 8192 --max-context-tokens MODEL_CONTEXT_LIMIT --minimum-request-interval-seconds 1.5
```

This compares Full Context, frozen v0.4, and Full Phase 5. It supports bounded provider retries,
request pacing, and provenance-checked resumption via `--resume-from`. Full Context overflows are
recorded, never silently truncated.

The older `longbench run` command remains available for the six-strategy Phase 4 comparison.
`longbench score` validates and scores complete externally generated ID-keyed predictions.

The retained standard Phase 5 comparison is
`results/20261002T021250.312800Z-comparison-standard`. It contains 298 successful predictions
and two legitimate Full Context RepoBench-P overflows. Across 98 matched Full Context/Phase 5
cases, Phase 5 reduces context tokens by 31.58%; quality effects are mixed and include a
statistically non-zero HotpotQA regression.

LongBench and constituent task records remain third-party material. The retained normalized
case subset is covered by [THIRD_PARTY_DATA.md](results/THIRD_PARTY_DATA.md); it is not
relicensed under the ContextInvariant MIT license.

## Controlled positional retrieval

The positional grid crosses four target lengths (4K, 8K, 16K, and 32K), five evidence positions,
and three layouts (original, relevance-descending, and ContextInvariant position-aware).

Offline plumbing check:

```bash
context-invariant benchmark positional --profile quick --provider deterministic --output-directory out/positional-quick
```

Explicit provider run:

```bash
context-invariant benchmark positional --profile full --provider openai --model MODEL_ID --max-context-tokens MODEL_CONTEXT_LIMIT --output-directory out/positional-real
```

The retained provider artifact is
`results/20261002T032213.979841Z-layout-comparison-full`. Every one of its 60 predictions is
correct, so it is a ceiling-effect null and cannot support a claim that ContextInvariant reproduced or
mitigated *Lost in the Middle*.

## Metrics and statistical reporting

Raw per-case measurements are retained. With at least 20 successful paired cases, reports use a
seeded 1,000-resample percentile-bootstrap 95% confidence interval over within-case candidate
minus reference deltas. Unlike LongBench task metrics are never averaged into a universal
quality number.

The positional grid has one observation per experimental cell, and the deduplication fixture
has ten cases, so those reports do not fabricate confidence intervals.

Provider comparisons must use the same case IDs, prompt templates, provider, model snapshot,
temperature, output limits, and evaluator. Runs from different model or decoding configurations
are not evidence of a ContextInvariant effect.

## Artifact contract

Every meaningful run writes one timestamped directory containing exactly:

```text
config.json
environment.json
cases.jsonl
predictions.jsonl
metrics.json
metrics.csv
report.md
```

Writers refuse an existing path unless its file set and bytes match. Raw cases, predictions, and
JSON metrics are authoritative; CSV and Markdown are derived views. Environment provenance
includes Python, ContextInvariant, Git SHA, operating system, relevant dependencies, embedding model,
and provider/model when applicable.

Generated result directories are ignored by default. The six allowlisted directories in
`results/` are the reviewed v0.5.0 evidence set and must remain byte-identical. Their inventory,
confidence intervals, supported claims, null results, and limitations are consolidated in the
[v0.5.0 research-readiness report](reports/v0.5.0-research-readiness.md).

## Interpretation

The controlled constraint benchmark supports a narrow reliability claim under token pressure.
LongBench does not support universal task-quality superiority, the positional run is
non-discriminating, and the current cumulative ablation does not establish a causal contribution
for every Phase 5 mechanism. See [Research](../docs/research.md) and
[Known limitations](../docs/limitations.md) before citing results.
