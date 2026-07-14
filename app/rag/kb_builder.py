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

EXT_MD = ".md"
EXT_TXT = ".txt"
EXT_JSON = ".json"
EXT_CSV = ".csv"
EXT_XLS = ".xls"
EXT_XLSX = ".xlsx"
EXT_XLSM = ".xlsm"

TEXT_SUFFIXES: frozenset[str] = frozenset({EXT_MD, EXT_TXT, EXT_JSON})
EXCEL_SUFFIXES: frozenset[str] = frozenset({EXT_XLS, EXT_XLSX, EXT_XLSM})
SUPPORTED_SUFFIXES: frozenset[str] = frozenset(
    {*TEXT_SUFFIXES, EXT_CSV, *EXCEL_SUFFIXES}
)

_STRUCTURED_SUFFIXES: frozenset[str] = frozenset({EXT_CSV, *EXCEL_SUFFIXES})
_OLE_MAGIC = b"\xd0\xcf\x11\xe0"


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


def _choose_text_chunk_end(
    normalized: str,
    *,
    start: int,
    target_end: int,
    chunk_size: int,
) -> int:
    if target_end >= len(normalized):
        return target_end

    minimum_boundary = start + (chunk_size // 2)
    boundaries = (
        normalized.rfind("\n", start, target_end),
        normalized.rfind(" ", start, target_end),
    )
    return next(
        (boundary for boundary in boundaries if boundary > minimum_boundary),
        target_end,
    )


def _next_text_chunk_start(
    normalized: str,
    *,
    start: int,
    end: int,
    safe_overlap: int,
) -> int:
    next_start = max(end - safe_overlap, start + 1)
    while next_start < len(normalized) and normalized[next_start].isspace():
        next_start += 1
    return next_start


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
        end = _choose_text_chunk_end(
            normalized,
            start=start,
            target_end=target_end,
            chunk_size=chunk_size,
        )

        chunk_text = normalized[start:end].strip()
        if chunk_text and (not chunks or chunks[-1] != chunk_text):
            chunks.append(chunk_text)

        if end >= length:
            break

        start = _next_text_chunk_start(
            normalized,
            start=start,
            end=end,
            safe_overlap=safe_overlap,
        )

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
        if ext in {EXT_MD, EXT_TXT}:
            raw = path.read_text(encoding="utf-8", errors="replace")
        elif ext == EXT_JSON:
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


def _read_excel_header(path: Path) -> bytes:
    try:
        return path.read_bytes()[:4]
    except OSError:
        return b""


def _excel_engine_for_suffix(ext: str) -> str:
    return "xlrd" if ext == EXT_XLS else "openpyxl"


def _read_excel_sheets(path: Path, relative_path: str) -> dict[str, Any] | None:
    try:
        import pandas as pd  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "pandas is required for Excel support. Install it with: pip install pandas openpyxl"
        ) from exc

    ext = path.suffix.lower()
    if _read_excel_header(path) == _OLE_MAGIC and ext != EXT_XLS:
        logger.warning(
            "Skipping %s: file appears to be in old .xls (OLE) format despite %s extension. "
            "Re-save the file as .xlsx, or rename it to .xls and install xlrd.",
            relative_path,
            ext,
        )
        return None

    try:
        return pd.read_excel(
            path,
            sheet_name=None,
            dtype=str,
            keep_default_na=False,
            engine=_excel_engine_for_suffix(ext),
        )
    except ImportError as exc:
        raise RuntimeError(
            f"Missing Excel engine for {path.suffix}: {exc}. "
            "Install openpyxl (for .xlsx/.xlsm) or xlrd (for .xls)."
        ) from exc
    except Exception as exc:
        logger.warning("Corrupt or unreadable Excel file %s: %s", relative_path, exc)
        return None


def _spreadsheet_chunk_metadata(
    *,
    relative_path: str,
    category: str,
    file_type: str,
    sheet_name: str | None,
    row_start: int | None,
    row_end: int | None,
    columns: list[str],
    chunk_type: str,
) -> dict[str, Any]:
    return {
        "source_path": relative_path,
        "type": category,
        "file_type": file_type,
        "sheet_name": sheet_name,
        "row_start": row_start,
        "row_end": row_end,
        "columns": columns,
        "chunk_type": chunk_type,
    }


def _excel_summary_chunk(
    *,
    path: Path,
    sheet_name: str,
    sheet_doc_id: str,
    sheet_title: str,
    relative_path: str,
    category: str,
    valid_headers: list[str],
    row_count: int,
    chunk_id: int,
) -> dict[str, Any]:
    summary_text = (
        f"Source: {path.name}\n"
        f"Sheet: {sheet_name}\n"
        f"File type: {path.suffix.lstrip('.')}\n"
        f"Columns: {', '.join(valid_headers)}\n"
        f"Row count: {row_count}"
    )
    return {
        "doc_id": f"{sheet_doc_id}_summary",
        "chunk_id": chunk_id,
        "title": sheet_title,
        "text": summary_text,
        "metadata": _spreadsheet_chunk_metadata(
            relative_path=relative_path,
            category=category,
            file_type=path.suffix.lstrip(".").lower(),
            sheet_name=sheet_name,
            row_start=None,
            row_end=None,
            columns=valid_headers,
            chunk_type="spreadsheet_sheet_summary",
        ),
    }


