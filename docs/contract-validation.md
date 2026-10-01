# Contract-validated transformations

Every lossy candidate produced by `CompressionExecutor` is validated against its item's `PreservationContract` before it can enter model-visible context.

## Validators

- `NumericPreservationValidator` checks every exact numeric token, including currency and percentages.
- `DatePreservationValidator` checks numeric and English-month date forms.
- `IdentifierPreservationValidator` checks structured, mixed-case, alphanumeric, and function identifiers.
- `CitationPreservationValidator` checks URLs, DOIs, bracketed citations, and `SRC`/`REF`/`DOC` identifiers.
- `NegationPreservationValidator` checks explicit polarity markers and their multiplicity.
- `StructuredFieldValidator` checks required JSON keys and exact values.
- `DependencyReferenceValidator` checks caller-supplied references needed by a transformed representation.

Validation is deterministic and returns every observed violation rather than stopping at the first one.

```python
result = ContractValidationEngine().validate(source_item, transformed_text)

if not result.passed:
    print(result.violations)
```

## Fallback sequence

The executor applies this bounded sequence:

1. attempt the preferred type-aware transformation;
2. for eligible prose, attempt deterministic extractive fallback when the preferred strategy was more aggressive;
3. retain the original representation if it fits the remaining compression budget and class maximum;
4. otherwise reject an optional item or raise `RequiredContextOverflow` for required retention.

Code and structured state never fall back to generic prose extraction. Required content is never silently discarded.

## Trace data

Each `ItemTrace` can now include:

- every transformation strategy attempted;
- representation type;
- individual validator names and pass/fail outcomes;
- exact violations;
- failure reasons;
- fallback path;
- final representation type.

A lossless original selected after fallback is reported as retained, not compressed, and does not increment `compressed_count`.

## Dependency references

`CompressionExecutor.execute(..., required_references={item_id: (...)})` allows the hard-relation layer to declare references that a transformed item must keep. This phase exposes the deterministic bridge; the later research optimizer composition will supply relation-derived references automatically.
