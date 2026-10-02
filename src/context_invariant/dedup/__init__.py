"""Exact and semantic context deduplication."""

from context_invariant.dedup.base import DeduplicationResult, DuplicateMatch
from context_invariant.dedup.exact import (
    exact_deduplicate,
    normalize_content,
    normalized_content_hash,
)
from context_invariant.dedup.metrics import (
    DeduplicationCase,
    DeduplicationMetrics,
    evaluate_deduplication_cases,
)
from context_invariant.dedup.semantic import semantic_deduplicate

__all__ = [
    "DeduplicationCase",
    "DeduplicationMetrics",
    "DeduplicationResult",
    "DuplicateMatch",
    "evaluate_deduplication_cases",
    "exact_deduplicate",
    "normalize_content",
    "normalized_content_hash",
    "semantic_deduplicate",
]
