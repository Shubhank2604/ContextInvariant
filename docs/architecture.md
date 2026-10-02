# Architecture

ContextInvariant sits between application state and an LLM provider. It accepts typed context items,
relations, and a token policy, then returns an `OptimizedContext` containing selected items,
removed items, exact budget accounting, and a versioned decision trace. It does not call the
downstream LLM during normal optimization.

## Compatibility boundary

The public `ContextOptimizer` has two paths:

- The default unconstrained path preserves the v0.4 selection behavior.
- The constraint-aware path is enabled only through `ConstraintPolicy.enforced()` and wraps the
  stable pipeline with legal-state filtering and dependency-closure convergence.

This separation keeps legacy users and the frozen research baseline reproducible. Hard relation
semantics do not alter the v0.4 `DependencyGraph`, which remains a soft, cycle-safe utility
propagation mechanism.

## Constraint-aware execution order

The implemented order is:

1. Validate unique item IDs and tokenize isolated copies.
2. Validate dependency-reference and validated-representation configuration.
3. Construct `ContextConstraintGraph` and resolve the legal candidate universe.
4. Remove illegal superseded or conflicting candidates according to explicit policy.
5. Run the stable optimizer over the remaining candidates.
6. Resolve directed closure over the selected items.
7. If closure adds required items, mark those items mandatory and rerun the stable optimizer.
8. Stop at a fixed point, or raise typed infeasibility when the required closure cannot fit.
9. Assemble the complete result, patch constraint evidence into the trace, and optionally
   persist the original items and edges atomically.

The convergence loop is bounded by the candidate count. ContextInvariant never drops a selected root
just to make its dependency closure fit.

## Stable optimization pipeline

Each stable pass performs:

1. static policy validation;
2. tokenization and mandatory-budget reservation;
3. exact deduplication;
4. guarded semantic deduplication;
5. contextual budget validation;
6. relevance, importance, recency, novelty, dependency, and type-priority scoring;
7. optional omission- and transformation-risk assessment;
8. deterministic budget allocation;
9. type-aware transformation and validation;
10. position-aware or caller-supplied layout;
11. budget and accounting invariants;
12. complete per-item trace construction.

Embedding failures are visible in trace warnings and use the deterministic provider fallback.
Caller-owned items are never mutated.

## Context model and preservation contracts

`ContextItem` represents system instructions, tool definitions, user/assistant messages, tool
outputs, retrieved documents, memory, decisions, errors, plans, code, and task state. Every item
has timezone-aware timestamps, importance, lifecycle state, legacy retention flags, and an
optional `PreservationContract`.

Contracts support:

- `optional`, `required`, and `required_if_referenced` retention;
- exact number, date, identifier, citation, and negation preservation;
- structured preservation with unique required top-level keys.

`required` maps to mandatory, non-evictable retention. `required_if_referenced` activates when a
selected relation requires the item. Unknown contract fields and inconsistent structured-key
configuration are rejected during model validation.

Items without a contract keep their legacy behavior and serialize `contract` as `null`.

## Directed hard relations

`ContextConstraintGraph` gives relations deterministic enforcement semantics:

- `B REQUIRES A`: selecting or representing `B` requires `A` or an explicitly validated
  representation of `A`.
- `B SUPERSEDES A`: current `B` replaces obsolete `A` unless the caller explicitly retains
  superseded history.
- `A CONTRADICTS B`: active contradiction requires deterministic authority, a caller override,
  or an explicit retain-both policy.
- `B DERIVED_FROM A`: the active derivation remains available as provenance.
- `RELATED_TO`: soft graph evidence only; it is not a hard constraint.

Requirement traversal is directed and cycle-safe. Strongly connected `REQUIRES` components are
reported as atomic groups.

Contradiction authority is compared in this order:

1. `metadata["canonical"] is True`;
2. numeric `authority_rank`;
3. numeric `version`;
4. numeric `source_priority`;
5. `updated_at`.

Item ID is not treated as semantic authority. A complete tie raises `UnresolvedConflict` unless
the caller supplies a winner or selects the retain-both policy.

## Deduplication and scoring

Exact deduplication runs before embeddings and removes only optional items. Semantic
deduplication compares only matching context types and defaults to cosine threshold `0.92`.
Differences in numbers, dates, identifiers, URLs, paths, code, or negation force both records to
survive even when their embeddings are similar.

Every score component is normalized to `[0, 1]`; policy weights are renormalized to sum to one.
The deterministic local provider supports tests and reproducibility. The optional Sentence
Transformers provider loads lazily, and embeddings are cached by a normalized-content SHA-256
digest.

