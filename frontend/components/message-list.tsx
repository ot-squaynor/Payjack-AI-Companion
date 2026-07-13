import { ArrowDown, Bot, PieChart, Receipt, Repeat, TriangleAlert, User, Wallet } from "lucide-react";
import type { ConversationMessage } from "@/lib/types";
import { ResponseCard } from "@/components/response-card";
import { ToolResultCard } from "@/components/tool-result-card";
import { MessageActions } from "@/components/message-actions";

const QUICK_PROMPTS = [
  { id: "transactions", label: "Last transactions", prompt: "Show my last 10 transactions", icon: Receipt },
  { id: "spend", label: "Spending summary", prompt: "Summarise my spending this month", icon: PieChart },
  { id: "recurring", label: "Recurring payments", prompt: "What recurring payments do I have?", icon: Repeat },
  { id: "fees", label: "Fee breakdown", prompt: "Break down my fees this month", icon: Wallet }
] as const;

type MessageListProps = {
  messages: ConversationMessage[];
  showDebug?: boolean;
  isLoading?: boolean;
  anchorRef?: React.RefObject<HTMLDivElement | null>;
  listRef?: React.RefObject<HTMLDivElement | null>;
  onScroll?: () => void;
  showJumpToLatest?: boolean;
  onJumpToLatest?: () => void;
  onQuickPrompt?: (prompt: string) => void;
  onRegenerate?: () => void;
};

function actionContentFor(message: ConversationMessage): string | null {
  if (message.isError) return null;
  if (message.toolResult) return JSON.stringify(message.toolResult.payload, null, 2);
  if (message.response) return message.response.answer;
  return message.content;
}

export function MessageList({
  messages,
  showDebug = false,
  isLoading = false,
  anchorRef,
  listRef,
  onScroll,
  showJumpToLatest = false,
  onJumpToLatest,
  onQuickPrompt,
  onRegenerate
}: MessageListProps) {
  const showChips = messages.length === 1 && !isLoading && onQuickPrompt;
  const lastAssistantIndex = messages.map((m) => m.role).lastIndexOf("assistant");

  return (
    <div
      className="message-list"
      ref={listRef}
      onScroll={onScroll}
      aria-label="Chat messages"
      role="log"
      aria-live="polite"
      aria-relevant="additions"
    >
      {messages.map((message, index) => {
        const isUser = message.role === "user";
        const actionContent = !isUser ? actionContentFor(message) : null;
        const isLastAssistant = !isUser && index === lastAssistantIndex;

        return (
          <div key={message.id} className={isUser ? "message-row user" : "message-row assistant"}>
            <span className={`message-avatar ${isUser ? "user" : "assistant"}`} aria-hidden="true">
              {isUser ? <User size={14} /> : <Bot size={14} />}
            </span>
            <div className="message-stack">
              <span className="message-meta">{isUser ? "You" : "Payjack AI"}</span>
              {isUser ? (
                <div className="message-bubble user-bubble">{message.content}</div>
              ) : message.toolResult ? (
                <ToolResultCard toolResult={message.toolResult} />
              ) : message.response ? (
                <ResponseCard response={message.response} showDebug={showDebug} />
              ) : (
                <div className={`message-bubble ${message.isError ? "error-bubble" : "assistant-bubble"}`}>
                  {message.isError && (
                    <span className="error-bubble-icon" aria-hidden="true">
                      <TriangleAlert size={12} />
                    </span>
                  )}
                  {message.content}
                </div>
              )}
              {actionContent !== null && (
                <MessageActions
                  content={actionContent}
                  onRegenerate={isLastAssistant ? onRegenerate : undefined}
                  disabled={isLoading}
                />
              )}
            </div>
          </div>
        );
      })}

      {showChips && (
        <div className="message-row assistant">
          <div className="message-stack">
            <div className="quick-prompts" aria-label="Suggested questions">
              {QUICK_PROMPTS.map(({ id, label, prompt, icon: Icon }) => (
                <button
                  key={id}
                  type="button"
                  className="quick-prompt-card"
                  onClick={() => onQuickPrompt(prompt)}
                >
                  <span className="quick-prompt-icon" aria-hidden="true">
                    <Icon size={16} />
                  </span>
                  <span className="quick-prompt-label">{label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="message-row assistant" aria-live="polite" aria-label="Payjack AI is thinking">
          <span className="message-avatar assistant" aria-hidden="true">
            <Bot size={14} />
          </span>
          <div className="message-stack">
            <span className="message-meta">Payjack AI</span>
            <div className="message-bubble assistant-bubble typing-indicator">
              <span className="typing-dot" aria-hidden="true" />
              <span className="typing-dot" aria-hidden="true" />
              <span className="typing-dot" aria-hidden="true" />
            </div>
          </div>
        </div>
      )}

      {showJumpToLatest && (
        <div className="jump-to-latest-wrap">
          <button
            type="button"
            className="jump-to-latest"
            onClick={onJumpToLatest}
            aria-label="Jump to latest message"
          >
            <ArrowDown size={14} aria-hidden="true" />
            Latest
          </button>
        </div>
      )}

      <div ref={anchorRef} />
    </div>
  );
}
