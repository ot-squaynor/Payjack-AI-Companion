#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python_bin="${PYTHON_BIN:-python3}"

"$python_bin" -m pip install -r requirements.dev.txt
"$python_bin" scripts/run_coverage.py

test -s coverage.xml
printf 'coverage.xml ready for SonarQube: %s/coverage.xml\n' "$repo_root"
