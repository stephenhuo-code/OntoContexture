import type { HTMLAttributes } from "react";
export interface StatusBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: "neutral" | "positive" | "warning";
}
export function StatusBadge({
  tone = "neutral",
  className = "",
  children,
  ...props
}: StatusBadgeProps) {
  return (
    <span {...props} className={`ctx-badge ctx-badge--${tone} ${className}`}>
      {children}
    </span>
  );
}
