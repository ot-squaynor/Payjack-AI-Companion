from __future__ import annotations

import argparse
import logging
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload processed KB artifacts to S3.")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", default="")
    parser.add_argument("--processed-dir", default="backend/kb/processed_docs")
    parser.add_argument("--metadata-dir", default="backend/kb/metadata")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def _upload_directory(s3_client, *, bucket: str, prefix: str, directory: Path) -> None:
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        relative_path = path.relative_to(directory).as_posix()
        key = f"{prefix}/{relative_path}" if prefix else relative_path
        try:
            s3_client.upload_file(str(path), bucket, key)
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Failed to upload {path} to s3://{bucket}/{key}: {exc}") from exc


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    s3_client = boto3.client("s3")
    processed_dir = Path(args.processed_dir)
    metadata_dir = Path(args.metadata_dir)
    prefix = args.prefix.strip("/")

    _upload_directory(
        s3_client,
        bucket=args.bucket,
        prefix=f"{prefix}/processed_docs" if prefix else "processed_docs",
        directory=processed_dir,
    )
    _upload_directory(
        s3_client,
        bucket=args.bucket,
        prefix=f"{prefix}/metadata" if prefix else "metadata",
        directory=metadata_dir,
    )

    logger.info("KB artifacts published to s3://%s/%s", args.bucket, prefix)


if __name__ == "__main__":
    main()
