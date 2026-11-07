import { useEffect, useId, useRef, useState } from "react";
import { Button, StatusBadge } from "@contexture/ui";
import type {
  ApiError,
  ServiceType,
  SourceDetail,
  SourceUpsert,
  TestConnectionResult,
} from "@contexture/ts-api";
import { ErrorBanner } from "../../components/ErrorBanner";
import {
  createSource,
  getTestConnection,
  startTestConnection,
  updateSource,
} from "./api";
import {
  CONNECTORS,
  connector,
  cronToTime,
  databaseOptional,
  invalidPattern,
  pipelineOf,
  splitPatterns,
  timeToCron,
  tlsOffered,
} from "./format";
import { asApiError } from "./useLoad";

const MASK = "*********";
const LEVELS = [
  ["databaseFilterPattern", "数据库"],
  ["schemaFilterPattern", "Schema"],
  ["tableFilterPattern", "表"],
] as const;
type Level = (typeof LEVELS)[number][0];
type Filters = Record<Level, { includes: string; excludes: string }>;

interface Draft {
  displayName: string;
  name: string;
  serviceType: ServiceType;
  host: string;
  port: string;
  database: string;
  username: string;
  password: string;
  tls: boolean;
  filters: Filters;
  includeViews: boolean;
  lineage: boolean;
  metaMode: "daily" | "manual";
  metaTime: string;
  lineageMode: "daily" | "manual";
  lineageTime: string;
}

function initial(source?: SourceDetail): Draft {
  const [host = "", port = ""] = (source?.connection.hostPort ?? "").split(
    /:(?=\d+$)/,
  );
  const meta = source && pipelineOf(source, "metadata");
  const lin = source && pipelineOf(source, "lineage");
  const filters = Object.fromEntries(
    LEVELS.map(([k]) => {
      const p = source?.scope[k] ?? null;
      return [
        k,
        {
          includes: (p?.includes ?? []).join(", "),
          excludes: (p?.excludes ?? []).join(", "),
        },
      ];
    }),
  ) as Filters;
  const type = source?.serviceType ?? "Mysql";
  return {
    displayName: source?.displayName ?? "",
    name: source?.name ?? "",
    serviceType: type,
    host,
    port: port || String(connector(type).port),
    database: source?.connection.database ?? "",
    username: source?.connection.username ?? "",
    password: source ? MASK : "",
    tls: !!source?.connection.tls,
    filters,
    includeViews: source?.scope.includeViews ?? true,
    lineage: source ? !!lin : false,
    metaMode: meta && !meta.schedule?.cron ? "manual" : "daily",
    metaTime: cronToTime(meta?.schedule?.cron) ?? "02:00",
    lineageMode: lin && !lin.schedule?.cron ? "manual" : "daily",
    lineageTime: cronToTime(lin?.schedule?.cron) ?? "03:00",
  };
}

function Field({
  label,
  help,
  full,
  children,
}: {
  label: string;
  help?: string;
  full?: boolean;
  children: (props: {
    id: string;
    "aria-describedby"?: string;
  }) => React.ReactNode;
}) {
  const id = useId();
  return (
    <div className={`field${full ? " full" : ""}`}>
      <label htmlFor={id}>{label}</label>
      {children({ id, "aria-describedby": help ? `${id}-help` : undefined })}
      {help && (
        <small className="help" id={`${id}-help`}>
          {help}
        </small>
      )}
    </div>
  );
}

const STEPS = ["选择连接器", "连接验证", "采集范围", "调度与确认"];
const POLL_MS = 1000;

