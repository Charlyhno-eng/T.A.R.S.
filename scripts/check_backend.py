"""Run with `uv run --group test python scripts/check_backend.py`."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    config = str(root / "pyproject.toml")
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
                   "COVERAGE_FILE": str(root / ".coverage")}
    checks = (
        (root, ["vulture", "--config", config]),
        (root / "src", ["coverage", "run", "--rcfile", config, "-m",
                        "unittest", "discover", "-s", "../tests"]),
        (root / "src", ["coverage", "report", "--rcfile", config]),
    )
    for directory, arguments in checks:
        result = subprocess.run([sys.executable, "-m", *arguments],
                                cwd=directory, env=environment, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
