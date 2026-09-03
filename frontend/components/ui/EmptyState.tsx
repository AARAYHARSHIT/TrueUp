import { FileSearch } from "lucide-react";

export function EmptyState({
  title = "No data available",
  description = "There is nothing to display right now.",
}: {
  title?: string;
  description?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <FileSearch className="h-12 w-12 text-muted mb-4" strokeWidth={1} />
      <h3 className="text-lg font-medium text-foreground">{title}</h3>
      <p className="mt-1 text-sm text-muted max-w-sm">{description}</p>
    </div>
  );
}
