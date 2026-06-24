import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ToolMenu } from "@/components/tool-menu";

const baseProps = {
  isOpen: true,
  onClose: vi.fn(),
  onInvoke: vi.fn(),
  disabled: false,
};

describe("ToolMenu", () => {
  it("does not render when isOpen is false", () => {
    render(<ToolMenu {...baseProps} isOpen={false} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders the dialog when isOpen is true", () => {
    render(<ToolMenu {...baseProps} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
  });

  it("renders all 6 tool cards in the grid view", () => {
    render(<ToolMenu {...baseProps} />);
    expect(screen.getByText("Transaction Lookup")).toBeInTheDocument();
    expect(screen.getByText("Spend Summary")).toBeInTheDocument();
    expect(screen.getByText("Recurring Payments")).toBeInTheDocument();
    expect(screen.getByText("Account Balances")).toBeInTheDocument();
    expect(screen.getByText("Status Explanation")).toBeInTheDocument();
    expect(screen.getByText("Fee Breakdown")).toBeInTheDocument();
  });

  it("transitions to form view when a tool card is clicked", async () => {
    const user = userEvent.setup();
    render(<ToolMenu {...baseProps} />);

    await user.click(screen.getByRole("button", { name: /Account Balances:/i }));

    // Run Tool button appears in the form view
    expect(screen.getByRole("button", { name: "Run Tool" })).toBeInTheDocument();
    // Grid is no longer shown
    expect(screen.queryByText("Transaction Lookup")).not.toBeInTheDocument();
  });

  it("back button returns to the tool grid", async () => {
    const user = userEvent.setup();
    render(<ToolMenu {...baseProps} />);

    await user.click(screen.getByRole("button", { name: /Account Balances:/i }));
    expect(screen.getByRole("button", { name: /back to tool list/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /back to tool list/i }));

    // Grid is visible again
    expect(screen.getByText("Transaction Lookup")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run Tool" })).not.toBeInTheDocument();
  });

  it("close button calls onClose", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<ToolMenu {...baseProps} onClose={onClose} />);

    await user.click(screen.getByRole("button", { name: /close tools menu/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("Escape key calls onClose", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<ToolMenu {...baseProps} onClose={onClose} />);

    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onInvoke with tool name and parsed args when Run Tool is clicked", async () => {
    const user = userEvent.setup();
    const onInvoke = vi.fn();
    render(<ToolMenu {...baseProps} onInvoke={onInvoke} />);

    await user.click(screen.getByRole("button", { name: /Account Balances:/i }));
    await user.click(screen.getByRole("button", { name: "Run Tool" }));

    expect(onInvoke).toHaveBeenCalledWith("balances", expect.any(Object));
  });

  it("calls onInvoke for transaction_lookup with limit parsed as integer", async () => {
    const user = userEvent.setup();
    const onInvoke = vi.fn();
    render(<ToolMenu {...baseProps} onInvoke={onInvoke} />);

    await user.click(screen.getByText("Transaction Lookup"));
    const limitInput = screen.getByLabelText("Max results");
    await user.clear(limitInput);
    await user.type(limitInput, "5");
    await user.click(screen.getByRole("button", { name: "Run Tool" }));

    expect(onInvoke).toHaveBeenCalledWith("transaction_lookup", expect.objectContaining({ limit: 5 }));
  });

  it("disables all tool cards when disabled prop is true", () => {
    render(<ToolMenu {...baseProps} disabled={true} />);
    // Each tool card is a button with aria-label "ToolName: description"
    const toolCards = screen.getAllByRole("button", { name: /Find transactions|Summarise spending|Detect recurring|Current and available|Understand pending|Itemise fees/i });
    expect(toolCards.length).toBe(6);
    toolCards.forEach((btn) => expect(btn).toBeDisabled());
  });

  it("Cancel button closes the dialog", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<ToolMenu {...baseProps} onClose={onClose} />);

    await user.click(screen.getByRole("button", { name: /Account Balances:/i }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
