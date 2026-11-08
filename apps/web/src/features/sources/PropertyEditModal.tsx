import { useState } from "react";
import { Button, PageState } from "@contexture/ui";
import type {
  CatalogEntity,
  GovernanceOptions,
  GovernancePatch,
  SourceDetail,
} from "@contexture/ts-api";
import { ApiFailure } from "../../api";
import {
  getCatalogEntity,
  getGovernanceOptions,
  patchCatalogEntity,
} from "./api";
import { AssetProperties } from "./AssetProperties";
import { Field } from "./Field";
import { INHERITABLE, KIND_NAME, assetChain } from "./format";
import { asApiError, useLoad } from "./useLoad";
import { useInvalidateSources } from "./queries";

type Column = NonNullable<
  NonNullable<CatalogEntity["table"]>["columns"]
>[number];
type Ref = { id: string; type: string; name?: string; displayName?: string };
const label = (r: Ref) => r.displayName || r.name || r.id;
const TIERS = [1, 2, 3, 4, 5].map((n) => `Tier.Tier${n}`);
// ISO 8601 时长：周单独使用，或 年月日 + T 时分秒（与 BFF 校验一致）
const ISO_DURATION =
  /^(?:P\d+W|P(?=\d|T\d)(?:\d+Y)?(?:\d+M)?(?:\d+D)?(?:T(?=\d)(?:\d+H)?(?:\d+M)?(?:\d+(?:\.\d+)?S)?)?)$/;

type Draft = {
  displayName: string;
  description: string;
  domain: string;
  tier: string;
  ownerType: "user" | "team";
  owners: string[];
  retentionPeriod: string;
  tags: string[];
  glossaryTerms: string[];
  dataProducts: string[];
};

function initialDraft(entity: CatalogEntity, column?: Column): Draft {
  const g = entity.governance ?? {};
  const inherited = g.inheritedFrom ?? {};
  const own = <T,>(field: string, value: T, empty: T) =>
    inherited[field] ? empty : value;
  const owners = own("owners", (g.owners ?? []) as Ref[], []);
  return {
    displayName: (column ? column.displayName : g.displayName) ?? "",
    description: (column ? column.description : g.description) ?? "",
    domain: own("domains", (g.domains as Ref[] | undefined)?.[0]?.id ?? "", ""),
    tier: g.tier ?? "",
    ownerType: owners[0]?.type === "team" ? "team" : "user",
    owners: owners.map((o) => o.id),
    retentionPeriod: own("retentionPeriod", g.retentionPeriod ?? "", ""),
    tags: [...((column ? column.tags : g.tags) ?? [])],
    glossaryTerms: [
      ...((column ? column.glossaryTerms : g.glossaryTerms) ?? []),
    ],
    dataProducts: ((g.dataProducts ?? []) as Ref[]).map((p) => p.id),
  };
}

const same = (a: unknown, b: unknown) =>
  JSON.stringify(a) === JSON.stringify(b);

function Choices({
  legend,
  items,
  selected,
  onToggle,
  hint,
}: {
  legend: string;
  items: { value: string; label: string; note?: string }[];
  selected: string[];
  onToggle: (value: string) => void;
  hint?: string;
}) {
  return (
    <fieldset className="property-choices">
      <legend>{legend}</legend>
      {items.length ? (
        items.map((x) => (
          <label key={x.value} className="row">
            <input
              type="checkbox"
              checked={selected.includes(x.value)}
              onChange={() => onToggle(x.value)}
            />
            {x.label}
            {x.note && <span className="help">（{x.note}）</span>}
          </label>
        ))
      ) : (
        <span className="muted">暂无可选项</span>
      )}
      {hint && <p className="help">{hint}</p>}
    </fieldset>
  );
}

