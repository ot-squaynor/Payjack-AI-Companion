"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getHealth, invokeToolDirect, sendChat } from "@/lib/api";
import type { ConversationMessage, HealthResponse, ToolName } from "@/lib/types";
import { MessageInput } from "@/components/message-input";
import { MessageList } from "@/components/message-list";
import { Toast } from "@/components/toast";
import { TOOL_CATALOG, ToolMenu } from "@/components/tool-menu";

const TOOL_DISPLAY_NAMES: Record<ToolName, string> = Object.fromEntries(
  TOOL_CATALOG.map((t) => [t.name, t.label])
) as Record<ToolName, string>;

export const INITIAL_MESSAGE: ConversationMessage = {
  id: "assistant-intro",
  role: "assistant",
  content:
    "Ask me about your transactions, spend summaries, recurring payments, or Payjack documentation."
};

const NEAR_BOTTOM_PX = 80;

function checkNearBottom(el: HTMLElement): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX;
}

type ChatShellProps = {
  showDebug?: boolean;
  initialMessages?: ConversationMessage[];
  initialSessionId?: string | null;
  onMessagesChange?: (messages: ConversationMessage[], sessionId: string | null) => void;
  onMobileSidebarOpen?: () => void;
};

export function ChatShell({
  showDebug = false,
  initialMessages,
  initialSessionId = null,
  onMessagesChange,
  onMobileSidebarOpen
}: ChatShellProps) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId);
  const [loading, setLoading] = useState(false);
  const [isToolMenuOpen, setIsToolMenuOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const bottomAnchorRef = useRef<HTMLDivElement>(null);
  const messageListRef = useRef<HTMLDivElement | null>(null);
  const saveDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>(
    initialMessages ?? [INITIAL_MESSAGE]
  );

  useEffect(() => {
    getHealth()
      .then((response) => {
        setHealth(response);
        setHealthError(null);
      })
      .catch((error: Error) => {
        setHealthError(error.message);
      });
  }, []);

  useEffect(() => {
    if (!loading) {
      inputRef.current?.focus();
    }
  }, [loading]);

  // Debounced save to parent when messages or sessionId changes
  useEffect(() => {
    if (!onMessagesChange) return;
    if (saveDebounceRef.current) clearTimeout(saveDebounceRef.current);
    saveDebounceRef.current = setTimeout(() => {
      onMessagesChange(messages, sessionId);
    }, 300);
    return () => {
      if (saveDebounceRef.current) clearTimeout(saveDebounceRef.current);
    };
  }, [messages, sessionId, onMessagesChange]);

  // Auto-scroll to bottom — only when autoScroll is true
  useEffect(() => {
    if (!autoScroll) {
      if (messages.length > 1) setShowJumpToLatest(true);
      return;
    }
    const anchor = bottomAnchorRef.current;
    if (anchor && typeof anchor.scrollIntoView === "function") {
      anchor.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, loading, autoScroll]);

  // Scroll event handler — tracks whether user is near the bottom
  const handleListScroll = useCallback(() => {
    const el = messageListRef.current;
    if (!el) return;
    const near = checkNearBottom(el);
    setAutoScroll(near);
    if (near) setShowJumpToLatest(false);
  }, []);

  // Alt+T keyboard shortcut to open tool menu
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.altKey && e.key === "t" && !loading) {
        e.preventDefault();
        setIsToolMenuOpen(true);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [loading]);

  const scrollToLatest = useCallback(() => {
    const anchor = bottomAnchorRef.current;
    if (anchor && typeof anchor.scrollIntoView === "function") {
      anchor.scrollIntoView({ behavior: "smooth" });
    }
  }, []);

  const handleJumpToLatest = useCallback(() => {
    setAutoScroll(true);
    setShowJumpToLatest(false);
    scrollToLatest();
  }, [scrollToLatest]);

  const submitMessage = async (text: string) => {
    if (!text.trim() || loading) return;

    // Re-engage auto-scroll when user explicitly sends a message
    setAutoScroll(true);
    setShowJumpToLatest(false);

    const userMessage: ConversationMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text.trim()
    };
    setMessages((current) => [...current, userMessage]);
    setLoading(true);

    try {
      const response = await sendChat({
        message: text.trim(),
        session_id: sessionId
      });
      setSessionId(response.session_id);
      setMessages((current) => [
        ...current,
        {
          id: response.request_id,
          role: "assistant",
          content: response.answer,
          response
        }
      ]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown chat error.";
      setMessages((current) => [
        ...current,
        {
          id: `assistant-error-${Date.now()}`,
          role: "assistant",
          content: `Chat request failed: ${message}`,
          isError: true
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput("");
    await submitMessage(text);
  };

  const handleQuickPrompt = (prompt: string) => {
    if (loading) return;
    submitMessage(prompt);
  };

  const handleReset = () => {
    setMessages([INITIAL_MESSAGE]);
    setSessionId(null);
    setInput("");
    setAutoScroll(true);
    setShowJumpToLatest(false);
    inputRef.current?.focus();
  };

  const handleToolInvoke = async (tool: ToolName, args: Record<string, unknown>) => {
    setIsToolMenuOpen(false);
    const label = TOOL_DISPLAY_NAMES[tool] ?? tool;

    setMessages((current) => [
      ...current,
      { id: `user-tool-${Date.now()}`, role: "user", content: `📊 ${label}` }
    ]);
    setLoading(true);

    try {
      const result = await invokeToolDirect({ tool, arguments: args });
      setMessages((current) => [
        ...current,
        { id: result.request_id, role: "assistant", content: "", toolResult: result }
      ]);
      setToast("Tool result ready");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown tool error.";
      setMessages((current) => [
        ...current,
        {
          id: `assistant-tool-error-${Date.now()}`,
          role: "assistant",
          content: `Tool invocation failed: ${message}`,
          isError: true
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="chat-shell" aria-label="Payjack AI chat workspace">
      <div className="chat-header">
        <div className="chat-header-left">
          {onMobileSidebarOpen && (
            <button
              type="button"
              className="sidebar-toggle-mobile"
              onClick={onMobileSidebarOpen}
              aria-label="Open chat history"
            >
              ☰
            </button>
          )}
          <div className="chat-title">
            <h1>Payjack AI Financial Companion</h1>
            <p>Read-only transaction interpretation and grounded product guidance.</p>
          </div>
        </div>
        {sessionId && (
          <div className="chat-header-actions">
            <button
              type="button"
              className="new-session-btn"
              onClick={handleReset}
              aria-label="Start a new conversation"
            >
              New chat
            </button>
          </div>
        )}
      </div>

      <MessageList
        messages={messages}
        showDebug={showDebug}
        isLoading={loading}
        anchorRef={bottomAnchorRef}
        listRef={messageListRef}
        onScroll={handleListScroll}
        showJumpToLatest={showJumpToLatest}
        onJumpToLatest={handleJumpToLatest}
        onQuickPrompt={handleQuickPrompt}
      />
      <MessageInput
        ref={inputRef}
        value={input}
        onChange={setInput}
        onSubmit={handleSubmit}
        onToolMenuOpen={() => setIsToolMenuOpen(true)}
        disabled={loading}
      />
      <ToolMenu
        isOpen={isToolMenuOpen}
        onClose={() => setIsToolMenuOpen(false)}
        onInvoke={handleToolInvoke}
        disabled={loading}
      />
      {toast && <Toast message={toast} onDismiss={() => setToast(null)} />}
    </section>
  );
}
