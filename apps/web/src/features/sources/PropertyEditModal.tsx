import type { SourceDetail } from "@contexture/ts-api";
import { connector } from "./format";

/** 数据源属性卡片（US4 增加治理属性与编辑）。 */
export function SourceProperties({
  source,
}: {
  source: SourceDetail;
  onSaved: () => void;
}) {
  return (
    <section className="ctx-panel">
      <h3>数据源属性</h3>
      <dl className="kv">
        <dt>显示名称</dt>
        <dd>{source.displayName}</dd>
        <dt>服务标识</dt>
        <dd className="mono">{source.name}</dd>
        <dt>连接器</dt>
        <dd>{connector(source.serviceType).label}</dd>
        <dt>描述</dt>
        <dd>{source.description || "暂无描述"}</dd>
      </dl>
    </section>
  );
}
