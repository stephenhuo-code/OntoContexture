// 005 展示规则：状态推导与格式化（data-model.md 第 3 节）。只做展示转换，不产生任何数据。
import type {
  CatalogEntityType,
  PipelineKind,
  PipelineState,
  PipelineSummary,
  ServiceType,
  SourceSummary,
} from "@contexture/ts-api";

export const CONNECTORS: {
  type: ServiceType;
  label: string;
  abbr: string;
  port: number;
}[] = [
  { type: "Mysql", label: "MySQL", abbr: "My", port: 3306 },
  { type: "Postgres", label: "PostgreSQL", abbr: "Pg", port: 5432 },
  { type: "Oracle", label: "Oracle", abbr: "Or", port: 1521 },
  { type: "Mssql", label: "SQL Server", abbr: "MS", port: 1433 },
  { type: "Doris", label: "Doris", abbr: "Do", port: 9030 },
];

export const connector = (type: ServiceType) =>
  CONNECTORS.find((c) => c.type === type) ?? CONNECTORS[0]!;

/** OM 原生：MySQL / Doris 的库为选填 databaseSchema；PostgreSQL / SQL Server 必填 database；Oracle 用 Service Name */
export const databaseOptional = (type: ServiceType) =>
  type === "Mysql" || type === "Doris";
/** OM 原生 TLS：PostgreSQL sslMode、SQL Server encrypt；MySQL / Doris 需证书、Oracle 无此项（本期不提供） */
export const tlsOffered = (type: ServiceType) =>
  type === "Postgres" || type === "Mssql";

export const KIND_LABEL: Record<PipelineKind, string> = {
  metadata: "元数据采集",
  lineage: "视图血缘",
};

export type UiState = PipelineState | "draft" | "pending";

export const STATE_LABEL: Record<UiState, string> = {
  success: "成功",
  partialSuccess: "部分成功",
  failed: "失败",
  running: "采集中",
  queued: "排队中",
  stopped: "已停止",
  draft: "待配置",
  pending: "待首次采集",
};

export const stateTone = (s: UiState): "positive" | "warning" | "neutral" =>
  s === "success"
    ? "positive"
    : s === "partialSuccess" || s === "failed"
      ? "warning"
      : "neutral";

export const pipelineOf = (s: SourceSummary, kind: PipelineKind) =>
  s.pipelines.find((p) => p.kind === kind);

/** 数据源状态：未配置为“待配置”；有任务未运行为“待首次采集”；否则为元数据采集最近一次运行状态 */
export function sourceState(s: SourceSummary): UiState {
  if (!s.configured) return "draft";
  const meta = pipelineOf(s, "metadata");
  return meta?.lastRun?.pipelineState ?? "pending";
}

export function taskState(p: PipelineSummary): UiState {
  return p.lastRun?.pipelineState ?? "pending";
}

export const needsAttention = (s: SourceSummary) =>
  s.pipelines.some((p) =>
    ["partialSuccess", "failed"].includes(p.lastRun?.pipelineState ?? ""),
  );

export const schedulePaused = (s: SourceSummary) =>
  s.pipelines.some((p) => !!p.schedule?.cron && !p.scheduleEnabled);

/** cron（分 时 * * *）→ “每天 HH:MM”；空为“手动触发”；其他 cron 原样显示 */
export function cronLabel(cron?: string | null): string {
  if (!cron) return "手动触发";
  const m = /^(\d{1,2}) (\d{1,2}) \* \* \*$/.exec(cron.trim());
  if (!m) return cron;
  return `每天 ${m[2]!.padStart(2, "0")}:${m[1]!.padStart(2, "0")}`;
}

export function timeToCron(hhmm: string): string {
  const [h, m] = hhmm.split(":").map(Number);
  return `${m} ${h} * * *`;
}

export function cronToTime(cron?: string | null): string | null {
  const m = cron ? /^(\d{1,2}) (\d{1,2}) \* \* \*$/.exec(cron.trim()) : null;
  return m ? `${m[2]!.padStart(2, "0")}:${m[1]!.padStart(2, "0")}` : null;
}

