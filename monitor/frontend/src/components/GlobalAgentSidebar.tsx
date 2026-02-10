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
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [isResizing]);

  // Collapsed state — thin strip with sparkle icon
  if (!expanded) {
    return (
      <div className="w-12 flex-shrink-0 bg-panel border-l border-border flex flex-col items-center pt-4">
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

  // Fullscreen state — overlay the entire viewport
  if (fullscreen) {
    return (
      <div className="fixed inset-0 bg-panel z-50 flex flex-col">
        <ChatPanel
          onClose={() => setExpanded(false)}
          onFullscreen={() => setFullscreen(false)}
          isFullscreen={true}
        />
      </div>
    );
  }

  // Expanded state — resizable sidebar with ChatPanel
  return (
    <div
      ref={containerRef}
      style={{ width: `${width}px` }}
      className="flex-shrink-0 border-l border-border flex flex-col relative"
    >
      {/* Draggable resize handle — wider hit area overlapping the border */}
      <div
        onMouseDown={() => setIsResizing(true)}
        className="absolute left-[-3px] top-0 bottom-0 w-[6px] cursor-col-resize z-10 hover:bg-accent/40 transition-colors"
      />

      <ChatPanel
        onClose={() => setExpanded(false)}
        onFullscreen={() => setFullscreen(true)}
        isFullscreen={false}
      />
    </div>
  );
}
