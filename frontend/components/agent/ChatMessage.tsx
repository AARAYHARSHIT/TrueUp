"use client";

import { Badge } from "@/components/ui/Badge";
import { ToolCallCard } from "./ToolCallCard";
import { User, Bot, AlertCircle, RotateCcw } from "lucide-react";
import type { ChatMessage as ChatMessageType } from "@/hooks/useChat";

interface ChatMessageProps {
  message: ChatMessageType;
  onRetry?: () => void;
}

export function ChatMessage({ message, onRetry }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}
    >
      {!isUser && (
        <div className="shrink-0 mt-1">
          <div className="w-7 h-7 rounded-full bg-blue-dim flex items-center justify-center">
            <Bot className="h-4 w-4 text-blue" strokeWidth={1.5} />
          </div>
        </div>
      )}

      <div
        className={`max-w-[80%] space-y-2 ${
          isUser ? "order-first" : ""
        }`}
      >
        {/* Message bubble */}
        <div
          className={`rounded-lg px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? "bg-blue-dim text-foreground border border-blue/20"
              : message.error
              ? "bg-red-dim text-foreground border border-red/20"
              : "bg-card text-foreground border border-border"
          }`}
        >
          {message.error && (
            <div className="flex items-center gap-2 mb-2 text-red">
              <AlertCircle className="h-4 w-4" strokeWidth={1.5} />
              <span className="text-xs font-medium">Error</span>
            </div>
          )}
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Tool calls */}
        {!isUser && message.toolsUsed && message.toolsUsed.length > 0 && (
          <ToolCallCard tools={message.toolsUsed} />
        )}

        {/* Meta info */}
        {!isUser && (
          <div className="flex items-center gap-3 text-[10px] text-muted">
            {message.provider && (
              <span>
                {message.provider}/{message.model}
              </span>
            )}
            {message.inputTokens !== undefined && message.inputTokens > 0 && (
              <span>
                {message.inputTokens} in / {message.outputTokens} out
              </span>
            )}
            {message.error && onRetry && (
              <button
                onClick={onRetry}
                className="inline-flex items-center gap-1 text-muted hover:text-foreground transition-colors"
              >
                <RotateCcw className="h-3 w-3" />
                Retry
              </button>
            )}
          </div>
        )}
      </div>

      {isUser && (
        <div className="shrink-0 mt-1">
          <div className="w-7 h-7 rounded-full bg-card flex items-center justify-center border border-border">
            <User className="h-4 w-4 text-muted" strokeWidth={1.5} />
          </div>
        </div>
      )}
    </div>
  );
}
