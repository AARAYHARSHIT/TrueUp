export function LoadingSkeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`animate-pulse space-y-3 ${className}`}>
      <div className="h-4 w-1/3 rounded bg-border" />
      <div className="h-8 w-1/2 rounded bg-border" />
      <div className="h-3 w-2/3 rounded bg-border" />
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="rounded-lg border border-border bg-card p-5 animate-pulse">
      <div className="h-3 w-20 rounded bg-border mb-3" />
      <div className="h-8 w-32 rounded bg-border mb-2" />
      <div className="h-3 w-24 rounded bg-border" />
    </div>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2 animate-pulse">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-10 rounded bg-border" />
      ))}
    </div>
  );
}
