# app/config.py
# 2026-04-02
"""Purpose: Resolve Payjack runtime settings from shell variables and the local backend `.env` file."""

from __future__ import annotations

##BRICK 1: Imports and local env bootstrap
from dataclasses import dataclass
import os
from pathlib import Path

from app.env import load_local_env


load_local_env()


##BRICK 2: Primitive environment parsing helpers
def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _get_tuple(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _resolve_runtime_path(raw_value: str, *, backend_root: Path) -> Path:
    candidate = Path(raw_value)
    if candidate.is_absolute():
        return candidate

    project_root = backend_root.parent
    path_parts = candidate.parts
    if path_parts and path_parts[0].lower() == backend_root.name.lower():
        return (project_root / candidate).resolve()

    return (backend_root / candidate).resolve()


##BRICK 3: Runtime settings contract
@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str
    app_env: str
    debug: bool
    log_level: str
    cors_origins: tuple[str, ...]
    max_message_chars: int
    processed_store_mode: str
    processed_local_root: Path
    processed_s3_bucket: str | None
    processed_s3_prefix: str
    external_transactions_bucket: str | None
    external_transactions_prefix: str
    external_accounts_bucket: str | None
    external_accounts_prefix: str
    managed_processed_bucket: str | None
    managed_processed_prefix: str
    managed_kb_source_bucket: str | None
    managed_kb_artifacts_bucket: str | None
    use_mock_bedrock: bool
    use_local_rag: bool
    enable_debug_traces: bool
    aws_region: str
    bedrock_model_id: str
    bedrock_embedding_model_id: str
    bedrock_timeout_seconds: int
    kb_chunks_path: Path
    kb_s3_bucket: str | None
    kb_s3_prefix: str

    @classmethod
    def from_env(cls) -> "Settings":
        """Build the application settings object from the effective environment."""

        load_local_env()
        backend_root = Path(__file__).resolve().parents[1]
        processed_local_root = _resolve_runtime_path(
            os.getenv(
                "PROCESSED_LOCAL_ROOT",
                str(backend_root / "data" / "processed"),
            ),
            backend_root=backend_root,
        )
        kb_chunks_path = _resolve_runtime_path(
            os.getenv(
                "KB_CHUNKS_PATH",
                str(backend_root / "kb" / "processed_docs" / "chunks.jsonl"),
            ),
            backend_root=backend_root,
        )
        return cls(
            app_name=os.getenv("APP_NAME", "payjack-ai-companion"),
            app_env=os.getenv("APP_ENV", "local"),
            debug=_get_bool("DEBUG", True),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            cors_origins=_get_tuple(
                "CORS_ORIGINS",
                ("http://localhost:3000", "http://127.0.0.1:3000"),
            ),
            max_message_chars=_get_int("MAX_MESSAGE_CHARS", 2000),
            processed_store_mode=os.getenv("PROCESSED_STORE_MODE", "local").strip().lower(),
            processed_local_root=processed_local_root,
            processed_s3_bucket=os.getenv("PROCESSED_S3_BUCKET"),
            processed_s3_prefix=os.getenv("PROCESSED_S3_PREFIX", "").strip("/"),
            external_transactions_bucket=os.getenv("EXTERNAL_TRANSACTIONS_BUCKET"),
            external_transactions_prefix=os.getenv("EXTERNAL_TRANSACTIONS_PREFIX", "").strip("/"),
            external_accounts_bucket=os.getenv("EXTERNAL_ACCOUNTS_BUCKET"),
            external_accounts_prefix=os.getenv("EXTERNAL_ACCOUNTS_PREFIX", "").strip("/"),
            managed_processed_bucket=os.getenv("MANAGED_PROCESSED_BUCKET"),
            managed_processed_prefix=os.getenv("MANAGED_PROCESSED_PREFIX", "").strip("/"),
            managed_kb_source_bucket=os.getenv("MANAGED_KB_SOURCE_BUCKET"),
            managed_kb_artifacts_bucket=os.getenv("MANAGED_KB_ARTIFACTS_BUCKET"),
            use_mock_bedrock=_get_bool("USE_MOCK_BEDROCK", True),
            use_local_rag=_get_bool("USE_LOCAL_RAG", True),
            enable_debug_traces=_get_bool("ENABLE_DEBUG_TRACES", True),
            aws_region=os.getenv("AWS_REGION", "eu-west-2"),
            bedrock_model_id=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20241022-v1:0"),
            bedrock_embedding_model_id=os.getenv("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"),
            bedrock_timeout_seconds=_get_int("BEDROCK_TIMEOUT_SECONDS", 30),
            kb_chunks_path=kb_chunks_path,
            kb_s3_bucket=os.getenv("KB_S3_BUCKET"),
            kb_s3_prefix=os.getenv("KB_S3_PREFIX", "").strip("/"),
        )
