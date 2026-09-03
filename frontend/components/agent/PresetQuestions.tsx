"use client";

import {
  BarChart3,
  AlertTriangle,
  Search,
  Banknote,
  TrendingUp,
  GitMerge,
} from "lucide-react";

interface PresetQuestionsProps {
  onSelect: (question: string) => void;
  disabled?: boolean;
}

const presets = [
  {
    question: "What is the final match rate?",
    label: "Match rate",
    icon: BarChart3,
  },
  {
    question: "How many exceptions are there?",
    label: "Exceptions",
    icon: AlertTriangle,
  },
  {
    question: "Why did ORD-10071 fail?",
    label: "ORD-10071",
    icon: Search,
  },
  {
    question: "How much cash is unreconciled?",
    label: "Cash position",
    icon: Banknote,
  },
  {
    question: "What is the 14-day forecast?",
    label: "Forecast",
    icon: TrendingUp,
  },
  {
    question: "What improved after fuzzy matching?",
    label: "Fuzzy improvement",
    icon: GitMerge,
  },
];

export function PresetQuestions({ onSelect, disabled }: PresetQuestionsProps) {
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted">Quick questions</p>
      <div className="flex flex-wrap gap-2">
        {presets.map((preset) => {
          const Icon = preset.icon;
          return (
            <button
              key={preset.question}
              onClick={() => onSelect(preset.question)}
              disabled={disabled}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border bg-card text-xs text-muted hover:text-foreground hover:bg-card-hover hover:border-blue/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Icon className="h-3.5 w-3.5" strokeWidth={1.5} />
              {preset.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
