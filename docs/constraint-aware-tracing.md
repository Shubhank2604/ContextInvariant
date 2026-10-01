# Constraint-aware optimization traces

Phase 5H promotes optimization traces from selection logs into versioned research and debugging artifacts. New traces declare `schema_version="phase5h-v1"`; older payloads remain readable because every new field has a compatibility default.

## Per-item evidence

An `ItemTrace` now records, where applicable:

- the complete preservation contract;
- activated hard-relation edges;
- items that require the current item;
- directed transitive requirement closure;
- items superseded by the current item;
- observed contradiction status;
- omission risk, transformation risk, and both risk-adjusted allocation values;
- every transformation attempt;
- validators executed and every validator result in attempt order;
- fallback use and path;
- final representation type and position;
- conservative constraint and contract counterfactuals.

The original nested `transformation_attempts` remain authoritative. The flattened validator fields make common inspection and analysis possible without discarding repeated fail/pass outcomes across fallbacks.

## Declared evidence versus enforcement

`ConstraintTraceIndex` derives factual relation evidence from the declared directed graph and the actual final selected IDs. A relation is considered activated when its source or conflict endpoint is selected according to that relation's direction. `RELATED_TO` remains a soft relation and is not reported as a hard constraint.

The field `constraint_resolution_applied` prevents an important ambiguity:

- `false` means the trace describes declared/activated constraints but does not claim that Phase 5D resolution produced the selection;
- `true` means a concrete `ConstraintResolution` was supplied, enabling resolver-backed outcomes and counterfactuals.

This distinction prevents debugging metadata from being presented as enforcement evidence.

## Conflict states

Contradiction traces distinguish:

- `not_involved`;
- `inactive`;
- `co_retained`;
- `retained_counterpart_removed`;
- `removed_counterpart_retained`;
- `unresolved`.

The states describe the observed selection. They do not silently choose a winner.

## Counterfactual policy

Counterfactuals are emitted only when the existing execution record provides direct evidence:

- `would_have_been_removed_without_constraints=true` only for an item listed in a supplied resolution's `added_required_item_ids`;
- `would_have_been_compressed_without_contract=true` only when a non-dependency preservation validator rejected a candidate transformation;
- `false` is used for the compression counterfactual when contract validators ran and all passed;
- otherwise the value is `null`, meaning unknown rather than guessed.

No optimizer stages are rerun to manufacture counterfactuals.
