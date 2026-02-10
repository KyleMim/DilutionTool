import { useState, useRef, useEffect, type KeyboardEvent } from "react";

interface Props {
  onSend: (content: string) => void;
  onStop?: () => void;
  isStreaming: boolean;
  placeholder?: string;
}

export default function ChatInput({ onSend, onStop, isStreaming, placeholder }: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 150) + "px";
    }
  }, [value]);

  const handleSend = () => {
    if (!value.trim() || isStreaming) return;
    onSend(value.trim());
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-border p-3">
      <div className="flex gap-2 items-end">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder || "Ask a question..."}
          rows={1}
          disabled={isStreaming}
          className="flex-1 bg-surface border border-border rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-muted resize-none focus:outline-none focus:border-accent/50 transition-colors disabled:opacity-50"
        />
        {isStreaming ? (
          <button
            onClick={onStop}
            className="w-9 h-9 rounded-lg bg-danger/80 hover:bg-danger text-white flex items-center justify-center transition-colors flex-shrink-0"
            title="Stop generating"
          >
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
              <rect x="6" y="6" width="12" height="12" rx="1" />
            </svg>
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!value.trim()}
            className="w-9 h-9 rounded-lg bg-accent hover:bg-accent-hover text-white flex items-center justify-center transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex-shrink-0"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"
              />
            </svg>
          </button>
        )}
      </div>
      <p className="text-[10px] text-muted mt-1.5 px-1">
        Enter to send, Shift+Enter for new line
      </p>
    </div>
  );
}
