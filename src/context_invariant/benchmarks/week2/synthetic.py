"""Thirty family-labelled pipeline fixtures derived only from public Week 1 development data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from context_invariant.benchmarks.week2.models import FAMILIES, Week2Case
from context_invariant.benchmarks.week2.preflight import ROOT, json_bytes


def write_synthetic(output_directory: Path, root: Path = ROOT) -> None:
    source = json.loads((root / "research/week1/inputs/pilot.json").read_bytes())
    keys = json.loads((root / "research/week1/inputs/checklists.json").read_bytes())
    cases: list[dict[str, Any]] = []
    labels: dict[str, Any] = {}
    for family in FAMILIES:
        for original in source:
            case_id = f"synthetic-{family}-{original['id']}"
            inputs = json.loads(json.dumps(original["inputs"]))
            inputs["task"] = f"Synthetic {family} pipeline fixture. {inputs['task']}"
            case = Week2Case(
                id=case_id,
                inputs=inputs,
                family=family,
                data_kind="synthetic_development",
                origin="synthetic",
            )
            cases.append(case.model_dump(mode="json"))
            labels[case_id] = {**keys[original["id"]], "development_only": True}
    output_directory.mkdir(parents=True, exist_ok=True)
    for name, value in (("cases.json", cases), ("keys.json", labels)):
        with (output_directory / name).open("xb") as output:
            output.write(json_bytes(value))
