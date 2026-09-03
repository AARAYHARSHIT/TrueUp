"use client";

import { useState } from "react";
import { useExceptions } from "@/hooks/useExceptions";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { TableSkeleton } from "@/components/ui/LoadingSkeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import Link from "next/link";
import type { ExceptionItem } from "@/lib/types";

function exceptionBadgeVariant(
  type: string
): "green" | "amber" | "red" | "blue" | "muted" {
  if (type.includes("MISSING")) return "red";
  if (type.includes("ORPHAN")) return "red";
  if (type.includes("BATCH")) return "amber";
  if (type.includes("SPLIT")) return "amber";
  if (type.includes("AMOUNT") || type.includes("DATE")) return "amber";
  if (type.includes("ROUNDING")) return "blue";
  if (type.includes("UNRESOLVED")) return "red";
  return "muted";
}

const typeLabels: Record<string, string> = {
  BATCH_SETTLEMENT: "Batch",
  MISSING_SETTLEMENT: "Missing",
  ORPHAN_LEDGER: "Orphan",
  MISSING_TXN: "Missing Txn",
  AMOUNT_MISMATCH: "Amount",
  DATE_MISMATCH: "Date",
  SPLIT_SETTLEMENT: "Split",
  ROUNDING_DIFF: "Rounding",
  UNRESOLVED_AMBIGUOUS: "Ambiguous",
};

export default function ExceptionsPage() {
  const [filter, setFilter] = useState<string | undefined>();
  const { data, isLoading, error, refetch } = useExceptions(filter);

  if (isLoading) return <TableSkeleton rows={10} />;
  if (error)
    return (
      <ErrorState
        message="Failed to load exceptions."
        onRetry={() => refetch()}
      />
    );
  if (!data || data.exceptions.length === 0) {
    return <EmptyState title="No exceptions" description="All records matched successfully." />;
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Exceptions</h1>
        <p className="text-sm text-muted mt-1">
          {data.total} exceptions across {Object.keys(data.by_type).length} types
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setFilter(undefined)}
          className={`px-3 py-1.5 rounded-md text-xs font-medium border transition-colors ${
            !filter
              ? "bg-blue-dim text-blue border-blue/30"
              : "bg-card text-muted border-border hover:text-foreground"
          }`}
        >
          All ({data.total})
        </button>
        {Object.entries(data.by_type)
          .filter(([, count]) => count > 0)
          .sort(([, a], [, b]) => b - a)
          .map(([type, count]) => (
            <button
              key={type}
              onClick={() => setFilter(filter === type ? undefined : type)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium border transition-colors ${
                filter === type
                  ? "bg-blue-dim text-blue border-blue/30"
                  : "bg-card text-muted border-border hover:text-foreground"
              }`}
            >
              {typeLabels[type] || type} ({count})
            </button>
          ))}
      </div>

      <Card className="p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left px-4 py-3 text-xs font-medium text-muted uppercase tracking-wider">
                  Type
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted uppercase tracking-wider">
                  Record ID
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted uppercase tracking-wider">
                  Amount
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted uppercase tracking-wider">
                  Date
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted uppercase tracking-wider">
                  Reason
                </th>
              </tr>
            </thead>
            <tbody>
              {data.exceptions.map((ex: ExceptionItem) => (
                <tr
                  key={ex.exception_id}
                  className="border-b border-border last:border-0 hover:bg-card-hover transition-colors"
                >
                  <td className="px-4 py-3">
                    <Badge variant={exceptionBadgeVariant(ex.type)}>
                      {ex.type.replace(/_/g, " ")}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/transactions?search=${ex.record_id}`}
                      className="text-foreground font-mono hover:text-blue transition-colors"
                    >
                      {ex.record_id}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-foreground tabular-nums">
                    {ex.amount
                      ? `₹${parseFloat(ex.amount).toLocaleString("en-IN")}`
                      : "—"}
                  </td>
                  <td className="px-4 py-3 text-muted">
                    {ex.date || "—"}
                  </td>
                  <td className="px-4 py-3 text-muted text-xs max-w-xs truncate">
                    {ex.reason}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
