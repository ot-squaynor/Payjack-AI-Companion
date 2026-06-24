"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ConversationMessage, StoredConversation } from "@/lib/types";

const STORAGE_KEY = "payjack_chat_history";
const MAX_CONVERSATIONS = 100;

export type TimeGroup = "Today" | "Yesterday" | "Previous 7 days" | "Older";

export function getTimeGroup(ts: number): TimeGroup {
  const now = new Date();
  const date = new Date(ts);
  const nowMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const dateMidnight = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const diffDays = Math.round((nowMidnight - dateMidnight) / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays <= 7) return "Previous 7 days";
  return "Older";
}

export function deriveTitle(messages: ConversationMessage[]): string {
  const firstUser = messages.find(
    (m) => m.role === "user" && !m.content.startsWith("📊")
  );
  if (!firstUser) return "New conversation";
  const text = firstUser.content.trim();
  return text.length > 60 ? text.slice(0, 60) + "…" : text;
}

function loadFromStorage(): StoredConversation[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveToStorage(conversations: StoredConversation[]): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  } catch {
    // Ignore quota errors
  }
}

function generateId(): string {
  return `conv-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function useChatHistory() {
  const [conversations, setConversations] = useState<StoredConversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const hydrated = useRef(false);

  // Load from localStorage once on mount (SSR-safe)
  useEffect(() => {
    const stored = loadFromStorage();
    setConversations(stored);
    hydrated.current = true;
  }, []);

  // Persist to localStorage whenever conversations change (after hydration)
  useEffect(() => {
    if (!hydrated.current) return;
    saveToStorage(conversations);
  }, [conversations]);

  const saveConversation = useCallback(
    (id: string, messages: ConversationMessage[], sessionId: string | null) => {
      // Don't save conversations that only contain the intro message
      const hasUserMessage = messages.some((m) => m.role === "user");
      if (!hasUserMessage) return;

      setConversations((prev) => {
        const existing = prev.find((c) => c.id === id);
        const title = deriveTitle(messages);
        const now = Date.now();

        if (existing) {
          const updated = prev.map((c) =>
            c.id === id ? { ...c, title, sessionId, messages, updatedAt: now } : c
          );
          // Re-sort: most recently updated first
          return updated.sort((a, b) => b.updatedAt - a.updatedAt);
        }

        const newConv: StoredConversation = {
          id,
          sessionId,
          title,
          createdAt: now,
          updatedAt: now,
          messages
        };

        // Prepend new, cap at MAX_CONVERSATIONS
        return [newConv, ...prev].slice(0, MAX_CONVERSATIONS);
      });
    },
    []
  );

  const createNewConversation = useCallback((): string => {
    const id = generateId();
    setActiveId(id);
    return id;
  }, []);

  const switchConversation = useCallback(
    (id: string): StoredConversation | null => {
      const conv = conversations.find((c) => c.id === id) ?? null;
      if (conv) setActiveId(id);
      return conv;
    },
    [conversations]
  );

  const deleteConversation = useCallback((id: string) => {
    setConversations((prev) => prev.filter((c) => c.id !== id));
    setActiveId((prev) => (prev === id ? null : prev));
  }, []);

  const searchConversations = useCallback(
    (query: string): StoredConversation[] => {
      if (!query.trim()) return conversations;
      const q = query.toLowerCase();
      return conversations.filter((c) => c.title.toLowerCase().includes(q));
    },
    [conversations]
  );

  return {
    conversations,
    activeId,
    setActiveId,
    saveConversation,
    createNewConversation,
    switchConversation,
    deleteConversation,
    searchConversations
  };
}
