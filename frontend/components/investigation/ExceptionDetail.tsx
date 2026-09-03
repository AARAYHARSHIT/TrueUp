"use client";

import type { TransactionExceptionResponse } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatINR, formatDate } from "@/lib/formatters";
import {
  AlertTriangle,
  Link2,
  FileText,
  HelpCircle,
} from "lucide-react";

interface ExceptionDetailProps {
  data: TransactionExceptionResponse;
}

const exceptionDescriptions: Record<string, string> = {
  MISSING_SETTLEMENT:
    "Gateway transaction exists but no matching bank settlement was found. The payment was captured but never settled to the bank account.",
  MISSING_TXN:
    "Bank settlement exists but no matching gateway transaction was found. A settlement arrived without a corresponding payment record.",
  ORPHAN_LEDGER:
    "Ledger entry exists with no matching payment or settlement. The merchant expects this amount but no transaction initiated it.",
  AMOUNT_MISMATCH:
    "A match was found on key fields but the amounts differ beyond the acceptable tolerance. Possible fee deduction, refund, or data error.",
  DATE_MISMATCH:
    "A match was found on key fields but the dates fall outside the acceptable window. Unusual timing that needs investigation.",
  SPLIT_SETTLEMENT:
    "One gateway transaction was split across multiple bank settlements. Common for partial settlements or installment payments.",
  BATCH_SETTLEMENT:
    "Multiple gateway transactions were batched into a single bank settlement. Common for aggregated payout schedules.",
  ROUNDING_DIFF:
    "Matched on key fields with only a paise-level amount difference. Likely a rounding artifact from fee calculations.",
  UNRESOLVED_AMBIGUOUS:
    "Multiple candidate matches exist but none could be distinguished with sufficient confidence. Requires human review.",
};

function getExceptionBadgeColor(type: string): "red" | "amber" {
  if (type === "ROUNDING_DIFF" || type === "DATE_MISMATCH") return "amber";
  return "red";
}

export function ExceptionDetail({ data }: ExceptionDetailProps) {
  const description =
    exceptionDescriptions[data.exception_type] ||
    "An exception was detected during reconciliation.";

  return (
    <div className="space-y-4">
      {/* Exception Header */}
      <Card>
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-amber mt-0.5" strokeWidth={1.5} />
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <h3 className="text-sm font-medium text-foreground">
                {data.exception_type.replace(/_/g, " ")}
              </h3>
              <Badge variant={getExceptionBadgeColor(data.exception_type)}>
                {data.source}
              </Badge>
            </div>
            <p className="text-sm text-muted">{description}</p>
          </div>
        </div>
      </Card>

      {/* Exception Facts */}
      <Card>
        <h3 className="text-xs text-muted uppercase tracking-wider mb-3">
          Exception Facts
        </h3>
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-muted">Reason</span>
            <span className="text-foreground text-right max-w-[60%]">
              {data.reason}
            </span>
          </div>
          {data.amount && (
            <div className="flex justify-between">
              <span className="text-muted">Amount</span>
              <span className="text-foreground font-mono tabular-nums">
                {formatINR(data.amount)}
              </span>
            </div>
          )}
          {data.date && (
            <div className="flex justify-between">
              <span className="text-muted">Date</span>
              <span className="text-foreground">{formatDate(data.date)}</span>
            </div>
          )}
          <div className="flex justify-between">
            <span className="text-muted">Exception ID</span>
            <span className="text-foreground font-mono text-xs">
              {data.exception_id}
            </span>
          </div>
        </div>
      </Card>

      {/* Linked Records */}
      {data.linked_record_ids.length > 0 && (
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <Link2 className="h-4 w-4 text-blue" strokeWidth={1.5} />
            <h3 className="text-xs text-muted uppercase tracking-wider">
              Linked Records
            </h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {data.linked_record_ids.map((id) => (
              <span
                key={id}
                className="px-2 py-1 rounded text-xs font-mono bg-blue-dim text-blue border border-blue/30"
              >
                {id}
              </span>
            ))}
          </div>
        </Card>
      )}

      {/* Evidence */}
      {Object.keys(data.evidence).length > 0 && (
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <FileText className="h-4 w-4 text-muted" strokeWidth={1.5} />
            <h3 className="text-xs text-muted uppercase tracking-wider">
              Evidence
            </h3>
          </div>
          <div className="space-y-2">
            {Object.entries(data.evidence).map(([key, value]) => (
              <div
                key={key}
                className="flex justify-between text-sm py-1 border-b border-border last:border-0"
              >
                <span className="text-muted capitalize">
                  {key.replace(/_/g, " ")}
                </span>
                <span className="text-foreground font-mono text-xs">
                  {typeof value === "object"
                    ? JSON.stringify(value)
                    : String(value)}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* AI Involvement */}
      <Card>
        <div className="flex items-center gap-2">
          <HelpCircle className="h-4 w-4 text-muted" strokeWidth={1.5} />
          <span className="text-xs text-muted">AI Involvement:</span>
          <Badge variant="muted">Not called</Badge>
        </div>
        <p className="text-xs text-muted mt-2">
          This exception was classified by deterministic rules. No LLM was
          involved in this determination.
        </p>
      </Card>
    </div>
  );
}
