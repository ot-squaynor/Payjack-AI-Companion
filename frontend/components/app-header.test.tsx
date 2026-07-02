import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AppHeader } from "@/components/app-header";

describe("AppHeader", () => {
  it("renders the standalone title and subtitle", () => {
    render(<AppHeader />);

    expect(screen.getByRole("heading", { name: "Payjack AI Companion" })).toBeInTheDocument();
    expect(
      screen.getByText("Understand transactions, spending, balances, fees, and Payjack features.")
    ).toBeInTheDocument();
  });

  it("does not render the mobile menu button when no handler is passed", () => {
    render(<AppHeader />);

    expect(screen.queryByRole("button", { name: "Open chat history" })).not.toBeInTheDocument();
  });

  it("renders the mobile menu button and invokes the handler on click", async () => {
    const user = userEvent.setup();
    const onMobileMenuOpen = vi.fn();

    render(<AppHeader onMobileMenuOpen={onMobileMenuOpen} />);

    const button = screen.getByRole("button", { name: "Open chat history" });
    await user.click(button);

    expect(onMobileMenuOpen).toHaveBeenCalledTimes(1);
  });
});
