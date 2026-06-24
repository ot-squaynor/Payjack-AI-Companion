import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MessageInput } from "@/components/message-input";


describe("MessageInput", () => {
  it("prevents empty submissions", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(<MessageInput value="" onChange={vi.fn()} onSubmit={onSubmit} />);

    const button = screen.getByRole("button", { name: "Send" });
    expect(button).toBeDisabled();
    await user.click(button);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("invokes the submit handler for non-empty input", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(<MessageInput value="Show my spending" onChange={vi.fn()} onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("submits with Enter and preserves Shift+Enter for multiline entry", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(<MessageInput value="Show my spending" onChange={vi.fn()} onSubmit={onSubmit} />);

    const textarea = screen.getByPlaceholderText("Ask about your transactions, spending, or Payjack features...");
    textarea.focus();

    await user.keyboard("{Shift>}{Enter}{/Shift}");
    expect(onSubmit).not.toHaveBeenCalled();

    await user.keyboard("{Enter}");
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("disables input controls while loading", () => {
    render(<MessageInput value="Working..." onChange={vi.fn()} onSubmit={vi.fn()} disabled />);

    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(screen.getByPlaceholderText("Ask about your transactions, spending, or Payjack features...")).toBeDisabled();
  });

  it("renders Tools button when onToolMenuOpen prop is provided", () => {
    render(
      <MessageInput
        value=""
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        onToolMenuOpen={vi.fn()}
      />
    );

    expect(screen.getByRole("button", { name: /open payjack tools menu/i })).toBeInTheDocument();
  });

  it("calls onToolMenuOpen when the Tools button is clicked", async () => {
    const user = userEvent.setup();
    const onToolMenuOpen = vi.fn();

    render(
      <MessageInput
        value=""
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        onToolMenuOpen={onToolMenuOpen}
      />
    );

    await user.click(screen.getByRole("button", { name: /open payjack tools menu/i }));
    expect(onToolMenuOpen).toHaveBeenCalledTimes(1);
  });

  it("does not render Tools button when onToolMenuOpen prop is omitted", () => {
    render(<MessageInput value="" onChange={vi.fn()} onSubmit={vi.fn()} />);

    expect(screen.queryByRole("button", { name: /open payjack tools menu/i })).not.toBeInTheDocument();
    // Only the Send button should be present
    expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
  });
});
