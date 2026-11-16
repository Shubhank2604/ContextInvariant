"""Run the fixed behavioral oracle against an explicitly supplied candidate file."""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path


def main() -> int:
    candidate = Path(sys.argv[1])
    function = runpy.run_path(str(candidate))["should_retry"]
    tests = json.loads(Path(__file__).with_name("oracle.json").read_text(encoding="utf-8"))
    failures: list[dict[str, object]] = []
    for test in tests:
        actual = function(**test["arguments"])
        if actual is not test["expected"]:
            failures.append({**test, "actual": actual})
    print(
        json.dumps(
            {"tests": len(tests), "passed": len(tests) - len(failures), "failures": failures}
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
