"""Deterministic pruning for JSON tool output and structured task state."""

from __future__ import annotations

import json
import re
from typing import Any

from contextos.compression.base import CompressionResult
from contextos.models import ContextItem
from contextos.tokenization import Tokenizer

_TERM = re.compile(r"[A-Za-z0-9_.-]{2,}")
_CRITICAL_KEYS = (
    "status",
    "state",
    "id",
    "error",
    "code",
    "result",
    "message",
    "timestamp",
)


class StructuredDataCompressor:
    """Prune top-level JSON fields without rewriting retained values."""

    def __init__(self, tokenizer: Tokenizer) -> None:
        self._tokenizer = tokenizer

    def compress(
        self,
        item: ContextItem,
        target_tokens: int,
        task: str,
    ) -> CompressionResult:
        """Keep required, task-related, and operationally critical fields."""
        original_tokens = self._tokenizer.count_tokens(item.content)
        try:
            payload = json.loads(item.content)
        except (TypeError, json.JSONDecodeError):
            return self._failure(item, original_tokens, "invalid_json")
        if not isinstance(payload, dict):
            return self._failure(item, original_tokens, "json_root_not_object")
        if not payload:
            return self._failure(item, original_tokens, "empty_json_object")

        required_keys = (
            item.contract.required_keys
            if item.contract is not None and item.contract.preserve_structure
            else ()
        )
        missing_keys = tuple(key for key in required_keys if key not in payload)
        if missing_keys:
            return self._failure(
                item,
                original_tokens,
                "missing_required_keys:" + ",".join(missing_keys),
            )
        task_terms = {term.casefold() for term in _TERM.findall(task)}

        def priority(key: str) -> tuple[int, int, str]:
            if key in required_keys:
                return (0, required_keys.index(key), key)
            if key.casefold() in task_terms:
                return (1, 0, key)
            if key.casefold() in _CRITICAL_KEYS:
                return (2, _CRITICAL_KEYS.index(key.casefold()), key)
            return (3, 0, key)

        selected: dict[str, Any] = {}
        for key in sorted(payload, key=priority):
            candidate = {**selected, key: payload[key]}
            content = self._serialize(candidate)
            if self._tokenizer.count_tokens(content) <= target_tokens:
                selected[key] = payload[key]
            elif key in required_keys:
                return self._failure(item, original_tokens, "required_keys_exceed_target")
        if not selected:
            return self._failure(item, original_tokens, "no_field_fits_target")
        content = self._serialize(selected)
        return CompressionResult(
            content=content,
            original_tokens=original_tokens,
            compressed_tokens=self._tokenizer.count_tokens(content),
            source_item_id=item.id,
            strategy="structured_pruning",
            provenance=(item.id,),
            lossy=content != item.content,
        )

    @staticmethod
    def _serialize(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _failure(item: ContextItem, original_tokens: int, reason: str) -> CompressionResult:
        return CompressionResult(
            original_tokens=original_tokens,
            compressed_tokens=0,
            source_item_id=item.id,
            strategy="structured_pruning",
            provenance=(item.id,),
            failure_reason=reason,
        )
