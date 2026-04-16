# scripts/eval_run_e2e.py
# 2026-04-14
"""Purpose: Exercise both tool and RAG chat paths and report the effective model usage."""

from __future__ import annotations

##BRICK 1: Imports and CLI parsing
import argparse
import json
import sys

from chat_eval_common import post_chat, summarize_payload, validate_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run end-to-end chat probes for the tool and RAG paths."
    )
    parser.add_argument("--api-base-url", default=None)
    parser.add_argument("--user-id", default="dev-user")
    parser.add_argument("--tenant-id", default="dev-tenant")
    parser.add_argument("--roles", default="customer")
    parser.add_argument("--account-ids", default="acc-001")
    parser.add_argument("--tool-message", default="Show my last 2 transactions")
    parser.add_argument("--rag-message", default="What is the Payjack fee policy?")
    parser.add_argument("--expect-model-id", default=None)
    parser.add_argument("--require-rag-citations", action="store_true")
    parser.add_argument("--print-full-response", action="store_true")
    return parser.parse_args()


##BRICK 2: CLI entrypoint
def main() -> None:
    args = parse_args()
    scenarios = [
        {
            "name": "tool", # This scenario is designed to trigger the tool route, which should invoke the mock Bedrock client and return a deterministic response. The test will validate that the expected route was taken, and that tool traces are present in the response. Citations are not expected for this scenario.
            "message": args.tool_message,
            "session_id": "e2e-tool",
            "client_request_id": "e2e-tool-cli",
            "expected_route": "tool",
            "require_citations": False,
            "require_tool_traces": True,
        },
        {
            "name": "rag", # This scenario is designed to trigger the RAG route, which should also invoke the mock Bedrock client and return a deterministic response. The test will validate that the expected route was taken, and that citations are present in the response if --require-rag-citations is set. Tool traces are not expected for this scenario.
            "message": args.rag_message,
            "session_id": "e2e-rag",
            "client_request_id": "e2e-rag-cli",
            "expected_route": "rag",
            "require_citations": args.require_rag_citations,
            "require_tool_traces": False,
        },
    ]

    summaries: list[dict[str, object]] = []
    failures: list[str] = []

    for scenario in scenarios:
        try:
            payload = post_chat(
                message=scenario["message"],
                session_id=scenario["session_id"],
                api_base_url=args.api_base_url,
                user_id=args.user_id,
                tenant_id=args.tenant_id,
                roles=args.roles,
                account_ids=args.account_ids,
                client_request_id=scenario["client_request_id"],
            )
        except Exception as exc:
            failures.append(f"{scenario['name']}: request failed: {exc}")
            continue
        summary = {
            "scenario": scenario["name"],
            **summarize_payload(payload),
        }
        summaries.append(summary)

        if args.print_full_response:
            print(json.dumps({"scenario": scenario["name"], "payload": payload}, indent=2))

        scenario_failures = validate_payload(
            payload,
            expected_route=scenario["expected_route"],
            expected_model_id=args.expect_model_id,
            require_citations=scenario["require_citations"],
            require_tool_traces=scenario["require_tool_traces"],
        )
        failures.extend(f"{scenario['name']}: {failure}" for failure in scenario_failures)

    print(json.dumps(summaries, indent=2))

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        raise SystemExit(1)

    print("PASS: Tool and RAG route probes completed.")


if __name__ == "__main__":
    main()
