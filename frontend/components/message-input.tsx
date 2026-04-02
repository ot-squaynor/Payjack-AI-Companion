"use client";

type MessageInputProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
};

export function MessageInput({
  value,
  onChange,
  onSubmit,
  disabled = false
}: MessageInputProps) {
  return (
    <div className="message-input">
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Ask about your transactions, spending, or Payjack features..."
        rows={3}
        disabled={disabled}
      />
      <button type="button" onClick={onSubmit} disabled={disabled || !value.trim()}>
        Send
      </button>
    </div>
  );
}
