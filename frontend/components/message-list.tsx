import type { ConversationMessage } from "@/lib/types";
import { ResponseCard } from "@/components/response-card";

type MessageListProps = {
  messages: ConversationMessage[];
  showDebug?: boolean;
};

export function MessageList({ messages, showDebug = false }: MessageListProps) {
  return (
    <div className="message-list">
      {messages.map((message) => (
        <div
          key={message.id}
          className={message.role === "user" ? "message-row user" : "message-row assistant"}
        >
          {message.role === "user" ? (
            <div className="message-bubble user-bubble">{message.content}</div>
          ) : message.response ? (
            <ResponseCard response={message.response} showDebug={showDebug} />
          ) : (
            <div className="message-bubble assistant-bubble">{message.content}</div>
          )}
        </div>
      ))}
    </div>
  );
}
