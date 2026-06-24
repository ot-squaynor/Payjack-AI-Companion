"use client";

import { useEffect, useRef, useState } from "react";

import { getHealth, invokeToolDirect, sendChat } from "@/lib/api";
import type { ConversationMessage, HealthResponse, ToolName } from "@/lib/types";
import { MessageInput } from "@/components/message-input";
import { MessageList } from "@/components/message-list";
import { Toast } from "@/components/toast";
import { TOOL_CATALOG, ToolMenu } from "@/components/tool-menu";

const TOOL_DISPLAY_NAMES: Record<ToolName, string> = Object.fromEntries(
  TOOL_CATALOG.map((t) => [t.name, t.label])
) as Record<ToolName, string>;

const INITIAL_MESSAGE: ConversationMessage = {
  id: "assistant-intro",
  role: "assistant",
  content:
    "Ask me about your transactions, spend summaries, recurring payments, or Payjack documentation."
};

type ChatShellProps = {
  showDebug?: boolean;
};

export function ChatShell({ showDebug = false }: ChatShellProps) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [isToolMenuOpen, setIsToolMenuOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const bottomAnchorRef = useRef<HTMLDivElement>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([INITIAL_MESSAGE]);

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

  // Auto-scroll to bottom when messages change or loading state changes
  useEffect(() => {
    const anchor = bottomAnchorRef.current;
    if (anchor && typeof anchor.scrollIntoView === "function") {
      anchor.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, loading]);

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

  const submitMessage = async (text: string) => {
    if (!text.trim() || loading) return;

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
        <div className="chat-title">
          <h1>Payjack AI Financial Companion</h1>
          <p>Read-only transaction interpretation and grounded product guidance.</p>
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
