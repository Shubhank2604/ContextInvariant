"""Preserve a research claim together with the evidence it depends on."""

from datetime import UTC, datetime

from context_invariant import (
    ConstraintPolicy,
    ContextEdge,
    ContextItem,
    ContextOptimizer,
    ContextType,
    DependencyRelation,
    OptimizationPolicy,
    PreservationContract,
    RetentionPolicy,
)

timestamp = datetime(2026, 1, 1, tzinfo=UTC)
items = [
    ContextItem(
        id="question",
        content="Summarize the measured effect without overstating generality.",
        type=ContextType.USER_MESSAGE,
        created_at=timestamp,
        updated_at=timestamp,
        contract=PreservationContract(retention=RetentionPolicy.REQUIRED),
    ),
    ContextItem(
        id="measured-claim",
        content="At an 80 percent budget, selection violations fell from 77.78 to 11.11 percent.",
        type=ContextType.DECISION,
        created_at=timestamp,
        updated_at=timestamp,
        importance=1.0,
        contract=PreservationContract(
            retention=RetentionPolicy.REQUIRED,
            preserve_numbers=True,
        ),
    ),
    ContextItem(
        id="evidence",
        content="Controlled development benchmark: 90 cases; Phase 5 succeeded on 80 cases.",
        type=ContextType.RETRIEVED_DOCUMENT,
        created_at=timestamp,
        updated_at=timestamp,
        contract=PreservationContract(
            retention=RetentionPolicy.REQUIRED_IF_REFERENCED,
            preserve_numbers=True,
        ),
    ),
    ContextItem(
        id="qualification",
        content="The benchmark co-evolved with the runtime and is not a held-out evaluation.",
        type=ContextType.SYSTEM_INSTRUCTION,
        created_at=timestamp,
        updated_at=timestamp,
        contract=PreservationContract(retention=RetentionPolicy.REQUIRED),
    ),
]
edges = [
    ContextEdge(
        source_id="measured-claim",
        target_id="evidence",
        relation=DependencyRelation.REQUIRES,
        weight=1.0,
    )
]

result = ContextOptimizer(
    edges=edges,
    constraint_policy=ConstraintPolicy.enforced(),
).optimize(
    "Summarize the measured constraint-preservation result",
    items,
    OptimizationPolicy.quality(max_input_tokens=96, risk_aware_allocation=True),
)

print("selected:", ", ".join(item.id for item in result.selected_items))
print("dependency closure:", ", ".join(result.constraint_resolution.added_required_item_ids))
print("constraint passes:", result.trace.optimization_passes)
