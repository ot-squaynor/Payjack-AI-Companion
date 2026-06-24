"use client";

import { useEffect, useRef, useState } from "react";
import type { ToolName } from "@/lib/types";

type ToolMenuProps = {
  isOpen: boolean;
  onClose: () => void;
  onInvoke: (tool: ToolName, args: Record<string, unknown>) => void;
  disabled?: boolean;
};

export const TOOL_CATALOG = [
  {
    name: "transaction_lookup" as const,
    label: "Transaction Lookup",
    icon: "🔍",
    description: "Find transactions by date, merchant, or category",
  },
  {
    name: "spend_summary" as const,
    label: "Spend Summary",
    icon: "📊",
    description: "Summarise spending by category, merchant, or month",
  },
  {
    name: "recurring_detection" as const,
    label: "Recurring Payments",
    icon: "🔁",
    description: "Detect recurring charges and subscriptions",
  },
  {
    name: "balances" as const,
    label: "Account Balances",
    icon: "💰",
    description: "Current and available balance for your accounts",
  },
  {
    name: "status_explanation" as const,
    label: "Status Explanation",
    icon: "ℹ️",
    description: "Understand pending, posted, or failed transaction statuses",
  },
  {
    name: "fee_breakdown" as const,
    label: "Fee Breakdown",
    icon: "🧾",
    description: "Itemise fees charged within a date range",
  },
] as const;

function getDefaultDateFrom(): string {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().slice(0, 10);
}

function getDefaultDateTo(): string {
  return new Date().toISOString().slice(0, 10);
}

function parseArgs(tool: ToolName, formState: Record<string, string>): Record<string, unknown> {
  const args: Record<string, unknown> = {};

  const str = (key: string) => formState[key]?.trim() || undefined;
  const num = (key: string) => {
    const v = parseFloat(formState[key] ?? "");
    return isNaN(v) ? undefined : v;
  };
  const int = (key: string) => {
    const v = parseInt(formState[key] ?? "", 10);
    return isNaN(v) ? undefined : v;
  };
  const arr = (key: string) =>
    formState[key]
      ? formState[key].split(",").map((s) => s.trim()).filter(Boolean)
      : undefined;
  const bool = (key: string) =>
    formState[key] === "true" ? true : formState[key] === "false" ? false : undefined;

  if (tool === "transaction_lookup") {
    if (str("date_from")) args.date_from = str("date_from");
    if (str("date_to")) args.date_to = str("date_to");
    if (str("merchant")) args.merchant = str("merchant");
    if (str("category")) args.category = str("category");
    if (str("direction")) args.direction = str("direction");
    if (num("amount_min") !== undefined) args.amount_min = num("amount_min");
    if (num("amount_max") !== undefined) args.amount_max = num("amount_max");
    if (int("limit") !== undefined) args.limit = int("limit");
    if (str("sort_by")) args.sort_by = str("sort_by");
    if (bool("sort_descending") !== undefined) args.sort_descending = bool("sort_descending");
  } else if (tool === "spend_summary") {
    if (str("date_from")) args.date_from = str("date_from");
    if (str("date_to")) args.date_to = str("date_to");
    if (str("group_by")) args.group_by = str("group_by");
    if (str("direction")) args.direction = str("direction");
    const cats = arr("categories");
    if (cats?.length) args.categories = cats;
    const merchants = arr("merchants");
    if (merchants?.length) args.merchants = merchants;
  } else if (tool === "recurring_detection") {
    if (str("cadence")) args.cadence = str("cadence");
    if (str("confidence")) args.confidence = str("confidence");
    if (bool("include_irregular") !== undefined) args.include_irregular = bool("include_irregular");
    if (num("min_average_amount") !== undefined) args.min_average_amount = num("min_average_amount");
    const merchants = arr("merchants");
    if (merchants?.length) args.merchants = merchants;
    const cats = arr("categories");
    if (cats?.length) args.categories = cats;
  } else if (tool === "status_explanation") {
    if (str("date_from")) args.date_from = str("date_from");
    if (str("date_to")) args.date_to = str("date_to");
  } else if (tool === "fee_breakdown") {
    if (str("date_from")) args.date_from = str("date_from");
    if (str("date_to")) args.date_to = str("date_to");
    if (int("limit") !== undefined) args.limit = int("limit");
    const txnIds = arr("transaction_ids");
    if (txnIds?.length) args.transaction_ids = txnIds;
  }
  // balances: no user-supplied args needed; account scoping is automatic

  return args;
}

