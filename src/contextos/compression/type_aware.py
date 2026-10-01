"""Central context-type transformation routing."""

from __future__ import annotations

from contextos.compression.base import CompressionResult, Compressor
from contextos.compression.code import CodeCompressor
from contextos.compression.evidence import EvidenceCompressor
from contextos.compression.extractive import ExtractiveCompressor
from contextos.compression.none import NoneCompressor
from contextos.compression.structured import StructuredDataCompressor
from contextos.compression.tool_output import ToolOutputCompressor
from contextos.models import ContextItem, ContextType
from contextos.tokenization import Tokenizer

_LOSSLESS_TYPES = {ContextType.SYSTEM_INSTRUCTION, ContextType.TOOL_DEFINITION}
_STRUCTURED_TYPES = {ContextType.TASK_STATE}
_TOOL_TYPES = {ContextType.TOOL_OUTPUT, ContextType.ERROR}


class TypeAwareCompressor:
    """Select a deterministic transformation family from the context type."""

    def __init__(
        self,
        tokenizer: Tokenizer,
        *,
        extractive: Compressor | None = None,
        tool_output: Compressor | None = None,
        none: Compressor | None = None,
        code: Compressor | None = None,
        structured: Compressor | None = None,
        evidence: Compressor | None = None,
    ) -> None:
        self._extractive = extractive or ExtractiveCompressor(tokenizer)
        self._tool_output = tool_output or ToolOutputCompressor(tokenizer)
        self._none = none or NoneCompressor(tokenizer)
        self._code = code or CodeCompressor(tokenizer)
        self._structured = structured or StructuredDataCompressor(tokenizer)
        self._evidence = evidence or extractive or EvidenceCompressor(tokenizer)

    def compress(
        self,
        item: ContextItem,
        target_tokens: int,
        task: str,
    ) -> CompressionResult:
        """Route protected content losslessly and other types conservatively."""
        compressor = self.compressor_for(item)
        return compressor.compress(item, target_tokens, task)

    def compressor_for(self, item: ContextItem) -> Compressor:
        """Expose the selected family for deterministic tests and traces."""
        if item.mandatory or not item.compressible or item.type in _LOSSLESS_TYPES:
            return self._none
        if item.type is ContextType.CODE:
            return self._code
        if item.type in _STRUCTURED_TYPES:
            return self._structured
        if item.type in _TOOL_TYPES:
            if item.content.lstrip().startswith("{"):
                return self._structured
            return self._tool_output
        if item.type is ContextType.RETRIEVED_DOCUMENT:
            return self._evidence
        return self._extractive
