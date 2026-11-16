# Offline development replay

| Budget | Method | Valid | Invalid | No context | Mean valid tokens |
|---|---|---|---|---|---|
| 80% | context_invariant_full | 3 | 0 | 1 | 309 |
| 80% | metadata_matched | 3 | 0 | 1 | 309 |

No-output runs have null token use and are visible in totals. See metrics.json for matched-valid token totals and failure reasons, config.json for every disagreement, and predictions.jsonl for text, traces and certificates. This development pilot makes no held-out or downstream-success claim.
