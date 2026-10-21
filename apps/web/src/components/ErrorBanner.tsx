import type { ApiError } from "@contexture/ts-api";

export function ErrorBanner({ error }: { error: ApiError }) {
  return (
    <div role="alert" className="error">
      <strong>{error.message}</strong>
      <span className="muted">
        错误码 <code>{error.code}</code>
        {error.trace_id && (
          <>
            {" "}
            · trace <code>{error.trace_id}</code>
          </>
        )}
      </span>
    </div>
  );
}
