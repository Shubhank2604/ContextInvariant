# Week 2 amendment v1: developer-curated, AI-assisted evaluation

Recorded 2026-11-18 before either method runs on the private final dataset. This is
an explicit alternative to the independent-human-review arrangement preserved in
the original protocol, study lock and analysis plan. Those files and all retained
evidence remain unchanged. The original `sealed_final` mode still requires its
original independent-review attestation and independently authenticated signature.

## Reason and description

No independent human reviewer is available. A separate Data Codex chat prepares
and cross-checks the private dataset. Shubhank Chandak makes final inclusion
decisions and must approve the exact dataset, scoring keys and execution freeze
after review is complete. That dataset approval has not been given by this
amendment. Report this study as **developer-curated, AI-assisted; no independent
human review**. AI cross-checks are not independent human review. Do not claim
independent authorship, blinded curation, or an independently validated held-out
dataset. Describe actual preparation, developer access and limitations in the paper.

## Unchanged scientific comparison

The original full ContextInvariant and metadata-matched methods, source behavior,
tokenizer, scoring, failure classification and analysis remain fixed. There are 30
cases, ten per coding-agent, operations and evidence-backed-analysis family, with
at least 15 eligible, permission-reviewed real traces. Both methods receive the
same selector inputs at 65%, 80% and 100% budgets: 180 unique evaluations. Keys
stay outside selector inputs and prompts. Hard exclusions must follow shared rules.
Keep valid context, invalid context and all no-context outcomes visible; certify
infeasibility only with the existing lower-bound proof, and distinguish other
failures. Preserve matched-valid token/recall denominators and every disagreement.
The avoidable-refusal variant and compression ablation remain excluded. This
amendment does not turn the descriptive study into independent confirmatory evidence.

## Explicit alternative execution and approval record

Use `--developer-curated` and a completed `--curation-record`; do not supply the
independent seal/signature/fingerprint flags. Final case envelopes use
`data_kind="developer_curated"`, eligible origins `authored` or `real_trace`, and
separate keys with `development_only=false`. No data is edited by the runner.

The versioned curation record must disclose actual authorship, AI assistance,
provenance/permissions, cross-checks and inclusion decisions, actual timestamped
access history, no independent human reviewers, and Shubhank Chandak's approval
reference and timestamp. It binds exact and canonical input/key hashes, family and
real-trace identities, the source/dependency/configuration freeze, original lock
and analysis hashes, and this amendment's hash. Freeze first, then record approval
of those exact bytes, then execute. Do not backdate access or manufacture approval.
Developer access before freezing is allowed and must be recorded accurately;
the earlier independent-review access restrictions are not claimed for this mode.

No separate human reviewer, signing key or independently authenticated fingerprint
is required. This is an **unsigned approval record**: hashes check recorded identity
and subsequent consistency, not human independence, approval authenticity or
provenance truth. Retain the actual human approval and review/access records
privately. Reapproval and new versioned artifacts are required if bound data,
configuration or executing source changes; preserve originals and explain changes.
Do not curate, tune or discard cases based on either method's final outcomes.

## Development checks and access boundary

`--developer-curated --synthetic` is a distinct
`developer_curated_development` mode, with synthetic origins, development-only keys
and `approval_status="synthetic_test_only"`. It cannot count as final approval or
final evidence and cannot enter final mode. Synthetic tests need no real traces;
the final mode still requires at least 15. Never relabel synthetic cases as real.

Preflight verifies the freeze, hashes, data/key correspondence, family/trace counts,
approval-record fields and tokenizability before selection. The existing runner
retains all 180 rows and the read-only audit rechecks exact text/tokens, prompts,
failures, unique coverage and metrics without rerunning selection. Outputs and
audit summaries identify the developer-curated arrangement and do not claim seal
verification. Keep raw bundles restricted; they include keys and prompts.

The implementation session only tests public synthetic fixtures. The private
dataset and keys remain with the Data chat. No final evaluation or live model call
is authorized in this implementation change. Exact later execution instructions:
[DEVELOPER_CURATED_COMMAND.md](../DEVELOPER_CURATED_COMMAND.md).
