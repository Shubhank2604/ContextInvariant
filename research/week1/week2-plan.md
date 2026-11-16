# Week 2 lock and held-out authoring instructions

The final question remains: with the same records, declared requirements and effective
budget, what does the full method add over the metadata-matched relevance selector?
The pilot is development evidence. Its cases, templates, source text, padding patterns,
and retry workflow must not be recycled into the held-out set.

## Protocol changes prompted by the pilot, before final evaluation

1. Keep validity, useful evidence, no-output coverage, and downstream task success
   separate. Explicit overflow can arise from a greedy optional selection even when a
   valid required-only context exists. Only a valid representation-aware lower-bound
   certificate warrants the term budget infeasibility. Retain selected-optional bundle
   failures as selection failures, never silently count them as unavoidable.
2. Report useful evidence and token use on matched-valid pairs as well as all-attempt
   outcome counts. Higher evidence recall obtained by spending more tokens is not a
   token-efficiency result. No-output token use remains null.
3. Avoid repeated padding and near-identical filler in realistic cases. Those features
   induced artificial semantic duplicates in the pilot. Keep exact tokenizer-boundary
   probes in their own diagnostic stratum, excluded from headline task-quality claims.
4. Keep contracts and relationships application-authored and independent of answer keys.
   Every scored hard requirement must be visible as declared input to both methods.
   Extra answer annotations may measure useful evidence, not retroactively define legality.
5. Preserve the default runtime on this branch. The optional-closure refusal and
   padding-induced deduplication are observed system behaviors, not a mismatched baseline
   API or evaluator defect. If a later implementation changes either behavior, version
   that method, freeze it before held-out access, and keep the original result alongside it.

## Authoring, review, and separation

An author who did not tune the methods should create the final cases. If independent
authorship is unavailable, have an independent reviewer check and seal cases before
developers see their final text or results; disclose this weaker separation. Do not
claim that an independent review has already happened. Do not inspect hidden final cases
through an app, repository search, or a generated summary during development.

Proposed fixed scope: 30 cases, ten each from evolving coding-agent state, operational
tool state, and evidence-backed analysis. Include both naturally feasible and genuinely
infeasible examples; record source/provenance and editing rules. At least half should
derive from realistic traces with permission to retain them, with secrets removed before
freezing. The author records retention and support semantics before seeing either
method's outputs. Human reviewers verify usefulness and qualifiers against raw sources.
No method outcome, desired winner, or target score is an authoring criterion.

Maintain separate files for selector inputs and evaluation checklists. One reviewer
checks IDs, edge direction, authority, supersession, and literal requirements; another
checks source-grounded spans, qualifiers, citations, and oracle tests. Reconcile
disagreements in writing without looking at method outputs. Any critical fact that is
mandatory in scoring must have corresponding declared retention/support in the input.
Optional useful evidence stays optional. Check all positive spans occur exactly in
their source, all forbidden states have an explicit semantic justification, and tests
actually distinguish correct and incorrect solutions. Save rejection reasons and
inter-review agreement descriptively; do not invent reviewer statistics.

The data steward publishes a timestamped manifest of case/checklist hashes, author and
reviewer attestations, exclusions, licenses, representation rules, fixed budgets,
method source SHAs, and planned analysis. Seal final files in a separate restricted
location until execution. Developers use a separate development set for changes.
Freeze analysis code using synthetic label-corruption tests. Run the final evaluation
once after this lock; no final-case-driven changes to methods, prompts, labels, or
thresholds. If a data or implementation defect is discovered, preserve the original
artifact, record the defect, version the amendment, and report both affected analyses.

## Final comparison and one targeted ablation

Keep the 65%, 80%, 100% floor-rounded original-token budgets unless the data steward
records an amendment before unsealing. Both methods get the same prepared objects and
tokenizer. Primary comparison is full runtime versus metadata-matched baseline; frozen
v0.4 is optional and must not replace the matched baseline. Use a different model family
for later live validation if practical, with equal prompts/tool budgets, randomized or
counterbalanced order, and recorded decoding/provider configuration.

One targeted ablation: full runtime with `compression_enabled=False`, otherwise identical
contracts, graph, relevance, risk weights, deduplication and layout. On the already
authored extraction stratum, compare validity, useful diagnostic/citation retention,
coverage and matched-valid token counts at the same budgets. Prediction: the pilot's
diagnostic-log/evidence advantage may disappear when extraction is disabled. This is a
testable hypothesis, not an already measured causal conclusion. Do not tune cases to
make this happen. Treat other mechanism hypotheses as exploratory.

Keep every attempt in the outcome table. Report certified infeasibility separately from
selection, conflict, provider and execution failures. For live coding tasks, all-attempt
success requires an actual model patch passing the sealed tests, not context retention
or a reference patch. Report paired effects by task family and budget; avoid pooling
incompatible task scores. Any bootstrap analysis requires enough independent cases;
budget repetitions and multiple checkpoints from the same task are not independent
samples. Prespecify clustering by case/workflow and descriptive reporting when sample
size is insufficient. The final claim must match the measured evidence, even if the
methods tie or the baseline wins.
