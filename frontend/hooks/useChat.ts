"use client";

import { useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { ChatResponse, ToolUsed } from "@/lib/types";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolsUsed?: ToolUsed[];
  provider?: string;
  model?: string;
  inputTokens?: number;
  outputTokens?: number;
  timestamp: number;
  error?: boolean;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(async (question: string) => {
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: question,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsPending(true);
    setError(null);

    try {
      const result: ChatResponse = await api.chat(question);

      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: result.answer,
        toolsUsed: result.tools_used,
        provider: result.provider,
        model: result.model,
        inputTokens: result.input_tokens,
        outputTokens: result.output_tokens,
        timestamp: Date.now(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Unknown error";
      setError(errorMsg);

      const error_msg: ChatMessage = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: `I encountered an error while processing your question: ${errorMsg}`,
        timestamp: Date.now(),
        error: true,
      };

      setMessages((prev) => [...prev, error_msg]);
    } finally {
      setIsPending(false);
    }
  }, []);

  const retry = useCallback(() => {
    if (messages.length === 0) return;
    const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
    if (lastUserMsg) {
      setMessages((prev) => prev.filter((m) => m.id !== lastUserMsg.id));
      sendMessage(lastUserMsg.content);
    }
  }, [messages, sendMessage]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return {
    messages,
    isPending,
    error,
    sendMessage,
    retry,
    clearMessages,
  };
}
