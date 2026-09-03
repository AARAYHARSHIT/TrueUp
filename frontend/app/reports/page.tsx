"use client";

import { useReport } from "@/hooks/useReport";
import { Card } from "@/components/ui/Card";
import { CardSkeleton } from "@/components/ui/LoadingSkeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { Download, FileText, Copy } from "lucide-react";

export default function ReportsPage() {
  const report = useReport();

  if (report.isLoading) return <CardSkeleton />;
  if (report.error)
    return (
      <ErrorState
        message="Failed to load report."
        onRetry={() => report.refetch()}
      />
    );

  const r = report.data!;

  const handleDownloadJSON = () => {
    const blob = new Blob([JSON.stringify(r, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "reconciliation_report.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadText = () => {
    const text = generateTextReport(r as unknown as Record<string, unknown>);
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "reconciliation_report.txt";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleCopyToClipboard = async () => {
    const text = generateTextReport(r as unknown as Record<string, unknown>);
    await navigator.clipboard.writeText(text);
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Reports</h1>
          <p className="text-sm text-muted mt-1">
            Reconciliation report — generated{" "}
            {r.generated_at
              ? new Date(r.generated_at).toLocaleString("en-IN")
              : "unknown"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopyToClipboard}
            className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-4 py-2 text-sm text-foreground hover:bg-card-hover transition-colors"
          >
            <Copy className="h-4 w-4" />
            Copy
          </button>
          <button
            onClick={handleDownloadText}
            className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-4 py-2 text-sm text-foreground hover:bg-card-hover transition-colors"
          >
            <FileText className="h-4 w-4" />
            Download TXT
          </button>
          <button
            onClick={handleDownloadJSON}
            className="inline-flex items-center gap-2 rounded-md bg-amber px-4 py-2 text-sm font-medium text-background hover:opacity-90 transition-opacity"
          >
            <Download className="h-4 w-4" />
            Download JSON
          </button>
        </div>
      </div>

      {r.record_counts && (
        <Card>
          <h3 className="text-xs text-muted uppercase tracking-wider mb-3">
            Record Counts
          </h3>
          <div className="grid grid-cols-3 gap-4 text-center">
            {Object.entries(r.record_counts).map(([key, val]) => (
              <div key={key}>
                <p className="text-2xl font-bold text-foreground tabular-nums">
                  {val}
                </p>
                <p className="text-xs text-muted capitalize">
                  {key.replace(/_/g, " ")}
                </p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {r.match_rates && (
        <Card>
          <h3 className="text-xs text-muted uppercase tracking-wider mb-3">
            Match Rates
          </h3>
          <pre className="text-sm text-muted overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(r.match_rates, null, 2)}
          </pre>
        </Card>
      )}

      {r.exceptions && (
        <Card>
          <h3 className="text-xs text-muted uppercase tracking-wider mb-3">
            Exception Breakdown
          </h3>
          <pre className="text-sm text-muted overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(r.exceptions, null, 2)}
          </pre>
        </Card>
      )}

      <Card>
        <h3 className="text-xs text-muted uppercase tracking-wider mb-3">
          Full Report JSON
        </h3>
        <pre className="text-xs text-muted overflow-x-auto whitespace-pre-wrap max-h-96">
          {JSON.stringify(r, null, 2)}
        </pre>
      </Card>
    </div>
  );
}

function generateTextReport(report: Record<string, unknown>): string {
  const lines: string[] = [];
  lines.push("=== TRUEUP RECONCILIATION REPORT ===");
  lines.push(`Generated: ${report.generated_at || "N/A"}`);
  lines.push(`Pipeline: ${report.pipeline || "N/A"}`);
  lines.push("");

  if (report.record_counts) {
    lines.push("--- RECORD COUNTS ---");
    const counts = report.record_counts as Record<string, number>;
    Object.entries(counts).forEach(([key, val]) => {
      lines.push(`  ${key.replace(/_/g, " ")}: ${val}`);
    });
    lines.push("");
  }

  if (report.match_rates) {
    lines.push("--- MATCH RATES ---");
    const rates = report.match_rates as Record<string, unknown>;
    Object.entries(rates).forEach(([key, val]) => {
      lines.push(`  ${key}: ${val}`);
    });
    lines.push("");
  }

  if (report.exceptions) {
    lines.push("--- EXCEPTIONS ---");
    const exceptions = report.exceptions as Record<string, unknown>;
    Object.entries(exceptions).forEach(([key, val]) => {
      lines.push(`  ${key}: ${val}`);
    });
    lines.push("");
  }

  lines.push("=== END REPORT ===");
  return lines.join("\n");
}
