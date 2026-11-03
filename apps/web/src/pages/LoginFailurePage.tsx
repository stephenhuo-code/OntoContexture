import { IdentityLayout, PageState } from "@contexture/ui";
import { Link, useSearchParams } from "react-router";
import { loginUrl, safeReturnTo } from "../api";
import { zh } from "../i18n/zh-CN";
export function LoginFailurePage() {
  const [params] = useSearchParams();
  const reason = params.get("reason");
  const message =
    reason === "cancelled"
      ? zh.failure.cancelled
      : reason === "unavailable"
        ? zh.failure.unavailable
        : reason === "internal"
          ? zh.failure.internal
          : zh.failure.invalid_response;
  return (
    <IdentityLayout copy={zh.identity} state>
      <PageState
        kind="error"
        title={message.title}
        description={message.description}
        traceId={params.get("trace_id") ?? undefined}
      />
      <div className="recovery-actions">
        <a
          className="ctx-button ctx-button--primary"
          href={loginUrl(safeReturnTo(params.get("return_to")))}
        >
          {zh.relogin}
        </a>
        <Link className="ctx-button ctx-button--secondary" to="/home">
          {zh.home}
        </Link>
      </div>
    </IdentityLayout>
  );
}
