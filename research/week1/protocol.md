# Week 1: metadata-matched development pilot

Protocol v1, fixed before implementing or running the pilot, 2026-11-15.

Question: Given the same inputs, declared requirements, and token budget, what does
ContextInvariant add over a simpler selector?

## Starting state and preservation

- Starting commit: `00a54b559f55a29bcdc61fc1663fa322d90fa466` (v0.5.0 checkout).
- Research branch: `research/metadata-matched-week1`.
- Existing untracked `ContextInvariant_Interview_QA.md` and `repo_cleanup_audit.md` belong
  to the user and are excluded from this work's commits.
- No AGENTS.md was found in the checkout or its parent. The current SDK, runner,
  evaluators, architecture, and six retained evidence bundles were inspected.
- Retained evidence and the 540-record Phase 5 parity fixture stay unchanged. The
  existing 90 cases co-evolved with the runtime; this pilot is a separate development set,
  and neither is held out. Existing controlled results and mixed LongBench results do
  not answer the new metadata-matched question.
- The historical runner uses numeric placeholders for some failed measurements and
  creates Phase 5 contracts from scoring annotations. This study uses a separate runner:
  requirements are authored inputs, never manufactured from evaluation labels, and
  no-output token use and utility are null.

## Comparison fixed up front

Primary methods: full ContextInvariant with enforced constraints, balanced utility,
omission-risk allocation, type-aware compression and validation; and a new
metadata-matched relevance selector. Frozen v0.4 (`4fdd88391300c56ad17af5458897ccdd08d6f7bf`)
is optional historical context, excluded from the primary 60 evaluations.

Both receive the same task, records, contracts, edges, conflict policy, literal-reference
requirements, tokenizer instance, and effective budget. Construct one input object per
case/budget and pass it to both; hash before and after to detect mutation. Evaluation
checklists are separate files and are never passed to either selector. No model calls.

Use `cl100k_base` tiktoken and the runtime's deterministic 1024-dimensional embeddings.
Budgets are floor(original record tokens × 0.65), floor(× 0.80), and × 1.00, minimum one.
Original tokens are the sum of individually tokenized original records, before filtering.
Output reservation is zero. These are record-content budgets; model prompt framing is
measured separately in replay. Do not imply these are complete provider request limits.

Full method configuration: standard balanced weights, compression ratio 0.5,
minimum compressed size 8 tokens, semantic threshold 0.92, risk weights 0.20/0.15,
position-aware layout, enforced constraints. These are fixed research choices, not
optimized hyperparameters. Representation substitutions are excluded in Week 1.
Mandatory roots and their declared supporting closure are lossless for both methods;
set their compressible flags false once during input preparation. Other records may
use the full runtime's validated type-aware extraction; baseline records remain verbatim.
This deliberately tests the incremental selection/transformation bundle, not a causal
claim about any one feature.

Baseline: retain mandatory roots and directed supporting closure; resolve declared
supersession/conflicts using shared low-level relation utilities; rank remaining legal
records by task relevance (descending cosine-derived score, original position then ID).
Try a candidate with its complete support. If the bundle does not fit, skip it and try
the next candidate. No risk scores, composite utility, deduplication, or compression.
Return original order and original text. Save accepted and skipped bundle decisions.

## Outcomes and evaluation

Exactly three primary outcomes: `valid_context`, `invalid_context`, `no_context`.
An empty returned selection is still evaluated, not automatically a failure to return.
Every output is checked by the same evaluator for budget, IDs, required retention,
directed dependencies, supersession, conflicts, unchanged protected content, contracts,
literal references, and separately authored required/conditional spans. Optional useful
evidence recall is a diagnostic, never silently promoted to a hard requirement.

For no output, save exception type and message. Call a failure `budget_infeasible` only
for an overflow with a certificate: mandatory roots plus their transitive supporting
records are explicitly lossless and their summed original token count exceeds budget.
Save the IDs, each token count, lower bound, budget, and representation rule. An overflow
caused by selecting optional evidence is `selection_failure`, not proved infeasibility.
Conflicts/invalid configuration and unexpected execution errors have separate reasons.
No-output runs have null selected records, token use, reduction, and useful evidence score.

Report all 10 cases per method/budget: valid, invalid, and no output, with reason counts.
Report successful-output token means separately (and matched-valid token totals), so
refusal cannot appear as compression. Save raw text, IDs, counts, hashes, traces, and
every disagreement. Distinguish validity, useful evidence, content/order, and token-only
differences. Keep baseline wins and mutual failures. No significance tests on 10
development cases; no generalization or downstream task-success claim.

## Development cases and audit

Author 10 cases before execution: simple tie, mandatory dependency chain, stale state,
authority-resolved conflict, competing optional bundles, extractable tool diagnostic,
qualifier-sensitive shortening, exact-value evidence, exact budget boundary, and true
required-closure overflow. Document required/optional records and failure conditions in
separate checklists. These cases are diagnostic, not sampled estimates of prevalence.

Audit one tie, one failure, an exact-boundary run, and every disagreement from saved
source and selected text. Fix implementation mismatches and rerun the whole pilot;
record protocol amendments before final evaluation. Do not tune cases to create a win.

## Replay and Week 2

Deliver one offline multi-turn coding replay with testable behavior, changed tool state,
stale-state removal, and a later dependency on earlier evidence. Save both methods'
model-facing prompts per checkpoint; test missing-requirement versus explicit-overflow
classification. A known reference patch can validate the task oracle, but is not a
model success. Live smoke is optional and omitted absent established model access.
Week 2 will freeze a separately authored/reviewed held-out set and labels before any
final evaluation or further implementation tuning. Record a targeted ablation only
after the pilot identifies a concrete mechanism.
