# Preservation contracts

`PreservationContract` gives a context item explicit, machine-readable preservation semantics without removing the legacy `mandatory`, `compressible`, or `evictable` fields.

```python
from contextos import ContextItem, PreservationContract, RetentionPolicy

item = ContextItem(
    # existing ContextItem fields...
    contract=PreservationContract(
        retention=RetentionPolicy.REQUIRED,
        preserve_numbers=True,
        preserve_identifiers=True,
        preserve_structure=True,
        required_keys=("status", "id", "amount"),
    ),
)
```

## Supported declarations

- `retention`: `optional`, `required`, or `required_if_referenced`.
- `preserve_numbers`: preserve numeric values exactly.
- `preserve_dates`: preserve dates exactly.
- `preserve_identifiers`: preserve identifiers exactly.
- `preserve_citations`: preserve citation and source identifiers.
- `preserve_negation`: preserve explicit polarity.
- `preserve_structure` with `required_keys`: preserve named structured fields.

Structured preservation requires at least one unique, nonblank key. The model rejects unknown options and inconsistent structured-key configurations.

## Phase 5C enforcement boundary

`retention=required` maps to `mandatory=True` and `evictable=False`, so the existing optimizer reserves the item and raises the existing overflow error if its original representation cannot fit. Explicit legacy flags that contradict required retention are rejected.

`required_if_referenced` is represented but is not yet activated by graph edges. Hard directed relation semantics are Phase 5D work.

The remaining feature flags define deterministic obligations but do not yet authorize lossy transformation. Phase 5F adds validators and fallback behavior for transformed representations. Until then, required items follow the existing lossless mandatory path. This separation prevents a declaration model from being mistaken for validation that has not been implemented.

Legacy items without a contract retain their existing behavior and serialized contract value of `null`.
