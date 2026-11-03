import { IdentityHelp, IdentityLayout } from "@contexture/ui";
import { login } from "../api";
import { zh } from "../i18n/zh-CN";

export function LoginPage({ returnTo }: { returnTo: string }) {
  const copy = zh.identity;
  return (
    <IdentityLayout copy={copy}>
      <p className="oc-kicker">WELCOME TO ONTOCONTEXTURE</p>
      <h2 className="oc-title">{copy.welcome}</h2>
      <p className="oc-card-description">{copy.welcomeDescription}</p>
      <div className="oc-account">
        <span className="oc-account-icon" aria-hidden="true">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
          >
            <path d="M5 21V4h14v17M3 21h18M9 7h1m4 0h1M9 11h1m4 0h1M9 15h1m4 0h1M10 21v-3h4v3" />
          </svg>
        </span>
        <div>
          <div className="oc-account-title">{copy.enterpriseAccount}</div>
          <div className="oc-account-description">
            {copy.accountDescription}
          </div>
        </div>
      </div>
      <button
        type="button"
        className="oc-submit"
        onClick={() => login(returnTo)}
      >
        {copy.signIn}
        <svg
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          aria-hidden="true"
        >
          <path d="M3 10h13m-5-5 5 5-5 5" />
        </svg>
      </button>
      <p className="oc-note">{copy.redirectNote}</p>
      <div className="oc-assist">
        <span>{copy.assistance}</span>
        <IdentityHelp copy={copy} />
      </div>
    </IdentityLayout>
  );
}
