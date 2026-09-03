interface CardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
}

export function Card({ children, className = "", hover = false }: CardProps) {
  return (
    <div
      className={`rounded-lg border border-border bg-card p-5 ${
        hover ? "transition-colors hover:bg-card-hover cursor-pointer" : ""
      } ${className}`}
    >
      {children}
    </div>
  );
}
