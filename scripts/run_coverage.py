"""Run backend tests and require a Sonar-compatible coverage.xml report."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COVERAGE_XML = PROJECT_ROOT / "coverage.xml"


def main() -> int:
    if COVERAGE_XML.exists():
        COVERAGE_XML.unlink()

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(PROJECT_ROOT)
        if not existing_pythonpath
        else os.pathsep.join((str(PROJECT_ROOT), existing_pythonpath))
    )

    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "-q",
        "-p",
        "no:cacheprovider",
        "--cov=app",
        "--cov=scripts",
        "--cov-report=xml:coverage.xml",
        "--cov-report=term-missing",
    ]
    completed = subprocess.run(command, cwd=PROJECT_ROOT, env=env)
    if completed.returncode != 0:
        return completed.returncode

    if not COVERAGE_XML.exists():
        print("coverage.xml was not generated; SonarQube will report zero coverage.", file=sys.stderr)
        return 2

    print(f"Coverage XML generated at {COVERAGE_XML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
