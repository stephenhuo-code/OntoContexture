import type { CatalogEntity } from "@contexture/ts-api";
import { Button } from "@contexture/ui";
import { INHERITABLE, KIND_NAME } from "./format";

type Ref = { name?: string; displayName?: string; fullyQualifiedName?: string };
type Origin = { entityType?: string; fullyQualifiedName?: string };

export function Chips({ items }: { items: string[] }) {
  return items.length ? (
    <span className="chips">
      {items.map((x) => (
        <span key={x} className="chip">
          {x}
        </span>
      ))}
    </span>
  ) : (
    <span className="muted">未分配</span>
  );
}

const names = (refs?: Ref[]) =>
  (refs ?? []).map(
    (r) => r.displayName || r.name || r.fullyQualifiedName || "",
  );

/** 资产属性卡片：值来自 OpenMetadata；可继承的属性标注“单独设置”或“继承自 <上级类型> · <上级 FQN>” */
export function AssetProperties({
  entity,
  onEdit,
}: {
  entity: CatalogEntity;
  onEdit?: () => void;
}) {
  const g = entity.governance ?? {};
  const kind = KIND_NAME[entity.entityType];
  const inherited = (g.inheritedFrom ?? {}) as Record<string, Origin>;
  const origin = (field: string, hasValue: boolean) => {
    const from = inherited[field];
    if (from)
      return (
        <p className="help">
          继承自{" "}
          {KIND_NAME[from.entityType as keyof typeof KIND_NAME] ??
            from.entityType}{" "}
          · {from.fullyQualifiedName}
        </p>
      );
    return hasValue && INHERITABLE[entity.entityType].includes(field) ? (
      <p className="help">单独设置</p>
    ) : null;
  };
  return (
    <section className="ctx-panel asset-properties" aria-label={`${kind}属性`}>
      <div className="panel-head">
        <div>
          <h3>
            {kind}属性 · {g.displayName || entity.name}
          </h3>
          <p className="muted">编辑元数据描述与治理属性，不修改源数据库。</p>
        </div>
        {onEdit && (
          <Button variant="secondary" onClick={onEdit}>
            编辑属性
          </Button>
        )}
      </div>
      <div className="detail-grid">
        <dl className="kv">
          <dt>名称（只读）</dt>
          <dd className="mono">{entity.name}</dd>
          <dt>显示名称</dt>
          <dd>{g.displayName || "未设置"}</dd>
          <dt>完整名称</dt>
          <dd className="mono">{entity.fullyQualifiedName}</dd>
          <dt>描述</dt>
          <dd className="pre">{g.description || "暂无描述"}</dd>
          <dt>负责人</dt>
          <dd>
            <Chips items={names(g.owners)} />
            {origin("owners", !!g.owners?.length)}
          </dd>
          {entity.entityType !== "databaseService" && (
            <>
              <dt>保留周期</dt>
              <dd>
                {g.retentionPeriod || "未设置"}
                {origin("retentionPeriod", !!g.retentionPeriod)}
              </dd>
            </>
          )}
        </dl>
        <dl className="kv">
          <dt>业务域</dt>
          <dd>
            <Chips items={names(g.domains)} />
            {origin("domains", !!g.domains?.length)}
          </dd>
          <dt>分级</dt>
          <dd>{g.tier || "未设置"}</dd>
          <dt>分类标签</dt>
          <dd>
            <Chips items={g.tags ?? []} />
          </dd>
          <dt>业务术语</dt>
          <dd>
            <Chips items={g.glossaryTerms ?? []} />
          </dd>
          <dt>数据产品</dt>
          <dd>
            <Chips items={names(g.dataProducts)} />
          </dd>
        </dl>
      </div>
    </section>
  );
}
