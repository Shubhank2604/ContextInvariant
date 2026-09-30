"""Conservative line-preserving transformation for source-code context."""

from __future__ import annotations

import re

from contextos.compression.base import CompressionResult
from contextos.models import ContextItem
from contextos.tokenization import Tokenizer

_COMMENT = re.compile(r"^\s*(?:#|//|/\*|\*|\*/)")
_IMPORT = re.compile(r"^\s*(?:from\s+\S+\s+import|import\s+|#include\b|using\s+)")
_SIGNATURE = re.compile(
    r"^\s*(?:async\s+def|def|class|function|interface|struct|enum)\s+[A-Za-z_$][\w$]*"
)
_RETURN = re.compile(r"^\s*(?:return|raise|throw)\b")
_SYMBOL = re.compile(r"[A-Za-z_$][\w$]*")


class CodeCompressor:
    """Keep exact imports, declarations, and task-referenced source lines."""

    def __init__(self, tokenizer: Tokenizer) -> None:
        self._tokenizer = tokenizer

    def compress(
        self,
        item: ContextItem,
        target_tokens: int,
        task: str,
    ) -> CompressionResult:
        """Extract code lines without prose summarization or token rewriting."""
        original_tokens = self._tokenizer.count_tokens(item.content)
        lines = item.content.splitlines()
        eligible = [index for index, line in enumerate(lines) if not _COMMENT.match(line)]
        if not eligible:
            return self._failure(item, original_tokens, "no_code_lines")
        task_symbols = {symbol.casefold() for symbol in _SYMBOL.findall(task)}

        def priority(index: int) -> tuple[int, int]:
            line = lines[index]
            line_symbols = {symbol.casefold() for symbol in _SYMBOL.findall(line)}
            if _IMPORT.match(line):
                return (0, index)
            if _SIGNATURE.match(line):
                return (1, index)
            if _RETURN.match(line):
                return (2, index)
            if task_symbols & line_symbols:
                return (3, index)
            return (4, index)

        selected: set[int] = set()
        for index in sorted(eligible, key=priority):
            proposed = "\n".join(
                line
                for line_index, line in enumerate(lines)
                if line_index in selected or line_index == index
            )
            if proposed.strip() and self._tokenizer.count_tokens(proposed) <= target_tokens:
                selected.add(index)
        content = "\n".join(line for index, line in enumerate(lines) if index in selected)
        if not content.strip():
            return self._failure(item, original_tokens, "no_code_line_fits_target")
        return CompressionResult(
            content=content,
            original_tokens=original_tokens,
            compressed_tokens=self._tokenizer.count_tokens(content),
            source_item_id=item.id,
            strategy="code_structural",
            provenance=(item.id,),
            lossy=content != item.content,
        )

    @staticmethod
    def _failure(item: ContextItem, original_tokens: int, reason: str) -> CompressionResult:
        return CompressionResult(
            original_tokens=original_tokens,
            compressed_tokens=0,
            source_item_id=item.id,
            strategy="code_structural",
            provenance=(item.id,),
            failure_reason=reason,
        )
