# Phase 5I Cumulative Ablation and Budget Sweep

## Scope and provenance

This report records the deterministic Phase 5 cumulative ablation at Git SHA
`3f42c96b35c49cf2ab4221fef731fc38b31eae6a`, compared with the frozen v0.4
baseline at `4fdd88391300c56ad17af5458897ccdd08d6f7bf`.

The run uses ContextOS-Bench Constraints generator version `1.2.0`: 90 cases,
six token-budget ratios, and eleven strategies, producing 5,940 raw
measurements. The authoritative local seven-file bundle is
`benchmarks/results/20261001T180015.015202Z-phase5-ablation-full`; the tracked
machine-readable summary is `phase5i_ablation_summary.json`.

Every constrained strategy at a given frontier point received the same case,
token budget, deterministic embedding provider, optimizer configuration, and
evaluator. Full Context remains an explicitly unbounded quality reference.

## Reliability-efficiency frontier

Task score, CIR, reduction, and latency are calculated over successful
executions. Constraint violation rate includes all 90 cases, so a typed
fail-closed overflow counts as an unsatisfied case rather than disappearing
from the reliability result.

| Budget | v0.4 success | Phase 5 success | v0.4 task | Phase 5 task | v0.4 CIR | Phase 5 CIR | v0.4 reduction | Phase 5 reduction | v0.4 violations | Phase 5 violations | Phase 5 p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 25% | 0/90 | 0/90 | n/a | n/a | n/a | n/a | n/a | n/a | 100.0% | 100.0% | n/a |
| 35% | 10/90 | 0/90 | 0.0% | n/a | 0.0% | n/a | 64.5% | n/a | 100.0% | 100.0% | n/a |
| 50% | 90/90 | 0/90 | 18.5% | n/a | 13.0% | n/a | 57.8% | n/a | 100.0% | 100.0% | n/a |
| 65% | 90/90 | 50/90 | 55.9% | 100.0% | 55.6% | 100.0% | 40.3% | 37.5% | 66.7% | 44.4% | 7.363 ms |
| 80% | 90/90 | 80/90 | 78.1% | 100.0% | 77.8% | 100.0% | 27.9% | 33.1% | 77.8% | 11.1% | 13.533 ms |
| 100% | 90/90 | 90/90 | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 8.4% | 55.6% | 0.0% | 7.905 ms |

The zero-success Phase 5 points at 25%, 35%, and 50% are deliberate typed
infeasibility results: mandatory instructions plus the declared legal context
cannot fit. Phase 5 does not silently drop required state to manufacture a
successful score.

At 100% budget, Full Phase 5 achieves 100% dependency closure, state
consistency, exact-value preservation, identifier preservation, and citation
preservation, with zero contradiction leakage. v0.4 also obtains perfect task
score and CIR at this budget, but violates 50 of 90 legal-context contracts.
This confirms that recall alone cannot detect stale or contradictory context.

## Paired results against v0.4

The existing seeded Phase 4 bootstrap system was reused. Task, CIR, and input
token deltas use cases where both strategies succeeded. Constraint-violation
deltas use all 90 paired cases.

| Budget | Shared successes | Task delta (95% CI) | CIR delta (95% CI) | Input-token delta (95% CI) | Violation-rate delta (95% CI) |
|---:|---:|---:|---:|---:|---:|
| 65% | 50 | +0.400 (+0.280, +0.540) | +0.400 (+0.260, +0.520) | +1.60 (+0.96, +2.28) | -0.222 (-0.300, -0.144) |
| 80% | 80 | +0.246 (+0.150, +0.338) | +0.250 (+0.163, +0.350) | -3.25 (-3.99, -2.59) | -0.667 (-0.767, -0.556) |
| 100% | 90 | 0.000 (0.000, 0.000) | 0.000 (0.000, 0.000) | -4.78 (-5.66, -3.84) | -0.556 (-0.656, -0.455) |

The 80% frontier is the strongest observed tradeoff: 33.1% mean context
reduction, perfect task score and CIR on 80 feasible cases, and a 66.7
percentage-point reduction in violations relative to v0.4. The remaining ten
cases are explicit overflows, not silent constraint violations.

The v0.4 violation rate increases from 66.7% at 65% budget to 77.8% at 80%.
The additional budget admits more stale or contradictory material. This is a
controlled example of why more retained context is not necessarily safer.

## Component findings

- Hard relations supply the principal correctness gain on this benchmark by
  enforcing dependency closure, supersession, and contradiction resolution.
- Preservation contracts add fail-closed retention semantics. At budgets where
  authoritative state cannot fit, the contract variant emits typed overflow
  instead of returning an apparently successful context missing that state.
- Validated transformations and omission-risk scoring show no additional
  aggregate selection gain once hard constraints dominate these short,
  deterministic fixtures. This is a measured null result, not evidence that
  those components are generally unnecessary.
- Full Phase 5 and the omission-risk variant match on all 540 case-budget
  pairs, confirming that Phase 5H tracing does not alter selection behavior.

## Limitations

- These are templated deterministic stress cases, not a production-distribution
  estimate.
- Task and CIR means exclude typed overflows; they must always be read with the
  success count and all-case violation rate.
- The fixtures are too short and constraint-dominated to establish a marginal
  benefit for validators or risk scoring.
- Latency is local Windows wall-clock telemetry from one run and should not be
  treated as a portable performance guarantee.
- No downstream language model was invoked. The result establishes deterministic
  context legality, not model answer quality.

## Stop/go decision

**Go to Phase 5J.** Deterministic hard-constraint behavior is stable, the full
budget reaches zero violations, infeasible budgets fail explicitly, bootstrap
comparisons are reproducible, and tracing is behavior-preserving. Phase 5J must
now test whether these deterministic improvements translate to downstream model
behavior without overstating what LongBench measures.
