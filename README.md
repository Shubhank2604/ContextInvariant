# ContextOS

ContextOS is a model-agnostic Python runtime for constructing an LLM's next input context under a fixed token budget. Version 0.5.0 adds opt-in constraint-aware construction: preservation contracts, directed dependency and state-consistency rules, omission-risk-aware allocation, validated type-aware transformations, explicit infeasibility, and auditable traces.

On the 90-case controlled constraint development benchmark at an 80% budget, Full Phase 5 reduced selection violations from 77.78% to 11.11% (85.7% relative) versus frozen v0.4. Answer violations fell by 50.0% on GPT-5.4-mini and 66.7% on GPT-5.4 while context reduction increased from 27.20% to 32.38%. Ten multi-hop cases were rejected as explicitly infeasible rather than silently violating their preservation contracts.

The external result is deliberately mixed. Across 98 matched successful LongBench cases, Phase 5 reduced input context by 31.58%, but it significantly trailed Full Context on HotpotQA and did not consistently outperform frozen v0.4. A real-provider positional test achieved 100% accuracy for every layout from 4K through 32K tokens, producing a ceiling-effect null rather than reproducing *Lost in the Middle*.

The detailed build specification and live project status are maintained locally during development. Checked-in version changes are recorded in [`CHANGELOG.md`](CHANGELOG.md).

The reviewed evidence, supported claims, null results, and paper-readiness decision are recorded in [`benchmarks/reports/v0.5.0-research-readiness.md`](benchmarks/reports/v0.5.0-research-readiness.md). Six complete raw evidence bundles are retained under [`benchmarks/results/`](benchmarks/results/), and resume wording is tracked in [`docs/resume-evidence.md`](docs/resume-evidence.md).

## Development setup

ContextOS requires Python 3.11 or newer.

```bash
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy
pytest
contextos --help
```

## Python SDK

```python
from contextos import (
    ContextItem,
    ContextOptimizer,
    ContextType,
    ConstraintPolicy,
    OptimizationPolicy,
    PreservationContract,
    RetentionPolicy,
)

optimizer = ContextOptimizer(constraint_policy=ConstraintPolicy.enforced())
result = optimizer.optimize(
    "Fix authentication timeout",
    items,
    OptimizationPolicy.balanced(max_input_tokens=8_000, reserve_output_tokens=1_000),
)
```

`ContextOptimizer.optimize(task, items, policy)` is the sole authority for the final input budget. Inputs are copied; caller-owned items are not mutated.

Items may declare an explicit `PreservationContract`. Required retention, feature validation, relation-dependent closure, and safe transformation fallback are enforced by the opt-in constraint-aware pipeline. Legacy items and the default unconstrained optimizer path remain backwards compatible. See [`docs/preservation-contracts.md`](docs/preservation-contracts.md).

Directed hard-relation resolution is available separately through `ContextConstraintGraph`; it does not change the frozen v0.4 soft dependency scorer. See [`docs/hard-constraints.md`](docs/hard-constraints.md).

Compression now routes by context type, including structured JSON pruning, conservative code extraction, evidence extraction, and lossless protected types. See [`docs/type-aware-transformations.md`](docs/type-aware-transformations.md).

Lossy candidates are checked by deterministic preservation validators before acceptance, with auditable fallback paths and explicit required-context overflow. See [`docs/contract-validation.md`](docs/contract-validation.md).

Optional allocation can explicitly enable deterministic omission- and transformation-risk adjustment while hard requirements remain outside numeric ranking. Existing policy semantics remain the default for compatibility. See [`docs/risk-aware-allocation.md`](docs/risk-aware-allocation.md).

Optimization traces use a versioned Phase 5 schema with preservation contracts, activated constraint evidence, directed dependency closure, conflict state, risk values, validator outcomes, fallbacks, final representations, and conservative counterfactuals. See [`docs/constraint-aware-tracing.md`](docs/constraint-aware-tracing.md).

## CLI

```bash
contextos optimize \
  --input examples/data/coding_context.json \
  --task "Fix authentication timeout" \
  --budget 100 \
  --strategy contextos \
  --trace-json out/trace.json

contextos benchmark --profile quick
contextos benchmark run \
  --input benchmarks/datasets/contextos_bench.json \
  --output-directory benchmarks/results
contextos benchmark ablation \
  --input benchmarks/datasets/contextos_bench.json \
  --output-directory benchmarks/results
contextos benchmark constraints \
  --output-directory benchmarks/results
contextos benchmark phase5-ablation \
  --output-directory benchmarks/results
contextos benchmark dedup \
  --input benchmarks/datasets/deduplication_cases.json \
  --output-directory benchmarks/results
contextos inspect --input examples/data/coding_context.json
contextos store stats --database out/contextos.sqlite
```

Full Context, Last-N, Sliding Window, Relevance Only, and Naive Extractive remain available with `--strategy` for controlled comparisons. The naive baselines deliberately do not enforce typed mandatory retention; that limitation is emitted in their traces.

ContextOS-Bench contains 50 deterministic templated base cases across coding, research, and support/operations agents. Every run compares Full Context, Last-N, Sliding Window, Relevance Only, Naive Extractive, and ContextOS, retaining raw per-case task score, critical-information recall, token reduction, compression ratio, decision reasons, and optimizer timings. Reports include total/p50/p95 optimizer latency, embedding/compression stage time, and process peak-memory observations.

The ablation command runs full ContextOS and five single-component removals over the same cases and budgets. Artifacts record each policy override and report task-score, critical-information-recall, input-token, and p95 optimizer-latency deltas against full ContextOS.

The separate Phase 5 constraint-sensitive track deterministically generates 90 cases across dependency, supersession, contradiction, exact-value, identifier, negation, tool-state, citation, and multi-hop categories. It retains the unchanged v0.4 strategies while adding constraint violation, dependency closure, state consistency, contradiction leakage, exact-value, identifier, and citation preservation metrics.

Meaningful benchmark commands write immutable directories under `benchmarks/results/<timestamp>-<strategy>-<profile>/`. Each bundle contains `config.json`, `environment.json`, `cases.jsonl`, `predictions.jsonl`, `metrics.json`, `metrics.csv`, and `report.md`. Raw JSONL and JSON metrics are authoritative; CSV and Markdown are derived views. Generated runs remain ignored unless they pass explicit evidence review; the six v0.5.0 bundles allowlisted in `.gitignore` are the public evidence set.

## License

MIT
