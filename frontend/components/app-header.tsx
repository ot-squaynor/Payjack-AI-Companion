import { HelpCircle, Menu } from "lucide-react";

type AppHeaderProps = {
  onMobileMenuOpen?: () => void;
};

export function AppHeader({ onMobileMenuOpen }: AppHeaderProps) {
  return (
    <header className="chat-header">
      <div className="chat-header-left">
        {onMobileMenuOpen && (
          <button
            type="button"
            className="sidebar-toggle-mobile"
            onClick={onMobileMenuOpen}
            aria-label="Open chat history"
          >
            <Menu size={18} aria-hidden="true" />
          </button>
        )}
        <div className="chat-title">
          <h1>Payjack AI Companion</h1>
          <p>Understand transactions, spending, balances, fees, and Payjack features.</p>
        </div>
      </div>
      <div className="chat-header-right">
        <button type="button" className="header-icon-btn" aria-label="Help">
          <HelpCircle size={18} aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}