const timeFmt = new Intl.DateTimeFormat("zh-CN", {
  timeZone: "Asia/Shanghai",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

export const formatTime = (ms?: number | null) =>
  ms ? timeFmt.format(new Date(ms)) : "—";

export function formatDuration(start?: number | null, end?: number | null) {
  if (!start || !end || end < start) return "—";
  const sec = Math.round((end - start) / 1000);
  if (sec < 60) return `${sec} 秒`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return s ? `${m} 分 ${s} 秒` : `${m} 分`;
}

export const splitPatterns = (text: string) =>
  text
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);

export function invalidPattern(patterns: string[]): string | null {
  for (const p of patterns) {
    try {
      new RegExp(p);
    } catch {
      return p;
    }
  }
  return null;
}

// ---------- US3 目录 ----------

export const KIND_NAME: Record<CatalogEntityType, string> = {
  databaseService: "数据源",
  database: "数据库",
  databaseSchema: "Schema",
  table: "数据表",
};

export const CHILD_TYPE: Partial<Record<CatalogEntityType, CatalogEntityType>> =
  {
    databaseService: "database",
    database: "databaseSchema",
    databaseSchema: "table",
  };

export const LEVELS: CatalogEntityType[] = [
  "databaseService",
  "database",
  "databaseSchema",
  "table",
];

/** 按 OM FQN 规则切分：以点分隔，含点的名称用双引号包裹（保留原始片段以便重新拼接） */
export function splitFqn(fqn: string): string[] {
  const parts: string[] = [];
  let cur = "";
  let quoted = false;
  for (const ch of fqn) {
    if (ch === '"') quoted = !quoted;
    if (ch === "." && !quoted) {
      parts.push(cur);
      cur = "";
    } else cur += ch;
  }
  parts.push(cur);
  return parts;
}

export const fqnLabel = (part: string) => part.replace(/^"(.*)"$/, "$1");

/** 006 D1：数据源管理在 /assets/sources 下，库 / Schema / 表详情在 /assets/{类型}/{fqn} 下 */
export const SOURCES_BASE = "/assets/sources";
export const sourceHref = (service: string) => `${SOURCES_BASE}/${service}`;

export const assetHref = (
  service: string,
  type: CatalogEntityType,
  fqn: string,
) =>
  type === "databaseService"
    ? sourceHref(service)
    : `/assets/${type}/${encodeURIComponent(fqn)}`;

/** 当前地址对应的目录层级链（从服务到当前资产），用于展开目录树与面包屑 */
export function assetChain(type: CatalogEntityType, fqn: string) {
  const parts = splitFqn(fqn);
  const depth = LEVELS.indexOf(type);
  return LEVELS.slice(0, depth + 1).map((t, i) => ({
    type: t,
    fqn: parts.slice(0, i + 1).join("."),
    label: fqnLabel(parts[i] ?? ""),
  }));
}

/** OM 继承规则：域 服务→库→Schema→表；负责人与保留周期 库→Schema→表（数据库不继承服务负责人） */
export const INHERITABLE: Record<CatalogEntityType, string[]> = {
  databaseService: [],
  database: ["domains"],
  databaseSchema: ["domains", "owners", "retentionPeriod"],
  table: ["domains", "owners", "retentionPeriod"],
};

/**
 * 采集范围逐层说明（按 OM 2.0.3 连接器核实：MySQL / Doris / Oracle 的数据库层取默认名 default，
 * 见 common_db_source.get_database_names；PostgreSQL / SQL Server 为连接时填写的数据库）。
 * 匹配方式为 OM filters._filter 的 re.match + IGNORECASE。
 */
export function scopeHelp(type: ServiceType): {
  rule: string;
  databaseFilterPattern: string;
  schemaFilterPattern: string;
  tableFilterPattern: string;
} {
  const physical = type === "Mysql" || type === "Doris";
  return {
    rule: "正则从名称开头匹配、不区分大小写；精确匹配写 ^名称$，多个规则用英文逗号分隔。包含留空表示全部；同时命中包含与排除时不采集。",
    databaseFilterPattern:
      physical || type === "Oracle"
        ? `${connector(type).label} 的数据库层在 OpenMetadata 中固定为 default，一般不用填写。`
        : "即连接时填写的数据库，一般不用填写。",
    schemaFilterPattern: physical
      ? `即 ${connector(type).label} 的物理库，例如只采 mes 写 ^mes$。`
      : type === "Oracle"
        ? "即 Oracle 的用户 Schema，例如 ^QMS$。"
        : type === "Mssql"
          ? "例如只采 dbo 写 ^dbo$。"
          : "例如只采 public 写 ^public$（OpenMetadata 默认也会采集 information_schema）。",
    tableFilterPattern: "表或视图名，例如排除临时表与备份表写 ^tmp_, _bak$。",
  };
}
