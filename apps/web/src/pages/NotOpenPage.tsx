import { PageState } from "@contexture/ui";
import { useLocation, useNavigate } from "react-router";
import { routePresentation } from "../layout/navigation";
import { zh } from "../i18n/zh-CN";
export function NotOpenPage() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  return (
    <PageState
      kind="not_open"
      title={zh.pendingTitle(routePresentation(pathname).title)}
      description={zh.pendingDescription}
      actionLabel={zh.home}
      action={() => navigate("/home")}
    />
  );
}
