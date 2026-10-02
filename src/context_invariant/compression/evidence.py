"""Extractive transformation policy for retrieved evidence."""

from __future__ import annotations

from context_invariant.compression.base import CompressionResult
from context_invariant.compression.extractive import ExtractiveCompressor
from context_invariant.embeddings import EmbeddingProvider
from context_invariant.models import ContextItem
from context_invariant.tokenization import Tokenizer


class EvidenceCompressor:
    """Retain verbatim evidence spans and source-item provenance."""

    def __init__(
        self,
        tokenizer: Tokenizer,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._extractive = ExtractiveCompressor(tokenizer, embedding_provider)

    def compress(
        self,
        item: ContextItem,
        target_tokens: int,
        task: str,
    ) -> CompressionResult:
        """Delegate to exact sentence extraction and label the evidence policy."""
        result = self._extractive.compress(item, target_tokens, task)
        return result.model_copy(update={"strategy": "evidence_extractive"})
