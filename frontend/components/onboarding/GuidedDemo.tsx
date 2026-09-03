"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  ChevronLeft,
  ChevronRight,
  GitMerge,
  AlertTriangle,
  TrendingUp,
  Bot,
  BarChart3,
} from "lucide-react";
import { useSummary } from "@/hooks/useSummary";
import { useExceptions } from "@/hooks/useExceptions";
import { useTransaction } from "@/hooks/useTransaction";
import { useHealth } from "@/hooks/useHealth";
import { MatchRateHero } from "@/components/metrics/MatchRateHero";
import { WaterfallChart } from "@/components/pipeline/WaterfallChart";
import { CardSkeleton } from "@/components/ui/LoadingSkeleton";

interface GuidedDemoProps {
  onComplete: () => void;
  onSkip: () => void;
}

const steps = [
  {
    id: "problem",
    title: "The Problem",
    subtitle: "Three sources disagree",
    icon: AlertTriangle,
    description:
      "In real finance, your gateway, bank, and merchant ledger often disagree. TrueUp reconciles all three automatically.",
  },
  {
    id: "pipeline",
    title: "The Pipeline",
    subtitle: "Deterministic → Fuzzy → Classify → LLM → Report",
    icon: GitMerge,
    description:
      "Five passes transform messy data into clean insights. Each pass adds precision without hiding exceptions.",
  },
  {
    id: "results",
    title: "The Results",
    subtitle: "73.75% → 87.50%",
    icon: TrendingUp,
    description:
      "Deterministic matching catches the easy cases. Fuzzy matching recovers 11 more records. Every exception is classified.",
  },
  {
    id: "investigation",
    title: "Investigation",
    subtitle: "Open ORD-10071",
    icon: BarChart3,
    description:
      "Click any exception to see full evidence: timeline, source comparison, match details, and AI involvement.",
  },
  {
    id: "ai",
    title: "AI Controller",
    subtitle: "Ask why it failed",
    icon: Bot,
    description:
      "Ask natural language questions. The AI uses 6 tools to query real data—never making up answers.",
  },
];

