import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import MessageBubble from "./MessageBubble";
import type { MessageResponse } from "../../api/client";

interface Props {
  messages: MessageResponse[];
  isStreaming: boolean;
  streamingContent: string;
}

export default function MessageList({ messages, isStreaming, streamingContent }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  if (messages.length === 0 && !isStreaming) {
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="text-center">
          <div className="w-12 h-12 rounded-full bg-accent/10 flex items-center justify-center mx-auto mb-3">
            <svg className="w-6 h-6 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
            </svg>
          </div>
          <p className="text-muted text-sm">Ask a question to get started</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      {isStreaming && streamingContent && (
        <div className="flex justify-start mb-3">
          <div className="max-w-[85%] rounded-lg px-4 py-3 text-sm leading-relaxed bg-surface border border-border text-gray-200">
            <div className="prose prose-invert prose-sm max-w-none [&_table]:text-xs [&_table]:border-collapse [&_th]:border [&_th]:border-border [&_th]:px-2 [&_th]:py-1 [&_th]:bg-panel [&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1 [&_code]:bg-panel [&_code]:px-1 [&_code]:rounded [&_pre]:bg-panel [&_pre]:border [&_pre]:border-border [&_pre]:rounded-lg [&_a]:text-accent [&_strong]:text-gray-100 [&_h1]:text-gray-100 [&_h2]:text-gray-100 [&_h3]:text-gray-100 [&_ul]:my-2 [&_ol]:my-2 [&_li]:my-0.5 [&_p]:my-2 first:[&_p]:mt-0 last:[&_p]:mb-0">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {streamingContent}
              </ReactMarkdown>
            </div>
            <span className="inline-block w-2 h-4 bg-accent/60 animate-pulse ml-0.5" />
          </div>
        </div>
      )}
      {isStreaming && !streamingContent && (
        <div className="flex justify-start mb-3">
          <div className="rounded-lg px-4 py-3 bg-surface border border-border">
            <div className="flex gap-1">
              <span className="w-2 h-2 rounded-full bg-muted animate-bounce [animation-delay:-0.3s]" />
              <span className="w-2 h-2 rounded-full bg-muted animate-bounce [animation-delay:-0.15s]" />
              <span className="w-2 h-2 rounded-full bg-muted animate-bounce" />
            </div>
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
