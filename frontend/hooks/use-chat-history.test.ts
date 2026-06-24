import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { deriveTitle, getTimeGroup, useChatHistory } from "@/hooks/use-chat-history";
import type { ConversationMessage } from "@/lib/types";

// ── Helper builders ─────────────────────────────────────────────────────────

function userMsg(content: string): ConversationMessage {
  return { id: `u-${Date.now()}-${Math.random()}`, role: "user", content };
}

function assistantMsg(content: string): ConversationMessage {
  return { id: `a-${Date.now()}-${Math.random()}`, role: "assistant", content };
}

// ── Pure helpers ────────────────────────────────────────────────────────────

describe("deriveTitle", () => {
  it("returns first user message up to 60 chars", () => {
    const msgs: ConversationMessage[] = [
      assistantMsg("Hello"),
      userMsg("Show my last 10 transactions")
    ];
    expect(deriveTitle(msgs)).toBe("Show my last 10 transactions");
  });

  it("truncates long messages to 60 chars with ellipsis", () => {
    const msgs: ConversationMessage[] = [
      userMsg("A".repeat(70))
    ];
    expect(deriveTitle(msgs)).toBe("A".repeat(60) + "…");
  });

  it("skips tool-invocation messages (starting with 📊)", () => {
    const msgs: ConversationMessage[] = [
      userMsg("📊 Transaction History"),
      userMsg("What are my fees?")
    ];
    expect(deriveTitle(msgs)).toBe("What are my fees?");
  });

  it("returns 'New conversation' when no eligible user message", () => {
    const msgs: ConversationMessage[] = [
      assistantMsg("Welcome"),
      userMsg("📊 Tool call")
    ];
    expect(deriveTitle(msgs)).toBe("New conversation");
  });
});

describe("getTimeGroup", () => {
  it("returns Today for a timestamp from today", () => {
    const now = Date.now();
    expect(getTimeGroup(now)).toBe("Today");
    expect(getTimeGroup(now - 3_600_000)).toBe("Today");
  });

  it("returns Yesterday for yesterday", () => {
    const midnight = new Date();
    midnight.setHours(0, 0, 0, 0);
    const yesterday = midnight.getTime() - 1;
    expect(getTimeGroup(yesterday)).toBe("Yesterday");
  });

  it("returns Previous 7 days for 3 days ago", () => {
    const ts = Date.now() - 3 * 86_400_000;
    expect(getTimeGroup(ts)).toBe("Previous 7 days");
  });

  it("returns Older for 8+ days ago", () => {
    const ts = Date.now() - 8 * 86_400_000;
    expect(getTimeGroup(ts)).toBe("Older");
  });
});

// ── Hook ────────────────────────────────────────────────────────────────────

function makeLocalStorageMock() {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    get length() {
      return Object.keys(store).length;
    },
    key: vi.fn((i: number) => Object.keys(store)[i] ?? null)
  };
}

describe("useChatHistory", () => {
  const storageKey = "payjack_chat_history";
  let lsMock: ReturnType<typeof makeLocalStorageMock>;

  beforeEach(() => {
    lsMock = makeLocalStorageMock();
    vi.stubGlobal("localStorage", lsMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts with empty conversations", () => {
    const { result } = renderHook(() => useChatHistory());
    expect(result.current.conversations).toEqual([]);
    expect(result.current.activeId).toBeNull();
  });

  it("loads conversations from localStorage on mount", async () => {
    const stored = [
      {
        id: "conv-1",
        sessionId: null,
        title: "Hello there",
        createdAt: 1000,
        updatedAt: 1000,
        messages: [userMsg("Hello there")]
      }
    ];
    lsMock.setItem(storageKey, JSON.stringify(stored));

    const { result } = renderHook(() => useChatHistory());

    await act(async () => {});
    expect(result.current.conversations).toHaveLength(1);
    expect(result.current.conversations[0].title).toBe("Hello there");
  });

  it("createNewConversation returns a new id and sets activeId", () => {
    const { result } = renderHook(() => useChatHistory());
    let id: string;

    act(() => {
      id = result.current.createNewConversation();
    });

    expect(id!).toMatch(/^conv-/);
    expect(result.current.activeId).toBe(id!);
  });

  it("saveConversation persists a new conversation", async () => {
    const { result } = renderHook(() => useChatHistory());

    await act(async () => {});

    const messages: ConversationMessage[] = [userMsg("My first message")];
    act(() => {
      result.current.saveConversation("conv-abc", messages, null);
    });

    expect(result.current.conversations).toHaveLength(1);
    expect(result.current.conversations[0].id).toBe("conv-abc");
    expect(result.current.conversations[0].title).toBe("My first message");
  });

  it("saveConversation does not save if no user messages", () => {
    const { result } = renderHook(() => useChatHistory());

    act(() => {
      result.current.saveConversation("conv-abc", [assistantMsg("Intro")], null);
    });

    expect(result.current.conversations).toHaveLength(0);
  });

  it("saveConversation updates existing conversation", async () => {
    const { result } = renderHook(() => useChatHistory());

    await act(async () => {});

    const first: ConversationMessage[] = [userMsg("First")];
    act(() => {
      result.current.saveConversation("conv-1", first, null);
    });

    const updated: ConversationMessage[] = [userMsg("Updated question")];
    act(() => {
      result.current.saveConversation("conv-1", updated, "sess-xyz");
    });

    expect(result.current.conversations).toHaveLength(1);
    expect(result.current.conversations[0].title).toBe("Updated question");
    expect(result.current.conversations[0].sessionId).toBe("sess-xyz");
  });

  it("deleteConversation removes the conversation", async () => {
    const { result } = renderHook(() => useChatHistory());

    await act(async () => {});

    act(() => {
      result.current.saveConversation("conv-1", [userMsg("Hello")], null);
    });
    expect(result.current.conversations).toHaveLength(1);

    act(() => {
      result.current.deleteConversation("conv-1");
    });
    expect(result.current.conversations).toHaveLength(0);
  });

  it("switchConversation returns the matching conversation", async () => {
    const { result } = renderHook(() => useChatHistory());

    await act(async () => {});

    act(() => {
      result.current.saveConversation("conv-1", [userMsg("Hello")], null);
    });

    let found: ReturnType<typeof result.current.switchConversation>;
    act(() => {
      found = result.current.switchConversation("conv-1");
    });

    expect(found!).not.toBeNull();
    expect(found!.id).toBe("conv-1");
    expect(result.current.activeId).toBe("conv-1");
  });

  it("searchConversations filters by title", async () => {
    const { result } = renderHook(() => useChatHistory());

    await act(async () => {});

    act(() => {
      result.current.saveConversation("conv-1", [userMsg("Apple purchases")], null);
      result.current.saveConversation("conv-2", [userMsg("Banana spending")], null);
    });

    const hits = result.current.searchConversations("apple");
    expect(hits).toHaveLength(1);
    expect(hits[0].id).toBe("conv-1");
  });

  it("searchConversations returns all when query is empty", async () => {
    const { result } = renderHook(() => useChatHistory());

    await act(async () => {});

    act(() => {
      result.current.saveConversation("conv-1", [userMsg("First")], null);
      result.current.saveConversation("conv-2", [userMsg("Second")], null);
    });

    const all = result.current.searchConversations("");
    expect(all).toHaveLength(2);
  });
});