The legacy `DependencyGraph` propagates soft score evidence bidirectionally to bounded depth.
The hard `ContextConstraintGraph` remains directed and independently decides legal state.

## Risk-aware allocation

Mandatory and required content is reserved before optional ranking, so risk scores cannot make
hard requirements removable.

For optional items, omission risk combines contract exposure, directed requirements, context
type, current/canonical metadata, and contradiction/supersession involvement. Transformation
risk combines transformability, exact-value density, negation, structured contracts, and type
fragility.

Given utility `u`, omission risk `o`, transformation risk `t`, omission coefficient `lambda`,
and transformation coefficient `gamma`:

```text
original_selection_value = (u + lambda * o) / (1 + lambda)
transformed_selection_value = max(0, original_selection_value - gamma * t)
```

Raw candidates rank by original value per token; compressed candidates rank by transformed
value per target token. Risk-aware allocation is opt-in. Its coefficients are research
parameters, not claimed optima.

The allocator applies per-type floors and maxima, followed by stable global value-density
selection. Its `AllocationPlan` partitions every optional item into direct selection, reserved
transformation, or rejection. This deterministic greedy allocator is not claimed globally
optimal.

## Type-aware transformations

`CompressionExecutor` owns reservation reuse, accounting, fallback, and final validation.
`TypeAwareCompressor` selects the initial transformation family:

| Context type | Transformation policy |
|---|---|
| System instruction and tool definition | Lossless only |
| Code | Conservative exact-line extraction |
| Tool output and error | Structured JSON pruning or line-aware extraction |
| Task state | Structured JSON pruning only |
| Retrieved document | Verbatim evidence extraction |
| Messages, memory, decisions, and plans | Verbatim sentence extraction |

Mandatory and explicitly non-compressible items remain lossless. Structured pruning retains
whole top-level values, prioritizing contract-required, task-mentioned, and operational keys.
Malformed JSON, scalar roots, arrays, and natural-language task state are not rewritten into
guessed structure. Code extraction never uses prose summarization or rewrites identifiers.

The optional LLM summarizer remains disabled by default and requires explicit injection.

## Validation and fallback

Every lossy candidate is provisional until deterministic validators check the configured
contract. Validators cover numbers, dates, identifiers, citations, negation, structured keys
and values, and caller-declared dependency references. All observed violations are returned;
validation does not stop at the first failure.

The fallback sequence is bounded:

1. attempt the preferred type-aware transformation;
2. for eligible prose, attempt deterministic extractive fallback;
3. retain the original representation if it fits;
4. otherwise reject an optional item or raise `RequiredContextOverflow` for required content.

Code and structured state do not fall back through generic prose extraction. A lossless
original selected after fallback is recorded as retained, not compressed.

## Layout

Layout is independent from selection and never changes item content. Available controls include
original order and relevance-descending order. The default position-aware layout places
mandatory system information first, high-utility evidence early, and recent task state or user
messages near the end.

## Tracing

The current trace schema is `phase5h-v2`. Each `ItemTrace` can record:

- preservation contract and final decision;
- exact/semantic duplicate evidence and utility component scores;
- activated hard relations, `required_by`, transitive closure, supersession, and conflict state;
- omission/transformation risk and allocation values;
- transformation attempts, validators, violations, fallback path, and final representation;
- final token count and position;
- conservative, evidence-backed counterfactual fields.

Counterfactual values are `null` when the execution record cannot support them; ContextInvariant does
not rerun stages to invent counterfactual evidence.

## Persistence

In-memory and SQLite stores share item, edge, query, lifecycle-tier, and delete operations.
SQLite maintains a schema version and migrates the supported version-zero layout. Saving a
constraint-aware optimization uses a single `save_context` operation so a failed write does not
leave a partial item/edge state.

Lifecycle transitions are deterministic, accept explicit overrides, and never automatically
delete archived records.

## Typed failures

Important invalid states are explicit:

- `InvalidOptimizationPolicy` for invalid budgets or policy values;
- `MandatoryContextOverflow` for legacy mandatory content that cannot fit;
- `RequiredContextOverflow` for a required contract/closure or safe original representation
  that cannot fit;
- `ConstraintUnsatisfiable` for mutually illegal constraint state;
- `UnresolvedConflict` when contradiction authority cannot be resolved;
- `UnknownDependencyReference` for missing edge, selection, representation, or reference IDs;
- typed provider, embedding, compression, and persistence errors at their respective boundaries.

The optimizer validates the complete returned result with Pydantic after trace assembly. Invalid
partial context is not returned.
