from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


PROCESSED_ARTIFACT_SCHEMA_VERSION = "2026-04-02.v1"
PROCESSED_ARTIFACT_MANIFEST_FILENAME = "manifest.json"


@dataclass(frozen=True, slots=True)
class DatasetArtifact:
    name: str
    filename: str
    row_count: int
    columns: tuple[str, ...]
    local_path: str | None = None
    s3_key: str | None = None


@dataclass(frozen=True, slots=True)
class QualityCheckSummary:
    passed: bool
    finding_count: int
    error_count: int
    warning_count: int
    info_count: int


@dataclass(frozen=True, slots=True)
class ProcessedArtifactManifest:
    schema_version: str
    dataset_version: str
    build_id: str
    environment: str
    source_mode: str
    created_at: str
    artifacts: dict[str, DatasetArtifact]
    qc_summary: QualityCheckSummary | None = None


def build_dataset_artifact(
    *,
    name: str,
    filename: str,
    row_count: int,
    columns: list[str] | tuple[str, ...],
    local_path: str | None = None,
    s3_key: str | None = None,
) -> DatasetArtifact:
    return DatasetArtifact(
        name=name,
        filename=filename,
        row_count=int(row_count),
        columns=tuple(str(column) for column in columns),
        local_path=local_path,
        s3_key=s3_key,
    )


def build_qc_summary(report: dict[str, Any] | None) -> QualityCheckSummary | None:
    if not report:
        return None

    return QualityCheckSummary(
        passed=bool(report.get("passed", False)),
        finding_count=int(report.get("finding_count", 0)),
        error_count=int(report.get("error_count", 0)),
        warning_count=int(report.get("warning_count", 0)),
        info_count=int(report.get("info_count", 0)),
    )


def manifest_to_dict(manifest: ProcessedArtifactManifest) -> dict[str, Any]:
    return {
        "schema_version": manifest.schema_version,
        "dataset_version": manifest.dataset_version,
        "build_id": manifest.build_id,
        "environment": manifest.environment,
        "source_mode": manifest.source_mode,
        "created_at": manifest.created_at,
        "artifacts": {
            name: {
                "name": artifact.name,
                "filename": artifact.filename,
                "row_count": artifact.row_count,
                "columns": list(artifact.columns),
                "local_path": artifact.local_path,
                "s3_key": artifact.s3_key,
            }
            for name, artifact in manifest.artifacts.items()
        },
        "qc_summary": (
            None
            if manifest.qc_summary is None
            else {
                "passed": manifest.qc_summary.passed,
                "finding_count": manifest.qc_summary.finding_count,
                "error_count": manifest.qc_summary.error_count,
                "warning_count": manifest.qc_summary.warning_count,
                "info_count": manifest.qc_summary.info_count,
            }
        ),
    }


def manifest_from_dict(payload: dict[str, Any]) -> ProcessedArtifactManifest:
    artifacts = {
        name: DatasetArtifact(
            name=artifact_payload["name"],
            filename=artifact_payload["filename"],
            row_count=int(artifact_payload["row_count"]),
            columns=tuple(artifact_payload.get("columns", [])),
            local_path=artifact_payload.get("local_path"),
            s3_key=artifact_payload.get("s3_key"),
        )
        for name, artifact_payload in payload.get("artifacts", {}).items()
    }

    qc_payload = payload.get("qc_summary")
    qc_summary = None
    if qc_payload is not None:
        qc_summary = QualityCheckSummary(
            passed=bool(qc_payload.get("passed", False)),
            finding_count=int(qc_payload.get("finding_count", 0)),
            error_count=int(qc_payload.get("error_count", 0)),
            warning_count=int(qc_payload.get("warning_count", 0)),
            info_count=int(qc_payload.get("info_count", 0)),
        )

    return ProcessedArtifactManifest(
        schema_version=payload["schema_version"],
        dataset_version=payload["dataset_version"],
        build_id=payload["build_id"],
        environment=payload["environment"],
        source_mode=payload["source_mode"],
        created_at=payload["created_at"],
        artifacts=artifacts,
        qc_summary=qc_summary,
    )


def write_manifest(
    manifest: ProcessedArtifactManifest,
    output_dir: Path | str,
) -> Path:
    output_path = Path(output_dir) / PROCESSED_ARTIFACT_MANIFEST_FILENAME
    output_path.write_text(
        json.dumps(manifest_to_dict(manifest), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def read_manifest(path: Path | str) -> ProcessedArtifactManifest:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return manifest_from_dict(payload)
