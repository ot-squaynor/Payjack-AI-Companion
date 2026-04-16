from __future__ import annotations

import re
from typing import Any


STOPWORDS = frozenset(
    {
        "a",
        "about",
        "an",
        "and",
        "are",
        "at",
        "be",
        "can",
        "could",
        "do",
        "for",
        "from",
        "hello",
        "hi",
        "how",
        "i",
        "in",
        "is",
        "it",
        "me",
        "my",
        "of",
        "on",
        "or",
        "our",
        "payjack",
        "please",
        "tell",
        "the",
        "there",
        "to",
        "us",
        "we",
        "what",
        "when",
        "where",
        "why",
        "with",
        "would",
        "you",
        "your",
    }
)


def _normalize_term(token: str) -> str:
    normalized = token.strip().lower()
    if not normalized:
        return ""

    if normalized.endswith("'s"):
        normalized = normalized[:-2]

    if len(normalized) > 4 and normalized.endswith("ies"):
        normalized = f"{normalized[:-3]}y"
    elif len(normalized) > 3 and normalized.endswith("s") and not normalized.endswith(("ss", "us", "is")):
        normalized = normalized[:-1]

    return normalized


def _tokenize(text: str, *, drop_stopwords: bool) -> list[str]:
    normalized_text = text.lower().replace("-", " ").replace("_", " ")
    tokens = re.findall(r"[a-z0-9]+", normalized_text)

    cleaned_tokens: list[str] = []
    for token in tokens:
        normalized = _normalize_term(token)
        if not normalized:
            continue
        if drop_stopwords and normalized in STOPWORDS:
            continue
        cleaned_tokens.append(normalized)
    return cleaned_tokens


def _query_terms(query: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_tokenize(query, drop_stopwords=True)))


def _contains_query_phrase(query_terms: tuple[str, ...], *, title: str, chunk_text: str) -> bool:
    if not query_terms:
        return False
    normalized_query = " ".join(query_terms)
    normalized_chunk = " ".join(_tokenize(f"{title} {chunk_text}", drop_stopwords=True))
    return normalized_query in normalized_chunk


def score_chunk(
    query: str,
    *,
    chunk_title: str,
    chunk_text: str,
) -> tuple[float, tuple[str, ...]]:
    query_terms = _query_terms(query)
    if not query_terms:
        return 0.0, ()

    query_term_set = set(query_terms)
    title_terms = set(_tokenize(chunk_title, drop_stopwords=True))
    body_terms = set(_tokenize(chunk_text, drop_stopwords=True))
    matched_title_terms = tuple(sorted(query_term_set.intersection(title_terms)))
    matched_terms = tuple(sorted(query_term_set.intersection(title_terms.union(body_terms))))
    if not matched_terms:
        return 0.0, ()

    term_coverage = len(matched_terms) / len(query_term_set)
    title_coverage = len(matched_title_terms) / len(query_term_set)
    phrase_bonus = 0.2 if _contains_query_phrase(query_terms, title=chunk_title, chunk_text=chunk_text) else 0.0
    score = term_coverage + (0.4 * title_coverage) + phrase_bonus
    return score, matched_terms


def rank_chunks(
    *,
    query: str,
    chunks: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    query_term_set = set(_query_terms(query))
    scored_chunks = []
    for chunk in chunks:
        title_term_set = set(_tokenize(str(chunk.get("title", "")), drop_stopwords=True))
        score, matched_terms = score_chunk(
            query,
            chunk_title=str(chunk.get("title", "")),
            chunk_text=str(chunk.get("text", "")),
        )
        if score <= 0:
            continue
        scored_chunks.append(
            {
                **chunk,
                "score": score,
                "matched_terms": matched_terms,
                "matched_term_count": len(matched_terms),
                "title_match_count": len(query_term_set.intersection(title_term_set)),
            }
        )

    scored_chunks.sort(
        key=lambda chunk: (
            float(chunk["score"]),
            int(chunk.get("matched_term_count", 0)),
            str(chunk.get("title", "")),
            str(chunk.get("doc_id", "")),
            int(chunk.get("chunk_id", 0)),
        ),
        reverse=True,
    )
    return scored_chunks[:limit]
