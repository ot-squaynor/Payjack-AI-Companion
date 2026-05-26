# app/rag/metadata_filters.py
# 2026-04-18
"""Module for applying metadata-based filters to retrieved chunks in the RAG pipeline. 
This module provides functionality for filtering retrieved chunks of information based on their associated metadata, such as type or source, 
to ensure that only relevant and appropriate information is used for generating responses to user queries. By centralizing this filtering logic 
in one place, we can maintain consistency across different parts of the application that utilize retrieved context and make it 
easier to update or modify the filtering criteria as needed."""

# IMPORTS - STANDARD LIBRARY
from __future__ import annotations

from typing import Any

#Function for applying metadata-based filters to a list of retrieved chunks based on allowed types specified as a tuple of strings. This function iterates through the list of chunks, checks their metadata for a "type" field, and includes only those chunks whose type matches one of the allowed types (case-insensitive) in the returned list. If no allowed types are specified, it returns all chunks unfiltered.
def apply_metadata_filters(
    chunks: list[dict[str, Any]],
    *,
    allowed_types: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    if not allowed_types:
        return list(chunks)

    allowed_type_set = {value.strip().lower() for value in allowed_types if value.strip()}
    filtered_chunks: list[dict[str, Any]] = []
    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        chunk_type = str(metadata.get("type", "")).strip().lower()
        if chunk_type in allowed_type_set:
            filtered_chunks.append(chunk)
    return filtered_chunks
