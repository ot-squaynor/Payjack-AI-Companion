import type { ConversationMessage } from "@/lib/types";
import { ResponseCard } from "@/components/response-card";
import { ToolResultCard } from "@/components/tool-result-card";

const QUICK_PROMPTS = [
  "Show my last 10 transactions",
  "Summarise my spending this month",
  "What recurring payments do I have?",
  "Break down my fees this month"
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
};

export function MessageList({
  messages,
  showDebug = false,
  isLoading = false,
  anchorRef,
  listRef,
  onScroll,
  showJumpToLatest = false,
  onJumpToLatest,
  onQuickPrompt
}: MessageListProps) {
  const showChips = messages.length === 1 && !isLoading && onQuickPrompt;

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
      {messages.map((message) => {
        const isUser = message.role === "user";

        return (
          <div key={message.id} className={isUser ? "message-row user" : "message-row assistant"}>
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
                  {message.isError && <span className="error-bubble-icon" aria-hidden="true">!</span>}
                  {message.content}
                </div>
              )}
            </div>
          </div>
        );
      })}

      {showChips && (
        <div className="message-row assistant">
          <div className="message-stack">
            <div className="quick-prompts" aria-label="Suggested questions">
              {QUICK_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="quick-prompt-chip"
                  onClick={() => onQuickPrompt(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="message-row assistant" aria-live="polite" aria-label="Payjack AI is thinking">
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
            ↓ Latest
          </button>
        </div>
      )}

      <div ref={anchorRef} />
    </div>
  );
}