function DateRangeFields({
  formState,
  onChange,
}: {
  formState: Record<string, string>;
  onChange: (key: string, value: string) => void;
}) {
  return (
    <div className="tool-date-range-row">
      <div className="tool-form-field">
        <label htmlFor="tool-date-from">From date</label>
        <input
          id="tool-date-from"
          type="date"
          value={formState.date_from ?? getDefaultDateFrom()}
          onChange={(e) => onChange("date_from", e.target.value)}
        />
      </div>
      <div className="tool-form-field">
        <label htmlFor="tool-date-to">To date</label>
        <input
          id="tool-date-to"
          type="date"
          value={formState.date_to ?? getDefaultDateTo()}
          onChange={(e) => onChange("date_to", e.target.value)}
        />
      </div>
    </div>
  );
}

function AdvancedSection({
  children,
}: {
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="tool-form-advanced-section">
      <button
        type="button"
        className="tool-form-advanced-toggle"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="advanced-toggle-icon" aria-hidden="true">{open ? "▾" : "▸"}</span>
        Advanced filters
      </button>
      {open && (
        <div className="tool-form-advanced-fields">
          {children}
        </div>
      )}
    </div>
  );
}

function ToolForm({
  tool,
  formState,
  onChange,
  onSubmit,
  onBack,
  onClose,
  disabled,
}: {
  tool: ToolName;
  formState: Record<string, string>;
  onChange: (key: string, value: string) => void;
  onSubmit: () => void;
  onBack: () => void;
  onClose: () => void;
  disabled?: boolean;
}) {
  const entry = TOOL_CATALOG.find((t) => t.name === tool)!;

  return (
    <div>
      <button type="button" className="tool-form-back" onClick={onBack} aria-label="Back to tool list">
        ← Back
      </button>
      <p className="tool-form-title">
        {entry.icon} {entry.label}{" "}
        <span className="badge-readonly">read-only</span>
      </p>

      {tool === "transaction_lookup" && (
        <>
          <DateRangeFields formState={formState} onChange={onChange} />
          <div className="tool-form-field">
            <label htmlFor="tool-limit">Max results</label>
            <input
              id="tool-limit"
              type="number"
              min={1}
              max={100}
              placeholder="20"
              value={formState.limit ?? ""}
              onChange={(e) => onChange("limit", e.target.value)}
            />
          </div>
          <AdvancedSection>
            <div className="tool-form-field">
              <label htmlFor="tool-merchant">Merchant</label>
              <input
                id="tool-merchant"
                type="text"
                placeholder="e.g. Fresh Market"
                value={formState.merchant ?? ""}
                onChange={(e) => onChange("merchant", e.target.value)}
              />
            </div>
            <div className="tool-form-field">
              <label htmlFor="tool-category">Category</label>
              <input
                id="tool-category"
                type="text"
                placeholder="e.g. groceries"
                value={formState.category ?? ""}
                onChange={(e) => onChange("category", e.target.value)}
              />
            </div>
            <div className="tool-form-field">
              <label htmlFor="tool-direction">Direction</label>
              <select
                id="tool-direction"
                value={formState.direction ?? ""}
                onChange={(e) => onChange("direction", e.target.value)}
              >
                <option value="">Any</option>
                <option value="debit">Debit</option>
                <option value="credit">Credit</option>
              </select>
            </div>
            <div className="tool-form-field">
              <label htmlFor="tool-amount-min">Min amount</label>
              <input
                id="tool-amount-min"
                type="number"
                min={0}
                step="0.01"
                placeholder="0.00"
                value={formState.amount_min ?? ""}
                onChange={(e) => onChange("amount_min", e.target.value)}
              />
            </div>
            <div className="tool-form-field">
              <label htmlFor="tool-amount-max">Max amount</label>
              <input
                id="tool-amount-max"
                type="number"
                min={0}
                step="0.01"
                placeholder="any"
                value={formState.amount_max ?? ""}
                onChange={(e) => onChange("amount_max", e.target.value)}
              />
            </div>
            <div className="tool-form-field">
              <label htmlFor="tool-sort-by">Sort by</label>
              <select
                id="tool-sort-by"
                value={formState.sort_by ?? ""}
                onChange={(e) => onChange("sort_by", e.target.value)}
              >
                <option value="">Default</option>
                <option value="timestamp">Date</option>
                <option value="amount">Amount</option>
                <option value="merchant">Merchant</option>
              </select>
            </div>
          </AdvancedSection>
        </>
      )}

      {tool === "spend_summary" && (
        <>
          <DateRangeFields formState={formState} onChange={onChange} />
          <div className="tool-form-field">
            <label htmlFor="tool-group-by">Group by</label>
            <select
              id="tool-group-by"
              value={formState.group_by ?? ""}
              onChange={(e) => onChange("group_by", e.target.value)}
            >
              <option value="">None</option>
              <option value="category">Category</option>
              <option value="merchant">Merchant</option>
              <option value="month">Month</option>
              <option value="currency">Currency</option>
            </select>
          </div>
          <AdvancedSection>
            <div className="tool-form-field">
              <label htmlFor="tool-direction-spend">Direction</label>
              <select
                id="tool-direction-spend"
                value={formState.direction ?? ""}
                onChange={(e) => onChange("direction", e.target.value)}
              >
                <option value="">Any</option>
                <option value="debit">Debit</option>
                <option value="credit">Credit</option>
              </select>
            </div>
            <div className="tool-form-field">
              <label htmlFor="tool-categories">Categories (comma-separated)</label>
              <input
                id="tool-categories"
                type="text"
                placeholder="e.g. groceries, transport"
                value={formState.categories ?? ""}
                onChange={(e) => onChange("categories", e.target.value)}
              />
            </div>
            <div className="tool-form-field">
              <label htmlFor="tool-merchants">Merchants (comma-separated)</label>
              <input
                id="tool-merchants"
                type="text"
                placeholder="e.g. Fresh Market"
                value={formState.merchants ?? ""}
                onChange={(e) => onChange("merchants", e.target.value)}
              />
            </div>
          </AdvancedSection>
        </>
      )}

      {tool === "recurring_detection" && (
        <>
          <div className="tool-form-field">
            <label htmlFor="tool-cadence">Cadence</label>
            <select
              id="tool-cadence"
              value={formState.cadence ?? ""}
              onChange={(e) => onChange("cadence", e.target.value)}
            >
              <option value="">Any</option>
              <option value="weekly">Weekly</option>
              <option value="biweekly">Biweekly</option>
              <option value="monthly">Monthly</option>
              <option value="irregular">Irregular</option>
            </select>
          </div>
          <div className="tool-form-field">
            <label htmlFor="tool-confidence">Minimum confidence</label>
            <select
              id="tool-confidence"
              value={formState.confidence ?? ""}
              onChange={(e) => onChange("confidence", e.target.value)}
            >
              <option value="">Any</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
          <AdvancedSection>
            <div className="tool-form-field">
              <label htmlFor="tool-include-irregular">Include irregular</label>
              <select
                id="tool-include-irregular"
                value={formState.include_irregular ?? ""}
                onChange={(e) => onChange("include_irregular", e.target.value)}
              >
                <option value="">Default</option>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </div>
            <div className="tool-form-field">
              <label htmlFor="tool-min-avg">Min average amount</label>
              <input
                id="tool-min-avg"
                type="number"
                min={0}
                step="0.01"
                placeholder="any"
                value={formState.min_average_amount ?? ""}
                onChange={(e) => onChange("min_average_amount", e.target.value)}
              />
            </div>
            <div className="tool-form-field">
              <label htmlFor="tool-recurring-merchants">Merchants (comma-separated)</label>
              <input
                id="tool-recurring-merchants"
                type="text"
                placeholder="e.g. Fuel Station"
                value={formState.merchants ?? ""}
                onChange={(e) => onChange("merchants", e.target.value)}
              />
            </div>
            <div className="tool-form-field">
              <label htmlFor="tool-recurring-categories">Categories (comma-separated)</label>
              <input
                id="tool-recurring-categories"
                type="text"
                placeholder="e.g. transport"
                value={formState.categories ?? ""}
                onChange={(e) => onChange("categories", e.target.value)}
              />
            </div>
          </AdvancedSection>
        </>
      )}

      {tool === "balances" && (
        <p style={{ color: "var(--text-muted)", fontSize: "0.88rem", margin: "0 0 16px" }}>
          Your scoped accounts will be queried automatically.
        </p>
      )}

      {tool === "status_explanation" && (
        <DateRangeFields formState={formState} onChange={onChange} />
      )}

      {tool === "fee_breakdown" && (
        <>
          <DateRangeFields formState={formState} onChange={onChange} />
          <div className="tool-form-field">
            <label htmlFor="tool-fee-limit">Max results</label>
            <input
              id="tool-fee-limit"
              type="number"
              min={1}
              max={100}
              placeholder="10"
              value={formState.limit ?? ""}
              onChange={(e) => onChange("limit", e.target.value)}
            />
          </div>
          <AdvancedSection>
            <div className="tool-form-field">
              <label htmlFor="tool-txn-ids">Transaction IDs (comma-separated)</label>
              <input
                id="tool-txn-ids"
                type="text"
                placeholder="e.g. txn-001, txn-002"
                value={formState.transaction_ids ?? ""}
                onChange={(e) => onChange("transaction_ids", e.target.value)}
              />
            </div>
          </AdvancedSection>
        </>
      )}

      <div className="tool-form-actions">
        <button
          type="button"
          className="tool-form-cancel"
          onClick={onClose}
        >
          Cancel
        </button>
        <button
          type="button"
          className="tool-form-submit"
          onClick={onSubmit}
          disabled={disabled}
        >
          {disabled ? (
            <>
              <span className="btn-spinner" aria-hidden="true" />
              Running…
            </>
          ) : "Run Tool"}
        </button>
      </div>
    </div>
  );
}

