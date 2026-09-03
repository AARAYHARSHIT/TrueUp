"use client";

import { useSummary } from "@/hooks/useSummary";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { CardSkeleton } from "@/components/ui/LoadingSkeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { formatPercent, formatNumber } from "@/lib/formatters";
import { motion } from "motion/react";

const stages = [
  { key: "deterministic", label: "Pass 1: Deterministic", desc: "Exact order_id matching" },
  { key: "fuzzy", label: "Pass 2: Fuzzy", desc: "Amount tolerance, date window, edit distance, split/batch" },
  { key: "classify", label: "Pass 3: Exception Classification", desc: "9 named exception types" },
  { key: "llm", label: "Pass 4: LLM Resolution", desc: "Claude for genuinely ambiguous only" },
  { key: "report", label: "Pass 5: Reporter", desc: "Match rate vs ground truth" },
];

export default function ReconcilePage() {
  const summary = useSummary();

  if (summary.isLoading) return <CardSkeleton />;
  if (summary.error)
    return (
      <ErrorState
        message="Failed to load pipeline data."
        onRetry={() => summary.refetch()}
      />
    );

  const s = summary.data!;

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Reconciliation Pipeline</h1>
        <p className="text-sm text-muted mt-1">
          Deterministic-first, fuzzy-second, LLM-only-when-genuinely-ambiguous cascade
        </p>
      </div>

      <div className="space-y-4">
        {stages.map((stage, i) => {
          let matched: number | null = null;
          let rate: string | null = null;
          let badge: "green" | "blue" | "amber" | "muted" = "muted";

          if (stage.key === "deterministic") {
            matched = s.deterministic_pass.matched;
            rate = s.deterministic_pass.rate;
            badge = "blue";
          } else if (stage.key === "fuzzy") {
            matched = s.fuzzy_pass.additional_matched;
            badge = "green";
          } else if (stage.key === "classify") {
            matched = s.unmatched.exceptions_total;
            badge = "amber";
          }

          return (
            <motion.div
              key={stage.key}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.1 }}
            >
              <Card>
                <div className="flex items-center gap-4">
                  <div className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-dim text-blue text-sm font-bold shrink-0">
                    {i + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <h3 className="text-sm font-medium text-foreground">{stage.label}</h3>
                      <Badge variant={badge}>{stage.desc}</Badge>
                    </div>
                    {matched !== null && (
                      <div className="mt-2 flex items-center gap-4 text-sm">
                        <span className="text-muted">Records:</span>
                        <span className="text-foreground font-medium tabular-nums">
                          {formatNumber(matched)}
                        </span>
                        {rate && (
                          <>
                            <span className="text-muted">Rate:</span>
                            <span className="text-green font-medium tabular-nums">
                              {formatPercent(rate)}
                            </span>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                  {i < stages.length - 1 && (
                    <div className="text-muted text-lg">↓</div>
                  )}
                </div>
              </Card>
            </motion.div>
          );
        })}
      </div>

      <Card>
        <h3 className="text-sm font-medium text-foreground mb-3">Summary</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
          <div>
            <p className="text-2xl font-bold text-blue tabular-nums">
              {formatPercent(s.deterministic_pass.rate)}
            </p>
            <p className="text-xs text-muted">Deterministic</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-green tabular-nums">
              {formatPercent(s.final.rate)}
            </p>
            <p className="text-xs text-muted">Final</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-amber tabular-nums">
              +{s.improvement_pp}pp
            </p>
            <p className="text-xs text-muted">Improvement</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-foreground tabular-nums">
              {s.deterministic_pass.full_triples}
            </p>
            <p className="text-xs text-muted">Full triples</p>
          </div>
        </div>
      </Card>
    </div>
  );
}
