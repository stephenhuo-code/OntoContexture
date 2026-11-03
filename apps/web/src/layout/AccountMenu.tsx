import { Button, Tooltip } from "@contexture/ui";
import { useSession } from "../auth/SessionProvider";
import { zh } from "../i18n/zh-CN";
export function AccountMenu() {
  const session = useSession();
  if (session.state.status !== "authenticated") return null;
  const user = session.state.user;
  const name = user.display_name || user.user_id;
  const roles = user.roles.filter((role) => Object.hasOwn(zh.roles, role));
  return (
    <div className="account-menu">
      <details className="account-dropdown">
        <Tooltip
          content={
            <>
              <strong>{name}</strong>
              <br />
              {user.user_id}
            </>
          }
        >
          <summary
            className="account-identity"
            aria-label={zh.currentAccount(name, user.user_id)}
          >
            <span className="account-avatar" aria-hidden="true">
              {name.slice(0, 1)}
            </span>
            <span className="account-name">{name}</span>
          </summary>
        </Tooltip>
        <div className="account-facts">
          <strong>{name}</strong>
          <p>
            {zh.userId}：{user.user_id}
          </p>
          <p>
            {zh.tenant}：{user.tenant_id}
          </p>
        </div>
      </details>
      {roles.length > 0 && (
        <span className="account-roles">
          {roles.map((role) => zh.roles[role]).join(" · ")}
        </span>
      )}
      <Button
        variant="ghost"
        busy={session.logoutPending}
        onClick={() => void session.logout()}
      >
        {zh.session.logout}
      </Button>
      {session.logoutError && (
        <span role="alert">{zh.session.logoutFailure}</span>
      )}
    </div>
  );
}
