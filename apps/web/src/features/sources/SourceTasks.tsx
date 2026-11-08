import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import { Button, PageState, StatusBadge } from "@contexture/ui";
import type {
  ApiError,
  PipelineKind,
  PipelineRun,
  PipelineState,
  PipelineSummary,
  SourceDetail,
} from "@contexture/ts-api";
import { ErrorBanner } from "../../components/ErrorBanner";
import {
  getLastLogs,
  listRuns,
  setScheduleEnabled,
  triggerPipeline,
} from "./api";
import {
  KIND_LABEL,
  STATE_LABEL,
  cronLabel,
  formatDuration,
  formatTime,
  stateTone,
  taskState,
} from "./format";
import { asApiError, useLoad } from "./useLoad";
import { useInvalidateSources } from "./queries";

const RUN_FILTERS: [PipelineState | "", string][] = [
  ["", "全部状态"],
  ["success", "成功"],
  ["partialSuccess", "部分成功"],
  ["failed", "失败"],
  ["running", "采集中"],
  ["queued", "排队中"],
];
const POLL_MS = 5000;
const inFlight = (s?: PipelineState) => s === "queued" || s === "running";

function Modal({
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
          <span className="muted">OpenMetadata Ingestion · Airflow</span>
          <div className="row">
            <Button variant="secondary" onClick={onClose}>
              关闭
            </Button>
            {foot}
          </div>
        </footer>
      </div>
    </div>
  );
}

