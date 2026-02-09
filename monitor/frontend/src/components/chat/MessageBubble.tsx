import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { MessageResponse } from "../../api/client";

interface Props {
  message: MessageResponse;
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      <div
        className={`max-w-[85%] rounded-lg px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? "bg-accent/15 border border-accent/25 text-gray-100"
            : "bg-surface border border-border text-gray-200"
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
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
