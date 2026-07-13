"use client";

import { useCallback, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { ChatShell } from "@/components/chat-shell";
import { ChatHistorySidebar } from "@/components/chat-history-sidebar";
import { useChatHistory } from "@/hooks/use-chat-history";
import type { ConversationMessage } from "@/lib/types";

export default function HomePage() {
  const {
    conversations,
    activeId,
    saveConversation,
    createNewConversation,
    switchConversation,
    deleteConversation
  } = useChatHistory();

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);

  const handleNewChat = useCallback(() => {
    const id = createNewConversation();
    setActiveConvId(id);
    setSidebarOpen(false);
  }, [createNewConversation]);

  const handleSelectChat = useCallback(
    (id: string) => {
      switchConversation(id);
      setActiveConvId(id);
      setSidebarOpen(false);
    },
    [switchConversation]
  );

  const handleDeleteChat = useCallback(
    (id: string) => {
      deleteConversation(id);
      if (activeConvId === id) setActiveConvId(null);
    },
    [deleteConversation, activeConvId]
  );

  const handleMessagesChange = useCallback(
    (messages: ConversationMessage[], sessionId: string | null) => {
      if (activeConvId) {
        saveConversation(activeConvId, messages, sessionId);
      }
    },
    [activeConvId, saveConversation]
  );

  const activeConv = conversations.find((c) => c.id === activeConvId) ?? null;

  return (
    <div className="app-shell">
      <ChatHistorySidebar
        conversations={conversations}
        activeId={activeConvId}
        onNewChat={handleNewChat}
        onSelectChat={handleSelectChat}
        onDeleteChat={handleDeleteChat}
        isMobileOpen={sidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
      />
      <div className="main-content">
        <AppHeader onMobileMenuOpen={() => setSidebarOpen(true)} />
        <main className="page-shell">
          <ChatShell
            key={activeConvId ?? "default"}
            initialMessages={activeConv?.messages}
            initialSessionId={activeConv?.sessionId ?? null}
            onMessagesChange={handleMessagesChange}
          />
        </main>
      </div>
    </div>
  );
}
