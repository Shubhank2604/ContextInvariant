# Offline development pilot

| Budget | Method | Valid | Invalid | No context | Mean valid tokens |
|---|---|---|---|---|---|
| 65% | context_invariant_full | 8 | 0 | 2 | 38 |
| 65% | metadata_matched | 9 | 0 | 1 | 19.88888888888889 |
| 80% | context_invariant_full | 8 | 0 | 2 | 38 |
| 80% | metadata_matched | 9 | 0 | 1 | 19.88888888888889 |
| 100% | context_invariant_full | 10 | 0 | 0 | 95.5 |
| 100% | metadata_matched | 10 | 0 | 0 | 102 |

No-output runs have null token use and are visible in totals. See metrics.json for matched-valid token totals and failure reasons, config.json for every disagreement, and predictions.jsonl for text, traces and certificates. This development pilot makes no held-out or downstream-success claim.
