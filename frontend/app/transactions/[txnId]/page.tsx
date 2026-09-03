"use client";

import { use, Suspense } from "react";
import Link from "next/link";
import { useTransaction } from "@/hooks/useTransaction";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ErrorState } from "@/components/ui/ErrorState";
import { EvidenceTimeline } from "@/components/investigation/EvidenceTimeline";
import { SourceComparison } from "@/components/investigation/SourceComparison";
import { MatchDetails } from "@/components/investigation/MatchDetails";
import { ExceptionDetail } from "@/components/investigation/ExceptionDetail";
import { CopyAsText } from "@/components/investigation/CopyAsText";
import { CompareView } from "@/components/investigation/CompareView";
import {
  TransactionMatchedResponse,
  TransactionExceptionResponse,
  TransactionNotFoundResponse,
} from "@/lib/types";
import {
  ArrowLeft,
  Building2,
  Search,
  ExternalLink,
} from "lucide-react";

function isMatched(r: unknown): r is TransactionMatchedResponse {
  return (r as TransactionMatchedResponse)?.status === "MATCHED";
}

function isException(r: unknown): r is TransactionExceptionResponse {
  return (r as TransactionExceptionResponse)?.status === "EXCEPTION";
}

function isNotFound(r: unknown): r is TransactionNotFoundResponse {
  return (r as TransactionNotFoundResponse)?.status === "NOT_FOUND";
}

const demoIds = [
  { id: "ORD-10071", label: "Exception", variant: "red" as const },
  { id: "ORD-10001", label: "Matched", variant: "green" as const },
  { id: "ORD-99999", label: "Not found", variant: "muted" as const },
];

