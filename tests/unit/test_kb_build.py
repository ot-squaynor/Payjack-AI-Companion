# tests/unit/test_kb_build.py
# 2026-06-24
"""Purpose: Unit tests for the KB build loader functions in app.rag.kb_builder."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import openpyxl
import pytest

from app.rag.kb_builder import (
    load_csv_chunks,
    load_excel_chunks,
    load_file_chunks,
    load_markdown_chunks,
)
from app.rag.vector_store import rank_chunks


# ---------------------------------------------------------------------------
# Helpers for building temp test files
# ---------------------------------------------------------------------------


def _make_csv(tmp_path: Path, headers: list[str], rows: list[list[str]]) -> Path:
    import csv

    p = tmp_path / "test.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        writer.writerows(rows)
    return p


def _make_xlsx(
    tmp_path: Path,
    sheets: dict[str, tuple[list[str], list[list[Any]]]],
    filename: str = "test.xlsx",
) -> Path:
    """Create an XLSX file with one or more sheets.

    sheets: {sheet_name: (headers, rows)}
    """
    p = tmp_path / filename
    wb = openpyxl.Workbook()
    first = True
    for sheet_name, (headers, rows) in sheets.items():
        if first:
            ws = wb.active
            ws.title = sheet_name
            first = False
        else:
            ws = wb.create_sheet(sheet_name)
        ws.append(headers)
        for row in rows:
            ws.append(row)
    wb.save(p)
    return p


_COMMON_KWARGS: dict[str, Any] = dict(
    doc_id="test_doc",
    title="Test Doc",
    relative_path="test/test.csv",
    category="test",
)

_REQUIRED_CHUNK_FIELDS = {"doc_id", "chunk_id", "title", "text", "metadata"}
_REQUIRED_METADATA_FIELDS = {
    "source_path", "type", "file_type", "sheet_name",
    "row_start", "row_end", "columns", "chunk_type",
}


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest) -> Path:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", request.node.name)
    path = Path(__file__).resolve().parents[2] / ".pytest_runtime_assets" / "kb_build" / safe_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _assert_chunk_schema(chunk: dict[str, Any]) -> None:
    assert _REQUIRED_CHUNK_FIELDS.issubset(chunk.keys()), f"Missing fields: {chunk.keys()}"
    assert _REQUIRED_METADATA_FIELDS.issubset(chunk["metadata"].keys()), (
        f"Missing metadata fields: {chunk['metadata'].keys()}"
    )


# ---------------------------------------------------------------------------
# Markdown tests
# ---------------------------------------------------------------------------


def test_load_markdown_chunks_returns_markdown_section_chunks(tmp_path: Path) -> None:
    p = tmp_path / "doc.md"
    p.write_text("# Hello\n\nThis is a test document with some content.\n", encoding="utf-8")

    chunks = load_markdown_chunks(
        p, doc_id="test", title="Doc", relative_path="doc.md", category="help"
    )

    assert len(chunks) >= 1
    assert all(c["metadata"]["chunk_type"] == "markdown_section" for c in chunks)
    assert all(c["metadata"]["file_type"] == "md" for c in chunks)
    assert all(c["metadata"]["sheet_name"] is None for c in chunks)


# ---------------------------------------------------------------------------
# CSV tests
# ---------------------------------------------------------------------------


def test_load_csv_chunks_basic(tmp_path: Path) -> None:
    p = _make_csv(tmp_path, ["Name", "Amount", "Status"], [["Alice", "100", "Active"]])

    chunks = load_csv_chunks(p, **{**_COMMON_KWARGS, "relative_path": "test/test.csv"})

    # at minimum: 1 summary + 1 row
    assert len(chunks) >= 2


def test_load_csv_chunks_summary_is_first_chunk(tmp_path: Path) -> None:
    p = _make_csv(tmp_path, ["Name", "Amount"], [["Bob", "50"]])

    chunks = load_csv_chunks(p, **{**_COMMON_KWARGS, "relative_path": "test/test.csv"})

    assert chunks[0]["metadata"]["chunk_type"] == "spreadsheet_sheet_summary"
    assert chunks[0]["chunk_id"] == 0


def test_load_csv_chunks_preserves_row_numbers(tmp_path: Path) -> None:
    p = _make_csv(
        tmp_path,
        ["Type", "Value"],
        [["fee", "1.5"], ["limit", "5000"]],
    )

    chunks = load_csv_chunks(p, **{**_COMMON_KWARGS, "relative_path": "test/test.csv"})

    row_chunks = [c for c in chunks if c["metadata"]["chunk_type"] == "spreadsheet_row"]
    assert row_chunks[0]["metadata"]["row_start"] == 1
    assert row_chunks[1]["metadata"]["row_start"] == 2


def test_load_csv_chunks_skips_empty_rows(tmp_path: Path) -> None:
    p = _make_csv(tmp_path, ["Name", "Amount"], [["Alice", "100"], ["", ""], ["Bob", "200"]])

    chunks = load_csv_chunks(p, **{**_COMMON_KWARGS, "relative_path": "test/test.csv"})

    row_chunks = [c for c in chunks if c["metadata"]["chunk_type"] == "spreadsheet_row"]
    assert len(row_chunks) == 2  # empty row skipped


def test_load_csv_chunks_preserves_column_names_in_metadata(tmp_path: Path) -> None:
    headers = ["Account ID", "Balance", "Currency"]
    p = _make_csv(tmp_path, headers, [["ACC-001", "500", "GHS"]])

    chunks = load_csv_chunks(p, **{**_COMMON_KWARGS, "relative_path": "test/test.csv"})

    assert chunks[0]["metadata"]["columns"] == headers


# ---------------------------------------------------------------------------
# Excel tests
# ---------------------------------------------------------------------------


def test_load_excel_chunks_basic(tmp_path: Path) -> None:
    p = _make_xlsx(
        tmp_path,
        {"Accounts": (["ID", "Name", "Balance"], [["ACC-001", "Ama Mensah", "1200.50"]])},
    )

    chunks = load_excel_chunks(
        p, doc_id="test_doc", title="Accounts", relative_path="test/test.xlsx", category="fees"
    )

    assert len(chunks) >= 2  # at least summary + 1 row


def test_load_excel_chunks_preserves_sheet_name(tmp_path: Path) -> None:
    p = _make_xlsx(
        tmp_path,
        {"Transfer Limits": (["Type", "Limit"], [["Wallet-to-Bank", "5000"]])},
    )

    chunks = load_excel_chunks(
        p, doc_id="test_doc", title="Limits", relative_path="test/test.xlsx", category="limits"
    )

    assert all(c["metadata"]["sheet_name"] == "Transfer Limits" for c in chunks)


def test_load_excel_chunks_preserves_row_numbers(tmp_path: Path) -> None:
    p = _make_xlsx(
        tmp_path,
        {"Fees": (["Name", "Rate"], [["Transfer Fee", "1.5%"], ["ATM Fee", "2.0%"]])},
    )

    chunks = load_excel_chunks(
        p, doc_id="test_doc", title="Fees", relative_path="test/test.xlsx", category="fees"
    )

    row_chunks = [c for c in chunks if c["metadata"]["chunk_type"] == "spreadsheet_row"]
    assert row_chunks[0]["metadata"]["row_start"] == 2  # header is row 1, first data row is 2
    assert row_chunks[1]["metadata"]["row_start"] == 3


def test_load_excel_chunks_multiple_sheets(tmp_path: Path) -> None:
    p = _make_xlsx(
        tmp_path,
        {
            "Fees": (["Type", "Rate"], [["Transfer", "1%"]]),
            "Limits": (["Type", "Value"], [["Daily", "5000"]]),
        },
    )

    chunks = load_excel_chunks(
        p, doc_id="test_doc", title="Doc", relative_path="test/test.xlsx", category="fees"
    )

    sheet_names = {c["metadata"]["sheet_name"] for c in chunks}
    assert "Fees" in sheet_names
    assert "Limits" in sheet_names


def test_load_excel_chunks_empty_cells_do_not_crash(tmp_path: Path) -> None:
    p = _make_xlsx(
        tmp_path,
        {"Data": (["Name", "Notes", "Amount"], [["Alice", "", "50"], ["", "some note", "100"]])},
    )

    chunks = load_excel_chunks(
        p, doc_id="test_doc", title="Data", relative_path="test/test.xlsx", category="test"
    )

    row_chunks = [c for c in chunks if c["metadata"]["chunk_type"] == "spreadsheet_row"]
    assert len(row_chunks) == 2
    # Verify text contains non-empty cell values and omits empty ones
    assert "Alice" in row_chunks[0]["text"]
    assert "Notes" not in row_chunks[0]["text"]  # empty Note cell omitted


def test_load_excel_chunks_corrupt_file_returns_empty_list(tmp_path: Path) -> None:
    p = tmp_path / "corrupt.xlsx"
    p.write_bytes(b"this is not a valid xlsx file at all")

    chunks = load_excel_chunks(
        p, doc_id="test_doc", title="Corrupt", relative_path="test/corrupt.xlsx", category="test"
    )

    assert chunks == []


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_chunk_schema_required_fields(tmp_path: Path) -> None:
    csv_path = _make_csv(tmp_path, ["Name", "Value"], [["Alpha", "10"]])
    chunks = load_csv_chunks(
        csv_path, doc_id="d", title="T", relative_path="t.csv", category="cat"
    )
    for chunk in chunks:
        _assert_chunk_schema(chunk)

    xlsx_path = _make_xlsx(tmp_path, {"Sheet1": (["Col1", "Col2"], [["a", "b"]])})
    xchunks = load_excel_chunks(
        xlsx_path, doc_id="d", title="T", relative_path="t.xlsx", category="cat"
    )
    for chunk in xchunks:
        _assert_chunk_schema(chunk)


# ---------------------------------------------------------------------------
# Retrieval smoke tests
# ---------------------------------------------------------------------------


def test_csv_chunks_retrievable_by_keyword(tmp_path: Path) -> None:
    p = _make_csv(
        tmp_path,
        ["Type", "Daily Limit", "Currency"],
        [
            ["Wallet-to-Bank", "5000", "GHS"],
            ["Wallet-to-Wallet", "10000", "GHS"],
        ],
    )

    chunks = load_csv_chunks(
        p,
        doc_id="limits",
        title="Transfer Limits",
        relative_path="limits.csv",
        category="limits",
    )

    ranked = rank_chunks(query="wallet bank daily limit", chunks=chunks, limit=5)

    assert len(ranked) >= 1
    top = ranked[0]
    assert "Wallet-to-Bank" in top["text"] or "Wallet-to-Bank" in top["title"]


def test_excel_chunks_retrievable_by_keyword(tmp_path: Path) -> None:
    p = _make_xlsx(
        tmp_path,
        {
            "Fees": (
                ["Fee Type", "Rate", "Notes"],
                [
                    ["Transfer Fee", "1.5%", "Wallet-to-bank transfers"],
                    ["ATM Withdrawal Fee", "2.0%", "Cash withdrawals"],
                ],
            )
        },
    )

    chunks = load_excel_chunks(
        p,
        doc_id="fees_doc",
        title="Payjack Fees",
        relative_path="fees/fees.xlsx",
        category="fees",
    )

    ranked = rank_chunks(query="transfer fee rate", chunks=chunks, limit=5)

    assert len(ranked) >= 1
    top = ranked[0]
    assert "Transfer Fee" in top["text"] or "Transfer Fee" in top["title"]


# ---------------------------------------------------------------------------
# load_file_chunks dispatcher
# ---------------------------------------------------------------------------


def test_load_file_chunks_dispatches_csv(tmp_path: Path) -> None:
    p = _make_csv(tmp_path, ["A", "B"], [["1", "2"]])

    chunks = load_file_chunks(
        p, doc_id="d", title="T", relative_path="t.csv", category="cat"
    )

    assert any(c["metadata"]["file_type"] == "csv" for c in chunks)


def test_load_file_chunks_dispatches_xlsx(tmp_path: Path) -> None:
    p = _make_xlsx(tmp_path, {"S1": (["X", "Y"], [["a", "b"]])})

    chunks = load_file_chunks(
        p, doc_id="d", title="T", relative_path="t.xlsx", category="cat"
    )

    assert any(c["metadata"]["file_type"] == "xlsx" for c in chunks)


def test_load_file_chunks_raises_on_unsupported_extension(tmp_path: Path) -> None:
    p = tmp_path / "file.pdf"
    p.write_bytes(b"%PDF fake")

    with pytest.raises(ValueError, match="Unsupported KB document format"):
        load_file_chunks(p, doc_id="d", title="T", relative_path="t.pdf", category="cat")
