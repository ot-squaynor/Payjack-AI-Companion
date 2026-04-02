from __future__ import annotations

from typing import Any


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
