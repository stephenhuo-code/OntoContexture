import { useLocation } from "react-router";
import { CatalogTree } from "../sources/CatalogTree";
import { useAssetsCriteria } from "./criteria";
import { TypeList } from "./TypeList";

/** 二级栏内容（FR-003）：探索视图有关键词时为类型列表，否则为目录树。 */
export function AssetsRail({ onPick }: { onPick?: () => void }) {
  const { pathname } = useLocation();
  const { criteria } = useAssetsCriteria();
  const explore = pathname.replace(/\/+$/, "") === "/assets";
  if (explore && criteria.keyword) return <TypeList />;
  return <CatalogTree onPick={onPick} />;
}
