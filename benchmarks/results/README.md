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

The evidence inventory, interpretation, supported claims, null results, and limitations are
recorded in [`../reports/v0.5.0-research-readiness.md`](../reports/v0.5.0-research-readiness.md).
Raw cases and predictions are authoritative; Markdown and CSV files are derived views.
The retained LongBench case records remain subject to their upstream licenses and attribution
requirements; see [`THIRD_PARTY_DATA.md`](THIRD_PARTY_DATA.md).

Other local result directories may be incomplete, exploratory, superseded, or failed runs and
must not be cited merely because they exist in a developer workspace.
