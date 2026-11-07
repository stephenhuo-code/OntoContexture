import { useEffect } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router";
import { Button, PageState, StatusBadge } from "@contexture/ui";
import type { SourceDetail } from "@contexture/ts-api";
import { getSource } from "./api";
import {
  KIND_LABEL,
  STATE_LABEL,
  connector,
  cronLabel,
  formatTime,
  pipelineOf,
  sourceState,
  stateTone,
  taskState,
} from "./format";
import { ConnectorBadge } from "./SourcesList";
import { SourceTasks } from "./SourceTasks";
import { SourceCatalog } from "./SourceCatalog";
import { SourceProperties } from "./PropertyEditModal";
import { useLoad } from "./useLoad";

const TABS = [
  ["overview", "概览"],
  ["metadata", "已采集元数据"],
  ["scope", "采集配置"],
  ["tasks", "采集任务"],
] as const;
type Tab = (typeof TABS)[number][0];

const LEVEL_LABEL = {
  databaseFilterPattern: "数据库",
  schemaFilterPattern: "Schema",
  tableFilterPattern: "表",
} as const;

function Overview({ s, reload }: { s: SourceDetail; reload: () => void }) {
  const bad = s.pipelines.filter((p) =>
    ["partialSuccess", "failed"].includes(p.lastRun?.pipelineState ?? ""),
  );
  return (
    <>
      <SourceProperties source={s} onSaved={reload} />
      {bad.length > 0 && (
        <div className="alert warning" role="note">
          <b>
            {bad.map((p) => KIND_LABEL[p.kind]).join("、")}最近一次运行
            {bad[0]!.lastRun!.pipelineState === "failed" ? "失败" : "部分成功"}
          </b>
          <p>
            已写入的元数据保留。请在运行详情中查看失败对象与日志，处理后重新运行。
          </p>
          <Link to={`?tab=tasks&task=${bad[0]!.kind}`}>查看运行与日志 →</Link>
        </div>
      )}
      <div className="metric-row">
        <div className="metric">
          <span>已采集表</span>
          <b>{s.tableCount}</b>
          <small>{s.database ?? "全部库"}</small>
        </div>
        <div className="metric">
          <span>字段元数据</span>
          <b>{s.columnCount}</b>
          <small>字段类型、注释与约束</small>
        </div>
        <div className="metric">
          <span>采集任务</span>
          <b>{s.pipelines.length}</b>
          <small>
            {s.pipelines.map((p) => KIND_LABEL[p.kind]).join(" · ") ||
              "尚未配置"}
          </small>
        </div>
      </div>
      <div className="detail-grid">
        <section className="ctx-panel">
          <h3>连接信息</h3>
          <dl className="kv">
            <dt>数据库</dt>
            <dd className="mono">{s.connection.database ?? "全部库"}</dd>
            <dt>连接地址</dt>
            <dd className="mono">{s.connection.hostPort}</dd>
            <dt>只读账号</dt>
            <dd className="mono">{s.connection.username}</dd>
            <dt>密码</dt>
            <dd className="mono">{s.connection.password}</dd>
            <dt>采集边界</dt>
            <dd>仅表、字段与视图血缘元数据</dd>
          </dl>
        </section>
        <section className="ctx-panel">
          <h3>调度与最近运行</h3>
          {s.pipelines.length ? (
            <dl className="kv">
              {s.pipelines.map((p) => {
                const st = taskState(p);
                return (
                  <div key={p.kind} className="kv-row">
                    <dt>{KIND_LABEL[p.kind]}</dt>
                    <dd>
                      <StatusBadge tone={stateTone(st)}>
                        {STATE_LABEL[st]}
                      </StatusBadge>{" "}
                      <span className="muted">
                        {formatTime(p.lastRun?.startDate)} ·{" "}
                        {cronLabel(p.schedule?.cron)}
                        {p.schedule?.cron && !p.scheduleEnabled
                          ? "（已暂停）"
                          : ""}
                      </span>
                    </dd>
                  </div>
                );
              })}
              <dt>时区</dt>
              <dd>Asia/Shanghai</dd>
            </dl>
          ) : (
            <p className="muted">完成连接与采集配置后生成采集任务。</p>
          )}
          <Link to="?tab=tasks">查看采集任务 ↗</Link>
        </section>
      </div>
    </>
  );
}

