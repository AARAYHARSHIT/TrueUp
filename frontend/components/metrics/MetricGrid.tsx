"use client";

import { Card } from "@/components/ui/Card";
import { formatINR, formatNumber } from "@/lib/formatters";
import { motion } from "motion/react";
import {
  TrendingUp,
  AlertTriangle,
  Banknote,
  BarChart3,
} from "lucide-react";

interface KpiCardProps {
  label: string;
  value: string;
  sublabel?: string;
  icon: React.ReactNode;
  color?: "green" | "amber" | "red" | "blue";
}

const colorMap = {
  green: "text-green",
  amber: "text-amber",
  red: "text-red",
  blue: "text-blue",
};

export function KpiCard({
  label,
  value,
  sublabel,
  icon,
  color = "blue",
}: KpiCardProps) {
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-xs text-muted font-medium uppercase tracking-wider">
            {label}
          </p>
          <p className={`text-2xl font-semibold tabular-nums ${colorMap[color]}`}>
            {value}
          </p>
          {sublabel && <p className="text-xs text-muted">{sublabel}</p>}
        </div>
        <div className={`p-2 rounded-md bg-${color}-dim`}>{icon}</div>
      </div>
    </Card>
  );
}

export function MetricGrid({
  gatewayTotal,
  exceptionsTotal,
  cashUnreconciled,
  forecastTotal,
}: {
  gatewayTotal: number;
  exceptionsTotal: number;
  cashUnreconciled: string;
  forecastTotal: string;
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <KpiCard
          label="Processed Records"
          value={formatNumber(gatewayTotal)}
          sublabel="Gateway transactions"
          icon={<BarChart3 className="h-4 w-4 text-blue" />}
          color="blue"
        />
      </motion.div>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
      >
        <KpiCard
          label="Exceptions"
          value={formatNumber(exceptionsTotal)}
          sublabel="Across 9 event types"
          icon={<AlertTriangle className="h-4 w-4 text-amber" />}
          color="amber"
        />
      </motion.div>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <KpiCard
          label="Unreconciled Cash"
          value={formatINR(cashUnreconciled)}
          sublabel="Total exposure"
          icon={<Banknote className="h-4 w-4 text-red" />}
          color="red"
        />
      </motion.div>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
      >
        <KpiCard
          label="14-Day Forecast"
          value={formatINR(forecastTotal)}
          sublabel="Projected inflows"
          icon={<TrendingUp className="h-4 w-4 text-green" />}
          color="green"
        />
      </motion.div>
    </div>
  );
}
