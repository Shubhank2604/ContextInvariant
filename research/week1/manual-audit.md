# Raw-record audit

The following checks were performed against the saved source records, selected text,
per-item traces and baseline bundle decisions, not only the aggregate report. No model
was asked to judge legality. The separate read-only audit rechecks every saved row.

- `simple-tie` at 65%: original sum 22, effective budget 14. Both selected `policy`
  (5 tokens) and `release` (9 tokens), unchanged. Their ordered selected content is
  identical. Formatting output does not fit. This also exercises an exact boundary.
- `exact-boundary` at 65%: direct token recount gives decision 25 plus state 40 = 65.
  Both return those two required records. Input relation is decision REQUIRES state;
  the returned context includes both. Padding is intentionally synthetic and is not
  treated as realistic task evidence.
- `required-overflow` at 65% and 80%: source decision is 20 tokens; transcript is 70.
  The edge declares the support and preparation marks both explicitly non-compressible.
  The certificate's 90-token lower bound exceeds both budgets. Each raw row has
  selected_items/context_tokens/context_reduction/useful_recall null. There is no
  zero-token “compression” observation.
- `diagnostic-log` at 65%: original log is 181 tokens and required policy is 7; budget
  is 122. Baseline bundle decision says proposed total 188, skipped over budget.
  Full excerpt is 90 tokens, twelve exact source lines (eleven background lines and
  the diagnostic line), plus policy 7 = 97. The saved text contains the full
  `error E503 request_id=req_A17: retry needs jitter.` line. Identifier and required
  reference checks passed. No evidence says the excerpt was only two lines.
- `qualifier-sensitive` at 65%: the full trace's numeric validator passes, while the
  literal-reference validator fails for the exact warm-cache qualifier. Fallback
  path is extractive then original; original does not fit. The final selected set
  contains only the unchanged seven-token policy, matching baseline. Failed provisional
  transformations are not counted as invalid final contexts.
- `optional-bundle` at 65%: original budget is floor(135 × .65) = 87. Baseline rejects
  the lead+support+policy total 115, accepts policy+alternative total 30, and rejects
  adding support to that selection (130). Full's observed pre-closure pass selected
  policy+lead; the exception reports forced policy+support total 110. Its required-only
  certificate is ten, not 110. Thus the full refusal is not a certified budget
  impossibility. The baseline's valid selection is a direct feasibility witness.
- `optional-bundle` at 100%: full's trace identifies alternative as a semantic duplicate
  of forced support. Source text inspection shows shared repeated padding dominates
  the deterministic embedding despite distinct useful phrases. Baseline retains the
  useful alternative. This observation remains in the data and limits interpretation.
- Every other differing pair was checked through `config.json`'s changed_records,
  full_decision, baseline_bundle_decisions and order fields. The report's disagreement
  table lists all 14. Noise excerpts do not become unearned useful-evidence wins;
  an order-only difference is explicitly identified.
- Replay normal checkpoints retain the unchanged source code, original request and
  earlier real failing-test output. In later checkpoints current-config replaces
  old-config. Prompt text is saved in full; prompt framing exceeds the record budget
  and is reported separately. The stress probe's required counts sum to 587 > 479.

An instrumentation rerun reproduced all 60 pilot selected records, outcomes, failure
classes and token counts exactly. Case contents and labels were not tuned after seeing
results. Explicit LF writing changed platform byte serialization only; canonical JSON
hashes identify semantic input content. See verification.json for all-output audit and
historical evidence integrity checks.
