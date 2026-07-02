import { useState, useRef, useEffect, useCallback } from "react";
import ChatPanel from "./chat/ChatPanel";

export default function GlobalAgentSidebar() {
  const [expanded, setExpanded] = useState(false);
  const [width, setWidth] = useState(384);
  const [fullscreen, setFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const isResizingRef = useRef(false);

  const minWidth = 300;
  const maxWidth = typeof window !== "undefined" ? window.innerWidth - 100 : 1200;

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isResizingRef.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const newWidth = rect.right - e.clientX;
      if (newWidth >= minWidth && newWidth <= maxWidth) {
        setWidth(newWidth);
      }
    },
    [maxWidth],
  );

  const handleMouseUp = useCallback(() => {
    isResizingRef.current = false;
    document.removeEventListener("mousemove", handleMouseMove);
    document.removeEventListener("mouseup", handleMouseUp);
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  }, [handleMouseMove]);

  const startResize = useCallback(() => {
    isResizingRef.current = true;
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, [handleMouseMove, handleMouseUp]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [handleMouseMove, handleMouseUp]);

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
          onClose={() => { setFullscreen(false); setExpanded(false); }}
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
      style={{ width: `${width}px`, flexShrink: 0, position: "relative" }}
      className="border-l border-border flex flex-col"
    >
      {/* Draggable resize handle */}
      <div
        onMouseDown={startResize}
        style={{
          position: "absolute",
          left: -4,
          top: 0,
          bottom: 0,
          width: 8,
          cursor: "col-resize",
          zIndex: 20,
        }}
        className="group"
      >
        {/* Visible resize bar */}
        <div
          style={{ position: "absolute", left: 3, top: 0, bottom: 0, width: 2 }}
          className="bg-border group-hover:bg-accent transition-colors"
        />
      </div>

      <ChatPanel
        onClose={() => setExpanded(false)}
        onFullscreen={() => setFullscreen(true)}
        isFullscreen={false}
      />
    </div>
  );
}
