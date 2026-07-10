from pathlib import Path

from app.config import Settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = PROJECT_ROOT / "app"


def test_settings_resolve_backend_relative_paths_independent_of_cwd(monkeypatch) -> None:
    monkeypatch.setenv("PROCESSED_LOCAL_ROOT", "data/processed")
    monkeypatch.setenv("KB_CHUNKS_PATH", "kb/processed_docs/chunks.jsonl")

    monkeypatch.chdir(PROJECT_ROOT)
    settings_from_repo_root = Settings.from_env()

    monkeypatch.chdir(APP_ROOT)
    settings_from_app_root = Settings.from_env()

    expected_processed = (PROJECT_ROOT / "data" / "processed").resolve()
    expected_kb = (PROJECT_ROOT / "kb" / "processed_docs" / "chunks.jsonl").resolve()

    assert settings_from_repo_root.processed_local_root == expected_processed
    assert settings_from_app_root.processed_local_root == expected_processed
    assert settings_from_repo_root.kb_chunks_path == expected_kb
    assert settings_from_app_root.kb_chunks_path == expected_kb


def test_settings_preserve_existing_backend_prefixed_env_paths(monkeypatch) -> None:
    monkeypatch.setenv("PROCESSED_LOCAL_ROOT", "backend/data/processed")
    monkeypatch.setenv("KB_CHUNKS_PATH", "backend/kb/processed_docs/chunks.jsonl")

    settings = Settings.from_env()

    assert settings.processed_local_root == (PROJECT_ROOT / "data" / "processed").resolve()
    assert settings.kb_chunks_path == (PROJECT_ROOT / "kb" / "processed_docs" / "chunks.jsonl").resolve()


def test_settings_default_cors_origins_cover_localhost_and_loopback(monkeypatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    settings = Settings.from_env()

    assert settings.cors_origins == ("http://localhost:3000", "http://127.0.0.1:3000")


def test_settings_resolve_expected_bucket_owner_from_specific_or_account_env(
    monkeypatch,
) -> None:
    monkeypatch.delenv("S3_EXPECTED_BUCKET_OWNER", raising=False)
    monkeypatch.setenv("AWS_ACCOUNT_ID", "111122223333")

    assert Settings.from_env().s3_expected_bucket_owner == "111122223333"

    monkeypatch.setenv("S3_EXPECTED_BUCKET_OWNER", "444455556666")

    assert Settings.from_env().s3_expected_bucket_owner == "444455556666"
