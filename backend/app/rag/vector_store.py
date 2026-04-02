from __future__ import annotations

from collections import Counter
import math
from typing import Any


def _tokenize(text: str) -> list[str]:
    return [token for token in text.lower().split() if token.strip()]


def score_chunk(query: str, chunk_text: str) -> float:
    query_tokens = Counter(_tokenize(query))
    chunk_tokens = Counter(_tokenize(chunk_text))
    if not query_tokens or not chunk_tokens:
        return 0.0

    numerator = sum(query_tokens[token] * chunk_tokens[token] for token in query_tokens)
    query_norm = math.sqrt(sum(value * value for value in query_tokens.values()))
    chunk_norm = math.sqrt(sum(value * value for value in chunk_tokens.values()))
    if query_norm == 0 or chunk_norm == 0:
        return 0.0
    return numerator / (query_norm * chunk_norm)


def rank_chunks(
    *,
    query: str,
    chunks: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    scored_chunks = []
    for chunk in chunks:
        score = score_chunk(query, str(chunk.get("text", "")))
        if score <= 0:
            continue
        scored_chunks.append({**chunk, "score": score})

    scored_chunks.sort(
        key=lambda chunk: (
            chunk["score"],
            str(chunk.get("doc_id", "")),
            int(chunk.get("chunk_id", 0)),
        ),
        reverse=True,
    )
    return scored_chunks[:limit]
