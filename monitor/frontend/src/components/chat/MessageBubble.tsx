import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { MessageResponse } from "../../api/client";

interface Props {
  message: MessageResponse;
  onEdit?: (messageId: number, newContent: string) => void;
  isStreaming?: boolean;
}

export default function MessageBubble({ message, onEdit, isStreaming }: Props) {
  const isUser = message.role === "user";
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(message.content);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (editing && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }
  }, [editing]);

  const handleSave = () => {
    const trimmed = editValue.trim();
    if (!trimmed || trimmed === message.content) {
      setEditing(false);
      setEditValue(message.content);
      return;
    }
    onEdit?.(message.id, trimmed);
    setEditing(false);
  };

  const handleCancel = () => {
    setEditing(false);
    setEditValue(message.content);
  };

  return (
    <div className={`group flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      <div
        className={`max-w-[85%] rounded-lg px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? "bg-accent/15 border border-accent/25 text-gray-100"
            : "bg-surface border border-border text-gray-200"
        }`}
      >
        {isUser && editing ? (
          <div>
            <textarea
              ref={textareaRef}
              value={editValue}
              onChange={(e) => {
                setEditValue(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = e.target.scrollHeight + "px";
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSave();
                }
                if (e.key === "Escape") handleCancel();
              }}
              className="w-full bg-transparent border-none text-sm text-gray-100 resize-none focus:outline-none"
              rows={1}
            />
            <div className="flex gap-2 mt-2 justify-end">
              <button
                onClick={handleCancel}
                className="px-2.5 py-1 text-xs text-muted hover:text-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="px-2.5 py-1 text-xs bg-accent/20 text-accent rounded hover:bg-accent/30 transition-colors"
              >
                Save & Resend
              </button>
            </div>
          </div>
        ) : isUser ? (
          <div className="flex items-start gap-2">
            <p className="whitespace-pre-wrap flex-1">{message.content}</p>
            {onEdit && !isStreaming && (
              <button
                onClick={() => setEditing(true)}
                className="opacity-0 group-hover:opacity-100 text-muted hover:text-gray-200 transition-all flex-shrink-0 mt-0.5"
                title="Edit message"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125" />
                </svg>
              </button>
            )}
          </div>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none [&_table]:text-xs [&_table]:border-collapse [&_th]:border [&_th]:border-border [&_th]:px-2 [&_th]:py-1 [&_th]:bg-panel [&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1 [&_code]:bg-panel [&_code]:px-1 [&_code]:rounded [&_pre]:bg-panel [&_pre]:border [&_pre]:border-border [&_pre]:rounded-lg [&_a]:text-accent [&_strong]:text-gray-100 [&_h1]:text-gray-100 [&_h2]:text-gray-100 [&_h3]:text-gray-100 [&_ul]:my-2 [&_ol]:my-2 [&_li]:my-0.5 [&_p]:my-2 first:[&_p]:mt-0 last:[&_p]:mb-0">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
