"""Author the Week 1 development fixtures without running either selector.

Run from the repository root with PYTHONPATH=src. These are development cases,
not a held-out dataset generator. Checklists are written separately from inputs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from context_invariant import (
    ConstraintPolicy,
    ContextEdge,
    ContextItem,
    ContextType,
    DependencyReferenceRequirement,
    DependencyRelation,
    PreservationContract,
    RetentionPolicy,
)
from context_invariant.benchmarks.week1.models import Checklist, SpanCheck, StudyCase, StudyInputs
from context_invariant.tokenization import TiktokenTokenizer

ROOT = Path(__file__).resolve().parents[1] / "research" / "week1" / "inputs"
NOW = datetime(2026, 11, 15, tzinfo=UTC)
TOKENIZER = TiktokenTokenizer()


def padded(text: str, tokens: int) -> str:
    while TOKENIZER.count_tokens(text) < tokens:
        text += " padding"
    if TOKENIZER.count_tokens(text) != tokens:
        raise ValueError("fixture padding did not reach the exact token boundary")
    return text


def record(
    item_id: str,
    text: str,
    *,
    kind: ContextType = ContextType.MEMORY,
    required: bool = False,
    compressible: bool = True,
    contract: PreservationContract | None = None,
    canonical: bool = False,
) -> ContextItem:
    return ContextItem(
        id=item_id,
        content=text,
        type=kind,
        created_at=NOW,
        updated_at=NOW,
        compressible=compressible,
        contract=contract
        or PreservationContract(
            retention=RetentionPolicy.REQUIRED if required else RetentionPolicy.OPTIONAL
        ),
        metadata={"canonical": canonical},
    )


def edge(source: str, target: str, relation: DependencyRelation) -> ContextEdge:
    return ContextEdge(source_id=source, target_id=target, relation=relation, weight=1.0)


def build() -> tuple[list[StudyCase], dict[str, Checklist]]:
    cases: list[StudyCase] = []
    labels: dict[str, Checklist] = {}

    def add(
        case_id: str,
        task: str,
        items: list[ContextItem],
        required: tuple[str, ...],
        purpose: str,
        *,
        edges: tuple[ContextEdge, ...] = (),
        forbidden: tuple[str, ...] = (),
        useful: tuple[SpanCheck, ...] = (),
        references: tuple[DependencyReferenceRequirement, ...] = (),
        conditional: tuple[SpanCheck, ...] = (),
    ) -> None:
        cases.append(
            StudyCase(
                id=case_id,
                inputs=StudyInputs(
                    task=task,
                    items=tuple(items),
                    edges=edges,
                    constraint_policy=ConstraintPolicy.enforced(dependency_references=references),
                ),
            )
        )
        labels[case_id] = Checklist(
            purpose=purpose,
            required="Retain unchanged: " + ", ".join(required),
            optional="Other records are optional; useful spans are diagnostic, not hard labels.",
            failure="Missing required record/support, stale/conflicting state, changed protected "
            "detail, failed declared literal preservation, or token overflow is invalid. "
            "Exceptions are no-context outcomes, classified by an independent lower bound.",
            required_ids=required,
            forbidden_ids=forbidden,
            required_spans=tuple(
                SpanCheck(item_id=item.id, text=item.content)
                for item in items
                if item.id in required
            ),
            conditional_spans=conditional,
            useful_spans=useful,
        )

    add(
        "simple-tie",
        "Summarize the approved release policy.",
        [
            record("policy", "Preserve approved release behavior.", required=True),
            record("release", "The approved release is ready for review.", compressible=False),
            record(
                "noise", "The unrelated formatting job completed this morning.", compressible=False
            ),
        ],
        ("policy",),
        "Straightforward verbatim relevance case; methods should agree when space permits.",
        useful=(SpanCheck(item_id="release", text="The approved release is ready for review."),),
    )
    add(
        "dependency-chain",
        "Keep the deployment decision and its supporting test and configuration.",
        [
            record("decision", "Deploy only after the signed test result.", required=True),
            record("test", "The signed test uses config_C12."),
            record("config", "config_C12 disables destructive migration."),
            record("noise", padded("Unrelated formatter output.", 60), compressible=False),
        ],
        ("decision", "test", "config"),
        "Required transitive closure should survive regardless of relevance.",
        edges=(
            edge("decision", "test", DependencyRelation.REQUIRES),
            edge("test", "config", DependencyRelation.REQUIRES),
        ),
    )
    add(
        "stale-state",
        "Use the current authentication timeout.",
        [
            record("task", "Use the approved current timeout.", required=True),
            record("old", "The timeout was 15 seconds.", kind=ContextType.TASK_STATE),
            record("current", "The approved timeout is 30 seconds.", kind=ContextType.TASK_STATE),
            record("noise", padded("Formatting output is unrelated.", 45)),
        ],
        ("task", "current"),
        "Superseded state must not leak into the returned context.",
        edges=(
            edge("task", "current", DependencyRelation.REQUIRES),
            edge("current", "old", DependencyRelation.SUPERSEDES),
        ),
        forbidden=("old",),
    )
    add(
        "canonical-conflict",
        "Follow the canonical maintenance policy.",
        [
            record("task", "Apply the canonical maintenance policy.", required=True),
            record("canonical", "Maintenance writes are disabled.", canonical=True),
            record("rumor", "Maintenance writes are enabled."),
            record("noise", padded("Unrelated style output.", 40)),
        ],
        ("task", "canonical"),
        "Both methods receive identical authority metadata; neither should keep the rumor.",
        edges=(
            edge("task", "canonical", DependencyRelation.REQUIRES),
            edge("canonical", "rumor", DependencyRelation.CONTRADICTS),
        ),
        forbidden=("rumor",),
    )
    add(
        "optional-bundle",
        "retry diagnostic",
        [
            record("policy", padded("Preserve authentication behavior.", 10), required=True),
            record("lead", padded("retry diagnostic", 5), compressible=False),
            record(
                "support", padded("Source telemetry supporting the lead.", 100), compressible=False
            ),
            record(
                "alternative",
                padded("A useful independent retry diagnosis.", 20),
                compressible=False,
            ),
        ],
        ("policy",),
        "An appealing optional lead has expensive support. Skip the whole bundle if it "
        "does not fit. A full-runtime refusal here is a selection failure, "
        "not global infeasibility.",
        edges=(edge("lead", "support", DependencyRelation.REQUIRES),),
        useful=(SpanCheck(item_id="alternative", text="A useful independent retry diagnosis."),),
    )
    diagnostic = "error E503 request_id=req_A17: retry needs jitter."
    log = "\n".join(
        ["background cache warm operation completed successfully."] * 12
        + [diagnostic]
        + ["background cache warm operation completed successfully."] * 12
    )
    add(
        "diagnostic-log",
        "Diagnose retry failure for req_A17 and retain the error code.",
        [
            record("policy", "Preserve the existing authentication interface.", required=True),
            record(
                "log",
                log,
                kind=ContextType.TOOL_OUTPUT,
                contract=PreservationContract(preserve_identifiers=True),
            ),
        ],
        ("policy",),
        "The full log may not fit; a verbatim diagnostic excerpt could retain useful evidence.",
        references=(DependencyReferenceRequirement(item_id="log", references=("req_A17",)),),
        useful=(SpanCheck(item_id="log", text=diagnostic),),
    )
    qualifier = "This threshold applies only to warm-cache requests."
    add(
        "qualifier-sensitive",
        "Review the timeout threshold.",
        [
            record("policy", "Do not generalize a qualified threshold.", required=True),
            record(
                "measurement",
                "The timeout threshold is 30 ms. "
                + qualifier
                + (
                    " Timeout threshold diagnostics remain unverified "
                    "under current workload conditions."
                )
                * 12,
                contract=PreservationContract(preserve_numbers=True),
            ),
        ],
        ("policy",),
        "Keeping 30 ms while dropping its warm-cache qualifier is invalid if the record survives.",
        references=(
            DependencyReferenceRequirement(item_id="measurement", references=(qualifier,)),
        ),
        conditional=(SpanCheck(item_id="measurement", text=qualifier),),
        useful=(
            SpanCheck(item_id="measurement", text="The timeout threshold is 30 ms. " + qualifier),
        ),
    )
    fact = "DOC-Z9 sets limit 64 for tenant_B42; see https://example.org/policy."
    add(
        "exact-evidence",
        "Find the tenant limit and policy citation.",
        [
            record("policy", "Keep exact evidence and its source attribution.", required=True),
            record(
                "document",
                fact + " Background history describes unrelated maintenance procedures." * 14,
                kind=ContextType.RETRIEVED_DOCUMENT,
                contract=PreservationContract(
                    preserve_numbers=True, preserve_identifiers=True, preserve_citations=True
                ),
            ),
        ],
        ("policy",),
        "Exact values and citation must survive when the optional document is transformed.",
        useful=(SpanCheck(item_id="document", text=fact),),
    )
    add(
        "exact-boundary",
        "Keep the required decision and supporting state at the exact boundary.",
        [
            record("decision", padded("Keep the signed deployment decision.", 25), required=True),
            record("state", padded("The approved state supports the decision.", 40)),
            record("noise", padded("Unrelated commentary.", 35), compressible=False),
        ],
        ("decision", "state"),
        "Exactly 100 original tokens; required closure is exactly the 65-token budget.",
        edges=(edge("decision", "state", DependencyRelation.REQUIRES),),
    )
    add(
        "required-overflow",
        "Retain the required decision and its lossless supporting transcript.",
        [
            record(
                "decision", padded("Keep this required operational decision.", 20), required=True
            ),
            record(
                "transcript", padded("The signed transcript is the declared supporting record.", 70)
            ),
            record("noise", padded("Unrelated output.", 10), compressible=False),
        ],
        ("decision", "transcript"),
        "Exactly 100 original tokens; 90 required lossless tokens cannot fit at 65 or 80.",
        edges=(edge("decision", "transcript", DependencyRelation.REQUIRES),),
    )
    return cases, labels


if __name__ == "__main__":
    cases, labels = build()
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "pilot.json").write_text(
        json.dumps([case.model_dump(mode="json") for case in cases], indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (ROOT / "checklists.json").write_text(
        json.dumps({key: value.model_dump(mode="json") for key, value in labels.items()}, indent=2)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Authored {len(cases)} development cases and separate checklists in {ROOT}")
