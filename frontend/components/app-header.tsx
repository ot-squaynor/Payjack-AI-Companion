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
            ☰
          </button>
        )}
        <div className="chat-title">
          <h1>Payjack AI Companion</h1>
          <p>Understand transactions, spending, balances, fees, and Payjack features.</p>
        </div>
      </div>
    </header>
  );
}