export function GuidedDemo({ onComplete, onSkip }: GuidedDemoProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [isReducedMotion, setIsReducedMotion] = useState(false);

  const summary = useSummary();
  const exceptions = useExceptions();
  const transaction = useTransaction("ORD-10071");

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updateMotionPreference = () => setIsReducedMotion(mq.matches);
    updateMotionPreference();
    mq.addEventListener("change", updateMotionPreference);
    return () => mq.removeEventListener("change", updateMotionPreference);
  }, []);

  const goNext = useCallback(() => {
    if (currentStep < steps.length - 1) {
      setCurrentStep((s) => s + 1);
    } else {
      onComplete();
    }
  }, [currentStep, onComplete]);

  const goPrev = useCallback(() => {
    if (currentStep > 0) {
      setCurrentStep((s) => s - 1);
    }
  }, [currentStep]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === " ") {
        e.preventDefault();
        goNext();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        goPrev();
      } else if (e.key === "Escape") {
        onSkip();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [goNext, goPrev, onSkip]);

  const step = steps[currentStep];
  const Icon = step.icon;

  const renderStepContent = () => {
    if (summary.isLoading || exceptions.isLoading || transaction.isLoading) {
      return (
        <div className="space-y-4">
          <CardSkeleton />
          <CardSkeleton />
        </div>
      );
    }

    switch (step.id) {
      case "problem":
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="rounded-lg border border-border bg-card p-4">
                <p className="text-xs text-muted mb-1">Gateway</p>
                <p className="text-2xl font-bold text-foreground">
                  {summary.data?.gateway_total || 80}
                </p>
                <p className="text-xs text-muted">records</p>
              </div>
              <div className="rounded-lg border border-border bg-card p-4">
                <p className="text-xs text-muted mb-1">Bank</p>
                <p className="text-2xl font-bold text-foreground">
                  {summary.data?.bank_total || 75}
                </p>
                <p className="text-xs text-muted">records</p>
              </div>
              <div className="rounded-lg border border-border bg-card p-4">
                <p className="text-xs text-muted mb-1">Ledger</p>
                <p className="text-2xl font-bold text-foreground">
                  {summary.data?.ledger_total || 78}
                </p>
                <p className="text-xs text-muted">records</p>
              </div>
            </div>
            <p className="text-sm text-center text-muted">
              Different counts mean different stories. TrueUp finds the truth.
            </p>
          </div>
        );

      case "pipeline":
        return (
          <div className="space-y-4">
            <WaterfallChart
              deterministic={summary.data?.deterministic_pass.matched || 59}
              fuzzyAdditional={summary.data?.fuzzy_pass.additional_matched || 11}
              exceptions={summary.data?.unmatched.exceptions_total || 10}
              total={summary.data?.gateway_total || 80}
            />
            <div className="flex justify-center gap-6 text-xs text-muted">
              <span>Pass 1: Exact</span>
              <span>Pass 2: Fuzzy</span>
              <span>Pass 3: Classify</span>
              <span>Pass 4: LLM</span>
              <span>Pass 5: Report</span>
            </div>
          </div>
        );

      case "results":
        return (
          <div className="space-y-4">
            <MatchRateHero
              deterministicRate={
                summary.data?.deterministic_pass.rate || "73.75%"
              }
              finalRate={summary.data?.final.rate || "87.50%"}
              improvement={summary.data?.improvement_pp || "+13.75pp"}
            />
            <p className="text-sm text-center text-muted">
              Every exception is classified into one of 9 named types.
            </p>
          </div>
        );

      case "investigation":
        const txData = transaction.data;
        const isException =
          txData && "exception_id" in txData;
        return (
          <div className="space-y-4">
            <div className="rounded-lg border border-border bg-card p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-mono font-medium text-foreground">
                  ORD-10071
                </span>
                <span
                  className={`px-2 py-0.5 rounded text-xs font-medium ${
                    isException
                      ? "bg-red-dim text-red"
                      : "bg-green-dim text-green"
                  }`}
                >
                  {isException ? "EXCEPTION" : "MATCHED"}
                </span>
              </div>
              {isException && txData && (
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted">Type</span>
                    <span className="text-foreground">
                      {txData.exception_type}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Reason</span>
                    <span className="text-foreground text-right max-w-[200px]">
                      {txData.reason}
                    </span>
                  </div>
                </div>
              )}
            </div>
            <p className="text-sm text-center text-muted">
              Click any record ID to see full evidence and source comparison.
            </p>
          </div>
        );

      case "ai":
        return (
          <div className="space-y-4">
            <div className="rounded-lg border border-border bg-card p-4">
              <div className="flex items-center gap-2 mb-3">
                <Bot className="h-4 w-4 text-blue" />
                <span className="text-sm font-medium text-foreground">
                  AI Controller
                </span>
              </div>
              <div className="space-y-2">
                <div className="rounded bg-background p-3 text-sm text-foreground">
                  Why did ORD-10071 fail reconciliation?
                </div>
                <div className="rounded bg-card-hover p-3 text-sm text-foreground/80">
                  ORD-10071 has a MISSING_SETTLEMENT exception. The gateway
                  recorded the transaction, but no corresponding bank settlement
                  was found. This could indicate a delayed settlement or a
                  failed payment.
                </div>
              </div>
            </div>
            <p className="text-sm text-center text-muted">
              Ask any question. The AI uses 6 tools to query real data.
            </p>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-background">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold tracking-wide text-foreground">
            TRUEUP
          </span>
          <span className="text-xs text-muted">Guided Demo</span>
        </div>
        <button
          onClick={onSkip}
          className="text-xs text-muted hover:text-foreground transition-colors"
        >
          Skip tour (Esc)
        </button>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-border">
        <motion.div
          className="h-full bg-amber"
          initial={false}
          animate={{
            width: `${((currentStep + 1) / steps.length) * 100}%`,
          }}
          transition={{ duration: isReducedMotion ? 0 : 0.3 }}
        />
      </div>

      {/* Content */}
      <div className="flex-1 flex items-center justify-center p-6 overflow-auto">
        <div className="max-w-2xl w-full">
          {/* Step indicator */}
          <div className="flex items-center justify-center gap-2 mb-6">
            {steps.map((s, i) => (
              <div
                key={s.id}
                className={`h-2 rounded-full transition-all duration-200 ${
                  i === currentStep
                    ? "w-8 bg-amber"
                    : i < currentStep
                    ? "w-2 bg-amber/50"
                    : "w-2 bg-border"
                }`}
              />
            ))}
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={step.id}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: isReducedMotion ? 0 : 0.3 }}
            >
              {/* Step header */}
              <div className="flex items-center gap-3 mb-2">
                <div className="flex items-center justify-center h-10 w-10 rounded-lg bg-amber-dim">
                  <Icon className="h-5 w-5 text-amber" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-foreground">
                    {step.title}
                  </h2>
                  <p className="text-sm text-muted">{step.subtitle}</p>
                </div>
              </div>

              <p className="text-sm text-foreground/70 mb-6 ml-13">
                {step.description}
              </p>

              {/* Step content */}
              <div className="ml-13">{renderStepContent()}</div>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-6 py-4 border-t border-border">
        <button
          onClick={goPrev}
          disabled={currentStep === 0}
          className="inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm text-muted hover:text-foreground hover:bg-card-hover transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <ChevronLeft className="h-4 w-4" />
          Previous
        </button>

        <span className="text-xs text-muted tabular-nums">
          {currentStep + 1} / {steps.length}
        </span>

        <button
          onClick={goNext}
          className="inline-flex items-center gap-2 rounded-md bg-amber px-4 py-2 text-sm font-medium text-background hover:opacity-90 transition-opacity"
        >
          {currentStep === steps.length - 1 ? "Finish" : "Next"}
          {currentStep < steps.length - 1 && (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>
      </div>
    </div>
  );
}
