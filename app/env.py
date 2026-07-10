# app/env.py
# 2026-04-02
"""Purpose: Auto-load the local `.env` file for development and tests."""

from __future__ import annotations

##BRICK 1: Imports and local module state
from pathlib import Path

from dotenv import load_dotenv


_LOADED_ENV_PATH: Path | None = None


##BRICK 2: Local `.env` path resolution and loading helpers
def resolve_backend_env_path() -> Path:
    """Return the canonical local `.env` path."""

    return Path(__file__).resolve().parents[1] / ".env"


def load_local_env(*, env_path: Path | None = None, override: bool = False) -> Path | None:
    """Load the local `.env` file once without overriding explicit shell variables."""

    global _LOADED_ENV_PATH

    resolved_path = (env_path or resolve_backend_env_path()).resolve()
    if _LOADED_ENV_PATH == resolved_path:
        return _LOADED_ENV_PATH

    if not resolved_path.exists():
        return None

    load_dotenv(dotenv_path=resolved_path, override=override)
    _LOADED_ENV_PATH = resolved_path
    return _LOADED_ENV_PATH
