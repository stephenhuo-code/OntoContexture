import { Button } from "./Button";

export type PageStateKind =
  "loading" | "empty" | "error" | "forbidden" | "not_open" | "not_found";
export interface PageStateProps {
  kind: PageStateKind;
  title: string;
  description?: string;
  actionLabel?: string;
  action?: () => void;
  busy?: boolean;
  traceId?: string;
}
export function PageState({
  kind,
  title,
  description,
  actionLabel,
  action,
  busy = false,
  traceId,
}: PageStateProps) {
  const pending = busy || kind === "loading";
  const safeTrace =
    traceId && /^[a-f0-9]{32}$/i.test(traceId) ? traceId : undefined;
  return (
    <section
      className="ctx-page-state"
      data-state={kind}
      role={kind === "error" ? "alert" : "status"}
      aria-busy={pending}
    >
      {kind === "loading" && (
        <span className="ctx-spinner" aria-hidden="true" />
      )}
      <h2>{title}</h2>
      {description && <p>{description}</p>}
      {action && actionLabel && (
        <Button
          onClick={action}
          busy={pending}
          variant={kind === "error" ? "primary" : "secondary"}
        >
          {actionLabel}
        </Button>
      )}
      {safeTrace && <small>诊断编号：{safeTrace}</small>}
    </section>
  );
}
