import type { ConversationMessage } from "@/lib/types";
import { ResponseCard } from "@/components/response-card";

type MessageListProps = {
  messages: ConversationMessage[];
  showDebug?: boolean;
};

export function MessageList({ messages, showDebug = false }: MessageListProps) {
  return (
    <div className="message-list">
      {messages.map((message) => {
        const isUser = message.role === "user";

        return (
          <div key={message.id} className={isUser ? "message-row user" : "message-row assistant"}>
            <div className="message-stack">
              <span className="message-meta">{isUser ? "You" : "Payjack AI"}</span>
              {isUser ? (
                <div className="message-bubble user-bubble">{message.content}</div>
              ) : message.response ? (
                <ResponseCard response={message.response} showDebug={showDebug} />
              ) : (
                <div className="message-bubble assistant-bubble">{message.content}</div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
