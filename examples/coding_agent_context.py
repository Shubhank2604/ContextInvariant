"""Build constraint-aware context for a small coding-agent task."""

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
        id="task",
        content="Fix the authentication timeout without changing the stateless design.",
        type=ContextType.USER_MESSAGE,
        created_at=timestamp,
        updated_at=timestamp,
        contract=PreservationContract(retention=RetentionPolicy.REQUIRED),
    ),
    ContextItem(
        id="legacy-state",
        content="The authentication service uses a 15 second timeout.",
        type=ContextType.TASK_STATE,
        created_at=timestamp,
        updated_at=timestamp,
    ),
    ContextItem(
        id="current-state",
        content="The approved timeout is 30 seconds and authentication remains stateless.",
        type=ContextType.TASK_STATE,
        created_at=timestamp,
        updated_at=timestamp,
        contract=PreservationContract(preserve_numbers=True, preserve_negation=True),
    ),
    ContextItem(
        id="unrelated-log",
        content="The documentation formatter completed successfully.",
        type=ContextType.TOOL_OUTPUT,
        created_at=timestamp,
        updated_at=timestamp,
        importance=0.1,
    ),
]
edges = [
    ContextEdge(
        source_id="task",
        target_id="current-state",
        relation=DependencyRelation.REQUIRES,
        weight=1.0,
    ),
    ContextEdge(
        source_id="current-state",
        target_id="legacy-state",
        relation=DependencyRelation.SUPERSEDES,
        weight=1.0,
    ),
]

result = ContextOptimizer(
    edges=edges,
    constraint_policy=ConstraintPolicy.enforced(),
).optimize(
    "Fix the authentication timeout",
    items,
    OptimizationPolicy.balanced(max_input_tokens=48, risk_aware_allocation=True),
)

print("selected:", ", ".join(item.id for item in result.selected_items))
print("removed:", ", ".join(item.id for item in result.removed_items))
print("strategy:", result.trace.strategy)
print("tokens:", f"{result.final_token_count}/{result.trace.effective_budget}")
