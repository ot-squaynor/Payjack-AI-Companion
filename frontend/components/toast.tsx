"use client";

import { useEffect } from "react";
import { CheckCircle2 } from "lucide-react";

type ToastProps = {
  message: string;
  onDismiss: () => void;
  durationMs?: number;
};

export function Toast({ message, onDismiss, durationMs = 3000 }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, durationMs);
    return () => clearTimeout(timer);
  }, [onDismiss, durationMs]);

  return (
    <div className="toast" role="status" aria-live="polite" aria-atomic="true">
      <span className="toast-icon" aria-hidden="true">
        <CheckCircle2 size={16} />
      </span>
      {message}
    </div>
  );
}