function RunDetail({
  source,
  task,
  run,
  latest,
  onClose,
  onRun,
}: {
  source: SourceDetail;
  task: PipelineSummary;
  run: PipelineRun;
  latest: boolean;
  onClose: () => void;
  onRun: () => void;
}) {
  // 运行未结束时 Airflow 3 读不到实时日志（只返回内部提示），结束后再读取
  const finished = !inFlight(run.pipelineState);
  const logs = useLoad(
    () =>
      latest && finished
        ? getLastLogs(source.name, task.kind)
        : Promise.resolve(null),
    [source.name, task.kind, latest, finished, run.runId],
  );
  const bad =
    run.pipelineState === "partialSuccess" || run.pipelineState === "failed";
  const failures = (run.steps ?? []).flatMap((s) => s.failures ?? []);
  return (
    <Modal
      title="运行详情"
      onClose={onClose}
      foot={bad ? <Button onClick={onRun}>立即运行</Button> : undefined}
    >
      <div className="panel-head">
        <div>
          <h3>
            {source.displayName} · {KIND_LABEL[task.kind]}
          </h3>
          <p className="mono muted">
            {task.name} · {run.runId}
          </p>
        </div>
        <StatusBadge tone={stateTone(run.pipelineState)}>
          {STATE_LABEL[run.pipelineState]}
        </StatusBadge>
      </div>
      <p className="muted">
        开始：{formatTime(run.startDate)} · 耗时：
        {formatDuration(run.startDate, run.endDate)}
      </p>
      {inFlight(run.pipelineState) ? (
        <p className="notice">
          {run.pipelineState === "queued"
            ? "已提交到 Airflow，等待调度。"
            : "运行中，完成后显示步骤统计。"}
        </p>
      ) : (
        <div className="table-scroll">
          <table className="data-table" aria-label="步骤统计">
            <thead>
              <tr>
                <th>步骤</th>
                <th>记录</th>
                <th>更新</th>
                <th>警告</th>
                <th>错误</th>
                <th>过滤</th>
              </tr>
            </thead>
            <tbody>
              {(run.steps ?? []).map((s) => (
                <tr key={s.name}>
                  <td className="mono">{s.name}</td>
                  <td>{s.records ?? 0}</td>
                  <td>{s.updatedRecords ?? 0}</td>
                  <td>{s.warnings ?? 0}</td>
                  <td>{s.errors ?? 0}</td>
                  <td>{s.filtered ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {failures.length > 0 && (
        <div className="alert warning">
          <b>失败对象</b>
          <ul>
            {failures.map((f, i) => (
              <li key={i}>
                <span className="mono">{f.name}</span>：{f.error}
              </li>
            ))}
          </ul>
          <p>
            其余对象已写入
            OpenMetadata。处理后点击“立即运行”重新运行；历史运行保留。
          </p>
        </div>
      )}
      {latest && !finished ? (
        <p className="help">运行结束后显示日志。</p>
      ) : latest ? (
        logs.state.status === "loading" ? (
          <p role="status">正在读取日志…</p>
        ) : logs.state.status === "error" ? (
          <ErrorBanner error={logs.state.error} />
        ) : (
          <pre className="log" aria-label="运行日志">
            {logs.state.data?.logs || "（OpenMetadata 未返回日志）"}
          </pre>
        )
      ) : (
        <p className="help">
          OpenMetadata 仅提供最近一次运行的日志；本次运行可查看状态与统计。
        </p>
      )}
    </Modal>
  );
}

function TaskRuns({
  source,
  task,
  onBack,
  onConfigure,
  onChanged,
}: {
  source: SourceDetail;
  task: PipelineSummary;
  onBack: () => void;
  onConfigure: () => void;
  onChanged: () => void;
}) {
  const [filter, setFilter] = useState<PipelineState | "">("");
  const runs = useLoad(
    () => listRuns(source.name, task.kind, filter || undefined),
    [source.name, task.kind, filter],
  );
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState<
    "confirm" | "dag" | { run: PipelineRun } | null
  >(null);
  const list = runs.state.status === "ready" ? runs.state.data : [];
  // 触发后到 OM 写入第一条状态之间列表可能为空：持续轮询，直到出现本次触发后的运行且结束（最长 10 分钟）
  const [awaitingSince, setAwaitingSince] = useState<number | null>(null);
  const newest = list[0];
  const awaiting =
    awaitingSince !== null &&
    Date.now() - awaitingSince < 600_000 &&
    !(
      newest &&
      (newest.startDate ?? 0) >= awaitingSince - 60_000 &&
      !inFlight(newest.pipelineState)
    );
  const running =
    awaiting ||
    inFlight(task.lastRun?.pipelineState) ||
    list.some((r) => inFlight(r.pipelineState));
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => {
      runs.reload(true);
      onChanged();
    }, POLL_MS);
    return () => clearInterval(t);
  }, [running]);
  // 运行由进行中变为结束：数据源列表与目录（含已展开的各层）全部失效，自动重新读取
  const invalidate = useInvalidateSources();
  const wasRunning = useRef(running);
  useEffect(() => {
    if (wasRunning.current && !running) void invalidate();
    wasRunning.current = running;
  }, [running, invalidate]);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      runs.reload(true);
      onChanged();
    } catch (e) {
      setError(asApiError(e));
    } finally {
      setBusy(false);
    }
  }
  const run = () =>
    act(async () => {
      await triggerPipeline(source.name, task.kind);
      setAwaitingSince(Date.now());
    }).then(() => setModal(null));
  const hasCron = !!task.schedule?.cron;
  const latestId =
    list.length && !filter ? list[0]!.runId : task.lastRun?.runId;
  return (
    <>
      <div className="panel-head">
        <div>
          <button className="link" onClick={onBack}>
            ← 返回采集任务
          </button>
          <h3>
            运行 · <span className="mono">{task.name}</span>
          </h3>
          <p className="muted">
            {KIND_LABEL[task.kind]} · {source.name} ·{" "}
            {cronLabel(task.schedule?.cron)}
            {hasCron && !task.scheduleEnabled ? "（已暂停）" : ""}
          </p>
        </div>
        <div className="row">
          {hasCron ? (
            <Button variant="secondary" onClick={() => setModal("confirm")}>
              {task.scheduleEnabled ? "暂停调度" : "恢复调度"}
            </Button>
          ) : (
            <Button
              variant="secondary"
              onClick={onConfigure}
              title="在“采集配置”中设置定时计划"
            >
              配置调度
            </Button>
          )}
          <Button onClick={run} disabled={running || busy} busy={busy}>
            立即运行
          </Button>
        </div>
      </div>
      {error && <ErrorBanner error={error} />}
      <section className="ctx-panel sources-panel">
        <div className="sources-toolbar">
          <select
            aria-label="筛选运行状态"
            value={filter}
            onChange={(e) => setFilter(e.target.value as PipelineState | "")}
          >
            {RUN_FILTERS.map(([v, t]) => (
              <option key={v} value={v}>
                {t}
              </option>
            ))}
          </select>
          <span className="spacer" />
          <span className="muted">{list.length} 次运行</span>
          <Button variant="ghost" onClick={() => runs.reload()}>
            刷新
          </Button>
        </div>
        {runs.state.status === "loading" ? (
          <PageState kind="loading" title="正在读取运行记录" />
        ) : runs.state.status === "error" ? (
          <PageState
            kind="error"
            title={runs.state.error.message}
            traceId={runs.state.error.trace_id}
            actionLabel="重试"
            action={() => runs.reload()}
          />
        ) : (
          <div className="table-scroll">
            <table className="sources-table" aria-label="运行记录">
              <thead>
                <tr>
                  <th>开始时间</th>
                  <th>状态</th>
                  <th>耗时</th>
                  <th>运行编号</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {list.map((r) => (
                  <tr key={r.runId}>
                    <td>{formatTime(r.startDate)}</td>
                    <td>
                      <StatusBadge tone={stateTone(r.pipelineState)}>
                        {STATE_LABEL[r.pipelineState]}
                      </StatusBadge>
                    </td>
                    <td>{formatDuration(r.startDate, r.endDate)}</td>
                    <td className="mono muted">{r.runId.slice(0, 8)}…</td>
                    <td>
                      <Button
                        variant="secondary"
                        onClick={() => setModal({ run: r })}
                      >
                        查看运行
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!list.length && (
              <div className="sources-empty">
                暂无运行记录。调整筛选，或点击“立即运行”。
              </div>
            )}
          </div>
        )}
        <div className="panel-foot">
          <span>OpenMetadata Ingestion · 独立 Airflow 调度</span>
          <Button variant="ghost" onClick={() => setModal("dag")}>
            调度详情
          </Button>
        </div>
      </section>
      {modal === "confirm" && (
        <Modal
          title={task.scheduleEnabled ? "暂停定时采集？" : "恢复定时采集？"}
          onClose={() => setModal(null)}
          foot={
            <Button
              busy={busy}
              onClick={() =>
                act(() =>
                  setScheduleEnabled(
                    source.name,
                    task.kind,
                    !task.scheduleEnabled,
                  ),
                ).then(() => setModal(null))
              }
            >
              {task.scheduleEnabled ? "确认暂停" : "确认恢复"}
            </Button>
          }
        >
          <p className="muted">
            {task.scheduleEnabled
              ? "暂停后不会触发新的定时采集，已有元数据和历史运行会保留，仍可手动立即运行。"
              : `恢复后按 ${cronLabel(task.schedule?.cron)}（Asia/Shanghai）执行。`}
          </p>
        </Modal>
      )}
      {modal === "dag" && (
        <Modal title="调度任务" onClose={() => setModal(null)}>
          <dl className="kv">
            <dt>DAG 标识</dt>
            <dd className="mono">{task.name}</dd>
            <dt>任务类型</dt>
            <dd>
              {KIND_LABEL[task.kind]}（{task.kind}）
            </dd>
            <dt>编排器</dt>
            <dd>独立部署的 Airflow</dd>
            <dt>执行器</dt>
            <dd>OpenMetadata Ingestion</dd>
            <dt>调度计划</dt>
            <dd>{cronLabel(task.schedule?.cron)} · Asia/Shanghai</dd>
            <dt>当前调度</dt>
            <dd>
              {!hasCron ? "手动触发" : task.scheduleEnabled ? "启用" : "已暂停"}
            </dd>
            <dt>已部署</dt>
            <dd>{task.deployed ? "是" : "否（OpenMetadata 记录）"}</dd>
          </dl>
        </Modal>
      )}
      {modal && typeof modal === "object" && (
        <RunDetail
          source={source}
          task={task}
          run={modal.run}
          latest={modal.run.runId === latestId}
          onClose={() => setModal(null)}
          onRun={run}
        />
      )}
    </>
  );
}

/** 采集任务页签（US2）：元数据采集与可选视图血缘两类任务，运行数据全部来自 OpenMetadata。 */
export function SourceTasks({
  source,
  onChanged,
}: {
  source: SourceDetail;
  onChanged: () => void;
}) {
  const [params, setParams] = useSearchParams();
  const kind = params.get("task") as PipelineKind | null;
  const task = source.pipelines.find((p) => p.kind === kind);
  if (!source.pipelines.length)
    return (
      <PageState
        kind="empty"
        title="尚未配置采集任务"
        description="先完成数据源连接与采集配置，再查看任务和运行记录。"
      />
    );
  if (task)
    return (
      <TaskRuns
        source={source}
        task={task}
        onBack={() => setParams({ tab: "tasks" })}
        onConfigure={() => setParams({ tab: "scope" })}
        onChanged={onChanged}
      />
    );
  return (
    <section className="ctx-panel sources-panel">
      <div className="sources-toolbar">
        <h3>采集任务</h3>
        <span className="spacer" />
        <StatusBadge>{source.pipelines.length} 个任务</StatusBadge>
      </div>
      <div className="table-scroll">
        <table className="sources-table" aria-label="采集任务">
          <thead>
            <tr>
              <th>任务名称</th>
              <th>类型</th>
              <th>调度计划</th>
              <th>最近运行</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {source.pipelines.map((p) => {
              const st = taskState(p);
              const open = () => setParams({ tab: "tasks", task: p.kind });
              return (
                <tr key={p.kind}>
                  <td>
                    <button className="link mono" onClick={open}>
                      {p.name}
                    </button>
                    <div className="cell-sub">OpenMetadata Ingestion</div>
                  </td>
                  <td>
                    {KIND_LABEL[p.kind]}
                    <div className="cell-sub">
                      {p.kind === "metadata"
                        ? "表、字段与视图元数据"
                        : "依据已采集的视图定义"}
                    </div>
                  </td>
                  <td>
                    {cronLabel(p.schedule?.cron)}
                    <div className="cell-sub">
                      {!p.schedule?.cron
                        ? "按需执行"
                        : p.scheduleEnabled
                          ? "Asia/Shanghai · 已启用"
                          : "定时调度已暂停"}
                    </div>
                  </td>
                  <td>
                    <StatusBadge tone={stateTone(st)}>
                      {STATE_LABEL[st]}
                    </StatusBadge>
                    <div className="cell-sub">
                      {formatTime(p.lastRun?.startDate)}
                    </div>
                  </td>
                  <td>
                    <Button variant="secondary" onClick={open}>
                      查看运行
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="panel-foot">
        <span>
          {source.pipelines.some((p) => p.kind === "lineage")
            ? "视图血缘依赖已采集的视图定义，建议安排在元数据采集之后。"
            : "未创建视图血缘任务；可在采集配置中开启。"}
        </span>
      </div>
    </section>
  );
}
