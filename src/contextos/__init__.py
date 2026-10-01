"""Public package surface for ContextOS."""

from contextos.baselines import (
    FullContextBaseline,
    LastNTokensBaseline,
    NaiveExtractiveBaseline,
    RelevanceOnlyBaseline,
    SlidingWindowBaseline,
)
from contextos.budget import AllocationPlan
from contextos.config import OptimizationPolicy
from contextos.constraints import (
    ConflictPolicy,
    ConstraintResolution,
    ContextConstraintGraph,
    ValidatedRepresentation,
)
from contextos.contracts import PreservationContract, RetentionPolicy
from contextos.models import (
    ContextEdge,
    ContextItem,
    ContextType,
    DependencyRelation,
    LifecycleTier,
)
from contextos.optimizer import ContextOptimizer
from contextos.scoring import RiskAssessment, assess_context_risk
from contextos.trace import (
    ConflictTraceStatus,
    ConstraintTraceEvidence,
    ConstraintTraceIndex,
    OptimizationTrace,
    OptimizedContext,
    TransformationTraceEvidence,
    summarize_transformation_trace,
)
from contextos.validation import ContractValidationEngine, ValidationResult

__all__ = [
    "AllocationPlan",
    "ConflictPolicy",
    "ConflictTraceStatus",
    "ConstraintResolution",
    "ConstraintTraceEvidence",
    "ConstraintTraceIndex",
    "ContextConstraintGraph",
    "ContextEdge",
    "ContextItem",
    "ContextOptimizer",
    "ContextType",
    "ContractValidationEngine",
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

__version__ = "0.3.0"