function ScopeTab({
  s,
  onConfigure,
}: {
  s: SourceDetail;
  onConfigure: () => void;
}) {
  const lineage = pipelineOf(s, "lineage");
  return (
    <div className="detail-grid">
      <section className="ctx-panel">
        <div className="panel-head">
          <h3>采集范围</h3>
          <Button variant="secondary" onClick={onConfigure}>
            调整配置
          </Button>
        </div>
        <dl className="kv">
          <dt>连接数据库</dt>
          <dd className="mono">{s.connection.database ?? "全部库"}</dd>
          {(Object.keys(LEVEL_LABEL) as (keyof typeof LEVEL_LABEL)[]).map(
            (k) => {
              const p = s.scope[k];
              const inc = p?.includes ?? [];
              const exc = p?.excludes ?? [];
              return (
                <div key={k} className="kv-row">
                  <dt>{LEVEL_LABEL[k]}过滤</dt>
                  <dd className="mono">
                    {inc.length || exc.length
                      ? [
                          inc.length ? `包含 ${inc.join(", ")}` : "",
                          exc.length ? `排除 ${exc.join(", ")}` : "",
                        ]
                          .filter(Boolean)
                          .join("；")
                      : "未设置（全部）"}
                  </dd>
                </div>
              );
            },
          )}
          <dt>视图</dt>
          <dd>{s.scope.includeViews ? "采集视图元数据" : "不采集视图"}</dd>
          <dt>视图血缘任务</dt>
          <dd>
            {lineage ? "已创建（处理视图血缘；不处理查询日志血缘）" : "未创建"}
          </dd>
        </dl>
      </section>
      <section className="ctx-panel">
        <h3>采集边界</h3>
        <ul className="checklist">
          <li>只读连接源系统</li>
          <li>密码由 OpenMetadata SecretsManager 加密托管</li>
          <li>不开启数据采样或数据剖析</li>
          <li>不复制表中的业务记录</li>
        </ul>
        <p className="help">
          过滤规则为 OpenMetadata 原生正则表达式；未设置时采集全部。
        </p>
      </section>
    </div>
  );
}

export function SourceDetailView({
  onConfigure,
  onChanged,
}: {
  onConfigure: (s: SourceDetail) => void;
  onChanged: () => void;
}) {
  const { name = "" } = useParams();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const tab = (TABS.find(([k]) => k === params.get("tab"))?.[0] ??
    "overview") as Tab;
  const detail = useLoad(() => getSource(name), [name]);
  const saved = (location.state as { saved?: number } | null)?.saved;
  useEffect(() => {
    if (saved) detail.reload(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saved]);

  const back = (
    <Link to="/sources" className="back-link">
      ← 返回数据源
    </Link>
  );
  if (detail.state.status === "loading")
    return (
      <>
        {back}
        <PageState kind="loading" title="正在读取数据源" />
      </>
    );
  if (detail.state.status === "error")
    return (
      <>
        {back}
        <PageState
          kind={
            detail.state.error.code === "source.not_found"
              ? "not_found"
              : "error"
          }
          title={detail.state.error.message}
          description={`错误码 ${detail.state.error.code}`}
          traceId={detail.state.error.trace_id}
          actionLabel="重试"
          action={() => detail.reload()}
        />
      </>
    );
  const s = detail.state.data;
  const st = sourceState(s);
  const reload = () => {
    detail.reload(true);
    onChanged();
  };
  return (
    <>
      {back}
      <div className="detail-head">
        <div className="source-cell">
          <ConnectorBadge type={s.serviceType} />
          <div>
            <h2>{s.displayName}</h2>
            <p className="muted">
              <span className="mono">{s.name}</span> ·{" "}
              {connector(s.serviceType).label} ·{" "}
              <StatusBadge tone={stateTone(st)}>{STATE_LABEL[st]}</StatusBadge>
            </p>
          </div>
        </div>
        <Button
          variant={s.configured ? "secondary" : "primary"}
          onClick={() => onConfigure(s)}
        >
          {s.configured ? "配置连接与范围" : "继续配置"}
        </Button>
      </div>
      <div role="tablist" aria-label="数据源详情" className="tabs">
        {TABS.map(([k, label]) => (
          <button
            key={k}
            role="tab"
            aria-selected={tab === k}
            className={tab === k ? "active" : ""}
            onClick={() => setParams({ tab: k })}
          >
            {label}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        {tab === "overview" && <Overview s={s} reload={reload} />}
        {tab === "metadata" && <SourceCatalog source={s} />}
        {tab === "scope" && (
          <ScopeTab s={s} onConfigure={() => onConfigure(s)} />
        )}
        {tab === "tasks" && <SourceTasks source={s} onChanged={reload} />}
      </div>
    </>
  );
}
