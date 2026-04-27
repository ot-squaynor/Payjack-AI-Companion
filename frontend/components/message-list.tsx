import type { ConversationMessage } from "@/lib/types";
import { ResponseCard } from "@/components/response-card";

type MessageListProps = {
  messages: ConversationMessage[];
  showDebug?: boolean;
  hasAvatar?: boolean;
};

function AssistantAvatar({ hasAvatar }: { hasAvatar: boolean }) {
  return hasAvatar ? (
    <img className="message-avatar" src="/avatar.png" alt="Payjack assistant avatar" />
  ) : (
    <div className="message-avatar assistant-avatar" aria-hidden="true">
      AI
    </div>
  );
}

function UserAvatar() {
  return (
    <div className="message-avatar user-avatar" aria-hidden="true">
      You
    </div>
  );
}

export function MessageList({ messages, showDebug = false, hasAvatar = false }: MessageListProps) {
  return (
    <div className="message-list">
      {messages.map((message) => (
        <div
          key={message.id}
          className={message.role === "user" ? "message-row user" : "message-row assistant"}
        >
          {message.role === "assistant" ? <AssistantAvatar hasAvatar={hasAvatar} /> : null}
          {message.role === "user" ? (
            <div className="message-bubble user-bubble">{message.content}</div>
          ) : message.response ? (
            <ResponseCard response={message.response} showDebug={showDebug} />
          ) : (
            <div className="message-bubble assistant-bubble">{message.content}</div>
          )}
          {message.role === "user" ? <UserAvatar /> : null}
        </div>
      ))}
    </div>
  );
}
