import { PageState } from "@contexture/ui";
import { useNavigate } from "react-router";
import { zh } from "../i18n/zh-CN";
export function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <PageState
      kind="not_found"
      title={zh.notFound}
      description={zh.missingDescription}
      actionLabel={zh.home}
      action={() => navigate("/home")}
    />
  );
}
