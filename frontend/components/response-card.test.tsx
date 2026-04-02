import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResponseCard } from "@/components/response-card";


describe("ResponseCard", () => {
  it("renders refusal, tool traces, citations, and debug details", () => {
    render(
      <ResponseCard
        showDebug
        response={{
          request_id: "req-1",
          session_id: "session-1",
          route: "hybrid",
          answer: "I can explain the restriction, but I cannot move money.",
          tool_traces: [
            {
              name: "status_explanation",
              arguments: { account_id: "acc-001" },
              result: { status: "restricted" },
              warnings: [],
              artifact_version: "dataset-1"
            }
          ],
          citations: [
            {
              doc_id: "fees_policy",
              title: "Fees Policy",
              snippet: "Transfers are disabled for read-only support sessions.",
              score: 0.92,
              metadata: { type: "policy" }
            }
          ],
          refusal: {
            category: "disallowed_action",
            message: "Payjack cannot execute money movement."
          },
          debug: {
            route_decision: "refuse"
          }
        }}
      />
    );

    expect(screen.getByText("I can explain the restriction, but I cannot move money.")).toBeInTheDocument();
    expect(screen.getByText("Refusal")).toBeInTheDocument();
    expect(screen.getByText(/Payjack cannot execute money movement/)).toBeInTheDocument();
    expect(screen.getByText("Tool Traces")).toBeInTheDocument();
    expect(screen.getByText("status_explanation")).toBeInTheDocument();
    expect(screen.getByText("Citations")).toBeInTheDocument();
    expect(screen.getByText("Fees Policy")).toBeInTheDocument();
    expect(screen.getByText("Debug")).toBeInTheDocument();
  });
});
