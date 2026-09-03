"use client";

import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatINR, formatDate } from "@/lib/formatters";
import {
  CheckCircle2,
  XCircle,
  ArrowRight,
  Building2,
  Landmark,
  BookOpen,
} from "lucide-react";

interface CompareTransaction {
  txn_id: string;
  status: "MATCHED" | "EXCEPTION";
  amount: string;
  date: string;
  method?: string;
  exception_type?: string;
}

interface CompareViewProps {
  current: CompareTransaction;
  compare: CompareTransaction;
}

export function CompareView({ current, compare }: CompareViewProps) {
  return (
    <Card>
      <h3 className="text-xs text-muted uppercase tracking-wider mb-4">
        Compare: Matched vs Unmatched
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Current */}
        <div
          className={`rounded-lg border p-4 ${
            current.status === "MATCHED"
              ? "border-green/30 bg-green-dim"
              : "border-red/30 bg-red-dim"
          }`}
        >
          <div className="flex items-center gap-2 mb-3">
            <Badge variant={current.status === "MATCHED" ? "green" : "red"}>
              {current.status}
            </Badge>
            <Link
              href={`/transactions/${current.txn_id}`}
              className="text-sm font-mono text-foreground hover:text-blue transition-colors"
            >
              {current.txn_id}
            </Link>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted">Amount</span>
              <span className="text-foreground font-mono tabular-nums">
                {formatINR(current.amount)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Date</span>
              <span className="text-foreground">{formatDate(current.date)}</span>
            </div>
            {current.method && (
              <div className="flex justify-between">
                <span className="text-muted">Method</span>
                <span className="text-foreground text-xs">
                  {current.method.replace(/_/g, " ")}
                </span>
              </div>
            )}
            {current.exception_type && (
              <div className="flex justify-between">
                <span className="text-muted">Exception</span>
                <span className="text-foreground text-xs">
                  {current.exception_type.replace(/_/g, " ")}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Compare */}
        <div
          className={`rounded-lg border p-4 ${
            compare.status === "MATCHED"
              ? "border-green/30 bg-green-dim"
              : "border-red/30 bg-red-dim"
          }`}
        >
          <div className="flex items-center gap-2 mb-3">
            <Badge variant={compare.status === "MATCHED" ? "green" : "red"}>
              {compare.status}
            </Badge>
            <Link
              href={`/transactions/${compare.txn_id}`}
              className="text-sm font-mono text-foreground hover:text-blue transition-colors"
            >
              {compare.txn_id}
            </Link>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted">Amount</span>
              <span className="text-foreground font-mono tabular-nums">
                {formatINR(compare.amount)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Date</span>
              <span className="text-foreground">{formatDate(compare.date)}</span>
            </div>
            {compare.method && (
              <div className="flex justify-between">
                <span className="text-muted">Method</span>
                <span className="text-foreground text-xs">
                  {compare.method.replace(/_/g, " ")}
                </span>
              </div>
            )}
            {compare.exception_type && (
              <div className="flex justify-between">
                <span className="text-muted">Exception</span>
                <span className="text-foreground text-xs">
                  {compare.exception_type.replace(/_/g, " ")}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Key difference */}
      <div className="mt-4 pt-3 border-t border-border">
        <div className="flex items-center gap-2 text-xs text-muted">
          <CheckCircle2 className="h-3.5 w-3.5 text-green" />
          <span>Matched: all three sources agree on identity and amount</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted mt-1">
          <XCircle className="h-3.5 w-3.5 text-red" />
          <span>Unmatched: one or more sources missing or disagreeing</span>
        </div>
      </div>
    </Card>
  );
}
