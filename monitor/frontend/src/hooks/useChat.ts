import { useState, useCallback, useRef } from "react";
import {
  createConversation,
  fetchConversations,
  fetchConversation,
  sendMessageUrl,
  deleteConversation,
  type ConversationResponse,
  type MessageResponse,
} from "../api/client";

interface UseChatReturn {
  conversation: ConversationResponse | null;
  messages: MessageResponse[];
  isStreaming: boolean;
  streamingContent: string;
  sendMessage: (content: string) => void;
  conversations: ConversationResponse[];
  selectConversation: (id: number) => Promise<void>;
  newConversation: () => void;
  removeConversation: (id: number) => Promise<void>;
  loadConversations: () => Promise<void>;
  error: string | null;
}

export function useChat(ticker?: string): UseChatReturn {
  const [conversation, setConversation] = useState<ConversationResponse | null>(null);
  const [messages, setMessages] = useState<MessageResponse[]>([]);
  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const loadConversations = useCallback(async () => {
    try {
      const data = await fetchConversations(ticker);
      setConversations(data);
    } catch {
      // silently fail on load
    }
  }, [ticker]);

  const selectConversation = useCallback(async (id: number) => {
    try {
      const detail = await fetchConversation(id);
      setConversation({
        id: detail.id,
        title: detail.title,
        ticker: detail.ticker,
        created_at: detail.created_at,
        updated_at: detail.created_at,
        message_count: detail.messages.length,
      });
      setMessages(detail.messages);
      setError(null);
    } catch (e) {
      setError("Failed to load conversation");
    }
  }, []);

  const newConversation = useCallback(() => {
    setConversation(null);
    setMessages([]);
    setStreamingContent("");
    setError(null);
  }, []);

  const removeConversation = useCallback(async (id: number) => {
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (conversation?.id === id) {
        newConversation();
      }
    } catch {
      setError("Failed to delete conversation");
    }
  }, [conversation, newConversation]);

  const sendMessage = useCallback(
    async (content: string) => {
      if (isStreaming || !content.trim()) return;
      setError(null);
      setIsStreaming(true);
      setStreamingContent("");

      try {
        // Create conversation if needed
        let convId = conversation?.id;
        if (!convId) {
          const newConv = await createConversation({ ticker });
          setConversation(newConv);
          convId = newConv.id;
        }

        // Add user message to UI immediately
        const userMsg: MessageResponse = {
          id: Date.now(),
          role: "user",
          content,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, userMsg]);

        // Stream AI response
        const controller = new AbortController();
        abortRef.current = controller;

        const response = await fetch(sendMessageUrl(convId), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let accumulated = "";
        let assistantMsgId: number | null = null;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const text = decoder.decode(value, { stream: true });
          const lines = text.split("\n");

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const jsonStr = line.slice(6).trim();
            if (!jsonStr) continue;

            try {
              const event = JSON.parse(jsonStr);
              if (event.type === "chunk") {
                accumulated += event.content;
                setStreamingContent(accumulated);
              } else if (event.type === "done") {
                assistantMsgId = event.message_id;
              } else if (event.type === "error") {
                setError(event.content);
              }
            } catch {
              // skip malformed JSON
            }
          }
        }

        // Move streaming content into messages
        if (accumulated) {
          const assistantMsg: MessageResponse = {
            id: assistantMsgId ?? Date.now() + 1,
            role: "assistant",
            content: accumulated,
            created_at: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, assistantMsg]);
          setStreamingContent("");
        }

        // Refresh conversation list
        loadConversations();
      } catch (e: any) {
        if (e.name !== "AbortError") {
          setError(e.message || "Failed to send message");
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [conversation, ticker, isStreaming, loadConversations]
  );

  return {
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
  };
}
