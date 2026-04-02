import { ChatShell } from "@/components/chat-shell";

export default function DebugPage() {
  return (
    <main className="page-shell">
      <p className="debug-note">
        Debug mode shows tool traces, citations, and model metadata returned by the backend.
      </p>
      <ChatShell showDebug />
    </main>
  );
}
