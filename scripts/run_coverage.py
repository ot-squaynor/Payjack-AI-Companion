"""Run backend tests and require a Sonar-compatible coverage.xml report."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COVERAGE_XML = PROJECT_ROOT / "coverage.xml"


def _coverage_stats() -> tuple[int, int, float]:
    root = ET.parse(COVERAGE_XML).getroot()
    lines_valid = int(root.attrib.get("lines-valid", "0"))
    lines_covered = int(root.attrib.get("lines-covered", "0"))
    line_rate = float(root.attrib.get("line-rate", "0"))
    return lines_valid, lines_covered, line_rate


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
    print(f"Running coverage command from {PROJECT_ROOT}")
    print(f"Coverage XML target: {COVERAGE_XML}")
    completed = subprocess.run(command, cwd=PROJECT_ROOT, env=env)
    if completed.returncode != 0:
        return completed.returncode

    if not COVERAGE_XML.exists():
        print("coverage.xml was not generated; SonarQube will report zero coverage.", file=sys.stderr)
        return 2

    try:
        lines_valid, lines_covered, line_rate = _coverage_stats()
    except ET.ParseError as exc:
        print(f"coverage.xml is not valid XML: {exc}", file=sys.stderr)
        return 2

    if lines_valid <= 0 or lines_covered <= 0 or line_rate <= 0:
        print(
            (
                "coverage.xml contains no covered Python lines; "
                "SonarQube will report zero coverage."
            ),
            file=sys.stderr,
        )
        return 2

    print(
        (
            f"Coverage XML generated at {COVERAGE_XML} "
            f"({lines_covered}/{lines_valid} lines, {line_rate:.1%})."
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
