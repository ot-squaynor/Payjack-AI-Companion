# app/rag/kb_builder.py
# 2026-06-24
"""
Purpose: File loaders for the KB build pipeline.

Each loader converts one source document into retrieval-ready chunk dicts.
New metadata fields (file_type, sheet_name, row_start, row_end, columns, chunk_type)
are additive and fully backwards-compatible with the existing KnowledgeRetriever.
"""

from __future__ import annotations

import csv
import datetime
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES: frozenset[str] = frozenset(
    {".md", ".txt", ".json", ".csv", ".xls", ".xlsx", ".xlsm"}
)

_STRUCTURED_SUFFIXES: frozenset[str] = frozenset({".csv", ".xls", ".xlsx", ".xlsm"})


# ---------------------------------------------------------------------------
# Cell value normalisation
# ---------------------------------------------------------------------------


def _cell_to_str(value: Any) -> str:
    """Convert a spreadsheet cell value to a clean, human-readable string."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()


def _sanitize_sheet_name(name: str) -> str:
    """Produce a safe identifier fragment from a sheet name."""
    return name.lower().replace(" ", "_").replace("/", "_").replace("\\", "_")


# ---------------------------------------------------------------------------
# Text chunker (Markdown / plain text / JSON)
# ---------------------------------------------------------------------------


def _split_into_chunks(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split text into overlapping chunks respecting paragraph and word boundaries."""
    paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    normalized = "\n".join(paragraphs).strip()
    if not normalized:
        return []

    safe_overlap = max(0, min(chunk_overlap, max(chunk_size - 1, 0)))
    chunks: list[str] = []
    start = 0
    length = len(normalized)

    while start < length:
        target_end = min(length, start + chunk_size)
        end = target_end

        if target_end < length:
            para_boundary = normalized.rfind("\n", start, target_end)
            word_boundary = normalized.rfind(" ", start, target_end)
            if para_boundary > start + (chunk_size // 2):
                end = para_boundary
            elif word_boundary > start + (chunk_size // 2):
                end = word_boundary

        chunk_text = normalized[start:end].strip()
        if chunk_text and (not chunks or chunks[-1] != chunk_text):
            chunks.append(chunk_text)

        if end >= length:
            break

        next_start = max(end - safe_overlap, start + 1)
        while next_start < length and normalized[next_start].isspace():
            next_start += 1
        start = next_start

    return chunks


# ---------------------------------------------------------------------------
# Markdown / plain text / JSON loader
# ---------------------------------------------------------------------------


def load_markdown_chunks(
    path: Path,
    *,
    doc_id: str,
    title: str,
    relative_path: str,
    category: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[dict[str, Any]]:
    """Load a Markdown, text, or JSON file and return text-based chunks."""
    ext = path.suffix.lower()
    try:
        if ext in {".md", ".txt"}:
            raw = path.read_text(encoding="utf-8", errors="replace")
        elif ext == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            raw = json.dumps(payload, indent=2, sort_keys=True)
        else:
            raise ValueError(f"load_markdown_chunks does not handle {ext}")
    except Exception as exc:
        logger.warning("Failed to read text document %s: %s", relative_path, exc)
        return []

    texts = _split_into_chunks(raw, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return [
        {
            "doc_id": doc_id,
            "chunk_id": i,
            "title": title,
            "text": chunk_text,
            "metadata": {
                "source_path": relative_path,
                "type": category,
                "file_type": ext.lstrip("."),
                "sheet_name": None,
                "row_start": None,
                "row_end": None,
                "columns": None,
                "chunk_type": "markdown_section",
            },
        }
        for i, chunk_text in enumerate(texts)
    ]


# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------


def load_csv_chunks(
    path: Path,
    *,
    doc_id: str,
    title: str,
    relative_path: str,
    category: str,
) -> list[dict[str, Any]]:
    """Load a CSV file and return one summary chunk plus one chunk per data row."""
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
            reader = csv.DictReader(fh)
            headers: list[str] = list(reader.fieldnames or [])
            rows = list(reader)
    except Exception as exc:
        logger.warning("Failed to read CSV %s: %s", relative_path, exc)
        return []

    if not headers:
        logger.warning("Skipping CSV %s: no column headers found", relative_path)
        return []

    chunks: list[dict[str, Any]] = []
    chunk_id = 0

    # Sheet-level summary chunk
    summary_text = (
        f"Source: {path.name}\n"
        f"File type: CSV\n"
        f"Columns: {', '.join(headers)}\n"
        f"Row count: {len(rows)}"
    )
    chunks.append(
        {
            "doc_id": f"{doc_id}_summary",
            "chunk_id": chunk_id,
            "title": title,
            "text": summary_text,
            "metadata": {
                "source_path": relative_path,
                "type": category,
                "file_type": "csv",
                "sheet_name": None,
                "row_start": None,
                "row_end": None,
                "columns": headers,
                "chunk_type": "spreadsheet_sheet_summary",
            },
        }
    )
    chunk_id += 1

    # Row-level chunks (row index is 1-based; header is row 0)
    for row_idx, row in enumerate(rows, start=1):
        col_lines = [
            f"  - {col}: {val}"
            for col in headers
            for val in [str(row.get(col, "")).strip()]
            if val
        ]
        if not col_lines:
            continue  # skip entirely empty rows

        # Include first 3 non-empty values in the title for BM25 title term matching
        first_vals = [
            str(row.get(col, "")).strip()
            for col in headers
            if str(row.get(col, "")).strip()
        ][:3]
        row_title = f"{title} – {' – '.join(first_vals)}" if first_vals else title

        row_text = (
            f"Source: {path.name}\n"
            f"Row: {row_idx}\n"
            f"Columns:\n" + "\n".join(col_lines)
        )

        chunks.append(
            {
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "title": row_title,
                "text": row_text,
                "metadata": {
                    "source_path": relative_path,
                    "type": category,
                    "file_type": "csv",
                    "sheet_name": None,
                    "row_start": row_idx,
                    "row_end": row_idx,
                    "columns": headers,
                    "chunk_type": "spreadsheet_row",
                },
            }
        )
        chunk_id += 1

    return chunks


# ---------------------------------------------------------------------------
# Excel loader (.xlsx / .xlsm / .xls)
# ---------------------------------------------------------------------------


def load_excel_chunks(
    path: Path,
    *,
    doc_id: str,
    title: str,
    relative_path: str,
    category: str,
) -> list[dict[str, Any]]:
    """
    Load every sheet in an Excel workbook and return one summary chunk per sheet
    plus one chunk per data row.

    Uses pandas.read_excel so both .xlsx (openpyxl) and .xls (xlrd) are supported.
    dtype=str and keep_default_na=False prevent float-coercion and NaN artefacts.
    """
    try:
        import pandas as pd  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "pandas is required for Excel support. Install it with: pip install pandas openpyxl"
        ) from exc

    # Choose engine explicitly so pandas doesn't attempt xlrd for .xlsx files.
    ext = path.suffix.lower()
    engine = "xlrd" if ext == ".xls" else "openpyxl"

    # Detect OLE magic bytes — a file that is actually XLS but named .xlsx.
    _OLE_MAGIC = b"\xd0\xcf\x11\xe0"
    try:
        file_header = path.read_bytes()[:4]
    except OSError:
        file_header = b""

    if file_header == _OLE_MAGIC and ext != ".xls":
        logger.warning(
            "Skipping %s: file appears to be in old .xls (OLE) format despite %s extension. "
            "Re-save the file as .xlsx, or rename it to .xls and install xlrd.",
            relative_path,
            ext,
        )
        return []

    try:
        sheets: dict[str, Any] = pd.read_excel(
            path,
            sheet_name=None,
            dtype=str,
            keep_default_na=False,
            engine=engine,
        )
    except ImportError as exc:
        raise RuntimeError(
            f"Missing Excel engine for {path.suffix}: {exc}. "
            "Install openpyxl (for .xlsx/.xlsm) or xlrd (for .xls)."
        ) from exc
    except Exception as exc:
        logger.warning("Corrupt or unreadable Excel file %s: %s", relative_path, exc)
        return []

    chunks: list[dict[str, Any]] = []
    chunk_id = 0

    for sheet_name, df in sheets.items():
        if df.empty:
            logger.debug("Skipping empty sheet '%s' in %s", sheet_name, relative_path)
            continue

        headers = [str(c).strip() for c in df.columns]
        valid_headers = [h for h in headers if h]
        if not valid_headers:
            continue

        sheet_doc_id = f"{doc_id}_{_sanitize_sheet_name(sheet_name)}"
        sheet_title = f"{title} – {sheet_name}"

        # Sheet-level summary chunk
        summary_text = (
            f"Source: {path.name}\n"
            f"Sheet: {sheet_name}\n"
            f"File type: {path.suffix.lstrip('.')}\n"
            f"Columns: {', '.join(valid_headers)}\n"
            f"Row count: {len(df)}"
        )
        chunks.append(
            {
                "doc_id": f"{sheet_doc_id}_summary",
                "chunk_id": chunk_id,
                "title": sheet_title,
                "text": summary_text,
                "metadata": {
                    "source_path": relative_path,
                    "type": category,
                    "file_type": path.suffix.lstrip(".").lower(),
                    "sheet_name": sheet_name,
                    "row_start": None,
                    "row_end": None,
                    "columns": valid_headers,
                    "chunk_type": "spreadsheet_sheet_summary",
                },
            }
        )
        chunk_id += 1

        # Row-level chunks
        # df_index is 0-based; spreadsheet row = df_index + 2 (header is row 1)
        for df_index, row in df.iterrows():
            col_lines = []
            for col in valid_headers:
                val = _cell_to_str(row.get(col, ""))
                if val:
                    col_lines.append(f"  - {col}: {val}")

            if not col_lines:
                continue  # skip rows where every cell is empty

            first_vals = [
                _cell_to_str(row.get(col, ""))
                for col in valid_headers
                if _cell_to_str(row.get(col, ""))
            ][:3]
            row_title = (
                f"{sheet_title} – {' – '.join(first_vals)}" if first_vals else sheet_title
            )

            spreadsheet_row = int(df_index) + 2  # 1=header, so data starts at 2

            row_text = (
                f"Source: {path.name}\n"
                f"Sheet: {sheet_name}\n"
                f"Row: {spreadsheet_row}\n"
                f"Columns:\n" + "\n".join(col_lines)
            )

            chunks.append(
                {
                    "doc_id": sheet_doc_id,
                    "chunk_id": chunk_id,
                    "title": row_title,
                    "text": row_text,
                    "metadata": {
                        "source_path": relative_path,
                        "type": category,
                        "file_type": path.suffix.lstrip(".").lower(),
                        "sheet_name": sheet_name,
                        "row_start": spreadsheet_row,
                        "row_end": spreadsheet_row,
                        "columns": valid_headers,
                        "chunk_type": "spreadsheet_row",
                    },
                }
            )
            chunk_id += 1

    return chunks


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def load_file_chunks(
    path: Path,
    *,
    doc_id: str,
    title: str,
    relative_path: str,
    category: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[dict[str, Any]]:
    """Route a KB source file to the appropriate loader by extension."""
    ext = path.suffix.lower()
    if ext not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"Unsupported KB document format: {ext!r}. "
            f"Supported: {sorted(SUPPORTED_SUFFIXES)}"
        )
    if ext in {".md", ".txt", ".json"}:
        return load_markdown_chunks(
            path,
            doc_id=doc_id,
            title=title,
            relative_path=relative_path,
            category=category,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    if ext == ".csv":
        return load_csv_chunks(
            path,
            doc_id=doc_id,
            title=title,
            relative_path=relative_path,
            category=category,
        )
    if ext in {".xls", ".xlsx", ".xlsm"}:
        return load_excel_chunks(
            path,
            doc_id=doc_id,
            title=title,
            relative_path=relative_path,
            category=category,
        )
    return []  # unreachable after SUPPORTED_SUFFIXES check