/** 编辑属性弹窗（US4）：选项实时来自 OM；只提交改动的字段，清空表示恢复继承。 */
export function PropertyEditModal({
  entity,
  column,
  onClose,
  onSaved,
}: {
  entity: CatalogEntity;
  column?: Column;
  onClose: () => void;
  onSaved: (e: CatalogEntity) => void;
}) {
  const type = entity.entityType;
  const title = column ? "编辑字段属性" : `编辑${KIND_NAME[type]}属性`;
  const options = useLoad(getGovernanceOptions, []);
  const parentRef =
    type === "databaseService"
      ? null
      : assetChain(type, entity.fullyQualifiedName).at(-2)!;
  const parent = useLoad(
    () =>
      parentRef
        ? getCatalogEntity(parentRef.type, parentRef.fqn)
        : Promise.resolve(null),
    [parentRef?.fqn],
  );
  const [initial] = useState(() => initialDraft(entity, column));
  const [draft, setDraft] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const inheritable = INHERITABLE[type];
  const opts: GovernanceOptions | null =
    options.state.status === "ready" ? options.state.data : null;
  const parentGov =
    parent.state.status === "ready" ? parent.state.data?.governance : undefined;
  const parentDomain = (parentGov?.domains as Ref[] | undefined)?.[0];
  const parentOwners = (parentGov?.owners ?? []) as Ref[];
  const effectiveDomain =
    draft.domain ||
    (inheritable.includes("domains") ? (parentDomain?.id ?? "") : "");
  const set = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }));
  const toggle = (
    field: "owners" | "tags" | "glossaryTerms" | "dataProducts",
    value: string,
  ) =>
    setDraft((d) => {
      const has = d[field].includes(value);
      if (field === "owners" && d.ownerType === "team")
        return { ...d, owners: has ? [] : [value] };
      let next = has
        ? d[field].filter((x) => x !== value)
        : [...d[field], value];
      if (field === "tags" && !has && opts) {
        // 同一互斥分类只保留一个标签：选择新标签替换同分类已选项
        const cls = opts.classifications?.find((c) => c.tags?.includes(value));
        if (cls?.mutuallyExclusive)
          next = next.filter((t) => t === value || !cls.tags?.includes(t));
      }
      return { ...d, [field]: next };
    });

  const loadState = options.state;
  if (!opts || loadState.status !== "ready")
    return (
      <Shell title={title} onClose={onClose}>
        {loadState.status === "loading" ? (
          <PageState kind="loading" title="正在读取治理选项" />
        ) : (
          <PageState
            kind="error"
            title={loadState.status === "error" ? loadState.error.message : ""}
            description={
              loadState.status === "error"
                ? `错误码 ${loadState.error.code}`
                : ""
            }
            traceId={
              loadState.status === "error" ? loadState.error.trace_id : ""
            }
            actionLabel="重试"
            action={() => options.reload()}
          />
        )}
      </Shell>
    );
  const productDomains = new Map(
    (opts.dataProducts ?? []).map((p) => [
      p.id,
      (p.domains ?? []).map((d) => d.id),
    ]),
  );

  async function save() {
    setError(null);
    if (
      !column &&
      draft.dataProducts.some(
        (id) => !productDomains.get(id)?.includes(effectiveDomain),
      )
    )
      return setError(
        "数据产品与业务域不匹配。请选择对应业务域，或取消勾选不匹配的数据产品。",
      );
    const retention = draft.retentionPeriod.trim();
    if (
      !column &&
      type !== "databaseService" &&
      retention &&
      !ISO_DURATION.test(retention)
    )
      return setError(
        "请输入有效的 ISO 8601 保留周期，例如 P30D 或 PT24H，或留空。",
      );
    const body: GovernancePatch = column ? { columnName: column.name } : {};
    const changed = (k: keyof Draft) => !same(draft[k], initial[k]);
    const text = (v: string) => v.trim() || null;
    if (changed("displayName")) body.displayName = text(draft.displayName);
    if (changed("description")) body.description = text(draft.description);
    if (changed("tags")) body.tags = draft.tags;
    if (changed("glossaryTerms")) body.glossaryTerms = draft.glossaryTerms;
    if (!column) {
      if (changed("domain"))
        body.domain = draft.domain
          ? { id: draft.domain, type: "domain" }
          : null;
      if (changed("tier")) body.tier = draft.tier || null;
      if (changed("owners") || changed("ownerType"))
        body.owners = draft.owners.length
          ? draft.owners.map((id) => ({ id, type: draft.ownerType }))
          : null;
      if (changed("retentionPeriod")) body.retentionPeriod = retention || null;
      if (changed("dataProducts"))
        body.dataProducts = draft.dataProducts.map((id) => ({
          id,
          type: "dataProduct",
        }));
    }
    if (Object.keys(body).length === (column ? 1 : 0)) return onClose();
    setSaving(true);
    try {
      onSaved(await patchCatalogEntity(type, entity.fullyQualifiedName, body));
    } catch (e) {
      const err = e instanceof ApiFailure ? e.error : asApiError(e);
      setError(`${err.message}（错误码 ${err.code}）`);
    } finally {
      setSaving(false);
    }
  }

  const ownerList = ((draft.ownerType === "user" ? opts.users : opts.teams) ??
    []) as Ref[];
  return (
    <Shell
      title={title}
      onClose={onClose}
      foot={
        <Button onClick={save} disabled={saving}>
          保存属性
        </Button>
      }
    >
      <div className="fields">
        <Field label="显示名称">
          {(p) => (
            <input
              {...p}
              className="ctx-input"
              value={draft.displayName}
              maxLength={256}
              placeholder="留空时使用原名称"
              onChange={(e) => set({ displayName: e.target.value })}
            />
          )}
        </Field>
        <Field
          label={
            type === "databaseService" && !column
              ? "服务标识"
              : "完整名称（只读）"
          }
          help="名称、所属层级与结构信息不在这里修改。"
        >
          {(p) => (
            <input
              {...p}
              className="ctx-input mono"
              value={entity.fullyQualifiedName}
              readOnly
            />
          )}
        </Field>
        <Field label="描述" full>
          {(p) => (
            <textarea
              {...p}
              className="ctx-input"
              rows={3}
              value={draft.description}
              placeholder="填写用途与说明"
              onChange={(e) => set({ description: e.target.value })}
            />
          )}
        </Field>
        {column ? (
          <div className="field full">
            <div className="review-chip">
              {column.name} · {column.dataTypeDisplay} ·{" "}
              {column.constraint ?? "约束未单独标注"}（只读）
            </div>
          </div>
        ) : (
          <>
            <Field
              label="业务域"
              help={`${
                inheritable.includes("domains")
                  ? "清除单独设置后恢复继承上级；上级未分配时显示未分配。"
                  : "下级数据库未单独设置时继承此域。"
              }域按默认规则单选。`}
            >
              {(p) => (
                <select
                  {...p}
                  value={draft.domain}
                  onChange={(e) => set({ domain: e.target.value })}
                >
                  <option value="">
                    {inheritable.includes("domains")
                      ? `继承上级（${parentDomain ? label(parentDomain) : "未分配"}）`
                      : "未分配"}
                  </option>
                  {((opts.domains ?? []) as Ref[]).map((d) => (
                    <option key={d.id} value={d.id}>
                      {label(d)}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field
              label="重要程度（Tier）"
              help="业务重要程度；不等同于敏感级别。"
            >
              {(p) => (
                <select
                  {...p}
                  value={draft.tier}
                  onChange={(e) => set({ tier: e.target.value })}
                >
                  <option value="">未分配</option>
                  {TIERS.map((t) => (
                    <option key={t} value={t}>
                      {t.replace("Tier.", "")}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field
              label="负责人类型"
              full
              help={`切换类型后重新选择。${
                inheritable.includes("owners")
                  ? `不选择负责人时继承上级：${parentOwners.map(label).join("、") || "未分配"}`
                  : "此层级不从上级继承负责人。"
              }`}
            >
              {(p) => (
                <select
                  {...p}
                  value={draft.ownerType}
                  onChange={(e) =>
                    set({
                      ownerType: e.target.value as Draft["ownerType"],
                      owners: [],
                    })
                  }
                >
                  <option value="user">用户（可多选）</option>
                  <option value="team">团队（单选）</option>
                </select>
              )}
            </Field>
            <div className="field full">
              <Choices
                legend="选择负责人"
                items={ownerList.map((o) => ({ value: o.id, label: label(o) }))}
                selected={draft.owners}
                onToggle={(v) => toggle("owners", v)}
              />
            </div>
            {type !== "databaseService" && (
              <Field
                label="保留周期"
                full
                help={`ISO 8601 时长，如 P30D 或 PT24H。${
                  inheritable.includes("retentionPeriod")
                    ? "留空时继承上级。"
                    : "留空表示未设置。"
                }仅记录元数据，不执行数据删除。`}
              >
                {(p) => (
                  <input
                    {...p}
                    className="ctx-input"
                    value={draft.retentionPeriod}
                    placeholder="例如 P30D"
                    onChange={(e) => set({ retentionPeriod: e.target.value })}
                  />
                )}
              </Field>
            )}
          </>
        )}
        <div className="field full">
          <Choices
            legend="分类标签"
            items={(opts.classifications ?? []).flatMap((c) =>
              (c.tags ?? []).map((t) => ({ value: t, label: t })),
            )}
            selected={draft.tags}
            onToggle={(v) => toggle("tags", v)}
            hint="同一互斥分类只能选择一个标签；选择新标签会替换同分类已选项。"
          />
        </div>
        <div className="field full">
          <Choices
            legend="业务术语"
            items={(opts.glossaryTerms ?? []).map((t) => ({
              value: t,
              label: t,
            }))}
            selected={draft.glossaryTerms}
            onToggle={(v) => toggle("glossaryTerms", v)}
          />
        </div>
        {!column && (
          <div className="field full">
            <Choices
              legend="数据产品"
              items={(
                (opts.dataProducts ?? []) as (Ref & { domains?: Ref[] })[]
              ).map((p) => ({
                value: p.id,
                label: label(p),
                note: productDomains.get(p.id)?.includes(effectiveDomain)
                  ? undefined
                  : "与当前业务域不匹配",
              }))}
              selected={draft.dataProducts}
              onToggle={(v) => toggle("dataProducts", v)}
              hint="数据产品必须与当前有效业务域匹配；数据产品不自动继承上级。"
            />
          </div>
        )}
      </div>
      {error && (
        <div className="alert warning" role="alert">
          {error}
        </div>
      )}
    </Shell>
  );
}

function Shell({
  title,
  onClose,
  children,
  foot,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  foot?: React.ReactNode;
}) {
  return (
    <div className="modal-backdrop">
      <div role="dialog" aria-modal="true" aria-label={title} className="modal">
        <header className="modal-head">
          <h2>{title}</h2>
          <Button variant="ghost" aria-label="关闭弹窗" onClick={onClose}>
            ×
          </Button>
        </header>
        <div className="modal-body">{children}</div>
        <footer className="modal-foot">
          <span className="help">取消不会保存本次修改</span>
          <div className="row">
            <Button variant="secondary" onClick={onClose}>
              取消
            </Button>
            {foot}
          </div>
        </footer>
      </div>
    </div>
  );
}

/** 可编辑的资产属性卡片：卡片 + 编辑弹窗 */
export function EditableProperties({
  entity,
  onSaved,
}: {
  entity: CatalogEntity;
  onSaved: (e: CatalogEntity) => void;
}) {
  const [editing, setEditing] = useState(false);
  const invalidate = useInvalidateSources();
  return (
    <>
      <AssetProperties entity={entity} onEdit={() => setEditing(true)} />
      {editing && (
        <PropertyEditModal
          entity={entity}
          onClose={() => setEditing(false)}
          onSaved={(e) => {
            setEditing(false);
            onSaved(e);
            void invalidate(); // 目录中的显示名称随之更新
          }}
        />
      )}
    </>
  );
}

/** 数据源概览的属性卡片：治理属性来自 OM DatabaseService（目录实体） */
export function SourceProperties({
  source,
  onSaved,
}: {
  source: SourceDetail;
  onSaved: () => void;
}) {
  const svc = useLoad(
    () => getCatalogEntity("databaseService", source.name),
    [source.name],
  );
  if (svc.state.status === "loading")
    return <PageState kind="loading" title="正在读取数据源属性" />;
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
  return (
    <EditableProperties
      entity={svc.state.data}
      onSaved={(e) => {
        svc.set(e);
        onSaved();
      }}
    />
  );
}
