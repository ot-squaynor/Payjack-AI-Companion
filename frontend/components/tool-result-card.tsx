"use client";

import { Wrench } from "lucide-react";
import type {
  ToolInvokeResponse,
  TransactionLookupPayload,
  SpendSummaryPayload,
  RecurringDetectionPayload,
  BalancesPayload,
  StatusExplanationPayload,
  FeeBreakdownPayload,
  TransactionRecord,
  FeeRecord,
} from "@/lib/types";
import { TOOL_CATALOG } from "@/components/tool-menu";

function maskAccountId(id: string): string {
  return id.length > 4 ? `••••${id.slice(-4)}` : id;
}

function formatAmount(amount: string | number | null | undefined, currency?: string | null): string {
  if (amount === null || amount === undefined) return "—";
  const n = typeof amount === "string" ? parseFloat(amount) : amount;
  if (isNaN(n)) return String(amount);
  const formatted = n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return currency ? `${formatted} ${currency}` : formatted;
}

function formatDate(ts: string): string {
  try {
    return new Date(ts).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return ts;
  }
}

function EmptyState({ message }: { message: string }) {
  return <p className="tool-empty-state">{message}</p>;
}

function TransactionTable({ records }: { records: TransactionRecord[] }) {
  if (records.length === 0) return <EmptyState message="No transactions found for the applied filters." />;
  return (
    <div className="tool-result-table-wrap">
      <table className="tool-result-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Merchant</th>
            <th>Category</th>
            <th>Direction</th>
            <th>Amount</th>
          </tr>
        </thead>
        <tbody>
          {records.map((r) => (
            <tr key={r.transaction_id}>
              <td>{formatDate(r.timestamp)}</td>
              <td>{r.merchant}</td>
              <td>{r.category}</td>
              <td>{r.direction}</td>
              <td>{formatAmount(r.amount, r.currency)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AppliedFilters({ args }: { args: Record<string, unknown> }) {
  const entries = Object.entries(args).filter(
    ([k, v]) => k !== "account_ids" && v !== null && v !== undefined && v !== ""
  );
  if (entries.length === 0) return null;
  return (
    <div className="tool-applied-filters" aria-label="Applied filters">
      {entries.map(([key, value]) => {
        let display = String(value);
        if (key.endsWith("_date") || key === "date_from" || key === "date_to") {
          display = new Date(display).toLocaleDateString();
        }
        if (Array.isArray(value)) display = value.join(", ");
        return (
          <span key={key} className="tool-filter-chip">
            {key.replace(/_/g, " ")}: {display}
          </span>
        );
      })}
    </div>
  );
}

function TransactionLookupResult({ payload }: { payload: TransactionLookupPayload }) {
  return (
    <>
      <p style={{ color: "var(--text-muted)", fontSize: "0.84rem", marginBottom: 12 }}>
        {payload.match_count} result{payload.match_count !== 1 ? "s" : ""} found
      </p>
      <TransactionTable records={payload.records} />
    </>
  );
}

function SpendSummaryResult({ payload }: { payload: SpendSummaryPayload }) {
  const currencies = Object.entries(payload.currency_breakdown);
  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <p style={{ color: "var(--text-muted)", fontSize: "0.78rem", margin: "0 0 4px" }}>Total spend</p>
        <p style={{ color: "var(--payjack-yellow)", fontSize: "1.5rem", fontWeight: 760, margin: 0 }}>
          {currencies.length === 1
            ? formatAmount(payload.total_amount, currencies[0][0])
            : formatAmount(payload.total_amount)}
        </p>
        <p style={{ color: "var(--text-muted)", fontSize: "0.82rem", margin: "4px 0 0" }}>
          {payload.transaction_count} transaction{payload.transaction_count !== 1 ? "s" : ""}
        </p>
      </div>
      {payload.grouped_breakdown.length > 0 ? (
        <div className="tool-result-table-wrap">
          <table className="tool-result-table">
            <thead>
              <tr>
                <th>Group</th>
                <th>Transactions</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {payload.grouped_breakdown.map((row) => (
                <tr key={row.key}>
                  <td>{row.key}</td>
                  <td>{row.transaction_count}</td>
                  <td>{formatAmount(row.total_amount, row.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState message="No grouped data available for the selected filters." />
      )}
    </>
  );
}

function RecurringDetectionResult({ payload }: { payload: RecurringDetectionPayload }) {
  return (
    <>
      <p style={{ color: "var(--text-muted)", fontSize: "0.84rem", marginBottom: 12 }}>
        {payload.match_count} recurring pattern{payload.match_count !== 1 ? "s" : ""} detected
      </p>
      {payload.records.length === 0 ? (
        <EmptyState message="No recurring patterns detected for the selected filters." />
      ) : (
        <div className="recurring-list">
          {payload.records.map((r, i) => (
            <div key={i} className="recurring-card">
              <div>
                <p className="recurring-card-merchant">{r.merchant}</p>
                <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", margin: "2px 0 0" }}>
                  {r.category}
                </p>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                <span className="badge-cadence">{r.cadence}</span>
                <span className="badge-cadence" style={{ background: "rgba(35,213,196,0.12)", color: "#72f4e8" }}>
                  {r.confidence} confidence
                </span>
                <span style={{ color: "var(--text-soft)", fontSize: "0.88rem", fontWeight: 760 }}>
                  {formatAmount(r.average_amount, r.currency)} avg
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function BalancesResult({ payload }: { payload: BalancesPayload }) {
  if (payload.records.length === 0) return <EmptyState message="No account records found." />;
  return (
    <div className="balance-cards">
      {payload.records.map((r) => (
        <div key={r.account_id} className="balance-card">
          <p className="balance-card-name">
            {r.account_name ?? maskAccountId(r.account_id)}
          </p>
          <p className="balance-card-amount">
            {formatAmount(r.current_balance, r.currency ?? undefined)}
          </p>
          <p className="balance-card-available">
            Available: {formatAmount(r.available_balance, r.currency ?? undefined)}
          </p>
          <p style={{ color: "var(--text-muted)", fontSize: "0.72rem", margin: "6px 0 0" }}>
            {maskAccountId(r.account_id)}
          </p>
        </div>
      ))}
    </div>
  );
}

function StatusExplanationResult({ payload }: { payload: StatusExplanationPayload }) {
  const entries = Object.entries(payload.counts_by_status);
  if (entries.length === 0) return <EmptyState message="No status data found for the selected period." />;
  return (
    <div className="tool-result-table-wrap">
      <table className="tool-result-table">
        <thead>
          <tr>
            <th>Status</th>
            <th>Count</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([status, count]) => (
            <tr key={status}>
              <td style={{ textTransform: "capitalize" }}>{status}</td>
              <td>{count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FeeBreakdownResult({ payload }: { payload: FeeBreakdownPayload }) {
  const currencies = Object.entries(payload.currency_breakdown);
  const primaryCurrency = currencies.length === 1 ? currencies[0][0] : undefined;
  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <p style={{ color: "var(--text-muted)", fontSize: "0.78rem", margin: "0 0 4px" }}>Total fees</p>
        <p style={{ color: "var(--payjack-yellow)", fontSize: "1.5rem", fontWeight: 760, margin: 0 }}>
          {formatAmount(payload.total_amount, primaryCurrency)}
        </p>
        <p style={{ color: "var(--text-muted)", fontSize: "0.82rem", margin: "4px 0 0" }}>
          {payload.transaction_count} fee transaction{payload.transaction_count !== 1 ? "s" : ""}
        </p>
      </div>
      {payload.records.length === 0 ? (
        <EmptyState message="No fees found for the selected period." />
      ) : (
        <div className="tool-result-table-wrap">
          <table className="tool-result-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Merchant</th>
                <th>Amount</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {payload.records.map((r: FeeRecord) => (
                <tr key={r.transaction_id}>
                  <td>{formatDate(r.timestamp)}</td>
                  <td>{r.merchant}</td>
                  <td>{formatAmount(r.amount, r.currency)}</td>
                  <td style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>{r.matched_reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function ToolPayload({ toolResult }: { toolResult: ToolInvokeResponse }) {
  const { tool, payload } = toolResult;

  switch (tool) {
    case "transaction_lookup":
      return <TransactionLookupResult payload={payload as unknown as TransactionLookupPayload} />;
    case "spend_summary":
      return <SpendSummaryResult payload={payload as unknown as SpendSummaryPayload} />;
    case "recurring_detection":
      return <RecurringDetectionResult payload={payload as unknown as RecurringDetectionPayload} />;
    case "balances":
      return <BalancesResult payload={payload as unknown as BalancesPayload} />;
    case "status_explanation":
      return <StatusExplanationResult payload={payload as unknown as StatusExplanationPayload} />;
    case "fee_breakdown":
      return <FeeBreakdownResult payload={payload as unknown as FeeBreakdownPayload} />;
    default:
      return (
        <pre style={{ overflowX: "auto", fontSize: "0.78rem", color: "var(--text-muted)" }}>
          {JSON.stringify(payload, null, 2)}
        </pre>
      );
  }
}

type ToolResultCardProps = {
  toolResult: ToolInvokeResponse;
};

export function ToolResultCard({ toolResult }: ToolResultCardProps) {
  const entry = TOOL_CATALOG.find((t) => t.name === toolResult.tool);
  const label = entry?.label ?? toolResult.tool;
  const Icon = entry?.icon ?? Wrench;

  return (
    <div className="tool-result-card" aria-label={`${label} result`}>
      <div className="tool-result-header">
        <h3 className="tool-result-title">
          <span aria-hidden="true"><Icon size={16} /></span> {label}
        </h3>
        <span className="badge-readonly">read-only</span>
        <span className="badge-latency" aria-label={`${toolResult.latency_ms}ms`}>
          {toolResult.latency_ms.toFixed(1)}ms
        </span>
      </div>

      {toolResult.warnings.length > 0 && (
        <div className="tool-warnings" role="alert" aria-label="Warnings">
          {toolResult.warnings.map((w, i) => (
            <span key={i} className="tool-warning-pill">⚠ {w}</span>
          ))}
        </div>
      )}

      <AppliedFilters args={toolResult.arguments} />

      <ToolPayload toolResult={toolResult} />
    </div>
  );
}
