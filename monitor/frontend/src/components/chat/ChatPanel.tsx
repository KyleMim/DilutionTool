import { useEffect, useState } from "react";
import { useChat } from "../../hooks/useChat";
import { useSaveAsNote, useGenerateMemo } from "../../hooks/useNotes";
import ChatHeader from "./ChatHeader";
import MessageList from "./MessageList";
import ChatInput from "./ChatInput";
import type { ConversationResponse } from "../../api/client";

interface Props {
  ticker?: string;
  onClose: () => void;
  onViewChange?: (view: "panel" | "full") => void;
  currentView?: "panel" | "full";
  showViewToggle?: boolean;
  className?: string;
}

export default function ChatPanel({
  ticker,
  onClose,
  onViewChange,
  currentView,
  showViewToggle,
  className,
}: Props) {
  const {
    conversation,
    messages,
    isStreaming,
    streamingContent,
    sendMessage,
    conversations,
    selectConversation,
    newConversation,
    removeConversation,
    loadConversations,
    error,
  } = useChat(ticker);

  const saveNote = useSaveAsNote();
  const generateMemo = useGenerateMemo();
  const [showHistory, setShowHistory] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const handleSaveNote = async () => {
    if (!conversation?.id) return;
    try {
      await saveNote.mutateAsync({ conversationId: conversation.id });
      setSaveStatus("Saved as note!");
      setTimeout(() => setSaveStatus(null), 2000);
    } catch {
      setSaveStatus("Failed to save");
      setTimeout(() => setSaveStatus(null), 2000);
    }
  };

  const handleGenerateMemo = async () => {
    if (!conversation?.id) return;
    try {
      setSaveStatus("Generating memo...");
      await generateMemo.mutateAsync({ conversationId: conversation.id });
      setSaveStatus("Memo generated!");
      setTimeout(() => setSaveStatus(null), 2000);
    } catch {
      setSaveStatus("Failed to generate memo");
      setTimeout(() => setSaveStatus(null), 2000);
    }
  };

  const title = conversation?.title ?? (ticker ? `${ticker} Chat` : "AI Agent");

  return (
    <div className={`flex flex-col h-full bg-panel ${className ?? ""}`}>
      <ChatHeader
        title={title}
        ticker={ticker}
        conversationId={conversation?.id}
        onClose={onClose}
        onNewChat={newConversation}
        onSaveNote={conversation?.id ? handleSaveNote : undefined}
        onGenerateMemo={conversation?.id ? handleGenerateMemo : undefined}
        onViewChange={onViewChange}
        currentView={currentView}
        showViewToggle={showViewToggle}
        isSaving={saveNote.isPending || generateMemo.isPending}
      />

      {/* Status toast */}
      {saveStatus && (
        <div className="px-3 py-1.5 bg-accent/10 border-b border-accent/20 text-accent text-xs text-center">
          {saveStatus}
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="px-3 py-1.5 bg-danger/10 border-b border-danger/20 text-danger text-xs text-center">
          {error}
        </div>
      )}

      {/* History sidebar toggle */}
      {showHistory ? (
        <div className="flex-1 overflow-y-auto border-b border-border">
          <div className="flex items-center justify-between px-3 py-2 border-b border-border">
            <span className="text-xs font-medium text-muted uppercase tracking-wider">
              History
            </span>
            <button
              onClick={() => setShowHistory(false)}
              className="text-xs text-accent hover:text-accent-hover"
            >
              Back
            </button>
          </div>
          <div className="p-2 space-y-1">
            <button
              onClick={() => {
                newConversation();
                setShowHistory(false);
              }}
              className="w-full text-left px-3 py-2 rounded-lg text-sm text-accent hover:bg-surface transition-colors flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              New Chat
            </button>
            {conversations.map((conv) => (
              <ConversationItem
                key={conv.id}
                conv={conv}
                isActive={conv.id === conversation?.id}
                onSelect={() => {
                  selectConversation(conv.id);
                  setShowHistory(false);
                }}
                onDelete={() => removeConversation(conv.id)}
              />
            ))}
            {conversations.length === 0 && (
              <p className="text-xs text-muted text-center py-4">
                No conversations yet
              </p>
            )}
          </div>
        </div>
      ) : (
        <>
          {/* History toggle bar */}
          {conversations.length > 0 && (
            <button
              onClick={() => setShowHistory(true)}
              className="flex items-center gap-2 px-3 py-1.5 border-b border-border text-xs text-muted hover:text-gray-200 hover:bg-surface/50 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {conversations.length} conversation{conversations.length !== 1 ? "s" : ""}
            </button>
          )}

          <MessageList
            messages={messages}
            isStreaming={isStreaming}
            streamingContent={streamingContent}
          />
        </>
      )}

      {!showHistory && (
        <ChatInput
          onSend={sendMessage}
          isStreaming={isStreaming}
          placeholder={ticker ? `Ask about ${ticker}...` : "Ask anything..."}
        />
      )}
    </div>
  );
}

function ConversationItem({
  conv,
  isActive,
  onSelect,
  onDelete,
}: {
  conv: ConversationResponse;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
}) {
  return (
    <div
      className={`group flex items-center rounded-lg transition-colors ${
        isActive ? "bg-accent/10 border border-accent/20" : "hover:bg-surface border border-transparent"
      }`}
    >
      <button
        onClick={onSelect}
        className="flex-1 text-left px-3 py-2 min-w-0"
      >
        <p className="text-sm text-gray-200 truncate">
          {conv.title || "Untitled"}
        </p>
        <p className="text-[10px] text-muted mt-0.5">
          {new Date(conv.updated_at).toLocaleDateString()} &middot; {conv.message_count} messages
        </p>
      </button>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        className="opacity-0 group-hover:opacity-100 w-7 h-7 rounded flex items-center justify-center text-muted hover:text-danger transition-all mr-1"
        title="Delete"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
        </svg>
      </button>
    </div>
  );
}
