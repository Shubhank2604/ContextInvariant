"""Safe, auditable compression strategies."""

from context_invariant.compression.base import CompressionResult, Compressor
from context_invariant.compression.code import CodeCompressor
from context_invariant.compression.evidence import EvidenceCompressor
from context_invariant.compression.executor import (
    CompressionAttempt,
    CompressionExecution,
    CompressionExecutor,
)
from context_invariant.compression.extractive import ExtractiveCompressor
from context_invariant.compression.llm_summary import LLMSummaryCompressor
from context_invariant.compression.none import NoneCompressor
from context_invariant.compression.structured import StructuredDataCompressor
from context_invariant.compression.tool_output import ToolOutputCompressor
from context_invariant.compression.type_aware import TypeAwareCompressor

__all__ = [
    "CodeCompressor",
    "CompressionAttempt",
    "CompressionExecution",
    "CompressionExecutor",
    "CompressionResult",
    "Compressor",
    "EvidenceCompressor",
    "ExtractiveCompressor",
    "LLMSummaryCompressor",
    "NoneCompressor",
    "StructuredDataCompressor",
    "ToolOutputCompressor",
    "TypeAwareCompressor",
]
