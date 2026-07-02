"use client";

import { useState } from "react";
import { Check, Copy, RotateCcw, Share2, ThumbsDown, ThumbsUp } from "lucide-react";

type MessageActionsProps = {
  content: string;
  onRegenerate?: () => void;
  disabled?: boolean;
};

export function MessageActions({ content, onRegenerate, disabled = false }: MessageActionsProps) {
  const [copied, setCopied] = useState(false);
  const [shared, setShared] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access denied — no-op.
    }
  };

  const handleShare = async () => {
    try {
      if (typeof navigator.share === "function") {
        await navigator.share({ text: content });
      } else {
        await navigator.clipboard.writeText(content);
      }
      setShared(true);
      setTimeout(() => setShared(false), 1500);
    } catch {
      // User cancelled the share sheet or clipboard access denied — no-op.
    }
  };

  const toggleFeedback = (value: "up" | "down") => {
    setFeedback((current) => (current === value ? null : value));
  };

  return (
    <div className="message-actions" role="group" aria-label="Message actions">
      <button
        type="button"
        className="message-action-btn"
        onClick={handleCopy}
        aria-label={copied ? "Copied" : "Copy response"}
      >
        {copied ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
      </button>
      <button
        type="button"
        className="message-action-btn"
        onClick={handleShare}
        aria-label={shared ? "Shared" : "Share response"}
      >
        {shared ? <Check size={14} aria-hidden="true" /> : <Share2 size={14} aria-hidden="true" />}
      </button>
      <button
        type="button"
        className={`message-action-btn${feedback === "up" ? " is-active" : ""}`}
        onClick={() => toggleFeedback("up")}
        aria-pressed={feedback === "up"}
        aria-label="Good response"
      >
        <ThumbsUp size={14} aria-hidden="true" />
      </button>
      <button
        type="button"
        className={`message-action-btn${feedback === "down" ? " is-active" : ""}`}
        onClick={() => toggleFeedback("down")}
        aria-pressed={feedback === "down"}
        aria-label="Bad response"
      >
        <ThumbsDown size={14} aria-hidden="true" />
      </button>
      {onRegenerate && (
        <button
          type="button"
          className="message-action-btn message-action-regenerate"
          onClick={onRegenerate}
          disabled={disabled}
          aria-label="Regenerate response"
        >
          <RotateCcw size={14} aria-hidden="true" />
          Regenerate
        </button>
      )}
    </div>
  );
}
