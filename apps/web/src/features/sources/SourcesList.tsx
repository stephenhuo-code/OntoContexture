import { useMemo, useState } from "react";
import { Link } from "react-router";
import { Button, PageState, StatusBadge } from "@contexture/ui";
import type { SourceSummary } from "@contexture/ts-api";
import {
  STATE_LABEL,
  connector,
  cronLabel,
  formatDuration,
  formatTime,
  needsAttention,
  pipelineOf,
  schedulePaused,
  sourceState,
  stateTone,
} from "./format";
import type { Load } from "./useLoad";

const FILTERS = [
  ["", "全部状态"],
  ["success", "采集成功"],
  ["partial", "需要关注"],
  ["draft", "待配置"],
  ["paused", "调度已暂停"],
] as const;

export function ConnectorBadge({
  type,
}: {
  type: SourceSummary["serviceType"];
}) {
  const c = connector(type);
  return (
    <span
      className={`connector-badge connector-${type.toLowerCase()}`}
      aria-hidden="true"
    >
      {c.abbr}
    </span>
  );
}

function Stat({
  label,
  value,
  unit,
  note,
}: {
  label: string;
  value: number;
  unit: string;
  note: string;
}) {
  return (
    <div className="source-stat">
      <span>{label}</span>
      <b>{value}</b>
      <small>{unit}</small>
      <p>{note}</p>
    </div>
  );
}

