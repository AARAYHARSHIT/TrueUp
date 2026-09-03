"use client";

import { Card } from "@/components/ui/Card";
import { formatPercent } from "@/lib/formatters";
import { motion } from "motion/react";

export function MatchRateHero({
  deterministicRate,
  finalRate,
  improvement,
}: {
  deterministicRate: string;
  finalRate: string;
  improvement: string;
}) {
  const finalNum = parseFloat(finalRate) || 0;

  return (
    <Card className="relative overflow-hidden">
      <div className="flex items-center gap-8">
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 200, damping: 20 }}
          className="shrink-0"
        >
          <div className="relative">
            <svg viewBox="0 0 120 120" className="w-28 h-28">
              <circle
                cx="60"
                cy="60"
                r="50"
                fill="none"
                stroke="var(--border)"
                strokeWidth="8"
              />
              <circle
                cx="60"
                cy="60"
                r="50"
                fill="none"
                stroke="var(--green)"
                strokeWidth="8"
                strokeDasharray={`${(finalNum / 100) * 314.16} 314.16`}
                strokeLinecap="round"
                transform="rotate(-90 60 60)"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-2xl font-bold text-foreground tabular-nums">
                {formatPercent(finalRate)}
              </span>
            </div>
          </div>
        </motion.div>

        <div className="space-y-2">
          <h2 className="text-lg font-semibold text-foreground">
            Final Match Rate
          </h2>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted">Deterministic</span>
            <span className="text-foreground font-medium tabular-nums">
              {formatPercent(deterministicRate)}
            </span>
            <span className="text-muted">→</span>
            <span className="text-green font-medium tabular-nums">
              +{improvement}pp improvement
            </span>
          </div>
          <p className="text-xs text-muted">
            Fuzzy matching resolved {improvement} percentage points of
            additional transactions
          </p>
        </div>
      </div>
    </Card>
  );
}
