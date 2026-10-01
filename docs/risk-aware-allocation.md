# Risk-aware allocation

Phase 5G adds deterministic omission and transformation risk to optional context allocation. Hard constraints remain separate: mandatory items and `REQUIRED` retention are reserved before optional items are ranked, so no numeric score can make required context removable.

## Risk signals

Omission risk combines five equally weighted, normalized signals:

- preservation or conditional-retention contracts;
- directed requirement exposure;
- a small context-type criticality tier;
- explicit current/canonical metadata;
- contradiction or supersession involvement.

Transformation risk combines:

- whether the item is transformable;
- exact-value density;
- negation presence;
- a structured-field contract;
- a small context-type fragility tier.

The signal groups are fixed and deterministic. The policy exposes only two coefficients rather than individual feature weights.

## Allocation values

Let `u` be the existing normalized composite utility, `o` omission risk, `t` transformation risk, `lambda` the omission coefficient, and `gamma` the transformation coefficient.

```text
original_selection_value = (u + lambda * o) / (1 + lambda)
transformed_selection_value = max(0, original_selection_value - gamma * t)
```

Omission risk is added because it represents loss incurred if an item is removed; retaining the item avoids that loss. Transformation risk is subtracted only when ranking compressed representations. This prevents fragile content from becoming easier to omit merely because it is unsafe to transform.

Raw allocation ranks by `original_selection_value / original_tokens`. Compression allocation ranks by `transformed_selection_value / target_tokens`. Allocation records retain the original utility, both risks, the action-specific selection value, and the density used for ranking.

## Policy and ablation

Risk-aware allocation is opt-in to preserve existing SDK and CLI semantics:

```python
policy = OptimizationPolicy.balanced(
    max_input_tokens=8_000,
    risk_aware_allocation=True,
    omission_risk_weight=0.20,
    transformation_risk_weight=0.15,
)
```

The defaults are intentionally moderate:

- `omission_risk_weight=0.20` can alter close optional-selection decisions without dominating task utility;
- `transformation_risk_weight=0.15` discourages fragile lossy representations while leaving validated transformation available;
- `risk_aware_allocation=False` is the controlled ablation and compatibility setting.

These defaults are research parameters, not measured optima. Phase 5 experiments must compare risk disabled and enabled on the same benchmark cases and budgets before making effectiveness claims.
