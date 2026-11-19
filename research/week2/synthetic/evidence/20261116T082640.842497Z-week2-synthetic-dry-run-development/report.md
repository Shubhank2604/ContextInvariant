# SYNTHETIC DEVELOPMENT DRY RUN — NOT FINAL EVIDENCE

| Family | Budget | Method | Valid | Invalid | No context | Mean valid tokens |
|---|---|---|---:|---:|---:|---:|
| all | 65% | context_invariant_full | 24 | 0 | 6 | 38 |
| all | 65% | metadata_matched | 27 | 0 | 3 | 19.88888888888889 |
| all | 80% | context_invariant_full | 24 | 0 | 6 | 38 |
| all | 80% | metadata_matched | 27 | 0 | 3 | 19.88888888888889 |
| all | 100% | context_invariant_full | 30 | 0 | 0 | 95.5 |
| all | 100% | metadata_matched | 30 | 0 | 0 | 102 |
| coding_agent | 65% | context_invariant_full | 8 | 0 | 2 | 38 |
| coding_agent | 65% | metadata_matched | 9 | 0 | 1 | 19.88888888888889 |
| coding_agent | 80% | context_invariant_full | 8 | 0 | 2 | 38 |
| coding_agent | 80% | metadata_matched | 9 | 0 | 1 | 19.88888888888889 |
| coding_agent | 100% | context_invariant_full | 10 | 0 | 0 | 95.5 |
| coding_agent | 100% | metadata_matched | 10 | 0 | 0 | 102 |
| operations | 65% | context_invariant_full | 8 | 0 | 2 | 38 |
| operations | 65% | metadata_matched | 9 | 0 | 1 | 19.88888888888889 |
| operations | 80% | context_invariant_full | 8 | 0 | 2 | 38 |
| operations | 80% | metadata_matched | 9 | 0 | 1 | 19.88888888888889 |
| operations | 100% | context_invariant_full | 10 | 0 | 0 | 95.5 |
| operations | 100% | metadata_matched | 10 | 0 | 0 | 102 |
| evidence_backed_analysis | 65% | context_invariant_full | 8 | 0 | 2 | 38 |
| evidence_backed_analysis | 65% | metadata_matched | 9 | 0 | 1 | 19.88888888888889 |
| evidence_backed_analysis | 80% | context_invariant_full | 8 | 0 | 2 | 38 |
| evidence_backed_analysis | 80% | metadata_matched | 9 | 0 | 1 | 19.88888888888889 |
| evidence_backed_analysis | 100% | context_invariant_full | 10 | 0 | 0 | 95.5 |
| evidence_backed_analysis | 100% | metadata_matched | 10 | 0 | 0 | 102 |

All attempts remain in the denominators. No-output token use and useful recall are null.
metrics.json reports certified, witnessed-avoidable and unproven failures separately,
plus matched-valid tokens and optional evidence recall overall and by family.
config.json includes preflight evidence and every disagreement. No live model calls.
