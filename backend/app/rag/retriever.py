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
        top_match_count = int(top_chunk.get("matched_term_count", 0))
        top_title_match_count = int(top_chunk.get("title_match_count", 0))

        if not top_snippet:
            return RetrieverResult.empty(
                reason="empty_top_snippet",
                retrieved_count=len(ranked_chunks),
                top_score=top_score,
            )
        if top_match_count < MIN_ACCEPTED_MATCHED_TERMS:
            return RetrieverResult.empty(
                reason="insufficient_term_overlap",
                retrieved_count=len(ranked_chunks),
                top_score=top_score,
            )
        if top_title_match_count < MIN_ACCEPTED_TITLE_MATCHES:
            return RetrieverResult.empty(
                reason="insufficient_title_overlap",
                retrieved_count=len(ranked_chunks),
                top_score=top_score,
            )
        if top_score < MIN_ACCEPTED_SCORE:
            return RetrieverResult.empty(
                reason="top_score_below_threshold",
                retrieved_count=len(ranked_chunks),
                top_score=top_score,
            )

        citations = []
        for chunk in ranked_chunks:
            snippet = str(chunk.get("text", "")).strip()
            if not snippet:
                continue
            if int(chunk.get("matched_term_count", 0)) < MIN_ACCEPTED_MATCHED_TERMS:
                continue
            if int(chunk.get("title_match_count", 0)) < MIN_ACCEPTED_TITLE_MATCHES:
                continue
            if float(chunk.get("score", 0.0)) < MIN_ACCEPTED_SCORE:
                continue
            citations.append(
                {
                    "doc_id": str(chunk.get("doc_id", "unknown")),
                    "title": str(chunk.get("title", chunk.get("doc_id", "Payjack documentation"))),
                    "snippet": snippet[:280],
                    "score": float(chunk.get("score", 0.0)),
                    "metadata": dict(chunk.get("metadata", {})),
                }
            )
            if len(citations) >= MAX_ACCEPTED_CITATIONS:
                break

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


def _load_s3_chunks(bucket: str, key: str) -> list[dict[str, Any]]:
    client = boto3.client("s3")
    try:
        response = client.get_object(Bucket=bucket, Key=key)
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
        prefix = settings.kb_s3_prefix.strip("/")
        key = f"{prefix}/chunks.jsonl" if prefix else "chunks.jsonl"
        chunks = _load_s3_chunks(settings.kb_s3_bucket, key)
        return KnowledgeRetriever(chunks)

    return None
