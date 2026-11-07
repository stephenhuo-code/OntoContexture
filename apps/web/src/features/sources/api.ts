// 005 数据源与目录接口封装：一律经 BFF（契约 contracts/openapi/bff.yaml）。
// 宪法 v2.2.0：错误原样抛出（含错误码与 trace_id），不得捕获后返回示例数据或伪造成功。
import type {
  CatalogEntity,
  CatalogEntityType,
  GovernanceOptions,
  GovernancePatch,
  PipelineKind,
  PipelineRun,
  PipelineState,
  PipelineSummary,
  SourceDetail,
  SourceSummary,
  SourceUpsert,
  TestConnectionResult,
  ServiceType,
  ConnectionInput,
} from "@contexture/ts-api";
import { ApiFailure, bff, toApiError } from "../../api";

type Call = Promise<{ data?: unknown; error?: unknown; response: Response }>;

async function unwrap<T>(call: Call, ok: number[] = [200]): Promise<T> {
  let result: Awaited<Call>;
  try {
    result = await call;
  } catch {
    throw new ApiFailure(0);
  }
  const { data, error, response } = result;
  if (!ok.includes(response.status))
    throw new ApiFailure(response.status, toApiError(error, response.status));
  return data as T;
}


export async function listSources(): Promise<SourceSummary[]> {
  const body = await unwrap<{ data: SourceSummary[] }>(
    bff.GET("/bff/v1/sources", { cache: "no-store" }),
  );
  return body.data;
}

export function getSource(name: string): Promise<SourceDetail> {
  return unwrap(
    bff.GET("/bff/v1/sources/{name}", {
      params: { path: { name } },
      cache: "no-store",
    }),
  );
}

export function createSource(body: SourceUpsert): Promise<SourceDetail> {
  return unwrap(bff.POST("/bff/v1/sources", { body }), [201]);
}

export function updateSource(
  name: string,
  body: SourceUpsert,
): Promise<SourceDetail> {
  return unwrap(
    bff.PUT("/bff/v1/sources/{name}", { params: { path: { name } }, body }),
  );
}

export function startTestConnection(body: {
  serviceName?: string;
  serviceType: ServiceType;
  connection: ConnectionInput;
}): Promise<TestConnectionResult> {
  return unwrap(bff.POST("/bff/v1/sources/test-connection", { body }), [202]);
}

export function getTestConnection(
  workflowId: string,
): Promise<TestConnectionResult> {
  return unwrap(
    bff.GET("/bff/v1/sources/test-connection/{workflowId}", {
      params: { path: { workflowId } },
      cache: "no-store",
    }),
  );
}

export async function listRuns(
  name: string,
  kind: PipelineKind,
  state?: PipelineState,
): Promise<PipelineRun[]> {
  const body = await unwrap<{ data: PipelineRun[] }>(
    bff.GET("/bff/v1/sources/{name}/pipelines/{kind}/runs", {
      params: { path: { name, kind }, query: state ? { state } : {} },
      cache: "no-store",
    }),
  );
  return body.data;
}

export async function triggerPipeline(
  name: string,
  kind: PipelineKind,
): Promise<void> {
  await unwrap(
    bff.POST("/bff/v1/sources/{name}/pipelines/{kind}/trigger", {
      params: { path: { name, kind } },
    }),
    [202],
  );
}

export function setScheduleEnabled(
  name: string,
  kind: PipelineKind,
  enabled: boolean,
): Promise<PipelineSummary> {
  return unwrap(
    bff.PUT("/bff/v1/sources/{name}/pipelines/{kind}/schedule", {
      params: { path: { name, kind } },
      body: { enabled },
    }),
  );
}

export function getLastLogs(
  name: string,
  kind: PipelineKind,
): Promise<{ runId?: string | null; logs: string }> {
  return unwrap(
    bff.GET("/bff/v1/sources/{name}/pipelines/{kind}/logs/last", {
      params: { path: { name, kind } },
      cache: "no-store",
    }),
  );
}

export function getCatalogEntity(
  entityType: CatalogEntityType,
  fqn: string,
): Promise<CatalogEntity> {
  return unwrap(
    bff.GET("/bff/v1/catalog/{entityType}/{fqn}", {
      params: { path: { entityType, fqn } },
      cache: "no-store",
    }),
  );
}

export function patchCatalogEntity(
  entityType: CatalogEntityType,
  fqn: string,
  body: GovernancePatch,
): Promise<CatalogEntity> {
  return unwrap(
    bff.PATCH("/bff/v1/catalog/{entityType}/{fqn}", {
      params: { path: { entityType, fqn } },
      body,
    }),
  );
}

export function getGovernanceOptions(): Promise<GovernanceOptions> {
  return unwrap(
    bff.GET("/bff/v1/governance/options", { cache: "no-store" }),
  );
}
