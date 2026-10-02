# Changelog

All notable changes to ContextInvariant are documented in this file. The project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

No unreleased changes.

## [0.5.0] - 2026-10-02

### Added

- Opt-in preservation contracts for retention, numeric, date, identifier, citation, negation,
  and structured-key requirements.
- Directed hard-constraint resolution for `REQUIRES`, `SUPERSEDES`, `CONTRADICTS`, and
  `DERIVED_FROM`, including cycle-safe closure, explicit conflict policy, caller overrides,
  validated representations, and typed infeasibility.
- Type-aware transformations for code, structured state, evidence, conversation, and tool
  output, with deterministic contract validation and bounded safe fallback.
- Optional omission- and transformation-risk-aware allocation while keeping required content
  outside numeric ranking.
- Versioned constraint-aware traces containing closure, conflict, risk, validation, fallback,
  representation, and conservative counterfactual evidence.
- A 90-case constraint-sensitive development benchmark, six-budget feasibility sweep,
  cumulative ablations, deterministic model-answer scoring, and model-backed provider runner.
- Direct Full Context/frozen-v0.4/Full-Phase-5 LongBench comparison with request pacing, bounded
  retry, provenance-checked resume, cost telemetry, and explicit context-overflow status.
- Frozen runtime-parity fixture, public constraint-policy controls, atomic persistence hardening,
  and inline typing marker.
- Six reviewed immutable research-evidence bundles, third-party dataset notices, and a complete
  research-readiness report.
- Executable offline coding/research examples and README snippet integration tests.

### Changed

- Renamed the project to ContextInvariant before publication: distribution `context-invariant`,
  import package `context_invariant`, and CLI `context-invariant`. Updated source, public
  symbols, examples, documentation, Docker, and CI. Historical evidence remains unchanged;
  legacy environment manifests remain readable.
- Package version advanced to `0.5.0` and public documentation consolidated around the README,
  architecture, benchmarking, research, limitations, and evidence ledger.
- Release automation now includes Linux 3.11-3.13, Windows, wheel/sdist installation, and Docker
  smoke-test jobs while keeping paid benchmarks manual-only.

### Fixed

- Preserved token-limited provider responses, separated answer targets from selection
  constraints, and made provider pacing patches portable.
- Hardened graph interfaces, dependency-reference validation, constraint telemetry, idempotent
  LongBench resume, and item/edge persistence atomicity.

## [0.4.0] - 2026-09-12

### Added

- ContextInvariant-Bench with 50 deterministic coding, research, and support/operations cases and
  annotated critical-information requirements.
- Controlled 4K-32K positional retrieval, a pinned four-task LongBench subset, and deterministic
  LongBench-compatible evaluators.
- Relevance Only and Naive Extractive baselines alongside Full Context, Last-N, Sliding Window,
  and ContextInvariant.
- Six-variant component ablation, deterministic paired bootstrap intervals, and performance
  telemetry for optimizer, embedding, compression, provider, tokens, and process memory.
- Immutable seven-file experiment bundles with source revision, environment, configuration, raw
  cases, predictions, JSON/CSV metrics, and derived reports.
- Public benchmark, limitations, evidence, and v0.4.0 result documentation.

## [0.3.0] - 2026-08-31

### Added

- Configurable semantic deduplication threshold with a conservative default of `0.92`.
- Deterministic and optional sentence-transformer embedding providers with normalized-content
  caching.
- Mandatory-aware exact and semantic deduplication with numeric, date, identifier, path, URL,
  code, and negation safety guards.
- Provider-driven relevance and novelty scoring.
- Complete serializable optimization policies with quality, balanced, and economy presets.
- Importance, recency, type-priority, dependency-propagation, and composite scoring.
- Typed dependency edges with bounded cycle-safe traversal and unknown-reference failures.
- Deterministic class-floor, class-maximum, value-density, and compression-reservation allocation.
- Safe extractive, tool-output, no-op, and optional LLM-summary compression contracts.
- Original-order, relevance-descending, and position-aware layout strategies.
- Versioned SQLite persistence, migrations, lifecycle transitions, and the integrated
  `ContextOptimizer` pipeline with per-item traces.
- Public optimizer CLI, input inspection, store statistics, benchmark comparison, and initial
  regression fixtures.

## [0.2.0] - 2026-08-30

### Added

- Token-budget `OptimizationPolicy` foundation.
- Full Context, Last-N, and Sliding Window deterministic baselines.
- Per-item and whole-run optimization traces.
- Baseline CLI and deterministic quick benchmark smoke profile.

## [0.1.0] - 2026-08-30

### Added

- Python package configuration and development tooling.
- Validated typed context model.
- Token-counting abstraction and tiktoken implementation.
- In-memory context store.
- CLI skeleton, documentation skeleton, tests, and CI.

### Fixed

- Bound NumPy below 2.5 so Python 3.11-targeted mypy checks do not parse Python 3.12-only NumPy
  stubs.
- Updated GitHub checkout and Python setup actions to their Node.js 24 releases.
