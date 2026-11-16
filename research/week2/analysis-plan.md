# Week 2 analysis plan v1

Prespecified before final-case author assignment or final-case access by the
implementation team. Identity and source freeze are recorded in study-lock.json.
This plan covers the original full method and metadata-matched baseline. A future
avoidable-refusal candidate is excluded until separately versioned and frozen.

- Dataset: 30 independently authored cases, ten per coding, operations and evidence
  family, with separately sealed keys; if only independent review is available,
  disclose the actual authorship and use that description. No Week 1 case reuse.
- Primary methods: `context_invariant_full` and `metadata_matched`, source behavior
  frozen at the recorded Week 1 execution revision. Use the fixed evaluator/auditor
  revision to prevent key-only exclusions and to verify replay prompts.
- Budget: floor(sum of original individually tokenized record content × 65/80/100%),
  minimum one token, output reservation zero, `cl100k_base`. Mandatory roots and their
  directed supporting closure are explicitly lossless for both methods. No representation
  substitutions. Full policy matches Week 1: balanced weights, risk on, compression on,
  ratio .5, minimum size 8, default position-aware layout and .92 semantic threshold.
- Prepare one shared input/policy/tokenizer per case/budget. Neither method receives
  scoring keys. Check source/input identity, mutation, selected text and token counts.
  No returned prompt exists on a no-context outcome. Replay prompt text and counts
  must match a reconstruction from verified inputs and saved selected records.
- Primary outcomes: valid context, invalid context and no context, with all 30 attempts
  per method/budget visible. Save exception type/message and distinguish certified
  required-budget infeasibility from avoidable selection, conflict and execution failures.
  An internal optional-closure overflow is not a global impossibility proof.
- A hard exclusion follows only from a rule supplied to both methods. Useful evidence
  recall is separate; preferences cannot change legality. Labels inconsistent with
  shared rules are a dataset/protocol defect, not a method-invalid outcome.
- Secondary descriptions: per-family and per-budget useful recall on matched-valid
  annotated cases, matched-valid token totals/means, all-valid output token means with
  explicit denominators, failure reasons and every disagreement. No-output tokens,
  reduction and useful recall remain null. Do not claim smaller context is better if
  it drops useful evidence or reflects refusal. Do not pool unlike task-quality metrics.
- Report all-attempt outcome differences and uncertainty descriptively. If paired
  intervals are reported, use 1,000 seeded percentile resamples over independent cases
  (seed 505), preserving within-case pairing and clustering all budgets/checkpoints
  from a workflow. Require at least 20 independent matched cases for the given estimate;
  report ten-case family strata descriptively. Budgets are not independent repetitions.
- Live task success, if later authorized, requires an actual method-conditioned model
  patch passing sealed behavioral tests and scope/interface checks. Freeze model snapshot,
  prompts, tools, decoding, replication and counterbalancing before live execution.
  The current lock covers offline context evaluation only; reference patches are not
  model successes. No live model access is authorized or assumed by this plan.
- Targeted exploratory ablation remains full with compression disabled and all other
  settings fixed, as proposed after Week 1. If included in final confirmatory analysis,
  add its exact method/configuration to the signed freeze before access; otherwise label
  it exploratory. No outcome-driven amendments after opening the final set.

The steward must preserve every case, including ties, baseline wins and mutual failures.
Any necessary correction after execution receives a new artifact/version and an explicit
original-versus-amended analysis. Final claims must follow these results, including nulls.
