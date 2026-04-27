"use client";

import { forwardRef, type KeyboardEvent } from "react";

type MessageInputProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
};

export const MessageInput = forwardRef<HTMLTextAreaElement, MessageInputProps>(function MessageInput(
  {
    value,
    onChange,
    onSubmit,
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
      <button type="button" onClick={onSubmit} disabled={disabled || !value.trim()}>
        Send
      </button>
    </div>
  );
});
