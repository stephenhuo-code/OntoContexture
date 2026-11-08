import { useState } from "react";
import { Route, Routes, useNavigate } from "react-router";
import type { SourceDetail } from "@contexture/ts-api";
import { listSources } from "./api";
import { SourcesList } from "./SourcesList";
import { SourceDetailView } from "./SourceDetailView";
import { SourceWizardModal } from "./SourceWizardModal";
import { CatalogAssetDetailView } from "./CatalogAssetDetailView";
import { CatalogTree } from "./CatalogTree";
import { useLoad } from "./useLoad";
import "./sources.css";

/** 数据源工作空间（005）：页面结构与交互对齐原型；数字、时间、运行与表结构全部来自 BFF。 */
export function SourcesWorkspace() {
  const navigate = useNavigate();
  const sources = useLoad(listSources, []);
  const [wizard, setWizard] = useState<{
    open: boolean;
    source?: SourceDetail;
  }>({
    open: false,
  });
  const [drawer, setDrawer] = useState(false);
  const existingNames =
    sources.state.status === "ready"
      ? sources.state.data.map((s) => s.name)
      : [];
  return (
    <div className="sources-workspace">
      {/* 窄屏（≤ 850px）下二级栏目录隐藏，改由“目录”抽屉浏览（原型 tree-mobile） */}
      <button
        type="button"
        className="ctx-button ctx-button--secondary tree-mobile"
        aria-expanded={drawer}
        onClick={() => setDrawer(!drawer)}
      >
        目录
      </button>
      {drawer && (
        <div role="dialog" aria-label="数据源目录" className="catalog-drawer">
          <CatalogTree onPick={() => setDrawer(false)} />
        </div>
      )}
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
        <Route
          path=":name/assets/:entityType/:fqn"
          element={<CatalogAssetDetailView />}
        />
      </Routes>
      {wizard.open && (
        <SourceWizardModal
          source={wizard.source}
          existingNames={existingNames}
          onClose={() => setWizard({ open: false })}
          onSaved={(saved) => {
            setWizard({ open: false });
            sources.reload(true);
            navigate(`/sources/${saved.name}`, {
              state: { saved: Date.now() },
            });
          }}
        />
      )}
    </div>
  );
}
