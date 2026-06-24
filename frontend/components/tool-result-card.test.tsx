import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ToolResultCard } from "@/components/tool-result-card";
import type { ToolInvokeResponse } from "@/lib/types";

function makeResult(overrides: Partial<ToolInvokeResponse>): ToolInvokeResponse {
  return {
    request_id: "req-test-1",
    tool: "balances",
    arguments: {},
    payload: { records: [], warnings: [] },
    warnings: [],
    artifact_version: "v1",
    latency_ms: 12.3,
    ...overrides,
  };
}

describe("ToolResultCard", () => {
  it("renders the tool display name and read-only badge", () => {
    render(<ToolResultCard toolResult={makeResult({ tool: "balances" })} />);
    expect(screen.getByText("Account Balances")).toBeInTheDocument();
    expect(screen.getByText(/read-only/i)).toBeInTheDocument();
  });

  it("renders latency chip with ms suffix", () => {
    render(<ToolResultCard toolResult={makeResult({ latency_ms: 42.5 })} />);
    expect(screen.getByText("42.5ms")).toBeInTheDocument();
  });

  it("renders warning pills when warnings are present", () => {
    render(
      <ToolResultCard
        toolResult={makeResult({ warnings: ["Multiple currencies detected", "Date range capped"] })}
      />
    );
    expect(screen.getByText(/Multiple currencies detected/)).toBeInTheDocument();
    expect(screen.getByText(/Date range capped/)).toBeInTheDocument();
  });

  it("renders balance cards for balances payload", () => {
    render(
      <ToolResultCard
        toolResult={makeResult({
          tool: "balances",
          payload: {
            records: [
              {
                account_id: "acc-001",
                account_name: "Main Wallet",
                currency: "GHS",
                current_balance: "1200.50",
                available_balance: "1180.50",
              },
            ],
            warnings: [],
          },
        })}
      />
    );
    expect(screen.getByText("Main Wallet")).toBeInTheDocument();
    expect(screen.getByText(/1,200\.50/)).toBeInTheDocument();
    expect(screen.getByText(/available/i)).toBeInTheDocument();
  });

  it("masks account_id to last 4 chars in balance cards", () => {
    render(
      <ToolResultCard
        toolResult={makeResult({
          tool: "balances",
          payload: {
            records: [
              {
                account_id: "acc-00112345",
                account_name: "Savings",
                currency: "GHS",
                current_balance: "500.00",
                available_balance: "500.00",
              },
            ],
            warnings: [],
          },
        })}
      />
    );
    expect(screen.getByText("••••2345")).toBeInTheDocument();
    expect(screen.queryByText("acc-00112345")).not.toBeInTheDocument();
  });

  it("renders empty state when balance records list is empty", () => {
    render(
      <ToolResultCard
        toolResult={makeResult({
          tool: "balances",
          payload: { records: [], warnings: [] },
        })}
      />
    );
    expect(screen.getByText(/no account records found/i)).toBeInTheDocument();
  });

  it("renders transaction table for transaction_lookup payload", () => {
    render(
      <ToolResultCard
        toolResult={makeResult({
          tool: "transaction_lookup",
          payload: {
            records: [
              {
                transaction_id: "txn-001",
                account_id: "acc-001",
                timestamp: "2026-03-28T10:00:00Z",
                amount: "45.50",
                currency: "GHS",
                direction: "debit",
                merchant: "Fresh Market",
                category: "groceries",
                subcategory: "food",
              },
            ],
            match_count: 1,
            applied_filters: {},
            warnings: [],
          },
        })}
      />
    );
    expect(screen.getByText("Fresh Market")).toBeInTheDocument();
    expect(screen.getByText("groceries")).toBeInTheDocument();
    expect(screen.getByText(/45\.50/)).toBeInTheDocument();
    expect(screen.getByText(/1 result/i)).toBeInTheDocument();
  });

  it("renders empty state when transaction records list is empty", () => {
    render(
      <ToolResultCard
        toolResult={makeResult({
          tool: "transaction_lookup",
          payload: {
            records: [],
            match_count: 0,
            applied_filters: {},
            warnings: [],
          },
        })}
      />
    );
    expect(screen.getByText(/no transactions found/i)).toBeInTheDocument();
  });

  it("renders spend summary total for spend_summary payload", () => {
    render(
      <ToolResultCard
        toolResult={makeResult({
          tool: "spend_summary",
          payload: {
            total_amount: "500.00",
            transaction_count: 10,
            currency_breakdown: { GHS: "500.00" },
            grouped_breakdown: [
              { key: "groceries", total_amount: "200.00", transaction_count: 4, currency: "GHS" },
            ],
            applied_filters: {},
            warnings: [],
          },
        })}
      />
    );
    expect(screen.getByText(/500\.00/)).toBeInTheDocument();
    expect(screen.getByText("groceries")).toBeInTheDocument();
    expect(screen.getByText(/10 transaction/i)).toBeInTheDocument();
  });

  it("renders recurring patterns for recurring_detection payload", () => {
    render(
      <ToolResultCard
        toolResult={makeResult({
          tool: "recurring_detection",
          payload: {
            records: [
              {
                merchant: "Fuel Station",
                category: "transport",
                subcategory: "fuel",
                account_id: "acc-001",
                direction: "debit",
                cadence: "monthly",
                confidence: "high",
                transaction_count: 3,
                first_seen_timestamp: "2026-01-20T09:15:00Z",
                last_seen_timestamp: "2026-03-20T09:15:00Z",
                average_amount: "25.00",
                currency: "GHS",
                is_irregular: false,
              },
            ],
            match_count: 1,
            summary: {},
            applied_filters: {},
            warnings: [],
          },
        })}
      />
    );
    expect(screen.getByText("Fuel Station")).toBeInTheDocument();
    expect(screen.getByText("monthly")).toBeInTheDocument();
    expect(screen.getByText(/high confidence/i)).toBeInTheDocument();
    expect(screen.getByText(/25\.00/)).toBeInTheDocument();
  });

  it("renders status table for status_explanation payload", () => {
    render(
      <ToolResultCard
        toolResult={makeResult({
          tool: "status_explanation",
          payload: {
            counts_by_status: { posted: 3, pending: 1 },
            warnings: [],
          },
        })}
      />
    );
    expect(screen.getByText("posted")).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("renders fee total and table for fee_breakdown payload", () => {
    render(
      <ToolResultCard
        toolResult={makeResult({
          tool: "fee_breakdown",
          payload: {
            records: [
              {
                transaction_id: "txn-004",
                account_id: "acc-001",
                timestamp: "2026-03-10T08:30:00Z",
                amount: "2.50",
                currency: "GHS",
                direction: "debit",
                merchant: "PayJack Service Fee",
                category: "fees",
                subcategory: "transfer_fee",
                matched_reason: "fee",
              },
            ],
            total_amount: "2.50",
            transaction_count: 1,
            currency_breakdown: { GHS: "2.50" },
            applied_filters: {},
            warnings: [],
          },
        })}
      />
    );
    expect(screen.getByText("PayJack Service Fee")).toBeInTheDocument();
    expect(screen.getAllByText(/2\.50/).length).toBeGreaterThan(0);
    expect(screen.getByText(/total fees/i)).toBeInTheDocument();
  });

  it("renders applied filters as chips (skipping account_ids)", () => {
    render(
      <ToolResultCard
        toolResult={makeResult({
          tool: "transaction_lookup",
          arguments: {
            limit: 5,
            account_ids: ["acc-001"],
            merchant: "Fresh Market",
          },
          payload: {
            records: [],
            match_count: 0,
            applied_filters: {},
            warnings: [],
          },
        })}
      />
    );
    expect(screen.getByText(/limit: 5/i)).toBeInTheDocument();
    expect(screen.getByText(/merchant: Fresh Market/i)).toBeInTheDocument();
    // account_ids must NOT appear
    expect(screen.queryByText(/account_ids/i)).not.toBeInTheDocument();
    expect(screen.queryByText("acc-001")).not.toBeInTheDocument();
  });
});
