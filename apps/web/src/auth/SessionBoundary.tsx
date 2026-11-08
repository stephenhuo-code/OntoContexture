import { IdentityLayout, PageState } from "@contexture/ui";
import { useEffect, useRef, type ReactNode } from "react";
import { useLocation } from "react-router";
import { LoginPage } from "../pages/LoginPage";
import { zh } from "../i18n/zh-CN";
import { useSession } from "./SessionProvider";
export function SessionBoundary({ children }: { children: ReactNode }) {
  const session = useSession();
  const location = useLocation();
  const { state } = session;
  if (state.status === "authenticated")
    return (
      // 按用户挂载：核验后换了用户时丢弃上一用户的页面状态
      <RecheckGate key={state.user.user_id} rechecking={state.rechecking}>
        {children}
      </RecheckGate>
    );
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

/** 后台核验身份期间页面保留但不可操作（inert），并提示正在确认身份 */
function RecheckGate({
  rechecking,
  children,
}: {
  rechecking: boolean;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.toggleAttribute("inert", rechecking);
  }, [rechecking]);
  return (
    <>
      <div
        ref={ref}
        className="session-content"
        aria-busy={rechecking || undefined}
      >
        {children}
      </div>
      {rechecking && (
        <div
          role="status"
          aria-label={zh.session.checking}
          className="session-rechecking"
        >
          {zh.session.checking}
        </div>
      )}
    </>
  );
}