export function ToolMenu({ isOpen, onClose, onInvoke, disabled }: ToolMenuProps) {
  const [selectedTool, setSelectedTool] = useState<ToolName | null>(null);
  const [formState, setFormState] = useState<Record<string, string>>({
    date_from: getDefaultDateFrom(),
    date_to: getDefaultDateTo(),
  });
  const dialogRef = useRef<HTMLDivElement>(null);

  // Reset form state when switching tools
  const handleSelectTool = (tool: ToolName) => {
    setFormState({ date_from: getDefaultDateFrom(), date_to: getDefaultDateTo() });
    setSelectedTool(tool);
  };

  const handleBack = () => {
    setSelectedTool(null);
  };

  const handleClose = () => {
    setSelectedTool(null);
    onClose();
  };

  const handleChange = (key: string, value: string) => {
    setFormState((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = () => {
    if (!selectedTool) return;
    const args = parseArgs(selectedTool, formState);
    onInvoke(selectedTool, args);
    setSelectedTool(null);
  };

  // Escape key closes dialog
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  // Focus first focusable element when dialog opens
  useEffect(() => {
    if (!isOpen || !dialogRef.current) return;
    const focusable = dialogRef.current.querySelector<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    focusable?.focus();
  }, [isOpen, selectedTool]);

  // Tab trap
  useEffect(() => {
    if (!isOpen || !dialogRef.current) return;
    const dialog = dialogRef.current;

    const handler = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const focusables = Array.from(
        dialog.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isOpen, selectedTool]);

  if (!isOpen) return null;

  return (
    <div className="tool-menu-overlay" aria-hidden={!isOpen}>
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Payjack Tools"
        className="tool-menu-dialog"
      >
        <div className="tool-menu-header">
          <h2 className="tool-menu-title">
            {selectedTool
              ? TOOL_CATALOG.find((t) => t.name === selectedTool)?.label
              : "Payjack Tools"}
          </h2>
          <button
            type="button"
            className="tool-menu-close"
            onClick={handleClose}
            aria-label="Close tools menu"
          >
            ×
          </button>
        </div>

        {selectedTool ? (
          <ToolForm
            tool={selectedTool}
            formState={formState}
            onChange={handleChange}
            onSubmit={handleSubmit}
            onBack={handleBack}
            onClose={handleClose}
            disabled={disabled}
          />
        ) : (
          <>
            <p style={{ color: "var(--text-muted)", fontSize: "0.84rem", margin: "0 0 16px" }}>
              Select a tool to run a read-only financial insight query.
            </p>
            <div className="tool-grid">
              {TOOL_CATALOG.map((tool) => (
                <button
                  key={tool.name}
                  type="button"
                  className="tool-card"
                  onClick={() => handleSelectTool(tool.name)}
                  disabled={disabled}
                  aria-label={`${tool.label}: ${tool.description}`}
                >
                  <span className="tool-card-icon" aria-hidden="true">{tool.icon}</span>
                  <span className="tool-card-label">{tool.label}</span>
                  <span className="tool-card-desc">{tool.description}</span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
