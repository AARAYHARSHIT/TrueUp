"use client";

import { Card } from "@/components/ui/Card";
import { formatNumber } from "@/lib/formatters";
import { motion } from "motion/react";

interface Stage {
  label: string;
  count: number;
  color: string;
}

export function WaterfallChart({
  deterministic,
  fuzzyAdditional,
  exceptions,
  total,
}: {
  deterministic: number;
  fuzzyAdditional: number;
  exceptions: number;
  total: number;
}) {
  const stages: Stage[] = [
    { label: "Deterministic", count: deterministic, color: "var(--blue)" },
    { label: "Fuzzy-assisted", count: fuzzyAdditional, color: "var(--green)" },
    { label: "Exceptions", count: exceptions, color: "var(--amber)" },
  ];

  const maxCount = total;

  return (
    <Card>
      <h3 className="text-sm font-medium text-foreground mb-4">
        Pipeline Waterfall
      </h3>
      <div className="space-y-3">
        {stages.map((stage, i) => {
          const pct = maxCount > 0 ? (stage.count / maxCount) * 100 : 0;
          return (
            <div key={stage.label} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted">{stage.label}</span>
                <span className="text-foreground font-medium tabular-nums">
                  {formatNumber(stage.count)}
                </span>
              </div>
              <div className="h-6 rounded bg-border overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={{ delay: 0.2 + i * 0.15, duration: 0.6, ease: "easeOut" }}
                  className="h-full rounded"
                  style={{ backgroundColor: stage.color }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-xs">
        <span className="text-muted">Total gateway records</span>
        <span className="text-foreground font-semibold tabular-nums">
          {formatNumber(total)}
        </span>
      </div>
    </Card>
  );
}
