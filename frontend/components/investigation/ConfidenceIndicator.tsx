"use client";

interface ConfidenceIndicatorProps {
  confidence: number;
  showLabel?: boolean;
}

function getConfidenceLevel(confidence: number): {
  label: string;
  color: string;
  bgColor: string;
  percentage: number;
} {
  if (confidence >= 0.8) {
    return {
      label: "High",
      color: "text-green",
      bgColor: "bg-green",
      percentage: confidence * 100,
    };
  }
  if (confidence >= 0.5) {
    return {
      label: "Review",
      color: "text-amber",
      bgColor: "bg-amber",
      percentage: confidence * 100,
    };
  }
  return {
    label: "Low",
    color: "text-red",
    bgColor: "bg-red",
    percentage: confidence * 100,
  };
}

export function ConfidenceIndicator({
  confidence,
  showLabel = true,
}: ConfidenceIndicatorProps) {
  const level = getConfidenceLevel(confidence);

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <div className="flex-1 h-1.5 rounded-full bg-border overflow-hidden">
          <div
            className={`h-full rounded-full ${level.bgColor} transition-all`}
            style={{ width: `${level.percentage}%` }}
          />
        </div>
        <span className={`text-sm font-mono tabular-nums ${level.color}`}>
          {level.percentage.toFixed(1)}%
        </span>
      </div>
      {showLabel && (
        <span className={`text-xs ${level.color}`}>{level.label}</span>
      )}
    </div>
  );
}
