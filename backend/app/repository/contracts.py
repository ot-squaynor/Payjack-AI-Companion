from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class StoreLocation:
    mode: str
    local_root: Path | None = None
    s3_bucket: str | None = None
    s3_prefix: str | None = None


@dataclass(frozen=True, slots=True)
class RepositoryHealth:
    ready: bool
    location: str
    dataset_version: str | None = None
    artifact_count: int = 0
    detail: str | None = None
