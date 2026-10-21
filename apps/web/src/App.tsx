import type { Me } from "@contexture/ts-api";
import { useEffect, useState } from "react";
import { Link, Navigate, Route, Routes } from "react-router";

import { bff, login, logout } from "./api";
import { ObjectsPage } from "./pages/ObjectsPage";

type Session =
  | { status: "loading" }
  | { status: "anonymous" }
  | { status: "signed-in"; me: Me };

export function App() {
  const [session, setSession] = useState<Session>({ status: "loading" });

  useEffect(() => {
    bff
      .GET("/bff/v1/me")
      .then(({ data }) =>
        setSession(
          data ? { status: "signed-in", me: data } : { status: "anonymous" },
        ),
      )
      .catch(() => setSession({ status: "anonymous" }));
  }, []);

  return (
    <div className="shell">
      <header>
        <Link to="/" className="brand">
          织境
        </Link>
        {session.status === "signed-in" && (
          <span className="user">
            {session.me.display_name ?? session.me.user_id}
            <span className="muted"> · 租户 {session.me.tenant_id}</span>
            <button type="button" onClick={() => void logout()}>
              退出
            </button>
          </span>
        )}
      </header>
      <main>
        {session.status === "loading" && <p className="muted">加载中…</p>}
        {session.status === "anonymous" && (
          <section className="login">
            <h1>织境 OntoContexture</h1>
            <p>请使用企业账号登录。</p>
            <button type="button" onClick={() => login()}>
              登录
            </button>
          </section>
        )}
        {session.status === "signed-in" && (
          <Routes>
            <Route
              path="/"
              element={<Navigate to="/objects/equipment" replace />}
            />
            <Route path="/objects/:typeKey" element={<ObjectsPage />} />
          </Routes>
        )}
      </main>
    </div>
  );
}
