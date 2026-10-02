"""Public package surface for ContextInvariant."""

from context_invariant.baselines import (
    FullContextBaseline,
    LastNTokensBaseline,
    NaiveExtractiveBaseline,
    RelevanceOnlyBaseline,
    SlidingWindowBaseline,
)
from context_invariant.budget import AllocationPlan
from context_invariant.config import OptimizationPolicy
from context_invariant.constraints import (
    ConflictOverride,
    ConflictPolicy,
    ConstraintPolicy,
    ConstraintResolution,
    ContextConstraintGraph,
    DependencyReferenceRequirement,
    ValidatedRepresentation,
)
from context_invariant.contracts import PreservationContract, RetentionPolicy
from context_invariant.models import (
    ContextEdge,
    ContextItem,
    ContextType,
    DependencyRelation,
    LifecycleTier,
)
from context_invariant.optimizer import ContextOptimizer
from context_invariant.scoring import RiskAssessment, assess_context_risk
from context_invariant.trace import (
    ConflictTraceStatus,
    ConstraintTraceEvidence,
    ConstraintTraceIndex,
    OptimizationTrace,
    OptimizedContext,
    TransformationTraceEvidence,
    summarize_transformation_trace,
)
from context_invariant.validation import ContractValidationEngine, ValidationResult

__all__ = [
    "AllocationPlan",
    "ConflictOverride",
    "ConflictPolicy",
    "ConflictTraceStatus",
    "ConstraintPolicy",
    "ConstraintResolution",
    "ConstraintTraceEvidence",
    "ConstraintTraceIndex",
    "ContextConstraintGraph",
    "ContextEdge",
    "ContextItem",
    "ContextOptimizer",
    "ContextType",
    "ContractValidationEngine",
    "DependencyReferenceRequirement",
    "DependencyRelation",
    "FullContextBaseline",
    "LastNTokensBaseline",
    "LifecycleTier",
    "NaiveExtractiveBaseline",
    "OptimizationPolicy",
    "OptimizationTrace",
    "OptimizedContext",
    "PreservationContract",
    "RelevanceOnlyBaseline",
    "RetentionPolicy",
    "RiskAssessment",
    "SlidingWindowBaseline",
    "TransformationTraceEvidence",
    "ValidatedRepresentation",
    "ValidationResult",
    "assess_context_risk",
    "summarize_transformation_trace",
]

__version__ = "0.5.0"
