"use client";

import type {
  TransactionMatchedResponse,
  TransactionExceptionResponse,
} from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatINR, formatDate } from "@/lib/formatters";
import { Building2, Landmark, BookOpen } from "lucide-react";

interface SourceComparisonProps {
  data: TransactionMatchedResponse | TransactionExceptionResponse;
}

export function SourceComparison({ data }: SourceComparisonProps) {
  const isMatched = data.status === "MATCHED";
  const matched = isMatched ? (data as TransactionMatchedResponse) : null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* Gateway */}
      <Card>
        <div className="flex items-center gap-2 mb-3">
          <Building2 className="h-4 w-4 text-blue" strokeWidth={1.5} />
          <h3 className="text-xs text-muted uppercase tracking-wider">
            Gateway
          </h3>
        </div>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted">Amount</span>
            <span className="text-foreground font-mono tabular-nums">
              {matched ? formatINR(matched.gateway_amount) : "—"}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Date</span>
            <span className="text-foreground">
              {matched ? formatDate(matched.gateway_date) : "—"}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Fee</span>
            <span className="text-foreground font-mono tabular-nums">
              {matched ? formatINR(matched.gateway_fee) : "—"}
            </span>
          </div>
          {!isMatched && (
            <div className="pt-2 border-t border-border">
              <Badge variant="red">No match found</Badge>
            </div>
          )}
        </div>
      </Card>

      {/* Bank Settlement */}
      <Card>
        <div className="flex items-center gap-2 mb-3">
          <Landmark className="h-4 w-4 text-green" strokeWidth={1.5} />
          <h3 className="text-xs text-muted uppercase tracking-wider">
            Bank Settlement
          </h3>
        </div>
        <div className="space-y-2 text-sm">
          {matched?.bank_settlement ? (
            <>
              <div className="flex justify-between">
                <span className="text-muted">UTR</span>
                <span className="text-foreground font-mono text-xs">
                  {matched.bank_settlement.utr}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Amount</span>
                <span className="text-foreground font-mono tabular-nums">
                  {formatINR(matched.bank_settlement.settlement_amount)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Date</span>
                <span className="text-foreground">
                  {formatDate(matched.bank_settlement.settlement_date)}
                </span>
              </div>
            </>
          ) : (
            <div className="pt-1">
              <Badge variant={isMatched ? "muted" : "red"}>
                {isMatched ? "Not linked" : "No settlement"}
              </Badge>
            </div>
          )}
        </div>
      </Card>

      {/* Merchant Ledger */}
      <Card>
        <div className="flex items-center gap-2 mb-3">
          <BookOpen className="h-4 w-4 text-amber" strokeWidth={1.5} />
          <h3 className="text-xs text-muted uppercase tracking-wider">
            Merchant Ledger
          </h3>
        </div>
        <div className="space-y-2 text-sm">
          {matched?.merchant_ledger ? (
            <>
              <div className="flex justify-between">
                <span className="text-muted">Expected</span>
                <span className="text-foreground font-mono tabular-nums">
                  {formatINR(matched.merchant_ledger.expected_amount)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Date</span>
                <span className="text-foreground">
                  {formatDate(matched.merchant_ledger.entry_date)}
                </span>
              </div>
              {matched.merchant_ledger.notes && (
                <div className="pt-2 border-t border-border">
                  <p className="text-xs text-muted italic">
                    {matched.merchant_ledger.notes}
                  </p>
                </div>
              )}
            </>
          ) : (
            <div className="pt-1">
              <Badge variant={isMatched ? "muted" : "red"}>
                {isMatched ? "Not linked" : "No ledger entry"}
              </Badge>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
