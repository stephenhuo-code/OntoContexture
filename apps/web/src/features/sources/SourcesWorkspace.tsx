import { useState } from "react";
import { Route, Routes, useLocation, useNavigate } from "react-router";
import type { SourceDetail } from "@contexture/ts-api";
import { SourcesList } from "./SourcesList";
import { SourceDetailView } from "./SourceDetailView";
import { SourceWizardModal } from "./SourceWizardModal";
import { useInvalidateSources, useSources } from "./queries";
import "./sources.css";
import { SOURCES_BASE } from "./format";

/** 数据源管理（005，006 起为 /assets/sources 子视图）：页面结构与交互对齐原型；数字、时间、运行与表结构全部来自 BFF。 */
export function SourcesWorkspace() {
  const navigate = useNavigate();
  const location = useLocation();
  // 006：数据资产页头的「添加数据源」以导航状态打开接入向导（US3 场景 1）
  const addSource =
    (location.state as { addSource?: boolean } | null)?.addSource === true;
  const sources = useSources();
  const invalidate = useInvalidateSources();
  const [wizard, setWizard] = useState<{
    open: boolean;
    source?: SourceDetail;
  }>({
    open: addSource,
  });
  const existingNames =
    sources.state.status === "ready"
      ? sources.state.data.map((s) => s.name)
      : [];
  return (
    <div className="sources-subview">
      <Routes>
        <Route
          index
          element={
            <SourcesList
              state={sources.state}
              reload={() => sources.reload()}
              onAdd={() => setWizard({ open: true })}
            />
          }
        />
        <Route
          path=":name"
          element={
            <SourceDetailView
              onConfigure={(source) => setWizard({ open: true, source })}
              onChanged={() => sources.reload(true)}
            />
          }
        />
      </Routes>
      {wizard.open && (
        <SourceWizardModal
          source={wizard.source}
          existingNames={existingNames}
          onClose={() => setWizard({ open: false })}
          onSaved={(saved) => {
            setWizard({ open: false });
            void invalidate();
            navigate(`${SOURCES_BASE}/${saved.name}`, {
              state: { saved: Date.now() },
            });
          }}
        />
      )}
    </div>
  );
}
