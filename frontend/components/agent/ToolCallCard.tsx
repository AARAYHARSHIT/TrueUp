"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import {
  Wrench,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Copy,
  Check,
} from "lucide-react";
import type { ToolUsed } from "@/lib/types";

interface ToolCallCardProps {
  tools: ToolUsed[];
}

function formatToolName(name: string): string {
  return name.replace(/_/g, " ");
}

function formatToolArgs(input: Record<string, unknown>): string {
  const entries = Object.entries(input);
  if (entries.length === 0) return "";
  return entries
    .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");
}

function ResultJson({ json }: { json: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(json);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* silent */
    }
  };

  let pretty = json;
  try {
    pretty = JSON.stringify(JSON.parse(json), null, 2);
  } catch {
    /* keep raw */
  }

  return (
    <div className="relative">
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-1 rounded text-muted hover:text-foreground hover:bg-card-hover transition-colors"
        title="Copy result"
      >
        {copied ? (
          <Check className="h-3.5 w-3.5 text-green" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
      </button>
      <pre className="text-xs text-foreground font-mono whitespace-pre-wrap break-all bg-background rounded-md p-3 border border-border max-h-64 overflow-auto">
        {pretty}
      </pre>
    </div>
  );
}

export function ToolCallCard({ tools }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState<number | null>(null);

  if (tools.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs text-muted">
        <Wrench className="h-3.5 w-3.5" strokeWidth={1.5} />
        <span>Tools used:</span>
      </div>
      <div className="space-y-1.5">
        {tools.map((tool, i) => {
          const isOpen = expanded === i;
          return (
            <div key={i} className="rounded-md border border-border overflow-hidden">
              <button
                onClick={() => setExpanded(isOpen ? null : i)}
                className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-card-hover transition-colors"
              >
                <CheckCircle2 className="h-3.5 w-3.5 text-green shrink-0" strokeWidth={1.5} />
                <span className="text-xs font-mono text-foreground">
                  {formatToolName(tool.name)}(
                  <span className="text-muted">{formatToolArgs(tool.input)}</span>)
                </span>
                <span className="ml-auto">
                  {isOpen ? (
                    <ChevronDown className="h-3.5 w-3.5 text-muted" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5 text-muted" />
                  )}
                </span>
              </button>
              {isOpen && (
                <div className="px-3 pb-3 border-t border-border">
                  <div className="pt-2">
                    <ResultJson json={tool.result_summary} />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
