"""Keep the README's complete Python examples executable."""

from __future__ import annotations

import re
from pathlib import Path

README = Path(__file__).resolve().parents[2] / "README.md"


def test_readme_python_examples_execute() -> None:
    snippets = re.findall(r"```python\n(.*?)\n```", README.read_text(encoding="utf-8"), re.DOTALL)

    assert len(snippets) == 2
    for index, snippet in enumerate(snippets, start=1):
        namespace = {"__name__": f"readme_example_{index}"}
        exec(compile(snippet, f"README.md:python-{index}", "exec"), namespace)
