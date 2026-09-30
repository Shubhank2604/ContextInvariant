# Hard relational constraints

`ContextConstraintGraph` is the Phase 5 directed enforcement layer. It is separate from the v0.4 `DependencyGraph`, which remains an undirected soft-score propagation mechanism for reproducible baseline behavior.

```python
from contextos import ContextConstraintGraph

resolution = ContextConstraintGraph(items, edges).resolve(
    selected_item_ids,
    effective_budget=policy.effective_budget,
)
```

The result contains the legal selected IDs, represented source IDs, items added by dependency closure, superseded or conflicting items removed, cyclic requirement groups, unresolved conflicts explicitly retained by policy, derivation relations, and final token count.

## Relation semantics

- `B REQUIRES A`: selecting or representing `B` requires `A` or a validated representation of `A`.
- `B SUPERSEDES A`: selecting obsolete `A` replaces it with current `B`, unless historical retention is explicitly enabled.
- `A CONTRADICTS B`: an active conflict must have a deterministic winner, a caller-supplied winner, or an explicit retain-both policy. The default is a typed `UnresolvedConflict` failure.
- `B DERIVED_FROM A`: active derivation relations remain in the resolution as provenance.

Requirement traversal is directed and cycle-safe. Strongly connected `REQUIRES` components are reported as atomic requirement groups.

## Deterministic contradiction authority

Contradiction resolution compares these signals in order:

1. `metadata["canonical"] is True`;
2. numeric `metadata["authority_rank"]`;
3. numeric `metadata["version"]`;
4. numeric `metadata["source_priority"]`;
5. `updated_at` timestamp.

If every signal ties, the conflict is unresolved. Item ID is deliberately not used as semantic authority.

Callers may supply an explicit winner keyed by the two conflicting IDs:

```python
resolution = graph.resolve(
    selected_ids,
    conflict_winners={("draft", "canonical"): "canonical"},
)
```

## Validated representations

A transformed item may satisfy a dependency only through an explicit `ValidatedRepresentation` naming at least one validator. The representation itself must be selected. Phase 5F will produce these attestations from actual contract validators; Phase 5D does not pretend that arbitrary compression is validated.

## Failure semantics

- `ConstraintUnsatisfiable`: relation requirements demand mutually illegal state, a protected item would have to be removed, a representation is invalid, or token counts are unavailable.
- `RequiredContextOverflow`: the legal selected closure exceeds the supplied effective budget.
- `UnresolvedConflict`: contradictory active state has no deterministic or caller-provided resolution.
- `UnknownDependencyReference`: an edge, selection, or representation references an unknown item.

The resolver does not silently drop a selected root merely to make its closure fit.

## Integration boundary

Phase 5D provides a composable legal-state resolver and does not change the default v0.4 optimizer pipeline. This keeps the frozen baseline reproducible. Later Phase 5 work will connect legal-state resolution, type-aware transformations, validators, and omission-risk selection into the research optimizer path.