def _non_empty_excel_cell_lines(row: Any, valid_headers: list[str]) -> list[str]:
    return [
        f"  - {col}: {value}"
        for col in valid_headers
        for value in [_cell_to_str(row.get(col, ""))]
        if value
    ]


def _excel_row_title(sheet_title: str, row: Any, valid_headers: list[str]) -> str:
    first_vals = [
        value
        for col in valid_headers
        for value in [_cell_to_str(row.get(col, ""))]
        if value
    ][:3]
    return f"{sheet_title} â€“ {' â€“ '.join(first_vals)}" if first_vals else sheet_title


def _excel_row_chunk(
    *,
    path: Path,
    row: Any,
    df_index: int,
    sheet_name: str,
    sheet_doc_id: str,
    sheet_title: str,
    relative_path: str,
    category: str,
    valid_headers: list[str],
    chunk_id: int,
) -> dict[str, Any] | None:
    col_lines = _non_empty_excel_cell_lines(row, valid_headers)
    if not col_lines:
        return None

    spreadsheet_row = int(df_index) + 2  # 1=header, so data starts at 2
    row_text = (
        f"Source: {path.name}\n"
        f"Sheet: {sheet_name}\n"
        f"Row: {spreadsheet_row}\n"
        f"Columns:\n" + "\n".join(col_lines)
    )
    return {
        "doc_id": sheet_doc_id,
        "chunk_id": chunk_id,
        "title": _excel_row_title(sheet_title, row, valid_headers),
        "text": row_text,
        "metadata": _spreadsheet_chunk_metadata(
            relative_path=relative_path,
            category=category,
            file_type=path.suffix.lstrip(".").lower(),
            sheet_name=sheet_name,
            row_start=spreadsheet_row,
            row_end=spreadsheet_row,
            columns=valid_headers,
            chunk_type="spreadsheet_row",
        ),
    }


def _append_excel_sheet_chunks(
    chunks: list[dict[str, Any]],
    *,
    chunk_id: int,
    path: Path,
    sheet_name: str,
    df: Any,
    doc_id: str,
    title: str,
    relative_path: str,
    category: str,
) -> int:
    if df.empty:
        logger.debug("Skipping empty sheet '%s' in %s", sheet_name, relative_path)
        return chunk_id

    valid_headers = [str(c).strip() for c in df.columns if str(c).strip()]
    if not valid_headers:
        return chunk_id

    sheet_doc_id = f"{doc_id}_{_sanitize_sheet_name(sheet_name)}"
    sheet_title = f"{title} â€“ {sheet_name}"
    chunks.append(
        _excel_summary_chunk(
            path=path,
            sheet_name=sheet_name,
            sheet_doc_id=sheet_doc_id,
            sheet_title=sheet_title,
            relative_path=relative_path,
            category=category,
            valid_headers=valid_headers,
            row_count=len(df),
            chunk_id=chunk_id,
        )
    )
    chunk_id += 1

    for df_index, row in df.iterrows():
        row_chunk = _excel_row_chunk(
            path=path,
            row=row,
            df_index=df_index,
            sheet_name=sheet_name,
            sheet_doc_id=sheet_doc_id,
            sheet_title=sheet_title,
            relative_path=relative_path,
            category=category,
            valid_headers=valid_headers,
            chunk_id=chunk_id,
        )
        if row_chunk is None:
            continue
        chunks.append(row_chunk)
        chunk_id += 1

    return chunk_id


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
    sheets = _read_excel_sheets(path, relative_path)
    if sheets is None:
        return []

    chunks: list[dict[str, Any]] = []
    chunk_id = 0

    for sheet_name, df in sheets.items():
        chunk_id = _append_excel_sheet_chunks(
            chunks,
            chunk_id=chunk_id,
            path=path,
            sheet_name=sheet_name,
            df=df,
            doc_id=doc_id,
            title=title,
            relative_path=relative_path,
            category=category,
        )

    return chunks

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
    if ext in TEXT_SUFFIXES:
        return load_markdown_chunks(
            path,
            doc_id=doc_id,
            title=title,
            relative_path=relative_path,
            category=category,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    if ext == EXT_CSV:
        return load_csv_chunks(
            path,
            doc_id=doc_id,
            title=title,
            relative_path=relative_path,
            category=category,
        )
    if ext in EXCEL_SUFFIXES:
        return load_excel_chunks(
            path,
            doc_id=doc_id,
            title=title,
            relative_path=relative_path,
            category=category,
        )
    return []  # unreachable after SUPPORTED_SUFFIXES check
