import { Link } from "react-router";
import { PageState } from "@contexture/ui";
import type { CatalogEntity, SourceDetail } from "@contexture/ts-api";
import { getCatalogEntity } from "./api";
import { assetHref } from "./format";
import { useLoad } from "./useLoad";

function Empty() {
  return (
    <section className="ctx-panel sources-empty">
      <h3>暂无元数据</h3>
      <p className="muted">首次采集完成后在这里浏览数据库目录。</p>
    </section>
  );
}

/** 已采集元数据页签：数据源下的数据库目录（OM DatabaseService 的直接子项）。 */
export function SourceCatalog({ source }: { source: SourceDetail }) {
  if (!source.configured) return <Empty />;
  return <Databases name={source.name} />;
}

function Databases({ name }: { name: string }) {
  const svc = useLoad(() => getCatalogEntity("databaseService", name), [name]);
  if (svc.state.status === "loading")
    return <PageState kind="loading" title="正在读取目录" />;
  if (svc.state.status === "error")
    return (
      <PageState
        kind="error"
        title={svc.state.error.message}
        description={`错误码 ${svc.state.error.code}`}
        traceId={svc.state.error.trace_id}
        actionLabel="重试"
        action={() => svc.reload()}
      />
    );
  const kids: NonNullable<CatalogEntity["children"]> =
    svc.state.data.children ?? [];
  if (!kids.length) return <Empty />;
  return (
    <section className="ctx-panel">
      <div className="panel-head">
        <div>
          <h3>数据库目录</h3>
          <p className="muted">选择数据库，逐层浏览 Schema、表与字段。</p>
        </div>
        <span className="chip">{kids.length} 个数据库</span>
      </div>
      <div className="table-scroll">
        <table aria-label="数据库目录">
          <thead>
            <tr>
              <th>数据库</th>
              <th>描述</th>
              <th>Schema 数</th>
            </tr>
          </thead>
          <tbody>
            {kids.map((c) => (
              <tr key={c.fullyQualifiedName}>
                <td>
                  <Link
                    to={assetHref(name, "database", c.fullyQualifiedName ?? "")}
                  >
                    {c.displayName || c.name}
                  </Link>
                  <div className="cell-sub mono">{c.fullyQualifiedName}</div>
                </td>
                <td className="muted">{c.description || "暂无描述"}</td>
                <td>{c.childCount}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
