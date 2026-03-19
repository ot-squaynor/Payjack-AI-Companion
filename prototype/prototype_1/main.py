"""Minimal entrypoint that dispatches to the existing script-level logic.

Usage:
    python main.py              # run app.py main()
    python main.py app          # run app.py main()
    python main.py ingest       # run ingest.py __main__ flow
    python main.py visualize    # run visualize.py __main__ flow
    python main.py all          # run ingest, then visualize, then app

This file intentionally preserves the logic already defined in each module,
rather than re-implementing orchestration.
"""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def run_script(script_name: str) -> None:
    """Execute a sibling script exactly as if it were run directly."""
    script_path = BASE_DIR / script_name
    if not script_path.exists():
        raise FileNotFoundError(f"Could not find {script_name} next to main.py at {script_path}")
    runpy.run_path(str(script_path), run_name="__main__")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Minimal dispatcher for the existing Payjack scripts."
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="app",
        choices=["app", "ingest", "visualize", "all"],
        help="Which existing script flow to run.",
    )
    args = parser.parse_args()

    try:
        if args.command == "app":
            run_script("app.py")
        elif args.command == "ingest":
            run_script("ingest.py")
        elif args.command == "visualize":
            run_script("visualize.py")
        elif args.command == "all":
            run_script("ingest.py")
            run_script("visualize.py")
            run_script("app.py")
    except KeyboardInterrupt:
        print("\nStopped by user.")
        sys.exit(130)


if __name__ == "__main__":
    main()
