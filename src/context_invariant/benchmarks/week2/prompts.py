"""Shared prompt formatting for execution and preflight tokenization checks."""

from __future__ import annotations

from typing import Any


def render_record_header(record_id: str, record_type: str) -> str:
    return f"[record {record_id}; type={record_type}]\n"


def render_context_prompt(task: str, selected: list[dict[str, Any]]) -> str:
    visible = "\n\n".join(
        render_record_header(item["id"], item["type"]) + item["content"] for item in selected
    )
    return f"Use the supplied records for the task.\n\nCONTEXT\n{visible}\n\nTASK\n{task}"
