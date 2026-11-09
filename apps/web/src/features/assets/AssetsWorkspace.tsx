import { useState } from "react";
import { Route, Routes, useParams } from "react-router";
import { SourcesWorkspace } from "../sources/SourcesWorkspace";
import { CatalogAssetDetailView } from "../sources/CatalogAssetDetailView";
import { AssetsRail } from "./AssetsRail";
import { ExploreView } from "./ExploreView";
import { NotFoundPage } from "../../pages/NotFoundPage";
import { AssetsCriteriaProvider } from "./criteria";
import "../sources/sources.css";
import "./assets.css";

const CATALOG_TYPES = new Set(["database", "databaseSchema", "table"]);

/**
 * 006 统一的「数据资产」页面（/assets，FR-001、FR-002）：
 * 探索视图为默认子视图；005 的数据源管理在 /assets/sources/*，库 / Schema / 表详情在 /assets/{类型}/{fqn}。
 * 搜索条件在本布局内跨子视图保留（FR-015），不写入地址。
 */
export function AssetsWorkspace() {
  const [drawer, setDrawer] = useState(false);
  return (
    <AssetsCriteriaProvider>
      <div className="sources-workspace">
        {/* 窄屏（≤ 850px）下二级栏目录隐藏，改由“目录”抽屉浏览（沿用 005） */}
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
            <AssetsRail onPick={() => setDrawer(false)} />
          </div>
        )}
        <Routes>
          <Route index element={<ExploreView />} />
          <Route path="sources/*" element={<SourcesWorkspace />} />
          <Route path=":entityType/:fqn" element={<AssetDetailRoute />} />
        </Routes>
      </div>
    </AssetsCriteriaProvider>
  );
}

/** /assets/{类型}/{fqn}：库、Schema、表进入 005 的资产详情；其他类型在后续故事中接入。 */
function AssetDetailRoute() {
  const { entityType = "" } = useParams();
  return CATALOG_TYPES.has(entityType) ? (
    <CatalogAssetDetailView />
  ) : (
    <NotFoundPage />
  );
}
