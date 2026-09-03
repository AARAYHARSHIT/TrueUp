"use client";

import { useState, useRef, useEffect } from "react";
import { useChat } from "@/hooks/useChat";
import { ChatMessage } from "@/components/agent/ChatMessage";
import { PresetQuestions } from "@/components/agent/PresetQuestions";
import { Send, Trash2, Loader2 } from "lucide-react";

export default function AgentPage() {
  const { messages, isPending, error, sendMessage, retry, clearMessages } =
    useChat();
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isPending]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isPending) return;
    setInput("");
    sendMessage(trimmed);
  };

  const handlePreset = (question: string) => {
    if (isPending) return;
    setInput("");
    sendMessage(question);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const hasMessages = messages.length > 0;

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-lg font-semibold text-foreground">
            AI Controller
          </h1>
          <p className="text-xs text-muted">
            Ask questions about the reconciliation run. Every answer is backed
            by tool results.
          </p>
        </div>
        {hasMessages && (
          <button
            onClick={clearMessages}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border bg-card text-xs text-muted hover:text-foreground hover:bg-card-hover transition-colors"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Clear
          </button>
        )}
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-auto rounded-lg border border-border bg-card">
        {!hasMessages ? (
          /* Empty state */
          <div className="flex flex-col items-center justify-center h-full py-12 px-6">
            <div className="w-12 h-12 rounded-full bg-blue-dim flex items-center justify-center mb-4">
              <Send className="h-5 w-5 text-blue" strokeWidth={1.5} />
            </div>
            <h2 className="text-sm font-medium text-foreground mb-1">
              TrueUp Settlement Assistant
            </h2>
            <p className="text-xs text-muted text-center max-w-sm mb-6">
              Ask questions about the reconciliation run. The agent uses six
              tools to retrieve facts and compose grounded answers.
            </p>
            <PresetQuestions onSelect={handlePreset} disabled={isPending} />
          </div>
        ) : (
          /* Message list */
          <div className="p-4 space-y-4">
            {messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                message={msg}
                onRetry={msg.error ? retry : undefined}
              />
            ))}
            {isPending && (
              <div className="flex gap-3">
                <div className="shrink-0 mt-1">
                  <div className="w-7 h-7 rounded-full bg-blue-dim flex items-center justify-center">
                    <Loader2 className="h-4 w-4 text-blue animate-spin" strokeWidth={1.5} />
                  </div>
                </div>
                <div className="rounded-lg px-4 py-3 bg-card border border-border">
                  <div className="flex items-center gap-2 text-xs text-muted">
                    <div className="flex gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-muted animate-bounce [animation-delay:-0.3s]" />
                      <span className="w-1.5 h-1.5 rounded-full bg-muted animate-bounce [animation-delay:-0.15s]" />
                      <span className="w-1.5 h-1.5 rounded-full bg-muted animate-bounce" />
                    </div>
                    Thinking...
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <form onSubmit={handleSubmit} className="mt-3 flex gap-2">
        <div className="flex-1 relative">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about reconciliation..."
            rows={1}
            disabled={isPending}
            className="w-full resize-none rounded-lg border border-border bg-card px-4 py-3 text-sm text-foreground placeholder:text-muted focus:outline-none focus:border-blue/50 disabled:opacity-50 transition-colors"
            style={{ minHeight: "44px", maxHeight: "120px" }}
          />
        </div>
        <button
          type="submit"
          disabled={!input.trim() || isPending}
          className="shrink-0 inline-flex items-center justify-center w-11 h-11 rounded-lg bg-blue text-background hover:bg-blue/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </button>
      </form>

      {/* Trust notice */}
      <p className="mt-2 text-[10px] text-muted text-center">
        All answers are grounded in tool results. Numbers come directly from the
        reconciliation engine.
      </p>
    </div>
  );
}
