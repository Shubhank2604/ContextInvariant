# Retained benchmark evidence

Generated benchmark outputs are ignored by default. The six directories allowlisted in
`.gitignore` are the reviewed evidence set for the ContextOS v0.5.0 research preview.

Each retained directory is an immutable seven-file bundle containing:

- `config.json`
- `environment.json`
- `cases.jsonl`
- `predictions.jsonl`
- `metrics.json`
- `metrics.csv`
- `report.md`

## Integrity anchors

The reviewed directories have these Git tree object IDs. They were verified unchanged from
commit `906f081`, where the evidence set was first retained, through the v0.5.0 release
candidate:

| Evidence bundle | Git tree object |
|---|---|
| `20261002T010620.923753Z-constraint-model-full` | `db05cbbde251e9e5044661dd7b8b3d4923a27bd2` |
| `20261002T011212.526789Z-constraint-model-full` | `ec78d055b0258bee8ae6603b1a272b30034a07cd` |
| `20261002T012723.643351Z-constraint-model-full` | `03dc7b320e8d43dc56f5dffdffc645ce65695330` |
| `20261002T021250.312800Z-comparison-standard` | `38f7be9ed3915d09f552bb282c9bc17f06804434` |
| `20261002T032213.979841Z-layout-comparison-full` | `a59cc5719890eb82847531ddb3ac67344d8e8302` |
| `20261002T032535.450250Z-phase5-ablation-full` | `c1caff271cde634c2f45e7f634cb9eb3cac5927c` |

For example, run
`git rev-parse HEAD:benchmarks/results/20261002T011212.526789Z-constraint-model-full` and
compare the result with the table. Git tree IDs cover filenames, file modes, file contents,
and directory structure without changing any bundle member.

The evidence inventory, interpretation, supported claims, null results, and limitations are
recorded in [`../reports/v0.5.0-research-readiness.md`](../reports/v0.5.0-research-readiness.md).
Raw cases and predictions are authoritative; Markdown and CSV files are derived views.
The retained LongBench case records remain subject to their upstream licenses and attribution
requirements; see [`THIRD_PARTY_DATA.md`](THIRD_PARTY_DATA.md).

Other local result directories may be incomplete, exploratory, superseded, or failed runs and
must not be cited merely because they exist in a developer workspace.
