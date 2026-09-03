"use client";

import { useCashPosition } from "@/hooks/useCashPosition";
import { useForecast } from "@/hooks/useForecast";
import { Card } from "@/components/ui/Card";
import { CardSkeleton } from "@/components/ui/LoadingSkeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { formatINR } from "@/lib/formatters";
import { motion } from "motion/react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export default function CashPage() {
  const cash = useCashPosition();
  const forecast = useForecast();

  const isLoading = cash.isLoading || forecast.isLoading;
  const error = cash.error || forecast.error;

  if (isLoading) {
    return (
      <div className="space-y-6">
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  }

  if (error) {
    return (
      <ErrorState
        message="Failed to load cash data."
        onRetry={() => {
          cash.refetch();
          forecast.refetch();
        }}
      />
    );
  }

  const c = cash.data!;
  const f = forecast.data!;

  const forecastData = Object.entries(f.by_date).map(([date, amount]) => ({
    date: new Date(date).toLocaleDateString("en-IN", { month: "short", day: "numeric" }),
    amount: parseFloat(amount),
  }));

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Cash Position</h1>
        <p className="text-sm text-muted mt-1">
          Unreconciled exposure and 14-day forecast
        </p>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <Card>
          <div className="text-center py-4">
            <p className="text-xs text-muted uppercase tracking-wider mb-1">
              Total Unreconciled
            </p>
            <p className="text-3xl font-bold text-red tabular-nums">
              {formatINR(c.total_unreconciled_inr)}
            </p>
          </div>
        </Card>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <Card>
            <p className="text-xs text-muted uppercase tracking-wider mb-1">
              Missing Settlement
            </p>
            <p className="text-xl font-semibold text-red tabular-nums">
              {formatINR(c.missing_settlement.exposure_inr)}
            </p>
            <p className="text-xs text-muted mt-1">
              {c.missing_settlement.count} transactions
            </p>
          </Card>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
          <Card>
            <p className="text-xs text-muted uppercase tracking-wider mb-1">
              Orphan Ledger
            </p>
            <p className="text-xl font-semibold text-amber tabular-nums">
              {formatINR(c.orphan_ledger.exposure_inr)}
            </p>
            <p className="text-xs text-muted mt-1">
              {c.orphan_ledger.count} entries
            </p>
          </Card>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <Card>
            <p className="text-xs text-muted uppercase tracking-wider mb-1">
              Batch Pending
            </p>
            <p className="text-xl font-semibold text-amber tabular-nums">
              {formatINR(c.batch_settlement_pending.exposure_inr)}
            </p>
            <p className="text-xs text-muted mt-1">
              {c.batch_settlement_pending.count} batch members
            </p>
          </Card>
        </motion.div>
      </div>

      <Card>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-foreground">
            14-Day Forecast
          </h3>
          <span className="text-sm text-green font-medium tabular-nums">
            Total: {formatINR(f.total_forecast_inr)}
          </span>
        </div>

        {forecastData.length > 0 ? (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={forecastData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "var(--muted)", fontSize: 11 }}
                  axisLine={{ stroke: "var(--border)" }}
                />
                <YAxis
                  tick={{ fill: "var(--muted)", fontSize: 11 }}
                  axisLine={{ stroke: "var(--border)" }}
                  tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}K`}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--card)",
                    border: "1px solid var(--border)",
                    borderRadius: "6px",
                    fontSize: "12px",
                  }}
                  formatter={(value) => [`₹${Number(value).toLocaleString("en-IN")}`, "Amount"]}
                />
                <Bar dataKey="amount" fill="var(--green)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="text-sm text-muted text-center py-8">No forecast data</p>
        )}

        <div className="mt-4 pt-3 border-t border-border">
          <h4 className="text-xs text-muted uppercase tracking-wider mb-2">
            By Exception Type
          </h4>
          <div className="flex flex-wrap gap-3">
            {Object.entries(f.by_exception_type).map(([type, amount]) => (
              <div key={type} className="flex items-center gap-2">
                <span className="text-xs text-muted">{type.replace(/_/g, " ")}:</span>
                <span className="text-xs text-foreground font-medium tabular-nums">
                  {formatINR(amount)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </Card>
    </div>
  );
}
