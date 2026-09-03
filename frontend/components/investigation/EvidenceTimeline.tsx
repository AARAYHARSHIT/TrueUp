"use client";

import type {
  TransactionMatchedResponse,
  TransactionExceptionResponse,
} from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import {
  Building2,
  Landmark,
  BookOpen,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Search,
  Brain,
} from "lucide-react";

interface EvidenceTimelineProps {
  data: TransactionMatchedResponse | TransactionExceptionResponse;
}

const steps = [
  { key: "gateway", label: "Gateway", icon: Building2 },
  { key: "bank", label: "Bank", icon: Landmark },
  { key: "ledger", label: "Ledger", icon: BookOpen },
  { key: "pass1", label: "Pass 1", icon: CheckCircle2, sub: "Deterministic" },
  { key: "pass2", label: "Pass 2", icon: Search, sub: "Fuzzy" },
  { key: "pass3", label: "Pass 3", icon: AlertTriangle, sub: "Classify" },
  { key: "pass4", label: "Pass 4", icon: Brain, sub: "LLM" },
];

function getStepStatus(
  data: TransactionMatchedResponse | TransactionExceptionResponse,
  stepKey: string
): "complete" | "active" | "failed" | "skipped" {
  if (data.status === "EXCEPTION") {
    const exc = data as TransactionExceptionResponse;
    if (stepKey === "gateway") return "complete";
    if (stepKey === "bank") return exc.source === "bank" ? "complete" : "skipped";
    if (stepKey === "ledger") return exc.source === "ledger" ? "complete" : "skipped";
    if (stepKey === "pass1") return "failed";
    if (stepKey === "pass2") return "failed";
    if (stepKey === "pass3") return "active";
    if (stepKey === "pass4") return "skipped";
  }

  const matched = data as TransactionMatchedResponse;
  if (stepKey === "gateway") return "complete";
  if (stepKey === "bank") return matched.bank_settlement ? "complete" : "skipped";
  if (stepKey === "ledger") return matched.merchant_ledger ? "complete" : "skipped";

  const passNum = parseInt(stepKey.replace("pass", ""));
  const matchedPass = matched.match_pass === "deterministic" ? 1 : 2;
  if (passNum < matchedPass) return "complete";
  if (passNum === matchedPass) return "active";
  return "skipped";
}

const statusStyles = {
  complete: "border-green bg-green-dim text-green",
  active: "border-blue bg-blue-dim text-blue",
  failed: "border-red bg-red-dim text-red",
  skipped: "border-border bg-card text-muted opacity-40",
};

const connectorStyles = {
  complete: "bg-green",
  active: "bg-blue",
  failed: "bg-red",
  skipped: "bg-border opacity-40",
};

export function EvidenceTimeline({ data }: EvidenceTimelineProps) {
  return (
    <Card>
      <h3 className="text-xs text-muted uppercase tracking-wider mb-4">
        Evidence Timeline
      </h3>
      <div className="flex items-center gap-1 overflow-x-auto pb-2">
        {steps.map((step, i) => {
          const status = getStepStatus(data, step.key);
          const Icon = step.icon;
          return (
            <div key={step.key} className="flex items-center">
              <div className="flex flex-col items-center gap-1 min-w-[60px]">
                <div
                  className={`flex items-center justify-center w-9 h-9 rounded-full border ${statusStyles[status]}`}
                >
                  <Icon className="h-4 w-4" strokeWidth={1.5} />
                </div>
                <span className="text-[10px] text-muted whitespace-nowrap">
                  {step.label}
                </span>
                {step.sub && (
                  <span className="text-[9px] text-muted/60 whitespace-nowrap">
                    {step.sub}
                  </span>
                )}
              </div>
              {i < steps.length - 1 && (
                <div
                  className={`w-6 h-0.5 mx-1 rounded ${connectorStyles[status]}`}
                />
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-3 flex items-center gap-4 text-[10px] text-muted">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-green" /> Complete
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-blue" /> Active
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-red" /> Failed
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-border" /> Skipped
        </span>
      </div>
    </Card>
  );
}