function InvestigationContent({ txnId }: { txnId: string }) {
  const { data, isLoading, error, refetch } = useTransaction(txnId);

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link
            href="/transactions"
            className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Transactions
          </Link>
        </div>
        {data && !isNotFound(data) && <CopyAsText data={data} />}
      </div>

      {/* Transaction ID + Status */}
      {isLoading && (
        <div className="space-y-4">
          <div className="animate-pulse space-y-3">
            <div className="h-8 w-64 rounded bg-border" />
            <div className="h-4 w-48 rounded bg-border" />
          </div>
          <div className="animate-pulse">
            <div className="h-16 rounded-lg bg-border" />
          </div>
        </div>
      )}

      {error && (
        <ErrorState
          message={`Failed to load transaction ${txnId}.`}
          onRetry={() => refetch()}
        />
      )}

      {data && isNotFound(data) && (
        <Card>
          <div className="text-center py-12">
            <Search className="h-12 w-12 text-muted mx-auto mb-4" strokeWidth={1} />
            <h2 className="text-lg font-medium text-foreground mb-1">
              Transaction Not Found
            </h2>
            <p className="text-sm text-muted max-w-md mx-auto">
              No gateway transaction with order ID{" "}
              <span className="font-mono text-foreground">{txnId}</span> was
              found in the dataset.
            </p>
            {data.hint && (
              <p className="text-xs text-muted mt-3">{data.hint}</p>
            )}
            <div className="mt-6 flex items-center justify-center gap-3">
              <Link
                href="/transactions"
                className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-4 py-2 text-sm text-foreground hover:bg-card-hover transition-colors"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to search
              </Link>
            </div>
            <div className="mt-6">
              <p className="text-xs text-muted mb-2">Try a known transaction:</p>
              <div className="flex items-center justify-center gap-2">
                {demoIds.map((d) => (
                  <Link
                    key={d.id}
                    href={`/transactions/${d.id}`}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-mono bg-card border border-border text-muted hover:text-foreground hover:bg-card-hover transition-colors"
                  >
                    {d.id}
                    <Badge variant={d.variant} className="text-[10px]">
                      {d.label}
                    </Badge>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </Card>
      )}

      {data && isMatched(data) && (
        <div className="space-y-4">
          {/* Title */}
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-foreground font-mono">
              {data.txn_id}
            </h1>
            <Badge variant="green">MATCHED</Badge>
            <Badge variant="blue">
              {data.match_pass === "deterministic" ? "Pass 1" : "Pass 2"}
            </Badge>
          </div>

          {/* Amount Hero */}
          <Card>
            <div className="flex items-baseline gap-3">
              <span className="text-3xl font-semibold text-green font-mono tabular-nums">
                {new Intl.NumberFormat("en-IN", {
                  style: "currency",
                  currency: "INR",
                }).format(parseFloat(data.gateway_amount))}
              </span>
              <span className="text-sm text-muted">settled and matched</span>
            </div>
          </Card>

          {/* Evidence Timeline */}
          <EvidenceTimeline data={data} />

          {/* Source Comparison */}
          <SourceComparison data={data} />

          {/* Match Details */}
          <MatchDetails data={data} />
        </div>
      )}

      {data && isException(data) && (
        <div className="space-y-4">
          {/* Title */}
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-foreground font-mono">
              {data.txn_id}
            </h1>
            <Badge variant="red">EXCEPTION</Badge>
            <Badge variant="amber">
              {data.exception_type.replace(/_/g, " ")}
            </Badge>
          </div>

          {/* Amount Hero */}
          <Card>
            <div className="flex items-baseline gap-3">
              {data.amount ? (
                <span className="text-3xl font-semibold text-red font-mono tabular-nums">
                  {new Intl.NumberFormat("en-IN", {
                    style: "currency",
                    currency: "INR",
                  }).format(parseFloat(data.amount))}
                </span>
              ) : (
                <span className="text-3xl font-semibold text-red font-mono">
                  —
                </span>
              )}
              <span className="text-sm text-muted">
                {data.exception_type.replace(/_/g, " ").toLowerCase()}
              </span>
            </div>
          </Card>

          {/* Evidence Timeline */}
          <EvidenceTimeline data={data} />

          {/* Source Comparison */}
          <SourceComparison data={data} />

          {/* Exception Detail */}
          <ExceptionDetail data={data} />
        </div>
      )}

      {/* Compare View — known demo pair */}
      {data && isMatched(data) && txnId.toUpperCase() === "ORD-10001" && (
        <CompareView
          current={{
            txn_id: data.txn_id,
            status: "MATCHED",
            amount: data.gateway_amount,
            date: data.gateway_date,
            method: data.method,
          }}
          compare={{
            txn_id: "ORD-10071",
            status: "EXCEPTION",
            amount: "21643.55",
            date: "2026-08-05",
            exception_type: "MISSING_SETTLEMENT",
          }}
        />
      )}
      {data && isException(data) && txnId.toUpperCase() === "ORD-10071" && (
        <CompareView
          current={{
            txn_id: data.txn_id,
            status: "EXCEPTION",
            amount: data.amount || "0",
            date: data.date || "",
            exception_type: data.exception_type,
          }}
          compare={{
            txn_id: "ORD-10001",
            status: "MATCHED",
            amount: "15240.00",
            date: "2026-08-04",
            method: "exact_order_id",
          }}
        />
      )}

      {/* Quick navigation */}
      {data && !isNotFound(data) && (
        <div className="pt-4 border-t border-border">
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted">Investigate another transaction</p>
            <div className="flex items-center gap-2">
              {demoIds
                .filter((d) => d.id !== txnId)
                .map((d) => (
                  <Link
                    key={d.id}
                    href={`/transactions/${d.id}`}
                    className="inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-mono text-muted hover:text-foreground transition-colors"
                  >
                    {d.id}
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function TransactionInvestigationPage({
  params,
}: {
  params: Promise<{ txnId: string }>;
}) {
  const { txnId } = use(params);

  return (
    <Suspense
      fallback={
        <div className="space-y-6 max-w-5xl">
          <div className="animate-pulse space-y-3">
            <div className="h-6 w-48 rounded bg-border" />
            <div className="h-8 w-64 rounded bg-border" />
            <div className="h-16 rounded-lg bg-border" />
          </div>
        </div>
      }
    >
      <InvestigationContent txnId={txnId} />
    </Suspense>
  );
}
