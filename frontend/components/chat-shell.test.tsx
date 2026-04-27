import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatShell } from "@/components/chat-shell";


const { getHealthMock, sendChatMock } = vi.hoisted(() => ({
  getHealthMock: vi.fn(),
  sendChatMock: vi.fn()
}));


vi.mock("@/lib/api", () => ({
  getHealth: getHealthMock,
  sendChat: sendChatMock
}));


describe("ChatShell", () => {
  beforeEach(() => {
    getHealthMock.mockReset();
    sendChatMock.mockReset();
  });

  it("shows backend unavailable when the health check fails", async () => {
    getHealthMock.mockRejectedValue(new Error("Failed to fetch"));

    render(<ChatShell />);

    await waitFor(() => {
      expect(screen.getByText("Backend unavailable")).toBeInTheDocument();
    });
    expect(screen.getByText("Failed to fetch")).toBeInTheDocument();
  });

  it("submits a chat request and renders the assistant response", async () => {
    const user = userEvent.setup();
    getHealthMock.mockResolvedValue({ status: "ok", environment: "local" });
    sendChatMock.mockResolvedValue({
      request_id: "req-123",
      session_id: "session-123",
      route: "tool",
      answer: "Here are your last 2 transactions.",
      tool_traces: [],
      citations: [],
      refusal: null,
      debug: {}
    });

    render(<ChatShell />);

    await user.type(
      screen.getByPlaceholderText("Ask about your transactions, spending, or Payjack features..."),
      "Show my last 2 transactions"
    );
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText("Here are your last 2 transactions.")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Ask about your transactions, spending, or Payjack features...")).toHaveFocus();
    });

    expect(sendChatMock).toHaveBeenCalledWith({
      message: "Show my last 2 transactions",
      session_id: null
    });
  });

  it("renders a chat error message when the backend request fails", async () => {
    const user = userEvent.setup();
    getHealthMock.mockResolvedValue({ status: "ok", environment: "local" });
    sendChatMock.mockRejectedValue(new Error("Chat backend timed out"));

    render(<ChatShell />);

    await user.type(
      screen.getByPlaceholderText("Ask about your transactions, spending, or Payjack features..."),
      "Show my last 2 transactions"
    );
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText("Chat request failed: Chat backend timed out")).toBeInTheDocument();
    });
  });
});
