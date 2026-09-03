"use client";

import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

export function SplitBatchProof({
  splitsDetected,
  batchesDetected,
}: {
  splitsDetected: number;
  batchesDetected: number;
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <Card>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-muted font-medium uppercase tracking-wider">
              Split Settlements
            </p>
            <p className="text-2xl font-semibold text-foreground tabular-nums mt-1">
              {splitsDetected}/4
            </p>
            <p className="text-xs text-muted mt-1">detected</p>
          </div>
          <Badge variant="green">100%</Badge>
        </div>
        <p className="text-xs text-muted mt-3">
          One gateway transaction splitting into multiple bank credits
        </p>
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-muted font-medium uppercase tracking-wider">
              Batch Settlements
            </p>
            <p className="text-2xl font-semibold text-foreground tabular-nums mt-1">
              {batchesDetected}/3
            </p>
            <p className="text-xs text-muted mt-1">detected</p>
          </div>
          <Badge variant="amber">67%</Badge>
        </div>
        <p className="text-xs text-muted mt-3">
          Multiple gateway transactions combined into one bank credit
        </p>
      </Card>
    </div>
  );
}
