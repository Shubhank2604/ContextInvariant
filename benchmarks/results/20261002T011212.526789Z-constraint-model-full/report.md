# Phase 5 Model-Backed Constraint Report

- Provider/model: `openai/gpt-5.4-mini-2026-03-17`
- Budget ratio: `80%`
- Temperature: `0.0`
- Predictions: 270

## Overall results

| Strategy | Successful | Task | Exact values | Answer violations | Selection violations | Mean context tokens | Reduction | Optimizer p95 ms | Provider p95 ms | Cost USD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| full_context | 90/90 | 1.0000 | 1.0000 | 0.0000 | 0.5556 | 63.6667 | 0.0000 | 0.5164 | 1742.7289 | 0.0196 |
| phase5_full | 80/90 | 1.0000 | 1.0000 | 0.1111 | 0.1111 | 42.6250 | 0.3238 | 4.2770 | 2018.8405 | 0.0147 |
| phase5_v040 | 90/90 | 0.7815 | 0.7815 | 0.2222 | 0.7778 | 46.1111 | 0.2720 | 2.4386 | 1571.8200 | 0.0167 |

## Results by failure family

| Category | Strategy | Successful | Task | Answer violations | Selection violations |
|---|---|---:|---:|---:|---:|
| dependency | full_context | 10/10 | 1.0000 | 0.0000 | 1.0000 |
| supersession | full_context | 10/10 | 1.0000 | 0.0000 | 1.0000 |
| contradiction | full_context | 10/10 | 1.0000 | 0.0000 | 1.0000 |
| exact_numeric | full_context | 10/10 | 1.0000 | 0.0000 | 0.0000 |
| identifier | full_context | 10/10 | 1.0000 | 0.0000 | 0.0000 |
| negation_policy | full_context | 10/10 | 1.0000 | 0.0000 | 1.0000 |
| tool_state | full_context | 10/10 | 1.0000 | 0.0000 | 1.0000 |
| citation_evidence | full_context | 10/10 | 1.0000 | 0.0000 | 0.0000 |
| multi_hop | full_context | 10/10 | 1.0000 | 0.0000 | 0.0000 |
| dependency | phase5_full | 10/10 | 1.0000 | 0.0000 | 0.0000 |
| supersession | phase5_full | 10/10 | 1.0000 | 0.0000 | 0.0000 |
| contradiction | phase5_full | 10/10 | 1.0000 | 0.0000 | 0.0000 |
| exact_numeric | phase5_full | 10/10 | 1.0000 | 0.0000 | 0.0000 |
| identifier | phase5_full | 10/10 | 1.0000 | 0.0000 | 0.0000 |
| negation_policy | phase5_full | 10/10 | 1.0000 | 0.0000 | 0.0000 |
| tool_state | phase5_full | 10/10 | 1.0000 | 0.0000 | 0.0000 |
| citation_evidence | phase5_full | 10/10 | 1.0000 | 0.0000 | 0.0000 |
| multi_hop | phase5_full | 0/10 | n/a | 1.0000 | 1.0000 |
| dependency | phase5_v040 | 10/10 | 1.0000 | 0.0000 | 0.0000 |
| supersession | phase5_v040 | 10/10 | 1.0000 | 0.0000 | 1.0000 |
| contradiction | phase5_v040 | 10/10 | 1.0000 | 0.0000 | 1.0000 |
| exact_numeric | phase5_v040 | 10/10 | 0.0000 | 1.0000 | 1.0000 |
| identifier | phase5_v040 | 10/10 | 0.0333 | 1.0000 | 1.0000 |
| negation_policy | phase5_v040 | 10/10 | 1.0000 | 0.0000 | 1.0000 |
| tool_state | phase5_v040 | 10/10 | 1.0000 | 0.0000 | 1.0000 |
| citation_evidence | phase5_v040 | 10/10 | 1.0000 | 0.0000 | 0.0000 |
| multi_hop | phase5_v040 | 10/10 | 1.0000 | 0.0000 | 1.0000 |

Outputs are scored by deterministic required-value recall and forbidden-value leakage. No LLM judge is used. Failed or infeasible executions count as answer violations and are never assigned invented task scores.

Raw `cases.jsonl` and `predictions.jsonl` are authoritative; this report is derived.
