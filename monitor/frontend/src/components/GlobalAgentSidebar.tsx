import { useState, useRef, useEffect } from "react";
import ChatPanel from "./chat/ChatPanel";

export default function GlobalAgentSidebar() {
  const [expanded, setExpanded] = useState(false);
  const [width, setWidth] = useState(384); // w-96 = 384px
  const [isResizing, setIsResizing] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const minWidth = 300;
  const maxWidth = typeof window !== "undefined" ? window.innerWidth - 100 : 1200;

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing || !containerRef.current) return;

      const container = containerRef.current;
      const rect = container.getBoundingClientRect();
      const newWidth = rect.right - e.clientX;

      if (newWidth >= minWidth && newWidth <= maxWidth) {
        setWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    }

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "auto";
      document.body.style.userSelect = "auto";
    };
  }, [isResizing]);

  if (!expanded) {
    return (
      <div className="w-12 flex-shrink-0 bg-panel border-l border-border flex flex-col items-center pt-4 gap-2">
        <button
          onClick={() => setExpanded(true)}
          className="w-8 h-8 rounded-lg bg-accent/20 text-accent hover:bg-accent/30 flex items-center justify-center transition-colors"
          title="Open AI Agent"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z"
            />
          </svg>
        </button>
      </div>
    );
  }

  if (fullscreen) {
    return (
      <div className="fixed inset-0 bg-panel border-l border-border z-50 flex flex-col">
        <div className="flex items-center justify-between px-3 py-2 border-b border-border flex-shrink-0">
          <span className="text-sm font-medium text-gray-200">AI Agent</span>
          <div className="flex gap-1">
            <button
              onClick={() => setFullscreen(false)}
              className="w-7 h-7 rounded flex items-center justify-center text-muted hover:text-gray-200 hover:bg-surface transition-colors"
              title="Exit fullscreen"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M9 9V4.5M9 9H4.5M9 9L3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5l5.25 5.25"
                />
              </svg>
            </button>
          </div>
        </div>
        <ChatPanel onClose={() => setExpanded(false)} />
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{ width: `${width}px` }}
      className="flex-shrink-0 border-l border-border flex flex-col relative"
    >
      {/* Draggable resize handle */}
      <div
        onMouseDown={() => setIsResizing(true)}
        className="absolute left-0 top-0 bottom-0 w-1 bg-border hover:bg-accent/50 cursor-col-resize transition-colors group"
      />

      {/* Header with fullscreen button */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border flex-shrink-0">
        <span className="text-xs font-medium text-muted uppercase tracking-wider select-none">
          Chat
        </span>
        <button
          onClick={() => setFullscreen(true)}
          className="w-6 h-6 rounded flex items-center justify-center text-muted hover:text-gray-200 hover:bg-surface transition-colors"
          title="Fullscreen"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15"
            />
          </svg>
        </button>
      </div>

      <ChatPanel onClose={() => setExpanded(false)} />
    </div>
  );
}
