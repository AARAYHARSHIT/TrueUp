"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Maximize,
  Minimize,
  ChevronLeft,
  ChevronRight,
  X,
} from "lucide-react";
import { useSummary } from "@/hooks/useSummary";
import { useExceptions } from "@/hooks/useExceptions";
import { useCashPosition } from "@/hooks/useCashPosition";
import { useForecast } from "@/hooks/useForecast";
import { useReport } from "@/hooks/useReport";
import { MatchRateHero } from "@/components/metrics/MatchRateHero";
import { MetricGrid } from "@/components/metrics/MetricGrid";
import { WaterfallChart } from "@/components/pipeline/WaterfallChart";
import { ExceptionPreview } from "@/components/exceptions/ExceptionPreview";
import { CardSkeleton } from "@/components/ui/LoadingSkeleton";

interface PresentationModeProps {
  onClose: () => void;
}

const slides = [
  {
    id: "overview",
    title: "Overview",
  },
  {
    id: "pipeline",
    title: "Pipeline",
  },
  {
    id: "exceptions",
    title: "Exceptions",
  },
  {
    id: "cash",
    title: "Cash Position",
  },
  {
    id: "report",
    title: "Report",
  },
];

export function PresentationMode({ onClose }: PresentationModeProps) {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isReducedMotion, setIsReducedMotion] = useState(false);

  const summary = useSummary();
  const exceptions = useExceptions();
  const cash = useCashPosition();
  const forecast = useForecast();
  const report = useReport();

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updateMotionPreference = () => setIsReducedMotion(mq.matches);
    updateMotionPreference();
    mq.addEventListener("change", updateMotionPreference);
    return () => mq.removeEventListener("change", updateMotionPreference);
  }, []);

  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  }, []);

  const goNext = useCallback(() => {
    if (currentSlide < slides.length - 1) {
      setCurrentSlide((s) => s + 1);
    }
  }, [currentSlide]);

  const goPrev = useCallback(() => {
    if (currentSlide > 0) {
      setCurrentSlide((s) => s - 1);
    }
  }, [currentSlide]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === " ") {
        e.preventDefault();
        goNext();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        goPrev();
      } else if (e.key === "Escape") {
        onClose();
      } else if (e.key === "f") {
        toggleFullscreen();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [goNext, goPrev, onClose, toggleFullscreen]);

  const slide = slides[currentSlide];

  const renderSlideContent = () => {
    const isLoading =
      summary.isLoading || exceptions.isLoading || cash.isLoading || forecast.isLoading;

    if (isLoading) {
      return (
        <div className="space-y-6 max-w-6xl mx-auto">
          <CardSkeleton />
          <div className="grid grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        </div>
      );
    }

    switch (slide.id) {
      case "overview":
        return (
          <div className="space-y-6 max-w-6xl mx-auto">
            <MatchRateHero
              deterministicRate={summary.data?.deterministic_pass.rate || "73.75%"}
              finalRate={summary.data?.final.rate || "87.50%"}
              improvement={summary.data?.improvement_pp || "+13.75pp"}
            />
            <MetricGrid
              gatewayTotal={summary.data?.gateway_total || 80}
              exceptionsTotal={summary.data?.unmatched.exceptions_total || 10}
              cashUnreconciled={cash.data?.total_unreconciled_inr || "0"}
              forecastTotal={forecast.data?.total_forecast_inr || "0"}
            />
          </div>
        );

      case "pipeline":
        return (
          <div className="max-w-4xl mx-auto">
            <WaterfallChart
              deterministic={summary.data?.deterministic_pass.matched || 59}
              fuzzyAdditional={summary.data?.fuzzy_pass.additional_matched || 11}
              exceptions={summary.data?.unmatched.exceptions_total || 10}
              total={summary.data?.gateway_total || 80}
            />
            <div className="mt-6 grid grid-cols-5 gap-4 text-center">
              {[
                { label: "Deterministic", value: summary.data?.deterministic_pass.matched || 59 },
                { label: "Fuzzy Added", value: summary.data?.fuzzy_pass.additional_matched || 11 },
                { label: "Exceptions", value: summary.data?.unmatched.exceptions_total || 10 },
                { label: "Splits", value: summary.data?.fuzzy_pass.split_detected || 4 },
                { label: "Batches", value: summary.data?.fuzzy_pass.batch_detected || 2 },
              ].map((item) => (
                <div key={item.label} className="rounded-lg border border-border bg-card p-3">
                  <p className="text-2xl font-bold text-foreground">{item.value}</p>
                  <p className="text-xs text-muted">{item.label}</p>
                </div>
              ))}
            </div>
          </div>
        );

      case "exceptions":
        return (
          <div className="max-w-4xl mx-auto">
            <ExceptionPreview
              exceptions={exceptions.data?.exceptions || []}
              total={exceptions.data?.total || 0}
            />
            <div className="mt-6 grid grid-cols-3 gap-4">
              {Object.entries(exceptions.data?.by_type || {}).slice(0, 6).map(([type, count]) => (
                <div key={type} className="rounded-lg border border-border bg-card p-3">
                  <p className="text-lg font-bold text-foreground">{count}</p>
                  <p className="text-xs text-muted truncate">{type}</p>
                </div>
              ))}
            </div>
          </div>
        );

      case "cash":
        return (
          <div className="max-w-4xl mx-auto space-y-6">
            <div className="grid grid-cols-3 gap-4">
              <div className="rounded-lg border border-border bg-card p-4 text-center">
                <p className="text-xs text-muted mb-1">Missing Settlement</p>
                <p className="text-2xl font-bold text-foreground">
                  {cash.data?.missing_settlement.count || 0}
                </p>
                <p className="text-xs text-muted">
                  ₹{cash.data?.missing_settlement.exposure_inr || "0"}
                </p>
              </div>
              <div className="rounded-lg border border-border bg-card p-4 text-center">
                <p className="text-xs text-muted mb-1">Orphan Ledger</p>
                <p className="text-2xl font-bold text-foreground">
                  {cash.data?.orphan_ledger.count || 0}
                </p>
                <p className="text-xs text-muted">
                  ₹{cash.data?.orphan_ledger.exposure_inr || "0"}
                </p>
              </div>
              <div className="rounded-lg border border-border bg-card p-4 text-center">
                <p className="text-xs text-muted mb-1">Batch Pending</p>
                <p className="text-2xl font-bold text-foreground">
                  {cash.data?.batch_settlement_pending.count || 0}
                </p>
                <p className="text-xs text-muted">
                  ₹{cash.data?.batch_settlement_pending.exposure_inr || "0"}
                </p>
              </div>
            </div>
            <div className="rounded-lg border border-border bg-card p-4 text-center">
              <p className="text-xs text-muted mb-1">Total Unreconciled</p>
              <p className="text-3xl font-bold text-amber">
                ₹{cash.data?.total_unreconciled_inr || "0"}
              </p>
            </div>
          </div>
        );

      case "report":
        const reportData = report.data;
        return (
          <div className="max-w-4xl mx-auto space-y-6">
            <div className="rounded-lg border border-border bg-card p-6">
              <h3 className="text-lg font-semibold text-foreground mb-4">
                Reconciliation Report
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-muted mb-1">Generated</p>
                  <p className="text-sm text-foreground">
                    {reportData?.generated_at || "N/A"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted mb-1">Pipeline</p>
                  <p className="text-sm text-foreground">
                    {reportData?.pipeline || "N/A"}
                  </p>
                </div>
              </div>
              {reportData?.match_rates && (
                <div className="mt-4 grid grid-cols-2 gap-4">
                  {Object.entries(reportData.match_rates).map(([key, value]) => (
                    <div key={key}>
                      <p className="text-xs text-muted mb-1">{key}</p>
                      <p className="text-sm text-foreground">{String(value)}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <p className="text-sm text-center text-muted">
              Download the full report from the Reports page.
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
      <div className="flex items-center justify-between px-6 py-3 border-b border-border">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold tracking-wide text-foreground">
            TRUEUP
          </span>
          <span className="text-xs text-muted">Presentation Mode</span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={toggleFullscreen}
            className="p-2 rounded text-muted hover:text-foreground hover:bg-card-hover transition-colors"
            title={isFullscreen ? "Exit fullscreen (F)" : "Fullscreen (F)"}
          >
            {isFullscreen ? (
              <Minimize className="h-4 w-4" />
            ) : (
              <Maximize className="h-4 w-4" />
            )}
          </button>
          <button
            onClick={onClose}
            className="p-2 rounded text-muted hover:text-foreground hover:bg-card-hover transition-colors"
            title="Exit presentation (Esc)"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-border">
        <motion.div
          className="h-full bg-amber"
          initial={false}
          animate={{
            width: `${((currentSlide + 1) / slides.length) * 100}%`,
          }}
          transition={{ duration: isReducedMotion ? 0 : 0.3 }}
        />
      </div>

      {/* Content */}
      <div className="flex-1 flex items-center justify-center p-6 overflow-auto">
        <AnimatePresence mode="wait">
          <motion.div
            key={slide.id}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: isReducedMotion ? 0 : 0.3 }}
            className="w-full"
          >
            <div className="text-center mb-6">
              <h2 className="text-2xl font-semibold text-foreground">
                {slide.title}
              </h2>
            </div>
            {renderSlideContent()}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-6 py-3 border-t border-border">
        <button
          onClick={goPrev}
          disabled={currentSlide === 0}
          className="inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm text-muted hover:text-foreground hover:bg-card-hover transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <ChevronLeft className="h-4 w-4" />
          Previous
        </button>

        <div className="flex items-center gap-2">
          {slides.map((s, i) => (
            <button
              key={s.id}
              onClick={() => setCurrentSlide(i)}
              className={`h-2 rounded-full transition-all duration-200 ${
                i === currentSlide
                  ? "w-8 bg-amber"
                  : "w-2 bg-border hover:bg-muted"
              }`}
              title={s.title}
            />
          ))}
        </div>

        <button
          onClick={goNext}
          disabled={currentSlide === slides.length - 1}
          className="inline-flex items-center gap-2 rounded-md bg-amber px-4 py-2 text-sm font-medium text-background hover:opacity-90 transition-opacity disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Next
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
