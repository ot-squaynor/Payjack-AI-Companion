# scripts/kb_build.py
# 2026-04-02
"""Purpose: Chunk local KB source documents into retrieval-ready JSONL artifacts."""

from __future__ import annotations

##BRICK 1: Imports, repository bootstrap, and env loading
import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.env import load_local_env
from backend.app.rag.kb_builder import SUPPORTED_SUFFIXES, load_file_chunks


load_local_env()
logger = logging.getLogger(__name__)


##BRICK 2: CLI parsing
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build chunked KB artifacts from local raw docs.")
    parser.add_argument("--input-dir", default="backend/kb/raw_docs")
    parser.add_argument("--output-dir", default="backend/kb/processed_docs")
    parser.add_argument("--metadata-dir", default="backend/kb/metadata")
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


##BRICK 3: CLI entrypoint
def main() -> None:
    load_local_env()
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    metadata_dir = Path(args.metadata_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    chunk_records: list[dict[str, object]] = []
    processed_documents: list[str] = []

    for path in sorted(input_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        relative_path = path.relative_to(input_dir).as_posix()
        doc_id = relative_path.replace("/", "_").replace(".", "_")
        title = path.stem.replace("_", " ").replace("-", " ").title()
        category = path.parts[-2] if len(path.parts) >= 2 else "general"
        try:
            file_chunks = load_file_chunks(
                path,
                doc_id=doc_id,
                title=title,
                relative_path=relative_path,
                category=category,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
            )
        except Exception as exc:  # pragma: no cover - depends on local document formats
            logger.warning("Skipping KB source %s: %s", relative_path, exc)
            continue
        if not file_chunks:
            logger.warning("Skipping empty or unreadable KB source %s", relative_path)
            continue
        processed_documents.append(relative_path)
        chunk_records.extend(file_chunks)

    chunks_path = output_dir / "chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as handle:
        for record in chunk_records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    manifest = {
        "build_id": datetime.now(timezone.utc).strftime("kb_%Y%m%dT%H%M%SZ"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "documents": processed_documents,
        "chunk_count": len(chunk_records),
    }
    (metadata_dir / "kb_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    logger.info("KB build complete. documents=%s chunks=%s", len(processed_documents), len(chunk_records))


if __name__ == "__main__":
    main()
