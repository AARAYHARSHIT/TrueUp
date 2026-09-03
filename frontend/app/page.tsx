"use client";

import { useState } from "react";
import { useSummary } from "@/hooks/useSummary";
import { useExceptions } from "@/hooks/useExceptions";
import { useCashPosition } from "@/hooks/useCashPosition";
import { useForecast } from "@/hooks/useForecast";
import { useRunDemo } from "@/hooks/useRunDemo";
import { useOnboarding } from "@/components/onboarding/OnboardingProvider";
import { MatchRateHero } from "@/components/metrics/MatchRateHero";
import { MetricGrid } from "@/components/metrics/MetricGrid";
import { WaterfallChart } from "@/components/pipeline/WaterfallChart";
import { SplitBatchProof } from "@/components/pipeline/SplitBatchCard";
import { ExceptionPreview } from "@/components/exceptions/ExceptionPreview";
import { CardSkeleton } from "@/components/ui/LoadingSkeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { WelcomeScreen } from "@/components/onboarding/WelcomeScreen";
import { GuidedDemo } from "@/components/onboarding/GuidedDemo";
import { PresentationMode } from "@/components/presentation/PresentationMode";

export default function DashboardPage() {
  const [showGuidedDemo, setShowGuidedDemo] = useState(false);
  const [showPresentation, setShowPresentation] = useState(false);

  const { showOnboarding, setShowOnboarding, setHasCompletedOnboarding } =
    useOnboarding();

  const summary = useSummary();
  const exceptions = useExceptions();
  const cash = useCashPosition();
  const forecast = useForecast();
  const runDemo = useRunDemo();

  const isLoading =
    summary.isLoading || exceptions.isLoading || cash.isLoading || forecast.isLoading;
  const error =
    summary.error || exceptions.error || cash.error || forecast.error;

  const handleStartDemo = async () => {
    setShowOnboarding(false);
    try {
      await runDemo.mutateAsync();
      setShowGuidedDemo(true);
    } catch (err) {
      console.error("Demo run failed:", err);
      setShowGuidedDemo(true);
    }
  };

  const handleExploreDashboard = () => {
    setHasCompletedOnboarding(true);
  };

  const handleGuidedDemoComplete = () => {
    setShowGuidedDemo(false);
    setHasCompletedOnboarding(true);
  };

  const handleGuidedDemoSkip = () => {
    setShowGuidedDemo(false);
    setHasCompletedOnboarding(true);
  };

  if (showOnboarding) {
    return (
      <WelcomeScreen
        onStartDemo={handleStartDemo}
        isStarting={runDemo.isPending}
      />
    );
  }

  if (showGuidedDemo) {
    return (
      <GuidedDemo
        onComplete={handleGuidedDemoComplete}
        onSkip={handleGuidedDemoSkip}
      />
    );
  }

  if (showPresentation) {
    return <PresentationMode onClose={() => setShowPresentation(false)} />;
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <CardSkeleton />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
        <CardSkeleton />
      </div>
    );
  }

  if (error) {
    return (
      <ErrorState
        message="Failed to load dashboard data. Is the API server running on port 8000?"
        onRetry={() => {
          summary.refetch();
          exceptions.refetch();
          cash.refetch();
          forecast.refetch();
        }}
      />
    );
  }

  const s = summary.data!;
  const ex = exceptions.data!;
  const c = cash.data!;
  const f = forecast.data!;

  return (
    <div className="space-y-6 max-w-7xl">
      <div className="flex items-center justify-between">
        <MatchRateHero
          deterministicRate={s.deterministic_pass.rate}
          finalRate={s.final.rate}
          improvement={s.improvement_pp}
        />
        <button
          onClick={() => setShowPresentation(true)}
          className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-4 py-2 text-sm text-foreground hover:bg-card-hover transition-colors"
        >
          Presentation Mode
        </button>
      </div>

      <MetricGrid
        gatewayTotal={s.gateway_total}
        exceptionsTotal={s.unmatched.exceptions_total}
        cashUnreconciled={c.total_unreconciled_inr}
        forecastTotal={f.total_forecast_inr}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <WaterfallChart
          deterministic={s.deterministic_pass.matched}
          fuzzyAdditional={s.fuzzy_pass.additional_matched}
          exceptions={s.unmatched.exceptions_total}
          total={s.gateway_total}
        />
        <SplitBatchProof
          splitsDetected={s.fuzzy_pass.split_detected}
          batchesDetected={s.fuzzy_pass.batch_detected}
        />
      </div>

      <ExceptionPreview
        exceptions={ex.exceptions}
        total={ex.total}
      />
    </div>
  );
}
