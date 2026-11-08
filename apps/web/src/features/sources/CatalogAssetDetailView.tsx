import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { Button, PageState } from "@contexture/ui";
import type { CatalogEntity, CatalogEntityType } from "@contexture/ts-api";
import { getCatalogEntity } from "./api";
import { Chips } from "./AssetProperties";
import { EditableProperties, PropertyEditModal } from "./PropertyEditModal";
import { KIND_NAME, LEVELS, assetChain, assetHref } from "./format";
import { useLoad } from "./useLoad";

type Child = NonNullable<CatalogEntity["children"]>[number];
type Table = NonNullable<CatalogEntity["table"]>;

function Crumbs({
  service,
  type,
  fqn,
}: {
  service: string;
  type: CatalogEntityType;
  fqn: string;
}) {
  const chain = assetChain(type, fqn);
  return (
    <nav className="catalog-path" aria-label="资产层级">
      {chain.map((c, i) =>
        i === chain.length - 1 ? (
          <span key={c.fqn} className="mono" aria-current="page">
            {c.label}
          </span>
        ) : (
          <span key={c.fqn}>
            <Link to={assetHref(service, c.type, c.fqn)}>{c.label}</Link>
            <span aria-hidden="true">›</span>
          </span>
        ),
      )}
    </nav>
  );
}

