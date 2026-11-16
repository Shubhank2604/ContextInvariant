# Packet for the independent author and data steward

Assignment is pending. This public packet contains templates and known development
examples only. Keep final case text and answer keys outside the implementation team's
checkout and account access. Do not send final cases to the method developer for help
with authoring, labeling, validation, or interpreting outcomes.

For the executable 30-case format, source freeze, signed manifest schema and detached
attestation verification, use the [offline command instructions](../OFFLINE_COMMAND.md).
That format adds family, data_kind and origin outside selector inputs. The original
templates below remain explanatory; neither a template nor a pending lock is a seal.

## Case construction

Author 30 new cases: ten evolving coding-agent cases, ten operational tool-state cases,
and ten evidence-backed analysis cases. At least 15 should derive from retainable,
sanitized realistic traces. Record provenance and permission. Do not reuse Week 1 text,
templates of its scenarios, the original 90 cases, or repeated padding. Exact tokenizer
boundary probes belong in a separate development diagnostic stratum.

The [case template](case-template.json) and [checklist template](checklist-template.json)
are single objects for explanation; the actual input file is a JSON list of case objects
and the key file is a JSON object mapping case IDs to checklists. Replace every
`REPLACE_` value and `__TEMPLATE_ONLY__` ID. Use valid timezone-aware timestamps,
stable unique IDs, genuine task text and source records. Unknown fields are rejected.
No final case may contain template markers. `development_only` is false only for actual
sealed final labels; the supplied checklist template remains true.

Write the application-supplied requirements before writing the answer key. Mandatory
retention must appear in `PreservationContract.retention=required` or the compatible
mandatory/non-evictable flags. Supporting records must have directed `REQUIRES` edges.
Use `SUPERSEDES` for obsolete state, and `CONTRADICTS` with explicit authority metadata
or an override for incompatible records. `retain_superseded=true` permits old state and
cannot justify an unconditional prohibition. A contradiction tie does not authorize
the key to choose a winner; resolve it in shared inputs or declare retain-both policy.

Every hard exclusion in `forbidden_ids` must be justified by those shared rules. Do not
forbid a merely less useful record, an irrelevant optional record, or an instruction
interpreted only by the evaluator. If a needed rule cannot be expressed by the frozen
input schema, flag the case for schema/protocol review before sealing; do not invent a
private key-only rule. Preferences about useful evidence go in `useful_spans` and are
reported separately from context legality.

`required_ids` must exactly match the mandatory roots and their transitive supporting
closure. All scored spans must occur in the annotated source record. Required spans
belong to required records; conditional qualifier spans must also be shared literal
reference requirements in `constraint_policy.dependency_references`. Use contracts for
exact numeric, identifier, date, citation, negation or structured-key preservation.
Check that the declared representation rules actually make the intended requirements
expressible. Both methods receive the same input object, never the answer key.

## Worked examples, all development-only

[development-examples.json](development-examples.json) copies three already public
Week 1 inputs and separate labels, with their source commit recorded. They are examples
of file shape and rule-to-label correspondence, not candidates for the held-out set.

- `simple-tie`: mandatory policy is hard retention. The optional release text has a
  useful span; omitting it can lower useful recall while the context remains valid.
  A key-only prohibition on that release record would be rejected.
- `stale-state`: task REQUIRES current; current SUPERSEDES old. `forbidden_ids=[old]`
  reflects a declared exclusion received by both methods. If history retention were
  enabled and there were no other exclusion, that same prohibition would be rejected.
- `qualifier-sensitive`: preserving 30 ms without its warm-cache qualifier is checked
  through an explicit literal requirement supplied to both methods. The label mirrors
  that declared requirement. An optional record may instead be omitted legally.

## Review before sealing

One reviewer verifies shared retention, edge direction, authority, explicit exclusions,
and representation rules. Another verifies exact spans, qualifiers, citations, source
provenance and behavioral test oracles. The same person may fill multiple roles only
if that is disclosed; independent review is not independent authorship. Reviewers must
not use desired method outcomes to repair labels or select cases.

Before signing, the steward may call `load_data(inputs_path.read_bytes(),
keys_path.read_bytes(), mode="sealed_final")` from
`context_invariant.benchmarks.week2.preflight` in their isolated environment. This checks
the 30-case structure, shared-rule correspondence and tokenizability of every task and
record, without running either selector or requiring a seal. It is a data check, not
signed preflight or attestation. Tokenization errors report case/record/field IDs only;
keep all validation output in the steward's restricted environment. Resolve or document
exclusions before signing; do not alter tokenizer behavior or silently sanitize traces.
Use a new execution freeze from the corrected committed source, then sign and run the
full evidence-checking preflight described in the offline command instructions.
Structural validation cannot replace human semantic review. Record every review
disagreement, resolution, exclusion and case replacement before sealing. No invented
author/reviewer identities, agreements, signatures or sample counts.

## Sealing and access order

1. Author and reviewers finish source-grounded cases and keys in the steward's restricted
   location. Keep selector inputs and answer keys in distinct files and access groups.
2. The implementation team publishes immutable method/evaluator source SHAs, dependency
   identity, the 65/80/100% budget rule, representation rules and analysis-plan hash.
   The [study lock](../study-lock.json) identifies the current comparison; any optional
   runtime candidate needs its own version and revised freeze before final access.
3. The steward validates the files privately, computes SHA-256 of each exact UTF-8 file,
   records canonical JSON hashes as well, completes the [manifest](sealing-manifest-template.json),
   and signs/timestamps it. Publish only the manifest/hashes and nonrevealing provenance
   summary while final content remains sealed. Preserve permissions and original bytes.
4. The steward checks the freeze predates final access. Prefer that the steward executes
   the frozen container/checkout themselves. The selectors receive inputs only; the
   evaluator receives keys afterward. Do not expose keys through prompts or logs sent
   back during development. Record who accesses what and when.
5. Run the final evaluation only after the signed freeze and seal. Save immutable raw
   inputs, outputs, available traces, prompts, token counts and exceptions. Verify prompt
   reconstruction and no-output accounting with the fixed auditor. Analyze with the
   frozen plan before reading exploratory results.
6. Preserve the original artifacts if a defect is discovered. Version any correction,
   explain it, and report original and amended results. Never silently rewrite Week 1
   or final evidence, retune against final cases, or replace unsuccessful cases.

SHA commands such as `Get-FileHash -Algorithm SHA256 -LiteralPath PATH` can be run by
the steward on restricted files. Do not upload those files here merely to calculate a
hash. Final-case authoring and sealing remain the designated author's/steward's work.
