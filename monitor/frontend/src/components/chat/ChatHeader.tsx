import { useState } from "react";

interface Props {
  title: string;
  ticker?: string;
  conversationId?: number;
  onClose: () => void;
  onNewChat: () => void;
  onSaveNote?: () => void;
  onGenerateMemo?: () => void;
  onViewChange?: (view: "panel" | "full") => void;
  currentView?: "panel" | "full";
  showViewToggle?: boolean;
  isSaving?: boolean;
}

export default function ChatHeader({
  title,
  ticker,
  conversationId,
  onClose,
  onNewChat,
  onSaveNote,
  onGenerateMemo,
  onViewChange,
  currentView,
  showViewToggle,
  isSaving,
}: Props) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="flex items-center justify-between px-3 py-2.5 border-b border-border bg-panel-light flex-shrink-0">
      <div className="flex items-center gap-2 min-w-0">
        {/* AI sparkle icon */}
        <div className="w-6 h-6 rounded bg-accent/20 flex items-center justify-center flex-shrink-0">
          <svg className="w-3.5 h-3.5 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
          </svg>
        </div>
        <div className="min-w-0">
          <h3 className="text-sm font-medium text-gray-200 truncate">{title}</h3>
          {ticker && (
            <span className="text-[10px] text-accent font-mono">{ticker}</span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-1 flex-shrink-0">
        {/* View toggle (panel/full) */}
        {showViewToggle && onViewChange && (
          <button
            onClick={() => onViewChange(currentView === "panel" ? "full" : "panel")}
            className="w-7 h-7 rounded flex items-center justify-center text-muted hover:text-gray-200 hover:bg-surface transition-colors"
            title={currentView === "panel" ? "Expand to full view" : "Collapse to panel"}
          >
            {currentView === "panel" ? (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 9V4.5M9 9H4.5M9 9L3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5l5.25 5.25" />
              </svg>
            )}
          </button>
        )}

        {/* Save menu */}
        {conversationId && (onSaveNote || onGenerateMemo) && (
          <div className="relative">
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              disabled={isSaving}
              className="w-7 h-7 rounded flex items-center justify-center text-muted hover:text-gray-200 hover:bg-surface transition-colors disabled:opacity-50"
              title="Save options"
            >
              {isSaving ? (
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
                </svg>
              )}
            </button>
            {menuOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
                <div className="absolute right-0 top-full mt-1 w-48 bg-panel border border-border rounded-lg shadow-xl z-20 py-1">
                  {onSaveNote && (
                    <button
                      onClick={() => {
                        setMenuOpen(false);
                        onSaveNote();
                      }}
                      className="w-full text-left px-3 py-2 text-sm text-gray-200 hover:bg-surface transition-colors flex items-center gap-2"
                    >
                      <svg className="w-4 h-4 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                      </svg>
                      Save as Note
                    </button>
                  )}
                  {onGenerateMemo && (
                    <button
                      onClick={() => {
                        setMenuOpen(false);
                        onGenerateMemo();
                      }}
                      className="w-full text-left px-3 py-2 text-sm text-gray-200 hover:bg-surface transition-colors flex items-center gap-2"
                    >
                      <svg className="w-4 h-4 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                      </svg>
                      Generate Memo
                    </button>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        {/* New chat */}
        <button
          onClick={onNewChat}
          className="w-7 h-7 rounded flex items-center justify-center text-muted hover:text-gray-200 hover:bg-surface transition-colors"
          title="New conversation"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
        </button>

        {/* Close */}
        <button
          onClick={onClose}
          className="w-7 h-7 rounded flex items-center justify-center text-muted hover:text-gray-200 hover:bg-surface transition-colors"
          title="Close"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}
