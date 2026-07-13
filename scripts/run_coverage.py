"""Run backend tests and require a Sonar-compatible coverage.xml report."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COVERAGE_XML = PROJECT_ROOT / "coverage.xml"
ABSOLUTE_SOURCE_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|/)")
SONAR_SOURCE_PREFIXES = ("app/", "scripts/")


def _normalize_coverage_sources() -> None:
    tree = ET.parse(COVERAGE_XML)
    root = tree.getroot()
    sources_node = root.find("./sources")
    if sources_node is None:
        sources_node = ET.SubElement(root, "sources")

    for child in list(sources_node):
        sources_node.remove(child)

    source_node = ET.SubElement(sources_node, "source")
    source_node.text = "."
    ET.indent(tree, space="\t")
    tree.write(COVERAGE_XML, encoding="utf-8", xml_declaration=True)


def _coverage_stats() -> tuple[int, int, float]:
    root = ET.parse(COVERAGE_XML).getroot()
    lines_valid = int(root.attrib.get("lines-valid", "0"))
    lines_covered = int(root.attrib.get("lines-covered", "0"))
    line_rate = float(root.attrib.get("line-rate", "0"))
    return lines_valid, lines_covered, line_rate


def _coverage_path_errors() -> list[str]:
    root = ET.parse(COVERAGE_XML).getroot()
    source_values = [
        (source.text or "").strip()
        for source in root.findall("./sources/source")
        if (source.text or "").strip()
    ]
    errors: list[str] = []

    for source_value in source_values:
        if ABSOLUTE_SOURCE_RE.match(source_value):
            errors.append(
                (
                    "coverage.xml contains an absolute <source> path. "
                    f"Use repo-relative coverage paths instead: {source_value}"
                )
            )

    source_roots = [
        (PROJECT_ROOT / source_value).resolve()
        for source_value in source_values
        if not ABSOLUTE_SOURCE_RE.match(source_value)
    ]
    if not source_roots:
        source_roots = [PROJECT_ROOT]

    unresolved: list[str] = []
    for class_node in root.findall(".//class"):
        filename = class_node.attrib.get("filename", "").strip()
        if not filename:
            continue
        if not filename.startswith(SONAR_SOURCE_PREFIXES):
            unresolved.append(filename)
            continue
        if not any((source_root / filename).exists() for source_root in source_roots):
            unresolved.append(filename)

    for filename in sorted(set(unresolved))[:20]:
        errors.append(f"coverage.xml contains an unresolved file path: {filename}")
    if len(set(unresolved)) > 20:
        errors.append(
            f"coverage.xml contains {len(set(unresolved)) - 20} more unresolved file paths."
        )

    return errors


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
        "--cov",
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
        _normalize_coverage_sources()
        lines_valid, lines_covered, line_rate = _coverage_stats()
    except ET.ParseError as exc:
        print(f"coverage.xml is not valid XML: {exc}", file=sys.stderr)
        return 2

    path_errors = _coverage_path_errors()
    if path_errors:
        for error in path_errors:
            print(error, file=sys.stderr)
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
