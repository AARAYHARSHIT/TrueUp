interface BadgeProps {
  variant: "green" | "amber" | "red" | "blue" | "muted";
  children: React.ReactNode;
  className?: string;
}

const variants = {
  green: "bg-green-dim text-green border-green/30",
  amber: "bg-amber-dim text-amber border-amber/30",
  red: "bg-red-dim text-red border-red/30",
  blue: "bg-blue-dim text-blue border-blue/30",
  muted: "bg-card text-muted border-border",
};

export function Badge({ variant, children, className = "" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${variants[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
