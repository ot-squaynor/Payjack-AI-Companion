"use client";

import { forwardRef, type KeyboardEvent } from "react";
import { SendHorizontal, Sparkles } from "lucide-react";

const MAX_CHARS = 3000;

type MessageInputProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onToolMenuOpen?: () => void;
  disabled?: boolean;
};

export const MessageInput = forwardRef<HTMLTextAreaElement, MessageInputProps>(function MessageInput(
  {
    value,
    onChange,
    onSubmit,
    onToolMenuOpen,
    disabled = false
  },
  ref
) {
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();

      if (!disabled && value.trim()) {
        onSubmit();
      }
    }
  };

  return (
    <div className="message-input">
      <div className={`composer-panel${disabled ? " is-loading" : ""}`}>
        <textarea
          ref={ref}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your transactions, spending, or Payjack features..."
          rows={3}
          maxLength={MAX_CHARS}
          disabled={disabled}
          autoFocus
        />
        <div className="composer-actions">
          <div className="composer-meta">
            <span className="composer-context">Secure read-only companion</span>
            <span className="composer-char-count" aria-hidden="true">
              {value.length} / {MAX_CHARS}
            </span>
          </div>
          <div className="composer-buttons">
            {onToolMenuOpen && (
              <button
                type="button"
                className="tool-menu-trigger"
                onClick={onToolMenuOpen}
                disabled={disabled}
                aria-label="Open Payjack Tools menu"
                aria-haspopup="dialog"
              >
                <Sparkles size={14} aria-hidden="true" />
                Tools
                <kbd className="tool-kbd-hint" aria-hidden="true">Alt T</kbd>
              </button>
            )}
            <button type="button" onClick={onSubmit} disabled={disabled || !value.trim()}>
              <SendHorizontal size={14} aria-hidden="true" />
              Send
            </button>
          </div>
        </div>
      </div>
      <p className="composer-disclaimer">
        Payjack AI can make mistakes. Verify important information before acting on it.
      </p>
    </div>
  );
});
