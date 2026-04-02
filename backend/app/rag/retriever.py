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


@dataclass(frozen=True, slots=True)
class RetrieverResult:
    citations: tuple[dict[str, Any], ...]

    def __iter__(self):
        return iter(self.citations)


class KnowledgeRetriever:
    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self.chunks = chunks

    def retrieve(
        self,
        query: str,
        *,
        limit: int = 3,
        allowed_types: tuple[str, ...] = (),
    ) -> RetrieverResult:
        filtered_chunks = apply_metadata_filters(self.chunks, allowed_types=allowed_types)
        ranked_chunks = rank_chunks(query=query, chunks=filtered_chunks, limit=limit)
        citations = []
        for chunk in ranked_chunks:
            citations.append(
                {
                    "doc_id": str(chunk.get("doc_id", "unknown")),
                    "title": str(chunk.get("title", chunk.get("doc_id", "Payjack documentation"))),
                    "snippet": str(chunk.get("text", ""))[:280],
                    "score": float(chunk.get("score", 0.0)),
                    "metadata": dict(chunk.get("metadata", {})),
                }
            )
        return RetrieverResult(citations=tuple(citations))


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
