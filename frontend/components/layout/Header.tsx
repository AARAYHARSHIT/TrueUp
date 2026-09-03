"use client";

import { useHealth } from "@/hooks/useHealth";
import { useRunDemo } from "@/hooks/useRunDemo";
import { Activity, Play, Loader2 } from "lucide-react";

export function Header() {
  const health = useHealth();
  const runDemo = useRunDemo();

  const statusColor =
    health.data?.status === "ok"
      ? "text-green"
      : health.data?.status === "degraded"
      ? "text-red"
      : "text-muted";

  return (
    <header className="flex items-center justify-between h-14 px-6 border-b border-border bg-card">
      <div className="flex items-center gap-3">
        <div className={`flex items-center gap-2 text-xs ${statusColor}`}>
          <Activity className="h-3 w-3" />
          <span className="font-medium">
            {health.data?.status === "ok"
              ? "Connected"
              : health.data?.status === "degraded"
              ? "Degraded"
              : "Loading..."}
          </span>
        </div>
        {health.data?.match_rate && (
          <span className="text-xs text-muted tabular-nums">
            Match rate: {health.data.match_rate}
          </span>
        )}
      </div>

      <button
        onClick={() => runDemo.mutate()}
        disabled={runDemo.isPending}
        className="inline-flex items-center gap-2 rounded-md bg-amber px-4 py-1.5 text-xs font-medium text-background hover:opacity-90 transition-opacity disabled:opacity-50"
      >
        {runDemo.isPending ? (
          <Loader2 className="h-3 w-3 animate-spin" />
        ) : (
          <Play className="h-3 w-3" />
        )}
        {runDemo.isPending ? "Running..." : "Run Demo"}
      </button>
    </header>
  );
}
