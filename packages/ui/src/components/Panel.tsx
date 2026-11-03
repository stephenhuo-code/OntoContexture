import type { HTMLAttributes } from "react";
export function Panel({
  title,
  children,
  className = "",
  ...props
}: HTMLAttributes<HTMLElement>) {
  return (
    <section {...props} className={`ctx-panel ${className}`}>
      {title && <h2 className="ctx-panel-title">{title}</h2>}
      {children}
    </section>
  );
}
