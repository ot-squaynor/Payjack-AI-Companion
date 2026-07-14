# app/rag/retriever.py
# 2026-04-18
"""Module for retrieving relevant chunks of information based on user queries in the RAG pipeline.
This module defines the `KnowledgeRetriever` class, which is responsible for retrieving and ranking chunks of information based on a user's query. 
It applies metadata-based filters to ensure that only relevant chunks are considered and uses a ranking mechanism to prioritize the most relevant 
chunks. The retrieved chunks are then formatted as citations that can be used in generating responses to user queries. This module also includes 
helper functions for loading chunks from local files or S3 storage, as well as a factory function for building a `KnowledgeRetriever` instance 
based on application settings."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings
from app.rag.metadata_filters import apply_metadata_filters
from app.rag.vector_store import rank_chunks


DEFAULT_RETRIEVAL_LIMIT = 5
MAX_ACCEPTED_CITATIONS = 3
MIN_ACCEPTED_MATCHED_TERMS = 2
MIN_ACCEPTED_TITLE_MATCHES = 1
MIN_ACCEPTED_SCORE = 0.35
DEFAULT_DOC_TITLE = "Payjack documentation"


@dataclass(frozen=True, slots=True)
class RetrieverResult:
    citations: tuple[dict[str, Any], ...]
    usable_context: bool
    fallback_reason: str | None = None
    retrieved_count: int = 0
    accepted_count: int = 0
    top_score: float = 0.0

    def __iter__(self):
        return iter(self.citations)

    @classmethod
    def empty(
        cls,
        *,
        reason: str,
        retrieved_count: int = 0,
        top_score: float = 0.0,
    ) -> "RetrieverResult":
        return cls(
            citations=(),
            usable_context=False,
            fallback_reason=reason,
            retrieved_count=retrieved_count,
            accepted_count=0,
            top_score=top_score,
        )


class KnowledgeRetriever:
    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self.chunks = chunks

    def retrieve(
        self,
        query: str,
        *,
        limit: int = DEFAULT_RETRIEVAL_LIMIT,
        allowed_types: tuple[str, ...] = (),
    ) -> RetrieverResult:
        filtered_chunks = apply_metadata_filters(self.chunks, allowed_types=allowed_types)
        ranked_chunks = rank_chunks(query=query, chunks=filtered_chunks, limit=limit)
        if not ranked_chunks:
            return RetrieverResult.empty(reason="no_candidate_chunks")

        top_chunk = ranked_chunks[0]
        top_score = float(top_chunk.get("score", 0.0))
        top_snippet = str(top_chunk.get("text", "")).strip()

        rejection_reason = _chunk_rejection_reason(top_chunk, snippet=top_snippet)
        if rejection_reason is not None:
            return RetrieverResult.empty(
                reason=rejection_reason,
                retrieved_count=len(ranked_chunks),
                top_score=top_score,
            )

        citations = _accepted_citations(ranked_chunks)

        if not citations:
            return RetrieverResult.empty(
                reason="no_accepted_chunks",
                retrieved_count=len(ranked_chunks),
                top_score=top_score,
            )

        return RetrieverResult(
            citations=tuple(citations),
            usable_context=True,
            fallback_reason=None,
            retrieved_count=len(ranked_chunks),
            accepted_count=len(citations),
            top_score=top_score,
        )


def _has_sufficient_overlap(*, matched_term_count: int, title_match_count: int) -> bool:
    if matched_term_count >= MIN_ACCEPTED_MATCHED_TERMS:
        return True
    return matched_term_count >= 1 and title_match_count >= MIN_ACCEPTED_TITLE_MATCHES


def _chunk_rejection_reason(chunk: dict[str, Any], *, snippet: str) -> str | None:
    if not snippet:
        return "empty_top_snippet"
    if not _chunk_has_accepted_overlap(chunk):
        return "insufficient_term_overlap"
    if int(chunk.get("title_match_count", 0)) < MIN_ACCEPTED_TITLE_MATCHES:
        return "insufficient_title_overlap"
    if float(chunk.get("score", 0.0)) < MIN_ACCEPTED_SCORE:
        return "top_score_below_threshold"
    return None


def _chunk_has_accepted_overlap(chunk: dict[str, Any]) -> bool:
    return _has_sufficient_overlap(
        matched_term_count=int(chunk.get("matched_term_count", 0)),
        title_match_count=int(chunk.get("title_match_count", 0)),
    )


def _accepted_citation_from_chunk(chunk: dict[str, Any]) -> dict[str, Any] | None:
    snippet = str(chunk.get("text", "")).strip()
    if _chunk_rejection_reason(chunk, snippet=snippet) is not None:
        return None
    return {
        "doc_id": str(chunk.get("doc_id", "unknown")),
        "title": str(chunk.get("title", chunk.get("doc_id", DEFAULT_DOC_TITLE))),
        "snippet": snippet[:280],
        "score": float(chunk.get("score", 0.0)),
        "metadata": dict(chunk.get("metadata", {})),
    }


def _accepted_citations(ranked_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for chunk in ranked_chunks:
        citation = _accepted_citation_from_chunk(chunk)
        if citation is None:
            continue
        citations.append(citation)
        if len(citations) >= MAX_ACCEPTED_CITATIONS:
            break
    return citations


def _load_local_chunks(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    chunks = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        chunks.append(json.loads(line))
    return chunks


def _load_s3_chunks(
    bucket: str,
    key: str,
    *,
    expected_bucket_owner: str,
) -> list[dict[str, Any]]:
    client = boto3.client("s3")
    try:
        response = client.get_object(
            Bucket=bucket,
            Key=key,
            ExpectedBucketOwner=expected_bucket_owner,
        )
        payload = response["Body"].read().decode("utf-8")
    except (BotoCoreError, ClientError, KeyError) as exc:
        raise RuntimeError(f"Failed to load RAG chunks from s3://{bucket}/{key}: {exc}") from exc

    chunks = []
    for line in payload.splitlines():
        line = line.strip()
        if not line:
            continue
        chunks.append(json.loads(line))
    return chunks


def build_retriever(settings: Settings) -> KnowledgeRetriever | None:
    if settings.use_local_rag:
        chunks = _load_local_chunks(settings.kb_chunks_path)
        return KnowledgeRetriever(chunks)

    if settings.kb_s3_bucket:
        if not settings.s3_expected_bucket_owner:
            raise RuntimeError(
                "S3_EXPECTED_BUCKET_OWNER or AWS_ACCOUNT_ID must be set "
                "when loading RAG chunks from S3."
            )
        prefix = settings.kb_s3_prefix.strip("/")
        key = f"{prefix}/chunks.jsonl" if prefix else "chunks.jsonl"
        chunks = _load_s3_chunks(
            settings.kb_s3_bucket,
            key,
            expected_bucket_owner=settings.s3_expected_bucket_owner,
        )
        return KnowledgeRetriever(chunks)

    return None
