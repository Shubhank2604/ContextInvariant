"""Execute public examples as offline integration smoke tests."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("relative_path", "expected_output"),
    [
        ("examples/basic.py", "task-1"),
        ("examples/coding_agent_context.py", "contextos_constraint_aware"),
        ("examples/research_agent_context.py", "evidence"),
    ],
)
def test_public_example_runs_offline(
    relative_path: str,
    expected_output: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runpy.run_path(str(ROOT / relative_path), run_name="__main__")

    assert expected_output in capsys.readouterr().out
