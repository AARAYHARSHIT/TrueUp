"use client";

import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { ExceptionItem } from "@/lib/types";

function exceptionBadgeVariant(
  type: string
): "green" | "amber" | "red" | "blue" | "muted" {
  if (type.includes("MISSING")) return "red";
  if (type.includes("ORPHAN")) return "red";
  if (type.includes("BATCH")) return "amber";
  if (type.includes("SPLIT")) return "amber";
  return "muted";
}

export function ExceptionPreview({
  exceptions,
  total,
}: {
  exceptions: ExceptionItem[];
  total: number;
}) {
  const shown = exceptions.slice(0, 5);

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-foreground">
          Top Exceptions
        </h3>
        <Link
          href="/exceptions"
          className="text-xs text-blue hover:text-blue/80 inline-flex items-center gap-1 transition-colors"
        >
          View all <ArrowRight className="h-3 w-3" />
        </Link>
      </div>

      {shown.length === 0 ? (
        <p className="text-sm text-muted py-4 text-center">No exceptions</p>
      ) : (
        <div className="space-y-2">
          {shown.map((ex) => (
            <Link
              key={ex.exception_id}
              href={`/transactions?search=${ex.record_id}`}
              className="flex items-center justify-between rounded-md border border-border px-3 py-2 hover:bg-card-hover transition-colors"
            >
              <div className="flex items-center gap-3 min-w-0">
                <Badge variant={exceptionBadgeVariant(ex.type)}>
                  {ex.type.replace(/_/g, " ")}
                </Badge>
                <span className="text-sm text-foreground font-mono truncate">
                  {ex.record_id}
                </span>
              </div>
              <div className="text-right shrink-0 ml-3">
                {ex.amount && (
                  <span className="text-sm text-foreground tabular-nums">
                    ₹{parseFloat(ex.amount).toLocaleString("en-IN")}
                  </span>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}

      {total > 5 && (
        <p className="text-xs text-muted mt-3 text-center">
          +{total - 5} more exceptions
        </p>
      )}
    </Card>
  );
}
