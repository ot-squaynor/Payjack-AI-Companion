# scripts/eval_run_rag.py
# 2026-04-14
"""Purpose: Probe a RAG-style chat prompt and report the effective model and citation state."""

from __future__ import annotations

##BRICK 1: Imports and CLI parsing
import argparse
import json
import sys

from chat_eval_common import post_chat, summarize_payload, validate_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a RAG-oriented chat probe against the local app or a live backend."
    )
    parser.add_argument("--message", default="What is the Payjack fee policy?")
    parser.add_argument("--api-base-url", default=None)
    parser.add_argument("--user-id", default="dev-user")
    parser.add_argument("--tenant-id", default="dev-tenant")
    parser.add_argument("--roles", default="customer")
    parser.add_argument("--account-ids", default="acc-001")
    parser.add_argument("--session-id", default="rag-eval")
    parser.add_argument("--client-request-id", default="rag-eval-cli")
    parser.add_argument("--expect-model-id", default=None)
    parser.add_argument("--require-citations", action="store_true")
    parser.add_argument("--print-full-response", action="store_true")
    return parser.parse_args()


##BRICK 2: CLI entrypoint
def main() -> None:
    args = parse_args()
    try:
        payload = post_chat(
            message=args.message,
            session_id=args.session_id,
            api_base_url=args.api_base_url,
            user_id=args.user_id,
            tenant_id=args.tenant_id,
            roles=args.roles,
            account_ids=args.account_ids,
            client_request_id=args.client_request_id,
        )
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    summary = summarize_payload(payload)
    print(json.dumps(summary, indent=2))

    if args.print_full_response:
        print(json.dumps(payload, indent=2))

    failures = validate_payload(
        payload,
        expected_route="rag",
        expected_model_id=args.expect_model_id,
        require_citations=args.require_citations,
    )
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        raise SystemExit(1)

    print("PASS: RAG route probe completed.")


if __name__ == "__main__":
    main()
