from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path

from openpyxl import load_workbook


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build chunked KB artifacts from local raw docs.")
    parser.add_argument("--input-dir", default="backend/kb/raw_docs")
    parser.add_argument("--output-dir", default="backend/kb/processed_docs")
    parser.add_argument("--metadata-dir", default="backend/kb/metadata")
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def _read_xlsx(path: Path) -> str:
    workbook = load_workbook(path, data_only=True, read_only=True)
    text_parts: list[str] = []
    for sheet in workbook.worksheets:
        text_parts.append(f"# Sheet: {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            values = [str(value).strip() for value in row if value is not None and str(value).strip()]
            if values:
                text_parts.append(" | ".join(values))
    return "\n".join(text_parts)


def _read_text_document(path: Path) -> str:
    if path.suffix.lower() in {".md", ".txt"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return json.dumps(payload, indent=2, sort_keys=True)
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        return _read_xlsx(path)
    raise ValueError(f"Unsupported KB document format: {path.suffix}")


def _split_into_chunks(text: str, *, chunk_size: int) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in text.splitlines() if paragraph.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for paragraph in paragraphs:
        paragraph_length = len(paragraph)
        if current and current_length + paragraph_length > chunk_size:
            chunks.append("\n".join(current))
            current = [paragraph]
            current_length = paragraph_length
        else:
            current.append(paragraph)
            current_length += paragraph_length

    if current:
        chunks.append("\n".join(current))

    return chunks


def main() -> None:
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

    supported_suffixes = {".md", ".txt", ".json", ".xlsx", ".xlsm"}
    for path in sorted(input_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in supported_suffixes:
            continue
        relative_path = path.relative_to(input_dir).as_posix()
        doc_id = relative_path.replace("/", "_").replace(".", "_")
        title = path.stem.replace("_", " ").replace("-", " ").title()
        text = _read_text_document(path)
        chunks = _split_into_chunks(text, chunk_size=args.chunk_size)
        processed_documents.append(relative_path)
        for chunk_index, chunk_text in enumerate(chunks):
            chunk_records.append(
                {
                    "doc_id": doc_id,
                    "chunk_id": chunk_index,
                    "title": title,
                    "text": chunk_text,
                    "metadata": {
                        "source_path": relative_path,
                        "type": path.parts[-2] if len(path.parts) >= 2 else "general",
                    },
                }
            )

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
