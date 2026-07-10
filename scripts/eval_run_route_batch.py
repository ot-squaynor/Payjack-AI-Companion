# scripts/eval_run_route_batch.py
# 2026-04-16
"""Purpose: Run JSONL route prompt batches against local or deployed Payjack chat backends."""

from __future__ import annotations

##BRICK 1: Imports, defaults, and CLI parsing
import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

from chat_eval_common import PROJECT_ROOT, request_chat, summarize_payload


DEFAULT_BATCH_DIR = PROJECT_ROOT / "tests" / "evaluation" / "route_batches"
PRESENCE_VALUES = {"empty", "non_empty", "any"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run route prompt JSONL batches against the local app or a deployed backend."
    )
    parser.add_argument(
        "--batch-path",
        action="append",
        default=[],
        help=(
            "JSONL file or directory of JSONL files. May be passed more than once. "
            "Defaults to tests/evaluation/route_batches."
        ),
    )
    parser.add_argument("--api-base-url", default=None)
    parser.add_argument("--user-id", default="dev-user")
    parser.add_argument("--tenant-id", default="dev-tenant")
    parser.add_argument("--roles", default="customer")
    parser.add_argument("--account-ids", default="acc-001")
    parser.add_argument("--expect-model-id", default=None)
    parser.add_argument("--changed-only", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--print-full-response", action="store_true")
    return parser.parse_args()


##BRICK 2: Batch loading helpers
def _resolve_batch_files(paths: list[str]) -> list[Path]:
    selected_paths = [Path(path) for path in paths] if paths else [DEFAULT_BATCH_DIR]
    batch_files: list[Path] = []
    for selected_path in selected_paths:
        resolved_path = selected_path if selected_path.is_absolute() else PROJECT_ROOT / selected_path
        if resolved_path.is_dir():
            batch_files.extend(sorted(resolved_path.glob("*.jsonl")))
        else:
            batch_files.append(resolved_path)
    return sorted(dict.fromkeys(batch_files))


def _load_cases(batch_files: list[Path], *, changed_only: bool, limit: int | None) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for batch_file in batch_files:
        if not batch_file.exists():
            raise FileNotFoundError(f"Batch file does not exist: {batch_file}")
        for line_number, line in enumerate(batch_file.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            case = json.loads(line)
            if changed_only and not case.get("normalization_changed"):
                continue
            case["_batch_path"] = str(batch_file)
            case["_line_number"] = line_number
            cases.append(case)
            if limit is not None and len(cases) >= limit:
                return cases
    return cases


def _safe_session_id(case_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._:-]", "-", f"route-batch-{case_id}")[:128]


##BRICK 3: Validation helpers
def _presence_failures(
    *,
    label: str,
    value: list[Any],
    expectation: str | None,
) -> list[str]:
    if expectation is None:
        return []
    if expectation not in PRESENCE_VALUES:
        return [f"{label}: unsupported presence expectation {expectation!r}"]
    if expectation == "empty" and value:
        return [f"{label}: expected empty but received {len(value)} item(s)"]
    if expectation == "non_empty" and not value:
        return [f"{label}: expected at least one item but received none"]
    return []


def _validate_case_response(
    *,
    case: dict[str, Any],
    status_code: int,
    body: dict[str, Any] | str,
    expected_model_id: str | None,
) -> list[str]:
    failures: list[str] = []
    expected_status = int(case.get("expected_http_status", 200))
    if status_code != expected_status:
        failures.append(f"expected HTTP {expected_status} but received {status_code}")
        return failures

    if not isinstance(body, dict):
        failures.append(f"expected JSON object response but received: {body!r}")
        return failures

    expected_route = case.get("expected_route")
    if expected_route is not None and body.get("route") != expected_route:
        failures.append(f"expected route {expected_route!r} but received {body.get('route')!r}")

    debug = body.get("debug") or {}
    expected_grounding_mode = case.get("expected_grounding_mode")
    if expected_grounding_mode is not None and debug.get("grounding_mode") != expected_grounding_mode:
        failures.append(
            f"expected grounding_mode {expected_grounding_mode!r} but received {debug.get('grounding_mode')!r}"
        )
    if expected_model_id and debug.get("model_id") != expected_model_id:
        failures.append(f"expected model_id {expected_model_id!r} but received {debug.get('model_id')!r}")

    tool_traces = body.get("tool_traces") or []
    failures.extend(
        _presence_failures(
            label="tool_traces",
            value=tool_traces,
            expectation=case.get("expected_tool_traces"),
        )
    )
    expected_tool_name = case.get("expected_tool_name")
    if expected_tool_name is not None and tool_traces:
        actual_tool_name = tool_traces[0].get("name")
        if actual_tool_name != expected_tool_name:
            failures.append(f"expected first tool {expected_tool_name!r} but received {actual_tool_name!r}")

    citations = body.get("citations") or []
    failures.extend(
        _presence_failures(
            label="citations",
            value=citations,
            expectation=case.get("expected_citations"),
        )
    )

    expected_refusal_category = case.get("expected_refusal_category")
    refusal = body.get("refusal")
    if expected_refusal_category is None and refusal is not None:
        failures.append(f"expected no refusal but received {refusal!r}")
    elif expected_refusal_category is not None:
        if not isinstance(refusal, dict):
            failures.append(f"expected refusal category {expected_refusal_category!r} but received no refusal")
        elif refusal.get("category") != expected_refusal_category:
            failures.append(
                f"expected refusal category {expected_refusal_category!r} but received {refusal.get('category')!r}"
            )

    return failures


def _summarize_case(
    *,
    case: dict[str, Any],
    status_code: int | None = None,
    body: dict[str, Any] | str | None = None,
    failures: list[str] | None = None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "id": case.get("id"),
        "batch": Path(case.get("_batch_path", "")).name,
        "line": case.get("_line_number"),
        "normalization_changed": bool(case.get("normalization_changed")),
        "expected_route": case.get("expected_route"),
        "expected_tool_name": case.get("expected_tool_name"),
    }
    if status_code is not None:
        summary["status_code"] = status_code
    if isinstance(body, dict):
        summary.update(
            {
                "actual_route": body.get("route"),
                "actual_tool_name": (body.get("tool_traces") or [{}])[0].get("name"),
                **summarize_payload(body),
            }
        )
    summary["passed"] = not failures
    if failures:
        summary["failures"] = failures
    return summary


##BRICK 4: CLI entrypoint
def main() -> None:
    args = parse_args()
    try:
        batch_files = _resolve_batch_files(args.batch_path)
        cases = _load_cases(batch_files, changed_only=args.changed_only, limit=args.limit)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if args.dry_run:
        print(
            json.dumps(
                {
                    "batch_files": [str(path) for path in batch_files],
                    "case_count": len(cases),
                    "changed_only": args.changed_only,
                },
                indent=2,
            )
        )
        return

    summaries: list[dict[str, Any]] = []
    failures_by_case: list[tuple[str, list[str]]] = []

    for case in cases:
        case_id = str(case.get("id", case.get("_line_number", "unknown")))
        try:
            status_code, body = request_chat(
                message=str(case["message"]),
                session_id=_safe_session_id(case_id),
                api_base_url=args.api_base_url,
                user_id=args.user_id,
                tenant_id=args.tenant_id,
                roles=args.roles,
                account_ids=args.account_ids,
                client_request_id=f"{case_id}-cli",
            )
        except Exception as exc:
            case_failures = [f"request failed: {exc}"]
            summaries.append(_summarize_case(case=case, failures=case_failures))
            failures_by_case.append((case_id, case_failures))
            if args.fail_fast:
                break
            continue

        case_failures = _validate_case_response(
            case=case,
            status_code=status_code,
            body=body,
            expected_model_id=args.expect_model_id,
        )
        summaries.append(
            _summarize_case(
                case=case,
                status_code=status_code,
                body=body,
                failures=case_failures,
            )
        )
        if args.print_full_response:
            print(json.dumps({"id": case_id, "response": body}, indent=2))
        if case_failures:
            failures_by_case.append((case_id, case_failures))
            if args.fail_fast:
                break

    print(json.dumps(summaries, indent=2))

    if failures_by_case:
        for case_id, case_failures in failures_by_case:
            for failure in case_failures:
                print(f"FAIL {case_id}: {failure}", file=sys.stderr)
        raise SystemExit(1)

    print(f"PASS: Route batch probe completed for {len(summaries)} case(s).")


if __name__ == "__main__":
    main()
