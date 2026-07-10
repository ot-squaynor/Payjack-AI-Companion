# scripts/embeddings_generate.py
# 2026-04-02
"""Purpose: Generate deterministic placeholder embedding artifacts for local KB testing."""

from __future__ import annotations

##BRICK 1: Imports, repository bootstrap, and env loading
import argparse
import hashlib
import json
import logging
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.env import load_local_env


load_local_env()
logger = logging.getLogger(__name__)


##BRICK 2: CLI parsing and deterministic embedding helpers
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic placeholder embedding metadata.")
    parser.add_argument("--chunks-path", default="kb/processed_docs/chunks.jsonl")
    parser.add_argument("--output-path", default="kb/processed_docs/embeddings.jsonl")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def _token_hashes(text: str) -> list[int]:
    hashes = []
    for token in sorted({token for token in text.lower().split() if token.strip()}):
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]
        hashes.append(int(digest, 16))
    return hashes


##BRICK 3: CLI entrypoint
def main() -> None:
    load_local_env()
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    chunks_path = Path(args.chunks_path)
    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    records_written = 0
    with chunks_path.open("r", encoding="utf-8") as source, output_path.open("w", encoding="utf-8") as target:
        for line in source:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            record = {
                "doc_id": payload["doc_id"],
                "chunk_id": payload["chunk_id"],
                "token_hashes": _token_hashes(str(payload.get("text", ""))),
            }
            target.write(json.dumps(record, ensure_ascii=False) + "\n")
            records_written += 1

    logger.info("Embedding metadata generation complete. records=%s", records_written)


if __name__ == "__main__":
    main()
