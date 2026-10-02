# Positional Retrieval Report

- Run ID: `348d1b7edd95158ba1df`
- Provider/model: `openai/gpt-5.4-mini-2026-03-17`
- Profile: `full`
- Predictions: 60
- Confidence intervals: not reported (one observation per experimental cell)

| Strategy | Target tokens | Accuracy | Max-min gap |
|---|---:|---:|---:|
| contextos_position_aware | 4096 | 1.0000 | 0.0000 |
| contextos_position_aware | 8192 | 1.0000 | 0.0000 |
| contextos_position_aware | 16384 | 1.0000 | 0.0000 |
| contextos_position_aware | 32768 | 1.0000 | 0.0000 |
| original_full | 4096 | 1.0000 | 0.0000 |
| original_full | 8192 | 1.0000 | 0.0000 |
| original_full | 16384 | 1.0000 | 0.0000 |
| original_full | 32768 | 1.0000 | 0.0000 |
| relevance_descending | 4096 | 1.0000 | 0.0000 |
| relevance_descending | 8192 | 1.0000 | 0.0000 |
| relevance_descending | 16384 | 1.0000 | 0.0000 |
| relevance_descending | 32768 | 1.0000 | 0.0000 |

## Provider performance

| Strategy | Calls | Mean input tokens | Total latency ms | p50 ms | p95 ms | Output tokens | Cached tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| contextos_position_aware | 20 | 15325.70 | 238961.130 | 12068.801 | 13015.394 | 254 | 302080 |
| original_full | 20 | 15325.70 | 233132.092 | 11911.599 | 13492.679 | 254 | 47360 |
| relevance_descending | 20 | 15325.70 | 234840.945 | 11807.988 | 13035.175 | 254 | 99840 |

Raw `cases.jsonl` and `predictions.jsonl` are authoritative; this report is derived.
