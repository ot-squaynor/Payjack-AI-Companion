"use client";

import { forwardRef, type KeyboardEvent } from "react";

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
      <div className="composer-panel">
        <textarea
          ref={ref}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your transactions, spending, or Payjack features..."
          rows={3}
          disabled={disabled}
          autoFocus
        />
        <div className="composer-actions">
          <span className="composer-context">Secure read-only companion</span>
          {onToolMenuOpen && (
            <button
              type="button"
              className="tool-menu-trigger"
              onClick={onToolMenuOpen}
              disabled={disabled}
              aria-label="Open Payjack Tools menu"
              aria-haspopup="dialog"
            >
              ✦ Tools
            </button>
          )}
          <button type="button" onClick={onSubmit} disabled={disabled || !value.trim()}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
});
