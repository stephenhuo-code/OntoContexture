import type { AssetRef } from "@contexture/ts-api";

/** 有织境详情页的类型（FR-012；其他类型只选中显示摘要，U1） */
const DETAIL_TYPES = new Set([
  "database",
  "databaseSchema",
  "table",
  "glossaryTerm",
  "tag",
]);

export type DetailTarget = { to: string; state?: { column: string } };

/** 进入详情：库、Schema、表、术语、标签 → /assets/{类型}/{fqn}；列 → 所属表并定位到该列（Q3） */
export function detailTarget(
  ref: AssetRef,
  parentTable?: AssetRef | null,
  columnName?: string | null,
): DetailTarget | null {
  if (ref.entityType === "tableColumn") {
    if (!parentTable?.fqn || !columnName) return null;
    return {
      to: `/assets/table/${encodeURIComponent(parentTable.fqn)}`,
      state: { column: columnName },
    };
  }
  if (!DETAIL_TYPES.has(ref.entityType)) return null;
  return { to: `/assets/${ref.entityType}/${encodeURIComponent(ref.fqn)}` };
}
