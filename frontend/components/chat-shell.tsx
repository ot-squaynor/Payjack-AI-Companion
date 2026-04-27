"use client";

import { useEffect, useRef, useState } from "react";

import { getHealth, sendChat } from "@/lib/api";
import type { ConversationMessage, HealthResponse } from "@/lib/types";
import { MessageInput } from "@/components/message-input";
import { MessageList } from "@/components/message-list";

type ChatShellProps = {
  showDebug?: boolean;
};

export function ChatShell({ showDebug = false }: ChatShellProps) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasAvatar, setHasAvatar] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([
    {
      id: "assistant-intro",
      role: "assistant",
      content:
        "Ask me about your transactions, spend summaries, recurring payments, or Payjack documentation."
    }
  ]);

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
    let cancelled = false;

    if (typeof window === "undefined" || typeof window.fetch !== "function") {
      return;
    }

    window
      .fetch("/avatar.png", { method: "HEAD" })
      .then((response) => {
        if (!cancelled) {
          setHasAvatar(response.ok);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHasAvatar(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!loading) {
      inputRef.current?.focus();
    }
  }, [loading]);

  const handleSubmit = async () => {
    if (!input.trim() || loading) {
      return;
    }

    const userMessage: ConversationMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: input.trim()
    };
    const nextInput = input.trim();
    setMessages((current) => [...current, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const response = await sendChat({
        message: nextInput,
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
          content: `Chat request failed: ${message}`
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="chat-shell">
      <div className="chat-header">
        <div>
          <h1>Payjack AI Financial Companion</h1>
          <p>Read-only transaction interpretation and grounded product guidance.</p>
        </div>
        <div className="health-panel">
          <span className={healthError ? "status-badge error" : "status-badge ok"}>
            {healthError ? "Backend unavailable" : health?.status || "Checking"}
          </span>
          {healthError ? <p>{healthError}</p> : <p>{health?.environment || "local"}</p>}
        </div>
      </div>

      <MessageList messages={messages} showDebug={showDebug} hasAvatar={hasAvatar} />
      <MessageInput
        ref={inputRef}
        value={input}
        onChange={setInput}
        onSubmit={handleSubmit}
        disabled={loading}
      />
    </section>
  );
}
