import { IdentityLayout, PageState } from "@contexture/ui";
import type { ReactNode } from "react";
import { useLocation } from "react-router";
import { LoginPage } from "../pages/LoginPage";
import { zh } from "../i18n/zh-CN";
import { useSession } from "./SessionProvider";
export function SessionBoundary({ children }: { children: ReactNode }) {
  const session = useSession();
  const location = useLocation();
  const { state } = session;
  if (state.status === "authenticated") return <>{children}</>;
  if (state.status === "checking")
    return (
      <IdentityLayout copy={zh.identity} state>
        <PageState kind="loading" title={zh.session.checking} />
      </IdentityLayout>
    );
  if (state.status === "anonymous")
    return <LoginPage returnTo={location.pathname + location.search} />;
  if (state.status === "unavailable")
    return (
      <IdentityLayout copy={zh.identity} state>
        <PageState
          kind="error"
          title={zh.session.unavailable}
          description={zh.session.unavailableDescription}
          actionLabel={zh.session.retry}
          action={session.recheck}
          traceId={state.error.error.trace_id}
        />
      </IdentityLayout>
    );
  return (
    <IdentityLayout copy={zh.identity} state>
      <PageState
        kind="forbidden"
        title={zh.session.forbidden}
        description={zh.session.forbiddenDescription}
        actionLabel={zh.session.logout}
        action={() => void session.logout()}
        busy={session.logoutPending}
      />
      {session.logoutError && <p role="alert">{zh.session.logoutFailure}</p>}
    </IdentityLayout>
  );
}
