"use client";

import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useTransaction } from "@/hooks/useTransaction";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ErrorState } from "@/components/ui/ErrorState";
import { Search, ExternalLink } from "lucide-react";
import type {
  TransactionMatchedResponse,
  TransactionExceptionResponse,
  TransactionNotFoundResponse,
} from "@/lib/types";

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

function TransactionsContent() {
  const searchParams = useSearchParams();
  const initial = searchParams.get("search") || "";
  const [search, setSearch] = useState(initial);
  const [query, setQuery] = useState(initial);

  const { data, isLoading, error, refetch } = useTransaction(query);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setQuery(search.trim());
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Transactions</h1>
        <p className="text-sm text-muted mt-1">
          Search by order ID to investigate a transaction
        </p>
      </div>

      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Enter order ID (e.g. ORD-10071)"
            className="w-full rounded-md border border-border bg-card pl-9 pr-4 py-2 text-sm text-foreground placeholder:text-muted focus:outline-none focus:border-blue transition-colors"
          />
        </div>
        <button
          type="submit"
          className="rounded-md bg-blue px-4 py-2 text-sm font-medium text-background hover:opacity-90 transition-opacity"
        >
          Search
        </button>
      </form>

      <div className="flex gap-2">
        <span className="text-xs text-muted py-1">Try:</span>
        {demoIds.map((d) => (
          <button
            key={d.id}
            onClick={() => {
              setSearch(d.id);
              setQuery(d.id);
            }}
            className="inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-mono bg-card border border-border text-muted hover:text-foreground hover:bg-card-hover transition-colors"
          >
            {d.id}
            <Badge variant={d.variant} className="text-[10px]">
              {d.label}
            </Badge>
          </button>
        ))}
      </div>

      {isLoading && (
        <Card>
          <div className="animate-pulse space-y-3">
            <div className="h-4 w-1/3 rounded bg-border" />
            <div className="h-8 w-1/2 rounded bg-border" />
          </div>
        </Card>
      )}

      {error && (
        <ErrorState
          message="Failed to fetch transaction."
          onRetry={() => refetch()}
        />
      )}

      {data && isNotFound(data) && (
        <Card>
          <div className="text-center py-8">
            <p className="text-lg font-medium text-foreground">Not Found</p>
            <p className="text-sm text-muted mt-1">{data.error}</p>
            {data.hint && (
              <p className="text-xs text-muted mt-2">{data.hint}</p>
            )}
          </div>
        </Card>
      )}

      {data && isMatched(data) && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-foreground font-mono">
              {data.txn_id}
            </h2>
            <Badge variant="green">MATCHED</Badge>
            <Badge variant="blue">{data.match_pass}</Badge>
            <Link
              href={`/transactions/${data.txn_id}`}
              className="ml-auto inline-flex items-center gap-1.5 text-xs text-blue hover:text-foreground transition-colors"
            >
              Investigate
              <ExternalLink className="h-3 w-3" />
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <h3 className="text-xs text-muted uppercase tracking-wider mb-2">
                Gateway
              </h3>
              <div className="space-y-1 text-sm">
                <p className="text-foreground tabular-nums">
                  Amount: ₹{parseFloat(data.gateway_amount).toLocaleString("en-IN")}
                </p>
                <p className="text-muted">Date: {data.gateway_date}</p>
                <p className="text-muted">Fee: ₹{parseFloat(data.gateway_fee).toLocaleString("en-IN")}</p>
              </div>
            </Card>

            {data.bank_settlement && (
              <Card>
                <h3 className="text-xs text-muted uppercase tracking-wider mb-2">
                  Bank Settlement
                </h3>
                <div className="space-y-1 text-sm">
                  <p className="text-muted">UTR: {data.bank_settlement.utr}</p>
                  <p className="text-foreground tabular-nums">
                    Amount: ₹{parseFloat(data.bank_settlement.settlement_amount).toLocaleString("en-IN")}
                  </p>
                  <p className="text-muted">Date: {data.bank_settlement.settlement_date}</p>
                </div>
              </Card>
            )}

            {data.merchant_ledger && (
              <Card>
                <h3 className="text-xs text-muted uppercase tracking-wider mb-2">
                  Merchant Ledger
                </h3>
                <div className="space-y-1 text-sm">
                  <p className="text-foreground tabular-nums">
                    Expected: ₹{parseFloat(data.merchant_ledger.expected_amount).toLocaleString("en-IN")}
                  </p>
                  <p className="text-muted">Date: {data.merchant_ledger.entry_date}</p>
                  <p className="text-muted text-xs">{data.merchant_ledger.notes}</p>
                </div>
              </Card>
            )}
          </div>

          <Card>
            <h3 className="text-xs text-muted uppercase tracking-wider mb-2">
              Match Details
            </h3>
            <div className="flex flex-wrap gap-4 text-sm">
              <div>
                <span className="text-muted">Method: </span>
                <span className="text-foreground">{data.method}</span>
              </div>
              <div>
                <span className="text-muted">Confidence: </span>
                <span className="text-green">{(data.confidence * 100).toFixed(1)}%</span>
              </div>
              <div>
                <span className="text-muted">Amount agrees: </span>
                <span className={data.amount_agrees ? "text-green" : "text-amber"}>
                  {data.amount_agrees ? "Yes" : "No"}
                </span>
              </div>
              {data.date_lag_days !== undefined && (
                <div>
                  <span className="text-muted">Date lag: </span>
                  <span className="text-foreground">{data.date_lag_days} days</span>
                </div>
              )}
            </div>
          </Card>
        </div>
      )}

      {data && isException(data) && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-foreground font-mono">
              {data.txn_id}
            </h2>
            <Badge variant="red">EXCEPTION</Badge>
            <Badge variant="amber">{data.exception_type.replace(/_/g, " ")}</Badge>
            <Link
              href={`/transactions/${data.txn_id}`}
              className="ml-auto inline-flex items-center gap-1.5 text-xs text-blue hover:text-foreground transition-colors"
            >
              Investigate
              <ExternalLink className="h-3 w-3" />
            </Link>
          </div>

          <Card>
            <h3 className="text-xs text-muted uppercase tracking-wider mb-2">
              Exception Details
            </h3>
            <div className="space-y-2 text-sm">
              <p className="text-foreground">{data.reason}</p>
              {data.amount && (
                <p className="text-muted tabular-nums">
                  Amount: ₹{parseFloat(data.amount).toLocaleString("en-IN")}
                </p>
              )}
              {data.date && <p className="text-muted">Date: {data.date}</p>}
              {data.linked_record_ids.length > 0 && (
                <p className="text-muted">
                  Linked: {data.linked_record_ids.join(", ")}
                </p>
              )}
            </div>
          </Card>

          {Object.keys(data.evidence).length > 0 && (
            <Card>
              <h3 className="text-xs text-muted uppercase tracking-wider mb-2">
                Evidence
              </h3>
              <pre className="text-xs text-muted overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(data.evidence, null, 2)}
              </pre>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

export default function TransactionsPage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-6 max-w-4xl">
          <div className="animate-pulse space-y-3">
            <div className="h-6 w-48 rounded bg-border" />
            <div className="h-4 w-64 rounded bg-border" />
          </div>
        </div>
      }
    >
      <TransactionsContent />
    </Suspense>
  );
}
