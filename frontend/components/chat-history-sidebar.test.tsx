import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ChatHistorySidebar } from "@/components/chat-history-sidebar";
import type { StoredConversation } from "@/lib/types";

function makeConv(overrides: Partial<StoredConversation> = {}): StoredConversation {
  return {
    id: "conv-1",
    sessionId: null,
    title: "Test conversation",
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [{ id: "m1", role: "user", content: "Test conversation" }],
    ...overrides
  };
}

const defaultProps = {
  conversations: [],
  activeId: null,
  onNewChat: vi.fn(),
  onSelectChat: vi.fn(),
  onDeleteChat: vi.fn(),
  isMobileOpen: false,
  onMobileClose: vi.fn()
};

describe("ChatHistorySidebar", () => {
  it("renders the sidebar landmark", () => {
    render(<ChatHistorySidebar {...defaultProps} />);
    expect(screen.getByRole("navigation", { name: "Chat history" })).toBeInTheDocument();
  });

  it("shows empty state when no conversations", () => {
    render(<ChatHistorySidebar {...defaultProps} />);
    expect(screen.getByText("No chats yet")).toBeInTheDocument();
  });

  it("renders a conversation item", () => {
    const conv = makeConv({ title: "My test chat" });
    render(<ChatHistorySidebar {...defaultProps} conversations={[conv]} />);
    expect(screen.getByTitle("My test chat")).toBeInTheDocument();
  });

  it("calls onSelectChat when a conversation is clicked", async () => {
    const user = userEvent.setup();
    const conv = makeConv();
    const onSelectChat = vi.fn();

    render(
      <ChatHistorySidebar
        {...defaultProps}
        conversations={[conv]}
        onSelectChat={onSelectChat}
      />
    );

    await user.click(screen.getByTitle("Test conversation"));
    expect(onSelectChat).toHaveBeenCalledWith("conv-1");
  });

  it("marks the active conversation with aria-current", () => {
    const conv = makeConv({ id: "conv-active" });
    render(
      <ChatHistorySidebar
        {...defaultProps}
        conversations={[conv]}
        activeId="conv-active"
      />
    );

    const item = screen.getByTitle("Test conversation");
    expect(item).toHaveAttribute("aria-current", "page");
  });

  it("calls onNewChat when New chat button is clicked", async () => {
    const user = userEvent.setup();
    const onNewChat = vi.fn();

    render(<ChatHistorySidebar {...defaultProps} onNewChat={onNewChat} />);

    await user.click(screen.getByRole("button", { name: /start a new conversation/i }));
    expect(onNewChat).toHaveBeenCalledOnce();
  });

  it("filters conversation list by search query", async () => {
    const user = userEvent.setup();
    const convs = [
      makeConv({ id: "c1", title: "Apple transactions" }),
      makeConv({ id: "c2", title: "Banana spending" })
    ];

    render(<ChatHistorySidebar {...defaultProps} conversations={convs} />);

    await user.type(screen.getByRole("searchbox"), "Apple");

    expect(screen.getByTitle("Apple transactions")).toBeInTheDocument();
    expect(screen.queryByTitle("Banana spending")).not.toBeInTheDocument();
  });

  it("shows 'No matching chats' when search has no results", async () => {
    const user = userEvent.setup();
    const conv = makeConv({ title: "Apple transactions" });

    render(<ChatHistorySidebar {...defaultProps} conversations={[conv]} />);

    await user.type(screen.getByRole("searchbox"), "zzz");
    expect(screen.getByText("No matching chats")).toBeInTheDocument();
  });

  it("calls onDeleteChat when delete button is clicked", async () => {
    const user = userEvent.setup();
    const conv = makeConv({ id: "conv-del", title: "Delete me" });
    const onDeleteChat = vi.fn();

    render(
      <ChatHistorySidebar
        {...defaultProps}
        conversations={[conv]}
        onDeleteChat={onDeleteChat}
      />
    );

    // The delete button is hidden until hover; find by aria-label
    const deleteBtn = screen.getByRole("button", { name: /delete conversation/i });
    await user.click(deleteBtn);
    expect(onDeleteChat).toHaveBeenCalledWith("conv-del");
  });

  it("calls onMobileClose when close button is clicked (mobile open)", async () => {
    const user = userEvent.setup();
    const onMobileClose = vi.fn();

    render(
      <ChatHistorySidebar
        {...defaultProps}
        isMobileOpen={true}
        onMobileClose={onMobileClose}
      />
    );

    await user.click(screen.getByRole("button", { name: /close chat history sidebar/i }));
    expect(onMobileClose).toHaveBeenCalledOnce();
  });

  it("calls onMobileClose when overlay is clicked", async () => {
    const user = userEvent.setup();
    const onMobileClose = vi.fn();

    const { container } = render(
      <ChatHistorySidebar
        {...defaultProps}
        isMobileOpen={true}
        onMobileClose={onMobileClose}
      />
    );

    const overlay = container.querySelector(".sidebar-overlay");
    if (overlay) await user.click(overlay as HTMLElement);
    expect(onMobileClose).toHaveBeenCalledOnce();
  });

  it("applies is-mobile-open class when isMobileOpen is true", () => {
    const { container } = render(
      <ChatHistorySidebar {...defaultProps} isMobileOpen={true} />
    );
    expect(container.querySelector(".chat-sidebar.is-mobile-open")).toBeInTheDocument();
  });
});
