# scripts/dataset_transform.py
# 2026-04-02
"""Purpose: Build processed runtime artifacts from raw Payjack datasets and optionally publish them to S3."""

from __future__ import annotations

##BRICK 1: Imports, repository bootstrap, and env loading
import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
from typing import Any
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data_pipeline import ingestion
from app.data_pipeline.category_mapping import map_categories, mapping_coverage_summary
from app.data_pipeline.normalization import NormalizationConfig, normalize_bundle
from app.data_pipeline.processed_schema import (
    PROCESSED_ARTIFACT_MANIFEST_FILENAME,
    PROCESSED_ARTIFACT_SCHEMA_VERSION,
    ProcessedArtifactManifest,
    build_dataset_artifact,
    build_qc_summary,
    manifest_to_dict,
    write_manifest,
)
from app.data_pipeline.quality_checks import quality_check_report_to_dict, run_quality_checks
from app.data_pipeline.recurring_logic import detect_recurring_transactions, recurrence_summary
from app.env import load_local_env


load_local_env()
logger = logging.getLogger(__name__)


##BRICK 2: CLI argument mapping and dataset source helpers
DATASET_FLAG_MAP: dict[str, tuple[str, str]] = {
    "transactions": ("transactions_bucket", "transactions_prefix"),
    "accounts": ("accounts_bucket", "accounts_prefix"),
    "fees_and_limits": ("fees_bucket", "fees_prefix"),
    "products": ("products_bucket", "products_prefix"),
    "metadata": ("metadata_bucket", "metadata_prefix"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transform raw Payjack datasets into processed runtime artifacts.",
    )
    parser.add_argument("--source-mode", choices=("local", "s3"), default="local")
    parser.add_argument("--environment", default="local")
    parser.add_argument("--local-root", default=str(PROJECT_ROOT / "data" / "raw"))
    parser.add_argument("--raw-bucket")
    parser.add_argument("--raw-prefix", default="")
    parser.add_argument("--transactions-bucket")
    parser.add_argument("--transactions-prefix", default="")
    parser.add_argument("--accounts-bucket")
    parser.add_argument("--accounts-prefix", default="")
    parser.add_argument("--fees-bucket")
    parser.add_argument("--fees-prefix", default="")
    parser.add_argument("--products-bucket")
    parser.add_argument("--products-prefix", default="")
    parser.add_argument("--metadata-bucket")
    parser.add_argument("--metadata-prefix", default="")
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "data" / "processed"))
    parser.add_argument("--output-bucket")
    parser.add_argument("--output-prefix", default="")
    parser.add_argument("--default-currency", default="GHS")
    parser.add_argument("--drop-invalid-rows", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def _resolve_source_config(
    dataset_name: str,
    args: argparse.Namespace,
) -> ingestion.DataSourceConfig | None:
    if args.source_mode == "local":
        return ingestion.DataSourceConfig(
            mode="local",
            local_root=Path(args.local_root),
        )

    bucket_attr, prefix_attr = DATASET_FLAG_MAP[dataset_name]
    bucket = getattr(args, bucket_attr) or args.raw_bucket
    prefix = getattr(args, prefix_attr) or args.raw_prefix

    if not bucket:
        return None

    return ingestion.DataSourceConfig(
        mode="s3",
        s3_bucket=bucket,
        s3_root_prefix=prefix or "",
    )


##BRICK 3: Raw bundle loading and deterministic enrichment
def _load_bundle(args: argparse.Namespace) -> dict[str, pd.DataFrame]:
    bundle: dict[str, pd.DataFrame] = {}
    specs = ingestion._specs()

    for dataset_name, spec in specs.items():
        source_config = _resolve_source_config(dataset_name, args)
        if source_config is None:
            logger.info("Skipping dataset '%s' because no source bucket was provided.", dataset_name)
            continue

        try:
            bundle[dataset_name] = ingestion.ingest_dataset(
                spec=spec,
                source_config=source_config,
            )
        except ingestion.IngestionError as exc:
            if dataset_name == "transactions":
                raise
            logger.warning("Skipping dataset '%s' after ingestion error: %s", dataset_name, exc)

    if "transactions" not in bundle:
        raise RuntimeError("The transactions dataset is required to build processed artifacts.")

    return bundle


def _prepare_transactions_for_mapping(transactions_df: pd.DataFrame) -> pd.DataFrame:
    prepared_df = transactions_df.copy()

    merchant_source = "merchant_clean" if "merchant_clean" in prepared_df.columns else "merchant"
    prepared_df["merchant_normalized"] = (
        prepared_df[merchant_source]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )
    prepared_df["category_normalized"] = (
        prepared_df["category"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    return prepared_df


def _finalize_transactions(transactions_df: pd.DataFrame) -> pd.DataFrame:
    finalized_df = transactions_df.copy()

    finalized_df["merchant"] = finalized_df["merchant_mapped"].where(
        finalized_df["merchant_mapped"].astype(str).str.strip() != "",
        finalized_df.get("merchant_clean", finalized_df.get("merchant")),
    )
    finalized_df["category"] = finalized_df["category_mapped"]
    finalized_df["subcategory"] = finalized_df["subcategory_mapped"]
    finalized_df["amount"] = pd.to_numeric(finalized_df["amount"], errors="coerce").abs()

    if "merchant_clean" in finalized_df.columns:
        finalized_df["merchant_clean"] = finalized_df["merchant_clean"].fillna(finalized_df["merchant"])

    return finalized_df


##BRICK 4: Artifact persistence and optional S3 publishing
def _write_dataset_artifacts(
    bundle: dict[str, pd.DataFrame],
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, Any] = {}

    for dataset_name, dataset_df in bundle.items():
        output_path = output_dir / f"{dataset_name}.parquet"
        dataset_df.to_parquet(output_path, index=False)
        artifacts[dataset_name] = build_dataset_artifact(
            name=dataset_name,
            filename=output_path.name,
            row_count=len(dataset_df),
            columns=list(dataset_df.columns),
            local_path=str(output_path.resolve()),
        )

    return artifacts


def _upload_outputs_to_s3(
    *,
    output_dir: Path,
    manifest: ProcessedArtifactManifest,
    output_bucket: str,
    output_prefix: str,
) -> ProcessedArtifactManifest:
    s3_client = boto3.client("s3")
    prefix = output_prefix.strip("/")
    manifest_payload = manifest_to_dict(manifest)

    for artifact_name, artifact in manifest.artifacts.items():
        key = f"{prefix}/{artifact.filename}" if prefix else artifact.filename
        local_path = Path(artifact.local_path or output_dir / artifact.filename)
        try:
            s3_client.upload_file(str(local_path), output_bucket, key)
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(
                f"Failed to upload processed artifact '{artifact_name}' to s3://{output_bucket}/{key}: {exc}"
            ) from exc
        manifest_payload["artifacts"][artifact_name]["s3_key"] = key

    for sidecar_name in ("qc_report.json", "pipeline_summary.json", PROCESSED_ARTIFACT_MANIFEST_FILENAME):
        sidecar_path = output_dir / sidecar_name
        if not sidecar_path.exists():
            continue
        sidecar_key = f"{prefix}/{sidecar_name}" if prefix else sidecar_name
        try:
            s3_client.upload_file(str(sidecar_path), output_bucket, sidecar_key)
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(
                f"Failed to upload sidecar artifact to s3://{output_bucket}/{sidecar_key}: {exc}"
            ) from exc

    return ProcessedArtifactManifest(
        schema_version=manifest_payload["schema_version"],
        dataset_version=manifest_payload["dataset_version"],
        build_id=manifest_payload["build_id"],
        environment=manifest_payload["environment"],
        source_mode=manifest_payload["source_mode"],
        created_at=manifest_payload["created_at"],
        artifacts={
            name: build_dataset_artifact(
                name=name,
                filename=artifact_payload["filename"],
                row_count=artifact_payload["row_count"],
                columns=artifact_payload["columns"],
                local_path=artifact_payload.get("local_path"),
                s3_key=artifact_payload.get("s3_key"),
            )
            for name, artifact_payload in manifest_payload["artifacts"].items()
        },
        qc_summary=manifest.qc_summary,
    )


##BRICK 5: CLI entrypoint
def main() -> None:
    load_local_env()
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    raw_bundle = _load_bundle(args)
    normalized_bundle = normalize_bundle(
        raw_bundle,
        NormalizationConfig(
            default_currency=args.default_currency,
            drop_invalid_rows=args.drop_invalid_rows,
        ),
    )

    transactions_df = _prepare_transactions_for_mapping(normalized_bundle["transactions"])
    transactions_df = map_categories(transactions_df)
    transactions_df = detect_recurring_transactions(transactions_df)
    transactions_df = _finalize_transactions(transactions_df)

    qc_report = run_quality_checks(transactions_df)
    qc_report_dict = quality_check_report_to_dict(qc_report)
    if not qc_report.passed:
        raise RuntimeError(
            "Processed transactions failed quality checks. "
            f"Errors={qc_report.error_count}, warnings={qc_report.warning_count}."
        )

    normalized_bundle["transactions"] = transactions_df

    output_dir = Path(args.output_dir)
    artifacts = _write_dataset_artifacts(normalized_bundle, output_dir)

    pipeline_summary = {
        "mapping_coverage": mapping_coverage_summary(transactions_df),
        "recurrence_summary": recurrence_summary(transactions_df),
    }
    (output_dir / "qc_report.json").write_text(
        json.dumps(qc_report_dict, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "pipeline_summary.json").write_text(
        json.dumps(pipeline_summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    build_id = f"{args.environment}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    dataset_version = build_id
    manifest = ProcessedArtifactManifest(
        schema_version=PROCESSED_ARTIFACT_SCHEMA_VERSION,
        dataset_version=dataset_version,
        build_id=build_id,
        environment=args.environment,
        source_mode=args.source_mode,
        created_at=datetime.now(timezone.utc).isoformat(),
        artifacts=artifacts,
        qc_summary=build_qc_summary(qc_report_dict),
    )
    manifest_path = write_manifest(manifest, output_dir)

    if args.output_bucket:
        output_prefix = args.output_prefix.strip("/") or args.environment
        manifest = _upload_outputs_to_s3(
            output_dir=output_dir,
            manifest=manifest,
            output_bucket=args.output_bucket,
            output_prefix=output_prefix,
        )
        manifest_path.write_text(
            json.dumps(manifest_to_dict(manifest), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    logger.info("Processed artifact manifest written to %s", manifest_path)


if __name__ == "__main__":
    main()
