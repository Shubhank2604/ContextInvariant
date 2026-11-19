"""Capture real local task-test outputs inside a scripted, offline agent sequence."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from build_week1_inputs import edge, record

from context_invariant import ContextType, DependencyRelation
from context_invariant.benchmarks.week1.models import (
    Checklist,
    SpanCheck,
    StudyCase,
    StudyInputs,
    required_ids,
)

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "research/week1/workflow/task"


def build() -> None:
    outputs: dict[str, object] = {}
    for name in ("retry.py", "reference_retry.py"):
        run = subprocess.run(
            [sys.executable, str(TASK / "check_task.py"), str(TASK / name)],
            check=False,
            capture_output=True,
            text=True,
        )
        outputs[name] = {
            "exit_code": run.returncode,
            "stdout": run.stdout.strip(),
            "stderr": run.stderr,
        }
    (ROOT / "research/week1/inputs/task-test-capture.json").write_text(
        json.dumps(outputs, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    cases: list[StudyCase] = []
    labels: dict[str, Checklist] = {}
    request = record(
        "original-request",
        "Fix should_retry without changing its signature. Retry only status 503; never retry 429.",
        kind=ContextType.USER_MESSAGE,
        required=True,
    )
    old = record(
        "old-config",
        '{"retry_limit":1,"retryable_status":503}',
        kind=ContextType.TASK_STATE,
    )
    code = record(
        "source-code", (TASK / "retry.py").read_text("utf-8"), kind=ContextType.CODE, required=True
    )
    failure = record(
        "earlier-test-result",
        json.dumps(outputs["retry.py"], sort_keys=True),
        kind=ContextType.TOOL_OUTPUT,
    )
    background = record(
        "background-tools",
        "\n".join(
            [
                "formatter: source files already follow the project style conventions",
                "type checker: function arguments and return values use declared types",
                "dependency inspector: local task has no third party runtime packages",
                "workspace scanner: retry module and behavioral oracle are available",
                "test collector: retry status and attempt limit checks are discovered",
                "documentation scanner: public retry interface must remain compatible",
                "environment probe: isolated interpreter started successfully",
                "build inspector: package metadata does not require modification",
                "source scanner: changes can be limited to the retry predicate",
                "review reminder: keep unrelated authentication behavior unchanged",
            ]
        ),
        kind=ContextType.TOOL_OUTPUT,
    )

    def add(case_id: str, inputs: StudyInputs, *, forbidden: tuple[str, ...] = ()) -> None:
        cases.append(StudyCase(id=case_id, inputs=inputs))
        required = required_ids(inputs)
        labels[case_id] = Checklist(
            purpose="Scripted checkpoint of one testable retry task; not a live model trajectory.",
            required="Retain unchanged: " + ", ".join(required),
            optional="Unrelated tooling and unreferenced state are optional.",
            failure="Missing request, active state, or supporting earlier test evidence; "
            "stale config; "
            "changed protected text; or budget overflow. A returned incomplete context is invalid.",
            required_ids=required,
            forbidden_ids=forbidden,
            required_spans=tuple(
                SpanCheck(item_id=item.id, text=item.content)
                for item in inputs.items
                if item.id in required
            ),
        )

    add(
        "01-investigate",
        StudyInputs(
            task="Investigate the retry predicate using the first failing behavioral test.",
            items=(request, old, code, failure, background),
            edges=(edge("original-request", "earlier-test-result", DependencyRelation.REQUIRES),),
        ),
    )
    current = record(
        "current-config",
        '{"retry_limit":2,"retryable_status":503,"request_id":"req_A17"}',
        kind=ContextType.TASK_STATE,
        canonical=True,
    )
    followup = record(
        "followup",
        "The tool configuration changed. Apply the current limit and preserve "
        "the original request.",
        kind=ContextType.USER_MESSAGE,
        required=True,
    )
    active_edges = (
        edge("followup", "original-request", DependencyRelation.REQUIRES),
        edge("followup", "current-config", DependencyRelation.REQUIRES),
        edge("original-request", "earlier-test-result", DependencyRelation.REQUIRES),
        edge("current-config", "old-config", DependencyRelation.SUPERSEDES),
    )
    active_items = (request, old, code, failure, current, followup, background)
    add(
        "02-config-changed",
        StudyInputs(
            task="Patch should_retry for the updated configuration.",
            items=active_items,
            edges=active_edges,
        ),
        forbidden=("old-config",),
    )
    final = record(
        "final-request",
        "Finish the patch, retain the earlier failing test, and verify the original no-429 rule.",
        kind=ContextType.USER_MESSAGE,
        required=True,
    )
    final_edges = (
        *active_edges,
        edge("final-request", "earlier-test-result", DependencyRelation.REQUIRES),
        edge("final-request", "original-request", DependencyRelation.REQUIRES),
    )
    final_items = (*active_items, final)
    add(
        "03-final-check",
        StudyInputs(
            task="Return a compatible patch and run the complete behavioral oracle.",
            items=final_items,
            edges=final_edges,
        ),
        forbidden=("old-config",),
    )
    transcript = record(
        "lossless-test-transcript",
        json.dumps(outputs, indent=2),
        kind=ContextType.TOOL_OUTPUT,
    )
    # Explicit stress probe of the final checkpoint, not an extra claimed agent turn.
    add(
        "04-budget-stress-probe",
        StudyInputs(
            task="Preserve the final task and the complete signed test transcript before patching.",
            items=(*final_items[:-2], final, transcript),
            edges=(
                *final_edges,
                edge("final-request", "lossless-test-transcript", DependencyRelation.REQUIRES),
            ),
        ),
        forbidden=("old-config",),
    )
    for filename, payload in (
        ("replay.json", [case.model_dump(mode="json") for case in cases]),
        (
            "replay-checklists.json",
            {key: value.model_dump(mode="json") for key, value in labels.items()},
        ),
    ):
        (ROOT / "research/week1/inputs" / filename).write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    print(
        "Captured failing/reference task tests and authored three checkpoints plus a budget probe."
    )


if __name__ == "__main__":
    build()
