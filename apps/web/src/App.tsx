import { Navigate, Route, Routes } from "react-router";
import { SessionProvider } from "./auth/SessionProvider";
import { SessionBoundary } from "./auth/SessionBoundary";
import { AppShell } from "./layout/AppShell";
import { uiExamplesEnabled } from "./layout/navigation";
import { HomePage } from "./pages/HomePage";
import { LoginFailurePage } from "./pages/LoginFailurePage";
import { ObjectsPage } from "./pages/ObjectsPage";
import { NotOpenPage } from "./pages/NotOpenPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { lazy, Suspense, useState } from "react";
import { PageState } from "@contexture/ui";
import { zh } from "./i18n/zh-CN";
const UiExamplesPage = uiExamplesEnabled
  ? lazy(() => import("./pages/UiExamplesPage"))
  : null;
function ProtectedShell() {
  // 非敏感的布局偏好在身份重新核验期间保留；刷新后此组件重新挂载。
  const [secondaryOpen, setSecondaryOpen] = useState(true);
  return (
    <SessionProvider>
      <SessionBoundary>
        <AppShell
          secondaryOpen={secondaryOpen}
          toggleSecondary={() => setSecondaryOpen((open) => !open)}
        />
      </SessionBoundary>
    </SessionProvider>
  );
}
export function App() {
  return (
    <Routes>
      <Route path="/auth/error" element={<LoginFailurePage />} />
      <Route element={<ProtectedShell />}>
        <Route index element={<Navigate to="/home" replace />} />
        <Route path="/home" element={<HomePage />} />
        {["/assets", "/agents", "/agents/new", "/approvals"].map((path) => (
          <Route key={path} path={path} element={<NotOpenPage />} />
        ))}
        <Route path="/objects/:typeKey" element={<ObjectsPage />} />
        {UiExamplesPage && (
          <Route
            path="/__dev/ui"
            element={
              <Suspense
                fallback={
                  <PageState kind="loading" title={zh.examples.loadingTitle} />
                }
              >
                <UiExamplesPage />
              </Suspense>
            }
          />
        )}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
