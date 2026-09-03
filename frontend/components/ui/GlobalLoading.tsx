"use client";

import { Loader2 } from "lucide-react";

interface GlobalLoadingProps {
  message?: string;
}

export function GlobalLoading({ message = "Loading..." }: GlobalLoadingProps) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="h-8 w-8 text-amber animate-spin" />
        <p className="text-sm text-muted">{message}</p>
      </div>
    </div>
  );
}
