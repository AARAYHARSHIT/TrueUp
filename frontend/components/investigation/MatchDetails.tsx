"use client";

import type { TransactionMatchedResponse } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ConfidenceIndicator } from "./ConfidenceIndicator";
import { CheckCircle2, XCircle, Clock } from "lucide-react";

interface MatchDetailsProps {
  data: TransactionMatchedResponse;
}

export function MatchDetails({ data }: MatchDetailsProps) {
  const passLabel =
    data.match_pass === "deterministic" ? "Pass 1 — Deterministic" : "Pass 2 — Fuzzy";

  return (
    <Card>
      <h3 className="text-xs text-muted uppercase tracking-wider mb-4">
        Match Details
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div>
          <p className="text-xs text-muted mb-1">Resolved By</p>
          <Badge variant="blue">{passLabel}</Badge>
        </div>
        <div>
          <p className="text-xs text-muted mb-1">Method</p>
          <p className="text-sm text-foreground font-mono">
            {data.method.replace(/_/g, " ")}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted mb-1">Confidence</p>
          <ConfidenceIndicator confidence={data.confidence} />
        </div>
        <div>
          <p className="text-xs text-muted mb-1">Amount Match</p>
          <div className="flex items-center gap-1.5">
            {data.amount_agrees ? (
              <CheckCircle2 className="h-4 w-4 text-green" strokeWidth={1.5} />
            ) : (
              <XCircle className="h-4 w-4 text-amber" strokeWidth={1.5} />
            )}
            <span
              className={`text-sm ${data.amount_agrees ? "text-green" : "text-amber"}`}
            >
              {data.amount_agrees ? "Agrees" : "Differs"}
            </span>
          </div>
        </div>
      </div>

      {data.date_lag_days !== undefined && data.date_lag_days !== null && (
        <div className="mt-4 pt-4 border-t border-border">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted" strokeWidth={1.5} />
            <span className="text-xs text-muted">Date lag:</span>
            <span className="text-sm text-foreground">
              {data.date_lag_days} {data.date_lag_days === 1 ? "day" : "days"}
            </span>
            {data.date_lag_days > 3 && (
              <Badge variant="amber">Drift</Badge>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
