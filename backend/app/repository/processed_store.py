from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
import pandas as pd

from app.data_pipeline.processed_schema import (
    PROCESSED_ARTIFACT_MANIFEST_FILENAME,
    ProcessedArtifactManifest,
    manifest_from_dict,
)
from app.repository.contracts import RepositoryHealth, StoreLocation


class ProcessedStoreError(RuntimeError):
    """Raised when processed artifacts cannot be loaded safely."""


class ProcessedStore:
    def __init__(
        self,
        location: StoreLocation,
        *,
        s3_client: Any | None = None,
    ) -> None:
        self.location = location
        self._s3_client = s3_client
        self._manifest: ProcessedArtifactManifest | None = None
        self._cache: dict[str, pd.DataFrame] = {}

    @property
    def s3_client(self) -> Any:
        if self._s3_client is None:
            self._s3_client = boto3.client("s3")
        return self._s3_client

    def _manifest_local_path(self) -> Path:
        if self.location.local_root is None:
            raise ProcessedStoreError("Local processed-data root is not configured.")
        return self.location.local_root / PROCESSED_ARTIFACT_MANIFEST_FILENAME

    def _manifest_s3_key(self) -> str:
        prefix = (self.location.s3_prefix or "").strip("/")
        return f"{prefix}/{PROCESSED_ARTIFACT_MANIFEST_FILENAME}" if prefix else PROCESSED_ARTIFACT_MANIFEST_FILENAME

    def load_manifest(self, *, force_refresh: bool = False) -> ProcessedArtifactManifest:
        if self._manifest is not None and not force_refresh:
            return self._manifest

        if self.location.mode == "local":
            manifest_path = self._manifest_local_path()
            if not manifest_path.exists():
                raise ProcessedStoreError(f"Missing processed artifact manifest: {manifest_path}")
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        elif self.location.mode == "s3":
            if not self.location.s3_bucket:
                raise ProcessedStoreError("S3 processed-data bucket is not configured.")
            key = self._manifest_s3_key()
            try:
                response = self.s3_client.get_object(Bucket=self.location.s3_bucket, Key=key)
                payload = json.loads(response["Body"].read().decode("utf-8"))
            except (BotoCoreError, ClientError, KeyError, json.JSONDecodeError) as exc:
                raise ProcessedStoreError(
                    f"Failed to load processed artifact manifest from s3://{self.location.s3_bucket}/{key}: {exc}"
                ) from exc
        else:
            raise ProcessedStoreError(f"Unsupported processed-store mode: {self.location.mode}")

        self._manifest = manifest_from_dict(payload)
        return self._manifest

    def _read_local_dataset(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            raise ProcessedStoreError(f"Missing processed dataset file: {path}")
        if path.suffix == ".parquet":
            return pd.read_parquet(path)
        if path.suffix == ".jsonl":
            return pd.read_json(path, orient="records", lines=True)
        raise ProcessedStoreError(f"Unsupported processed dataset file format: {path.suffix}")

    def _read_s3_dataset(self, key: str) -> pd.DataFrame:
        if not self.location.s3_bucket:
            raise ProcessedStoreError("S3 processed-data bucket is not configured.")
        try:
            response = self.s3_client.get_object(Bucket=self.location.s3_bucket, Key=key)
            payload = response["Body"].read()
        except (BotoCoreError, ClientError, KeyError) as exc:
            raise ProcessedStoreError(
                f"Failed to read processed artifact from s3://{self.location.s3_bucket}/{key}: {exc}"
            ) from exc

        if key.endswith(".parquet"):
            return pd.read_parquet(BytesIO(payload))
        if key.endswith(".jsonl"):
            return pd.read_json(BytesIO(payload), orient="records", lines=True)
        raise ProcessedStoreError(f"Unsupported processed dataset file format in S3 key: {key}")

    def get_dataframe(self, dataset_name: str, *, force_refresh: bool = False) -> pd.DataFrame:
        if dataset_name in self._cache and not force_refresh:
            return self._cache[dataset_name].copy()

        manifest = self.load_manifest(force_refresh=force_refresh)
        artifact = manifest.artifacts.get(dataset_name)
        if artifact is None:
            raise ProcessedStoreError(f"No artifact named '{dataset_name}' exists in the processed manifest.")

        if self.location.mode == "local":
            dataset_path = Path(artifact.local_path or (self.location.local_root / artifact.filename))  # type: ignore[arg-type]
            dataframe = self._read_local_dataset(dataset_path)
        else:
            s3_key = artifact.s3_key or (
                f"{(self.location.s3_prefix or '').strip('/')}/{artifact.filename}".strip("/")
            )
            dataframe = self._read_s3_dataset(s3_key)

        self._cache[dataset_name] = dataframe.copy()
        return dataframe.copy()

    def get_transactions(self) -> pd.DataFrame:
        return self.get_dataframe("transactions")

    def get_accounts(self) -> pd.DataFrame:
        return self.get_dataframe("accounts")

    def get_fees_and_limits(self) -> pd.DataFrame:
        return self.get_dataframe("fees_and_limits")

    def get_products(self) -> pd.DataFrame:
        return self.get_dataframe("products")

    def get_metadata(self) -> pd.DataFrame:
        return self.get_dataframe("metadata")

    def get_manifest(self) -> ProcessedArtifactManifest:
        return self.load_manifest()

    def healthcheck(self) -> RepositoryHealth:
        try:
            manifest = self.load_manifest()
        except ProcessedStoreError as exc:
            return RepositoryHealth(
                ready=False,
                location=self.location.mode,
                detail=str(exc),
            )

        return RepositoryHealth(
            ready=True,
            location=self.location.mode,
            dataset_version=manifest.dataset_version,
            artifact_count=len(manifest.artifacts),
            detail="processed manifest loaded",
        )
