# Naming and evidence provenance

ContextInvariant is the release identity of the project previously developed as ContextOS.
The rename occurs before the first public v0.5.0 package publication.

| Surface | Previous identity | Current identity |
|---|---|---|
| Project and repository | ContextOS | ContextInvariant |
| Python distribution | `contextos-runtime` | `context-invariant` |
| Python import | `contextos` | `context_invariant` |
| CLI executable | `contextos` | `context-invariant` |
| Base error | `ContextOSError` | `ContextInvariantError` |
| Benchmark schemas | `ContextOSBenchCase`, `ContextOSBenchDataset` | `ContextInvariantBenchCase`, `ContextInvariantBenchDataset` |
| Benchmark strategy | `contextos` | `context_invariant` |
| Constraint-aware trace strategy | `contextos_constraint_aware` | `context_invariant_constraint_aware` |
| Positional strategy | `contextos_position_aware` | `context_invariant_position_aware` |
| Environment version field | `contextos_version` | `context_invariant_version` |

New code uses the current imports and commands. No legacy import package or executable is
provided. The environment loader accepts either version field so historical bundles remain
readable; new manifests serialize `context_invariant_version`.

## Historical evidence

The six reviewed result bundles, Phase 4 analysis files and report, and frozen Phase 5 parity
fixture are preserved byte-for-byte. Their recorded ContextOS names describe the software
identity at execution time. Their Git SHAs and metrics must not be relabeled or regenerated
to imply that a new experiment was run after the rename.

The frozen constraint generator retains its original dataset name and per-item `source`
prefix. Those provenance strings are included in the parity fixture's selected-context hashes.
They are scientific dataset identifiers rather than current package or CLI names. The same
540 records across 90 cases and six budgets continue to be compared against that original
fixture without rewriting expected records or normalizing selected content.

Other live benchmark names, public symbols, strategy IDs, and generated trace labels use
ContextInvariant. When comparing new output to historical evidence, use the mapping above for
identity fields. Phase 5 protocol IDs such as `phase5_v040` and `phase5_full` are unchanged.
Selection, compression, constraint resolution, scoring, and budget behavior are unchanged.

## Local verification

The identity migration passed the full offline suite: 397 tests with 91.05% coverage, Ruff
lint and formatting, and strict mypy. The original 540-record runtime parity fixture passed
without modification. All 50 protected historical files were checked against their original
Git blobs; all six result bundles load successfully through the updated environment loader.

An AST comparison of all 88 source modules against the pre-rename HEAD found only the
declared identity changes and the historical environment-field compatibility change.
Fresh wheel and source-archive installations passed dependency checks, package import,
version, and offline benchmark smoke checks. Both distributions passed `twine check` and
archive-content inspection. Prior generated distributions were archived in the ignored
`out/pre-rename-dist/` directory.

The renamed GitHub CI matrix and Docker smoke job still need to run after the maintainer's
push. No paid model evaluations were required for this identity migration.

## Release transition

The package version remains 0.5.0 because the identity migration precedes package publication.
The existing v0.5.0 tag identifies the pre-rename tree until the maintainer replaces it after
verification. Earlier tags and commits remain historical records.

Repository ownership, repository renaming, remote configuration, commits, tag replacement,
and pushes are performed by the maintainer. Rename the GitHub repository to `ContextInvariant`
and update the local remote to `https://github.com/Shubhank2604/ContextInvariant.git` before
publishing the renamed release. The local checkout directory can be renamed separately.
