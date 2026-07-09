"use client";

import { useEffect, useRef, useState } from "react";
import { HelpCircle, Plus, Search, Settings, X } from "lucide-react";
import type { StoredConversation } from "@/lib/types";
import { getTimeGroup, type TimeGroup } from "@/hooks/use-chat-history";

// ── Helpers ────────────────────────────────────────────────────────────────

function formatRelativeTime(ts: number): string {
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60_000);
  const hours = Math.floor(diff / 3_600_000);
  const days = Math.floor(diff / 86_400_000);

  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days === 1) return "yesterday";
  return `${days}d ago`;
}

const GROUP_ORDER: TimeGroup[] = ["Today", "Yesterday", "Previous 7 days", "Older"];

function groupConversations(
  conversations: StoredConversation[]
): Map<TimeGroup, StoredConversation[]> {
  const map = new Map<TimeGroup, StoredConversation[]>();
  for (const conv of conversations) {
    const group = getTimeGroup(conv.updatedAt);
    if (!map.has(group)) map.set(group, []);
    map.get(group)!.push(conv);
  }
  return map;
}

// ── Sub-components ─────────────────────────────────────────────────────────

function SidebarBrand() {
  return (
    <div className="sidebar-brand-row">
      <span className="sidebar-brand-mark" aria-hidden="true">P</span>
      <span className="sidebar-brand-name">Payjack</span>
    </div>
  );
}

function NewChatButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      className="sidebar-new-chat"
      onClick={onClick}
      aria-label="Start a new conversation"
    >
      <Plus size={16} aria-hidden="true" />
      New chat
    </button>
  );
}

function ChatHistorySearch({
  value,
  onChange
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="sidebar-search">
      <Search size={14} className="sidebar-search-icon" aria-hidden="true" />
      <input
        type="search"
        placeholder="Search chats"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Search chat history"
      />
    </div>
  );
}

function SidebarNav() {
  return (
    <nav className="sidebar-nav" aria-label="Support links">
      {/* <button type="button" className="sidebar-nav-item">
        <Settings size={16} aria-hidden="true" />
        Settings
      </button> */}
      <button type="button" className="sidebar-nav-item">
        <HelpCircle size={16} aria-hidden="true" />
        Help
      </button>
    </nav>
  );
}

function ChatHistoryItem({
  conversation,
  isActive,
  onClick,
  onDelete
}: {
  conversation: StoredConversation;
  isActive: boolean;
  onClick: () => void;
  onDelete: () => void;
}) {
  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDelete();
  };

  const handleDeleteKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      e.stopPropagation();
      onDelete();
    }
  };

  return (
    <button
      type="button"
      className="sidebar-chat-item"
      onClick={onClick}
      aria-current={isActive ? "page" : undefined}
      title={conversation.title}
    >
      <span className="sidebar-chat-title">{conversation.title}</span>
      <span className="sidebar-chat-time" aria-hidden="true">
        {formatRelativeTime(conversation.updatedAt)}
      </span>
      <span
        role="button"
        tabIndex={0}
        className="sidebar-chat-delete"
        onClick={handleDeleteClick}
        onKeyDown={handleDeleteKeyDown}
        aria-label={`Delete conversation: ${conversation.title}`}
        title="Delete"
      >
        <X size={14} aria-hidden="true" />
      </span>
    </button>
  );
}

// ── Main Sidebar ───────────────────────────────────────────────────────────

type ChatHistorySidebarProps = {
  conversations: StoredConversation[];
  activeId: string | null;
  onNewChat: () => void;
  onSelectChat: (id: string) => void;
  onDeleteChat: (id: string) => void;
  isMobileOpen: boolean;
  onMobileClose: () => void;
};

export function ChatHistorySidebar({
  conversations,
  activeId,
  onNewChat,
  onSelectChat,
  onDeleteChat,
  isMobileOpen,
  onMobileClose
}: ChatHistorySidebarProps) {
  const [search, setSearch] = useState("");
  const closeRef = useRef<HTMLButtonElement>(null);
  const firstItemRef = useRef<HTMLButtonElement>(null);

  // Close mobile drawer on Escape
  useEffect(() => {
    if (!isMobileOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onMobileClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isMobileOpen, onMobileClose]);

  // Focus close button when mobile drawer opens
  useEffect(() => {
    if (isMobileOpen) {
      closeRef.current?.focus();
    }
  }, [isMobileOpen]);

  const filtered = search.trim()
    ? conversations.filter((c) =>
        c.title.toLowerCase().includes(search.toLowerCase())
      )
    : conversations;

  const grouped = groupConversations(filtered);

  return (
    <>
      <nav
        className={`chat-sidebar${isMobileOpen ? " is-mobile-open" : ""}`}
        aria-label="Chat history"
      >
        <div className="sidebar-header">
          <SidebarBrand />
          <button
            ref={closeRef}
            type="button"
            className="sidebar-close-mobile"
            onClick={onMobileClose}
            aria-label="Close chat history sidebar"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <NewChatButton onClick={onNewChat} />

        <ChatHistorySearch value={search} onChange={setSearch} />

        <div
          className="sidebar-chat-list"
          role="list"
          aria-label="Previous conversations"
        >
          {filtered.length === 0 ? (
            <p className="sidebar-empty">
              {search.trim() ? "No matching chats" : "No chats yet"}
            </p>
          ) : (
            GROUP_ORDER.map((group) => {
              const items = grouped.get(group);
              if (!items?.length) return null;
              return (
                <div key={group} role="listitem">
                  <p className="sidebar-group-label">{group}</p>
                  {items.map((conv) => (
                    <ChatHistoryItem
                      key={conv.id}
                      conversation={conv}
                      isActive={conv.id === activeId}
                      onClick={() => onSelectChat(conv.id)}
                      onDelete={() => onDeleteChat(conv.id)}
                    />
                  ))}
                </div>
              );
            })
          )}
        </div>

        <SidebarNav />

        <div className="sidebar-footer">
          <p className="sidebar-persistence-note">History stored locally</p>
        </div>
      </nav>

      {isMobileOpen && (
        <div
          className="sidebar-overlay"
          onClick={onMobileClose}
          aria-hidden="true"
        />
      )}
    </>
  );
}