function Folder({
  service,
  entity,
}: {
  service: string;
  entity: CatalogEntity;
}) {
  const isDb = entity.entityType === "database";
  const kids: Child[] = entity.children ?? [];
  return (
    <section className="ctx-panel catalog-folder">
      <div className="panel-head">
        <h3>
          {KIND_NAME[entity.entityType]} · {entity.name}
        </h3>
        <span className="chip">
          {kids.length} {isDb ? "个 Schema" : "张表"}
        </span>
      </div>
      {kids.length ? (
        <div className="table-scroll">
          <table aria-label={isDb ? "Schema 列表" : "数据表列表"}>
            <thead>
              <tr>
                <th>{isDb ? "Schema" : "表名称"}</th>
                <th>说明</th>
                <th>{isDb ? "表数" : "字段数"}</th>
              </tr>
            </thead>
            <tbody>
              {kids.map((c) => (
                <tr key={c.fullyQualifiedName}>
                  <td>
                    <Link
                      to={assetHref(
                        service,
                        c.entityType as CatalogEntityType,
                        c.fullyQualifiedName ?? "",
                      )}
                    >
                      {c.displayName || c.name}
                    </Link>
                    {c.displayName && (
                      <div className="cell-sub mono">{c.name}</div>
                    )}
                  </td>
                  <td className="muted">{c.description || "暂无描述"}</td>
                  <td>{c.childCount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="muted">暂无下级资产</p>
      )}
    </section>
  );
}

function TableSwitch({ service, fqn }: { service: string; fqn: string }) {
  const navigate = useNavigate();
  const schemaFqn = assetChain("table", fqn)[2]!.fqn;
  const siblings = useLoad(
    () => getCatalogEntity("databaseSchema", schemaFqn),
    [schemaFqn],
  );
  if (siblings.state.status !== "ready") return null;
  return (
    <label className="table-switch">
      选择数据表{" "}
      <select
        aria-label="选择数据表"
        value={fqn}
        onChange={(e) => navigate(assetHref(service, "table", e.target.value))}
      >
        {(siblings.state.data.children ?? []).map((c) => (
          <option key={c.fullyQualifiedName} value={c.fullyQualifiedName}>
            {c.displayName ? `${c.displayName} · ${c.name}` : c.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function Structure({
  entity,
  t,
  onSaved,
}: {
  entity: CatalogEntity;
  t: Table;
  onSaved: (e: CatalogEntity) => void;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const cols = t.columns ?? [];
  // OM：单列约束记在 columns[].constraint，多列约束记在 tableConstraints；两处合并展示，均为 OM 原始数据
  const tableLevel = t.constraints ?? [];
  const covered = new Set(tableLevel.map((c) => c.constraintType));
  const columnLevel = new Map<string, string[]>();
  for (const c of cols)
    if (
      c.constraint &&
      !["NULL", "NOT_NULL"].includes(c.constraint) &&
      !covered.has(c.constraint)
    )
      columnLevel.set(c.constraint, [
        ...(columnLevel.get(c.constraint) ?? []),
        c.name ?? "",
      ]);
  const constraints = [
    ...tableLevel,
    ...[...columnLevel].map(([constraintType, columns]) => ({
      constraintType,
      columns,
    })),
  ];
  const pk = new Set(
    constraints
      .filter((c) => c.constraintType === "PRIMARY_KEY")
      .flatMap((c) => c.columns ?? []),
  );
  return (
    <>
      <section className="ctx-panel" aria-label="结构信息">
        <div className="panel-head">
          <h3>结构信息</h3>
          <span className="muted">结构元数据 · 只读</span>
        </div>
        <dl className="kv">
          <dt>表类型</dt>
          <dd>{t.tableType ?? "—"}</dd>
          <dt>字段数</dt>
          <dd>{cols.length}</dd>
          <dt>表约束</dt>
          <dd className="mono">
            {constraints.length
              ? constraints
                  .map(
                    (c) =>
                      `${c.constraintType} (${(c.columns ?? []).join(", ")})`,
                  )
                  .join("；")
              : "源未提供约束信息"}
          </dd>
          {t.schemaDefinition && (
            <>
              <dt>视图定义</dt>
              <dd>
                <pre className="mono">{t.schemaDefinition}</pre>
              </dd>
            </>
          )}
        </dl>
      </section>
      <section className="ctx-panel">
        <div className="panel-head">
          <h3>字段元数据</h3>
          <span className="chip">{cols.length} 字段</span>
        </div>
        <div className="table-scroll">
          <table aria-label="字段元数据" className="column-metadata">
            <thead>
              <tr>
                <th>字段名称</th>
                <th>数据类型</th>
                <th>显示名称 / 描述</th>
                <th>分类标签</th>
                <th>业务术语</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {cols.map((c) => (
                <tr key={c.name}>
                  <td className="mono">
                    {c.name}{" "}
                    {(c.constraint === "PRIMARY_KEY" ||
                      pk.has(c.name ?? "")) && (
                      <span className="chip pk">PK</span>
                    )}
                  </td>
                  <td className="mono muted">{c.dataTypeDisplay}</td>
                  <td>
                    <b>{c.displayName || "未设置显示名称"}</b>
                    <div className="cell-sub pre">
                      {c.description || "暂无描述"}
                    </div>
                  </td>
                  <td>
                    <Chips items={c.tags ?? []} />
                  </td>
                  <td>
                    <Chips items={c.glossaryTerms ?? []} />
                  </td>
                  <td>
                    <Button
                      variant="secondary"
                      onClick={() => setEditing(c.name ?? null)}
                    >
                      编辑属性
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {editing && (
        <PropertyEditModal
          entity={entity}
          column={cols.find((c) => c.name === editing)}
          onClose={() => setEditing(null)}
          onSaved={(e) => {
            setEditing(null);
            onSaved(e);
          }}
        />
      )}
    </>
  );
}

/** 数据库 / Schema / 表独立资产详情（METADATA CATALOG）：不显示连接配置、采集页签与源级状态。 */
export function CatalogAssetDetailView() {
  const { name = "", entityType = "", fqn = "" } = useParams();
  const type = entityType as CatalogEntityType;
  const valid = LEVELS.includes(type) && type !== "databaseService";
  const entity = useLoad(
    () =>
      valid
        ? getCatalogEntity(type, fqn)
        : Promise.reject(new Error("invalid")),
    [type, fqn],
  );
  const back = (
    <Link to={`/sources/${name}`} className="back-link">
      ← 返回所属数据源
    </Link>
  );
  if (!valid)
    return (
      <>
        {back}
        <PageState kind="not_found" title="不支持的资产类型" />
      </>
    );
  if (entity.state.status === "loading")
    return (
      <>
        {back}
        <PageState kind="loading" title="正在读取资产" />
      </>
    );
  if (entity.state.status === "error")
    return (
      <>
        {back}
        <PageState
          kind={
            entity.state.error.code === "catalog.not_found"
              ? "not_found"
              : "error"
          }
          title={entity.state.error.message}
          description={`错误码 ${entity.state.error.code}`}
          traceId={entity.state.error.trace_id}
          actionLabel="重试"
          action={() => entity.reload()}
        />
      </>
    );
  const e = entity.state.data;
  return (
    <>
      {back}
      <div className="detail-head">
        <div>
          <p className="eyebrow">METADATA CATALOG</p>
          <h2>{e.governance?.displayName || e.name}</h2>
          <p className="muted">
            {KIND_NAME[e.entityType]} ·{" "}
            <span className="mono">{e.fullyQualifiedName}</span>
          </p>
        </div>
      </div>
      <Crumbs service={name} type={e.entityType} fqn={e.fullyQualifiedName} />
      {e.entityType === "table" && (
        <TableSwitch service={name} fqn={e.fullyQualifiedName} />
      )}
      <EditableProperties entity={e} onSaved={entity.set} />
      {e.entityType === "table" && e.table ? (
        <Structure entity={e} t={e.table} onSaved={entity.set} />
      ) : (
        <Folder service={name} entity={e} />
      )}
    </>
  );
}