export function SourcesList({
  state,
  reload,
  onAdd,
}: {
  state: Load<SourceSummary[]>;
  reload: () => void;
  onAdd: () => void;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<(typeof FILTERS)[number][0]>("");
  const sources = state.status === "ready" ? state.data : [];
  const shown = useMemo(
    () =>
      sources.filter((s) => {
        const text = [
          s.displayName,
          s.name,
          connector(s.serviceType).label,
          s.database ?? "",
        ]
          .join(" ")
          .toLowerCase();
        if (query && !text.includes(query.toLowerCase())) return false;
        if (filter === "paused") return schedulePaused(s);
        if (filter === "partial") return needsAttention(s);
        if (filter === "draft") return !s.configured;
        if (filter === "success") return sourceState(s) === "success";
        return true;
      }),
    [sources, query, filter],
  );

  const head = (
    <div className="sources-head">
      <div>
        <p className="eyebrow">DATA INGESTION</p>
        <p className="muted">从源系统到可信元数据，让每一张表都有来处。</p>
      </div>
      <Button onClick={onAdd}>
        <span aria-hidden="true">+</span> 添加数据源
      </Button>
    </div>
  );
  if (state.status === "loading")
    return (
      <>
        {head}
        <PageState kind="loading" title="正在读取数据源" />
      </>
    );
  if (state.status === "error")
    return (
      <>
        {head}
        <PageState
          kind="error"
          title={state.error.message}
          description={`错误码 ${state.error.code}`}
          traceId={state.error.trace_id}
          actionLabel="重试"
          action={reload}
        />
      </>
    );
  if (!sources.length)
    return (
      <>
        {head}
        <PageState
          kind="empty"
          title="还没有数据源"
          description="添加数据源并完成首次采集后，这里会显示采集状态与元数据统计。"
        />
      </>
    );

  const configured = sources.filter((s) => s.configured);
  const attention = sources.filter(needsAttention);
  return (
    <>
      {head}
      <section className="source-stats" aria-label="数据源汇总">
        <Stat
          label="已配置数据源"
          value={configured.length}
          unit={`/ ${sources.length}`}
          note="已创建元数据采集任务"
        />
        <Stat
          label="已采集表"
          value={configured.reduce((n, s) => n + s.tableCount, 0)}
          unit="张"
          note="来自 OpenMetadata 目录"
        />
        <Stat
          label="字段元数据"
          value={configured.reduce((n, s) => n + s.columnCount, 0)}
          unit="个"
          note="包含字段类型与业务注释"
        />
        <Stat
          label="需要关注"
          value={attention.length}
          unit="项"
          note={
            attention.length ? "存在部分成功或失败的采集" : "最近采集均已完成"
          }
        />
      </section>
      <section className="ctx-panel sources-panel">
        <div className="sources-toolbar">
          <input
            type="search"
            className="ctx-input"
            aria-label="搜索数据源"
            placeholder="搜索名称、服务标识、连接器或数据库"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select
            aria-label="按状态筛选"
            value={filter}
            onChange={(e) => setFilter(e.target.value as typeof filter)}
          >
            {FILTERS.map(([v, t]) => (
              <option key={v} value={v}>
                {t}
              </option>
            ))}
          </select>
          <span className="spacer" />
          <span className="muted">{sources.length} 个数据源</span>
          <Button
            variant="ghost"
            onClick={() => {
              setQuery("");
              setFilter("");
            }}
          >
            重置筛选
          </Button>
        </div>
        {shown.length ? (
          <div className="table-scroll">
            <table className="sources-table" aria-label="数据源列表">
              <thead>
                <tr>
                  <th>数据源 / 连接器</th>
                  <th>最近采集</th>
                  <th>元数据</th>
                  <th>调度</th>
                  <th>更新时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((s) => {
                  const st = sourceState(s);
                  const meta = pipelineOf(s, "metadata");
                  const run = meta?.lastRun;
                  return (
                    <tr key={s.name}>
                      <td>
                        <div className="source-cell">
                          <ConnectorBadge type={s.serviceType} />
                          <div>
                            <Link
                              to={`/sources/${s.name}`}
                              className="source-name"
                            >
                              {s.displayName}
                            </Link>
                            <div className="cell-sub">
                              {connector(s.serviceType).label} / {s.name}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <StatusBadge tone={stateTone(st)}>
                          {STATE_LABEL[st]}
                        </StatusBadge>
                        {needsAttention(s) && st === "success" && (
                          <div className="cell-sub">视图血缘需要关注</div>
                        )}
                      </td>
                      <td>
                        {s.configured ? (
                          <>
                            <div>{s.tableCount} 张表</div>
                            <div className="cell-sub">
                              {s.columnCount} 个字段
                            </div>
                          </>
                        ) : (
                          <>
                            <div>—</div>
                            <div className="cell-sub">尚未采集</div>
                          </>
                        )}
                      </td>
                      <td>
                        {!meta ? (
                          "—"
                        ) : meta.schedule?.cron && !meta.scheduleEnabled ? (
                          <StatusBadge>已暂停</StatusBadge>
                        ) : (
                          cronLabel(meta.schedule?.cron)
                        )}
                        {meta?.schedule?.cron && (
                          <div className="cell-sub">Asia/Shanghai</div>
                        )}
                      </td>
                      <td>
                        <div>{formatTime(run?.startDate)}</div>
                        <div className="cell-sub">
                          {formatDuration(run?.startDate, run?.endDate)}
                        </div>
                      </td>
                      <td>
                        <Link
                          className="ctx-button ctx-button--secondary"
                          to={`/sources/${s.name}`}
                        >
                          {s.configured ? "查看详情" : "继续配置"}
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="sources-empty">
            <h3>没有匹配的数据源</h3>
            <p className="muted">试试其他名称，或清除筛选条件。</p>
          </div>
        )}
        <div className="panel-foot">
          <span>采集结果统一写入 OpenMetadata</span>
          <span>独立 Airflow 调度</span>
        </div>
      </section>
      <div className="sources-bottom">
        <section className="notice-card">
          <h3>
            {attention.length
              ? `有 ${attention.length} 个数据源的采集需要处理`
              : "采集状态已更新"}
          </h3>
          <p>
            {attention.length
              ? `${attention.map((s) => s.displayName).join("、")}：最近一次运行部分成功或失败，已写入的元数据保留。`
              : "最近运行均已完成。可在数据源详情的采集任务中查看运行记录。"}
          </p>
          {attention[0] && (
            <Link to={`/sources/${attention[0].name}?tab=tasks`}>
              查看运行与日志 →
            </Link>
          )}
        </section>
        <section className="pipeline-strip">
          <h3>连接数据，保留数据边界</h3>
          <div className="flow">
            <span>源系统</span>
            <i>→</i>
            <span>OpenMetadata Ingestion</span>
            <i>→</i>
            <span>元数据目录</span>
          </div>
          <p className="muted">Airflow 编排采集任务 · 业务数据保留在源系统</p>
        </section>
      </div>
    </>
  );
}