export function SourceWizardModal({
  source,
  existingNames,
  onClose,
  onSaved,
}: {
  source?: SourceDetail;
  existingNames: string[];
  onClose: () => void;
  onSaved: (saved: SourceDetail) => void;
}) {
  const editing = !!source;
  const locked = editing && source.configured;
  const [d, setD] = useState<Draft>(() => initial(source));
  const [step, setStep] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<ApiError | null>(null);
  const [test, setTest] = useState<TestConnectionResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [testError, setTestError] = useState<ApiError | null>(null);
  const [saving, setSaving] = useState(false);
  const runId = useRef(0);
  useEffect(() => () => void (runId.current += 1), []);

  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => {
    setD((x) => ({ ...x, [k]: v }));
    setError(null);
    if (
      [
        "host",
        "port",
        "database",
        "username",
        "password",
        "tls",
        "serviceType",
      ].includes(k)
    ) {
      runId.current += 1;
      setTest(null);
      setTesting(false);
      setTestError(null);
    }
  };
  const tested =
    test?.status === "Successful" &&
    test.steps.every((s) => s.passed || !s.mandatory);
  const connection = () => ({
    hostPort: `${d.host.trim()}:${d.port.trim()}`,
    username: d.username.trim(),
    password: d.password,
    database: d.database.trim() || null,
    tls: tlsOffered(d.serviceType) && d.tls,
  });

  function validateConnection(): string | null {
    if (!/^[A-Za-z0-9.[\]:-]+$/.test(d.host.trim()))
      return "请输入有效的主机名或 IP 地址。";
    const port = Number(d.port);
    if (!Number.isInteger(port) || port < 1 || port > 65535)
      return "端口必须为 1–65535 的整数。";
    if (!databaseOptional(d.serviceType) && !d.database.trim())
      return d.serviceType === "Oracle"
        ? "请填写 Service Name。"
        : "请填写数据库名称。";
    if (!d.username.trim() || !d.password) return "请填写用户名与密码。";
    return null;
  }

  async function runTest() {
    const invalid = validateConnection();
    if (invalid) return setError(invalid);
    setError(null);
    const id = ++runId.current;
    setTesting(true);
    setTest(null);
    setTestError(null);
    try {
      let result = await startTestConnection({
        serviceName: editing ? d.name : null,
        serviceType: d.serviceType,
        connection: connection(),
      });
      while (
        id === runId.current &&
        result.status !== "Successful" &&
        result.status !== "Failed"
      ) {
        await new Promise((r) => setTimeout(r, POLL_MS));
        if (id !== runId.current) return;
        result = await getTestConnection(result.workflowId);
      }
      if (id === runId.current) setTest(result);
    } catch (e) {
      if (id === runId.current) setTestError(asApiError(e));
    } finally {
      if (id === runId.current) setTesting(false);
    }
  }

  function next() {
    if (step === 1) {
      if (!d.displayName.trim()) return setError("请填写数据源名称。");
      if (!/^[a-z][a-z0-9-]{1,49}$/.test(d.name))
        return setError(
          "服务标识需要 2–50 位小写字母、数字或连字符，以字母开头。",
        );
      if (d.name === "test-connection")
        return setError("test-connection 为保留名，请换一个名称。");
      if (!editing && existingNames.includes(d.name))
        return setError("服务标识已存在，请换一个名称。");
    }
    if (step === 2) {
      const invalid = validateConnection();
      if (invalid) return setError(invalid);
      if (!tested) return setError("请先完成连接测试，且必需步骤全部通过。");
    }
    if (step === 3) {
      for (const [k, label] of LEVELS)
        for (const part of ["includes", "excludes"] as const) {
          const bad = invalidPattern(splitPatterns(d.filters[k][part]));
          if (bad)
            return setError(`${label}过滤规则不是有效的正则表达式：${bad}`);
        }
    }
    setError(null);
    setStep(step + 1);
  }

  async function save() {
    const withLineage = d.lineage && d.includeViews;
    const body: SourceUpsert = {
      name: d.name,
      displayName: d.displayName.trim(),
      serviceType: d.serviceType,
      connection: connection(),
      scope: {
        ...Object.fromEntries(
          LEVELS.map(([k]) => [
            k,
            {
              includes: splitPatterns(d.filters[k].includes),
              excludes: splitPatterns(d.filters[k].excludes),
            },
          ]),
        ),
        includeViews: d.includeViews,
      },
      metadataSchedule: {
        cron: d.metaMode === "daily" ? timeToCron(d.metaTime) : null,
      },
      createLineageTask: withLineage,
      lineageSchedule: withLineage
        ? { cron: d.lineageMode === "daily" ? timeToCron(d.lineageTime) : null }
        : null,
    };
    setSaving(true);
    setSaveError(null);
    try {
      onSaved(
        editing ? await updateSource(d.name, body) : await createSource(body),
      );
    } catch (e) {
      setSaveError(asApiError(e));
    } finally {
      setSaving(false);
    }
  }

  const title = editing ? "配置数据源" : "添加数据源";
  const dbLabel =
    d.serviceType === "Oracle"
      ? "Service Name *"
      : databaseOptional(d.serviceType)
        ? "数据库（选填）"
        : "数据库 *";
  const withLineage = d.lineage && d.includeViews;
  return (
    <div className="modal-backdrop">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="modal wizard"
      >
        <header className="modal-head">
          <h2>{title}</h2>
          <Button variant="ghost" aria-label="关闭弹窗" onClick={onClose}>
            ×
          </Button>
        </header>
        <ol className="wizard-steps">
          {STEPS.map((s, i) => (
            <li
              key={s}
              className={step === i + 1 ? "active" : step > i + 1 ? "done" : ""}
            >
              <b>{step > i + 1 ? "✓" : i + 1}</b>
              {s}
            </li>
          ))}
        </ol>
        <div className="modal-body">
          {step === 1 && (
            <>
              <Field label="显示名称 *">
                {(p) => (
                  <input
                    {...p}
                    className="ctx-input"
                    maxLength={60}
                    value={d.displayName}
                    onChange={(e) => set("displayName", e.target.value)}
                    placeholder="例如：华东工厂 MES"
                  />
                )}
              </Field>
              <Field
                label="服务标识 *"
                help="用于稳定识别数据源，只能包含小写字母、数字和连字符。"
              >
                {(p) => (
                  <input
                    {...p}
                    className="ctx-input mono"
                    maxLength={50}
                    value={d.name}
                    readOnly={editing}
                    onChange={(e) => set("name", e.target.value)}
                    placeholder="例如：plant-mes"
                  />
                )}
              </Field>
              <h3>选择数据库连接器</h3>
              <div className="connector-grid">
                {CONNECTORS.map((c) => (
                  <button
                    key={c.type}
                    type="button"
                    className={`connector-card ${d.serviceType === c.type ? "active" : ""}`}
                    aria-pressed={d.serviceType === c.type}
                    disabled={locked && d.serviceType !== c.type}
                    onClick={() => {
                      set("serviceType", c.type);
                      set("port", String(c.port));
                    }}
                  >
                    <b>{c.label}</b> <small>数据库元数据</small>
                  </button>
                ))}
              </div>
            </>
          )}
          {step === 2 && (
            <>
              <div className="fields">
                <Field label="主机地址 *">
                  {(p) => (
                    <input
                      {...p}
                      className="ctx-input mono"
                      value={d.host}
                      onChange={(e) => set("host", e.target.value)}
                      placeholder="db.example.internal"
                    />
                  )}
                </Field>
                <Field label="端口 *">
                  {(p) => (
                    <input
                      {...p}
                      className="ctx-input mono"
                      inputMode="numeric"
                      value={d.port}
                      onChange={(e) => set("port", e.target.value)}
                    />
                  )}
                </Field>
                <Field
                  label={dbLabel}
                  help={
                    databaseOptional(d.serviceType)
                      ? "对应 OpenMetadata databaseSchema；留空表示全部库，范围也可在下一步用过滤规则设置。"
                      : undefined
                  }
                >
                  {(p) => (
                    <input
                      {...p}
                      className="ctx-input mono"
                      value={d.database}
                      onChange={(e) => set("database", e.target.value)}
                    />
                  )}
                </Field>
                <Field label="用户名 *">
                  {(p) => (
                    <input
                      {...p}
                      className="ctx-input mono"
                      value={d.username}
                      onChange={(e) => set("username", e.target.value)}
                    />
                  )}
                </Field>
                <Field
                  label="密码 *"
                  full
                  help={`由 OpenMetadata SecretsManager 加密存储，读取时脱敏${editing ? "；保持 ********* 表示不修改" : ""}。`}
                >
                  {(p) => (
                    <input
                      {...p}
                      className="ctx-input mono"
                      type="password"
                      value={d.password}
                      onChange={(e) => set("password", e.target.value)}
                    />
                  )}
                </Field>
              </div>
              {tlsOffered(d.serviceType) ? (
                <label className="checkrow">
                  <input
                    type="checkbox"
                    checked={d.tls}
                    onChange={(e) => set("tls", e.target.checked)}
                  />
                  启用 TLS 加密连接
                </label>
              ) : (
                <p className="help">
                  {d.serviceType === "Oracle"
                    ? "OpenMetadata 的 Oracle 连接器没有 TLS 选项。"
                    : `OpenMetadata 的 ${connector(d.serviceType).label} 连接器需上传 CA 证书才能启用 TLS，本期不提供。`}
                </p>
              )}
              <p className="notice">
                测试连接由 OpenMetadata
                在采集执行环境中逐步检查，只读取元数据目录，不读取业务记录。
              </p>
              <div className="row-end">
                <Button variant="secondary" onClick={runTest} busy={testing}>
                  {testing ? "测试中…" : "测试连接"}
                </Button>
              </div>
              {testing && (
                <p role="status">测试中，等待 OpenMetadata 返回检查结果…</p>
              )}
              {testError && <ErrorBanner error={testError} />}
              {test && (
                <div className="test-result">
                  <StatusBadge tone={tested ? "positive" : "warning"}>
                    {tested
                      ? "测试通过：必需步骤全部成功"
                      : "测试未通过：必需步骤未全部成功，无法继续"}
                  </StatusBadge>
                  <table aria-label="连接检查步骤">
                    <thead>
                      <tr>
                        <th>检查步骤</th>
                        <th>类型</th>
                        <th>结果</th>
                        <th>说明</th>
                      </tr>
                    </thead>
                    <tbody>
                      {test.steps.map((s) => (
                        <tr key={s.name}>
                          <td className="mono">{s.name}</td>
                          <td>{s.mandatory ? "必需" : "可选"}</td>
                          <td>
                            {s.passed === null
                              ? "未执行"
                              : s.passed
                                ? "通过"
                                : "失败"}
                          </td>
                          <td>{s.message ?? ""}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
          {step === 3 && (
            <>
              <p className="notice">
                按 OpenMetadata
                原生过滤规则（正则表达式，多个用逗号分隔）限定采集范围；全部留空即采集全部，后续新增的对象也会被采集。
              </p>
              {LEVELS.map(([k, label]) => (
                <div className="fields" key={k}>
                  {(["includes", "excludes"] as const).map((part) => (
                    <Field
                      label={`${label} · ${part === "includes" ? "包含" : "排除"}`}
                    >
                      {(p) => (
                        <input
                          {...p}
                          className="ctx-input mono"
                          value={d.filters[k][part]}
                          onChange={(e) =>
                            set("filters", {
                              ...d.filters,
                              [k]: { ...d.filters[k], [part]: e.target.value },
                            })
                          }
                        />
                      )}
                    </Field>
                  ))}
                </div>
              ))}
              <label className="checkrow">
                <input
                  type="checkbox"
                  checked={d.includeViews}
                  onChange={(e) => set("includeViews", e.target.checked)}
                />
                采集视图（视图元数据与视图定义）
              </label>
              <label className="checkrow">
                <input
                  type="checkbox"
                  checked={withLineage}
                  disabled={!d.includeViews}
                  onChange={(e) => set("lineage", e.target.checked)}
                />
                创建视图血缘任务（OpenMetadata lineage 采集）
              </label>
              <p className="help">
                视图血缘任务依据已采集的视图定义生成血缘，需同时采集视图；不处理查询日志血缘。
              </p>
              <div className="tags">
                <StatusBadge>表与字段元数据</StatusBadge>
                <StatusBadge>无数据采样</StatusBadge>
                <StatusBadge>无数据剖析</StatusBadge>
                <StatusBadge>不自动删除历史元数据</StatusBadge>
              </div>
            </>
          )}
          {step === 4 && (
            <>
              {(
                [
                  ["元数据采集", "metaMode", "metaTime"],
                  ...(withLineage
                    ? [["视图血缘", "lineageMode", "lineageTime"]]
                    : []),
                ] as [
                  string,
                  "metaMode" | "lineageMode",
                  "metaTime" | "lineageTime",
                ][]
              ).map(([label, mode, time]) => (
                <div className="fields" key={mode}>
                  <Field label={`${label} · 调度方式`}>
                    {(p) => (
                      <select
                        {...p}
                        value={d[mode]}
                        onChange={(e) =>
                          set(mode, e.target.value as "daily" | "manual")
                        }
                      >
                        <option value="daily">每天定时采集</option>
                        <option value="manual">仅手动触发</option>
                      </select>
                    )}
                  </Field>
                  <Field label={`${label} · 执行时间（Asia/Shanghai）`}>
                    {(p) => (
                      <input
                        {...p}
                        type="time"
                        className="ctx-input"
                        value={d[time]}
                        disabled={d[mode] === "manual"}
                        onChange={(e) => set(time, e.target.value)}
                      />
                    )}
                  </Field>
                </div>
              ))}
              {withLineage && (
                <p className="help">
                  视图血缘依赖已采集的视图定义，建议晚于元数据采集执行。
                </p>
              )}
              <section className="confirm">
                <h3>配置确认</h3>
                <dl className="kv">
                  <dt>数据源</dt>
                  <dd>
                    {d.displayName} · {connector(d.serviceType).label}
                  </dd>
                  <dt>目标数据库</dt>
                  <dd className="mono">{d.database || "全部库"}</dd>
                  <dt>采集范围</dt>
                  <dd>
                    {LEVELS.flatMap(([k, label]) => [
                      ...(splitPatterns(d.filters[k].includes).length
                        ? [
                            `${label}包含 ${splitPatterns(d.filters[k].includes).join(", ")}`,
                          ]
                        : []),
                      ...(splitPatterns(d.filters[k].excludes).length
                        ? [
                            `${label}排除 ${splitPatterns(d.filters[k].excludes).join(", ")}`,
                          ]
                        : []),
                    ]).join("；") || "全部（未设置过滤规则）"}
                    {" · "}
                    {d.includeViews ? "包含视图" : "不采集视图"}
                  </dd>
                  <dt>采集任务</dt>
                  <dd>
                    {withLineage
                      ? "元数据采集、视图血缘（2 个）"
                      : "元数据采集（1 个）"}
                  </dd>
                  <dt>调度执行</dt>
                  <dd>独立部署的 Airflow</dd>
                  <dt>结果写入</dt>
                  <dd>OpenMetadata 元数据目录</dd>
                </dl>
              </section>
              {saveError && <ErrorBanner error={saveError} />}
            </>
          )}
          {error && (
            <p role="alert" className="field-error">
              {error}
            </p>
          )}
        </div>
        <footer className="modal-foot">
          <span className="muted">
            步骤 {step} / {STEPS.length}
          </span>
          <div className="row">
            <Button
              variant="secondary"
              onClick={() => (step === 1 ? onClose() : setStep(step - 1))}
            >
              {step === 1 ? "取消" : "上一步"}
            </Button>
            {step < 4 ? (
              <Button onClick={next}>下一步</Button>
            ) : (
              <Button onClick={save} busy={saving}>
                保存配置
              </Button>
            )}
          </div>
        </footer>
      </div>
    </div>
  );
}
