"""005 源系统元数据采集：数据源、采集任务、运行、测试连接的 OM 适配（research R6–R9）。

全部经 OpenMetadata 公开 API、以登录用户的委托令牌调用（OmClient）；BFF 不连源库、不调 Airflow、不写运行状态，
不内置任何示例数据（宪法 v2.2.0）。实体映射见 specs/005-source-metadata-ingestion/data-model.md。
"""

import asyncio
import re
import secrets
import string
import time
import uuid
from typing import Any

from contexture_bff.adapters.om_client import MASK, OmClient
from contexture_core.auth import RequestContext
from contexture_core.errors import ContextureError

RESERVED_NAMES = ("test-connection",)  # 与 /bff/v1/sources/test-connection 冲突
SERVICE_TYPES = ("Mysql", "Postgres", "Oracle", "Mssql", "Doris")
KINDS = ("metadata", "lineage")
TIMEZONE = "Asia/Shanghai"
PAGE = 1000
_PIPELINE_TYPE = {"metadata": "metadata", "lineage": "lineage"}


def _invalid(message: str) -> ContextureError:
    return ContextureError("source.invalid_request", message, status_code=400)


# ---------- 连接字段（research R9） ----------


def om_connection(service_type: str, conn: dict[str, Any]) -> dict[str, Any]:
    """织境连接输入 → OM 原生 connection.config；密码为掩码时原样传给 OM，由 OM 保留已存密码。"""
    database = (conn.get("database") or "").strip() or None
    tls = bool(conn.get("tls"))
    base: dict[str, Any] = {
        "type": service_type,
        "hostPort": str(conn["hostPort"]).strip(),
        "username": str(conn["username"]).strip(),
    }
    password = str(conn["password"])
    if service_type in ("Mysql", "Doris"):
        if tls:
            raise _invalid(f"OpenMetadata 的 {service_type} 连接器需上传 CA 证书才能启用 TLS，本期不提供")
        if service_type == "Mysql":
            base["authType"] = {"password": password}
        else:
            base["password"] = password
        if database:
            base["databaseSchema"] = database
        return base
    if not database:
        raise _invalid("Oracle 须填写 Service Name" if service_type == "Oracle" else "须填写数据库")
    if service_type == "Postgres":
        base["authType"] = {"password": password}
        base.update(database=database, ingestAllDatabases=False)
        if tls:
            base["sslMode"] = "require"
    elif service_type == "Mssql":
        base.update(password=password, database=database, ingestAllDatabases=False)
        if tls:
            base["encrypt"] = True
    else:  # Oracle
        if tls:
            raise _invalid("OpenMetadata 的 Oracle 连接器没有 TLS 选项")
        base.update(password=password, oracleConnectionType={"oracleServiceName": database})
    return base


def connection_view(service_type: str, config: dict[str, Any]) -> dict[str, Any]:
    """OM connection.config → 织境连接视图（密码恒为掩码）。"""
    if service_type in ("Mysql", "Doris"):
        database = config.get("databaseSchema")
    elif service_type == "Oracle":
        database = (config.get("oracleConnectionType") or {}).get("oracleServiceName")
    else:
        database = config.get("database")
    tls = config.get("sslMode") not in (None, "disable") or bool(config.get("encrypt"))
    return {
        "hostPort": config.get("hostPort", ""),
        "username": config.get("username", ""),
        "password": MASK,
        "database": database,
        "tls": tls,
    }


# ---------- 采集管道（research R8） ----------


def _pattern(value: Any, label: str) -> dict[str, list[str]] | None:
    if not isinstance(value, dict):
        return None
    out: dict[str, list[str]] = {}
    for key in ("includes", "excludes"):
        items = [str(p).strip() for p in value.get(key) or [] if str(p).strip()]
        for p in items:
            try:
                re.compile(p)
            except re.error as exc:
                raise _invalid(f"{label}过滤规则不是有效的正则表达式：{p}") from exc
        out[key] = items
    return out if out["includes"] or out["excludes"] else None


def metadata_source_config(scope: dict[str, Any]) -> dict[str, Any]:
    """元数据采集配置：过滤规则按请求，只读边界固定（不采样、不删历史、不覆盖人工属性）。"""
    cfg: dict[str, Any] = {
        "type": "DatabaseMetadata",
        "includeViews": bool(scope.get("includeViews", True)),
        "markDeletedTables": False,
        "overrideMetadata": False,
        "extractJsonSchema": False,
        "includeDDL": False,
    }
    for key, label in (
        ("databaseFilterPattern", "数据库"),
        ("schemaFilterPattern", "Schema "),
        ("tableFilterPattern", "表"),
    ):
        pattern = _pattern(scope.get(key), label.strip())
        if pattern:
            cfg[key] = pattern
    return cfg


def lineage_source_config(scope: dict[str, Any]) -> dict[str, Any]:
    """视图血缘：只处理视图定义，不处理查询日志与存储过程（默认均为 true，须显式关闭）。"""
    cfg: dict[str, Any] = {
        "type": "DatabaseLineage",
        "processViewLineage": True,
        "processQueryLineage": False,
        "processStoredProcedureLineage": False,
    }
    for key in ("databaseFilterPattern", "schemaFilterPattern", "tableFilterPattern"):
        pattern = _pattern(scope.get(key), "")
        if pattern:
            cfg[key] = pattern
    return cfg


def pipeline_name(service: str, kind: str) -> str:
    """OM 前端命名规则：<服务名>_<类型>_<8 位随机串>（ServicePureUtils.getIngestionName）。"""
    alphabet = string.ascii_letters + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"{re.sub(r'[^A-Za-z0-9]', '_', service)}_{kind}_{suffix}"


def _cron(schedule: dict[str, Any] | None) -> str | None:
    cron = (schedule or {}).get("cron")
    return str(cron).strip() or None if cron else None


def run_view(status: dict[str, Any]) -> dict[str, Any]:
    """OM PipelineStatus → PipelineRun（原样投影；OM 不记录触发方式）。"""
    steps = []
    for s in status.get("status") or []:
        steps.append(
            {
                "name": s.get("name", ""),
                "records": int(s.get("records") or 0),
                "updatedRecords": int(s.get("updated_records") or 0),
                "warnings": int(s.get("warnings") or 0),
                "errors": int(s.get("errors") or 0),
                "filtered": int(s.get("filtered") or 0),
                "failures": [
                    {"name": str(f.get("name", "")), "error": str(f.get("error", ""))}
                    for f in s.get("failures") or []
                ],
            }
        )
    return {
        "runId": str(status.get("runId", "")),
        "pipelineState": status.get("pipelineState", "queued"),
        "startDate": status.get("startDate"),
        "endDate": status.get("endDate"),
        "steps": steps,
    }


def _pipeline_view(p: dict[str, Any]) -> dict[str, Any]:
    cron = (p.get("airflowConfig") or {}).get("scheduleInterval")
    last = p.get("pipelineStatuses")
    return {
        "kind": p["pipelineType"],
        "name": p["name"],
        "fullyQualifiedName": p["fullyQualifiedName"],
        "deployed": bool(p.get("deployed")),
        "schedule": {"cron": cron or None},
        # 手动任务无调度可启停；有 cron 时以 OM enabled 为准（toggleIngestion）
        "scheduleEnabled": bool(cron) and bool(p.get("enabled", True)),
        "lastRun": run_view(last) if isinstance(last, dict) and last.get("runId") else None,
    }


class SourcesService:
    def __init__(self, om: OmClient, *, poll_interval: float = 1.0) -> None:
        self.om = om
        self.poll_interval = poll_interval

    # ---------- 读取 ----------

    async def _paged(self, ctx: RequestContext, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        after: str | None = None
        while True:
            q = {**params, "limit": PAGE, **({"after": after} if after else {})}
            page = await self.om.request(ctx, "GET", path, params=q)
            items += page.get("data") or []
            after = (page.get("paging") or {}).get("after")
            if not after:
                return items

    async def _pipelines(self, ctx: RequestContext, service: str) -> list[dict[str, Any]]:
        data = await self._paged(
            ctx,
            "/services/ingestionPipelines",
            {"service": service, "fields": "pipelineStatuses,sourceConfig,airflowConfig"},
        )
        by_kind: dict[str, dict[str, Any]] = {}
        for p in data:
            if p.get("pipelineType") in KINDS and p["pipelineType"] not in by_kind:
                by_kind[p["pipelineType"]] = p
        return [by_kind[k] for k in KINDS if k in by_kind]

    async def _counts(self, ctx: RequestContext, service: str) -> tuple[int, int]:
        tables = await self._paged(ctx, "/tables", {"service": service, "fields": "columns"})
        return len(tables), sum(len(t.get("columns") or []) for t in tables)

    async def _summary(self, ctx: RequestContext, svc: dict[str, Any]) -> dict[str, Any]:
        stype = svc["serviceType"]
        pipes = await self._pipelines(ctx, svc["name"])
        tables, columns = await self._counts(ctx, svc["name"])
        conn = connection_view(stype, (svc.get("connection") or {}).get("config") or {})
        return {
            "name": svc["name"],
            "displayName": svc.get("displayName") or svc["name"],
            "serviceType": stype,
            "database": conn["database"],
            "configured": any(p["pipelineType"] == "metadata" for p in pipes),
            "tableCount": tables,
            "columnCount": columns,
            "pipelines": [_pipeline_view(p) for p in pipes],
        }

    async def list_sources(self, ctx: RequestContext) -> list[dict[str, Any]]:
        services = await self._paged(ctx, "/services/databaseServices", {})
        supported = [s for s in services if s.get("serviceType") in SERVICE_TYPES]
        return list(await asyncio.gather(*(self._summary(ctx, s) for s in supported)))

    async def _service(self, ctx: RequestContext, name: str) -> dict[str, Any]:
        svc = await self.om.request(
            ctx,
            "GET",
            f"/services/databaseServices/name/{name}",
            params={"fields": "owners,domains,tags,dataProducts"},
            allow_404=True,
        )
        if svc is None or svc.get("serviceType") not in SERVICE_TYPES:
            raise ContextureError("source.not_found", f"数据源 {name} 不存在", status_code=404)
        return dict(svc)

    async def get_source(self, ctx: RequestContext, name: str) -> dict[str, Any]:
        svc = await self._service(ctx, name)
        summary = await self._summary(ctx, svc)
        pipes = await self._pipelines(ctx, name)
        meta = next((p for p in pipes if p["pipelineType"] == "metadata"), None)
        cfg = ((meta or {}).get("sourceConfig") or {}).get("config") or {}
        scope = {
            k: cfg[k]
            for k in ("databaseFilterPattern", "schemaFilterPattern", "tableFilterPattern")
            if isinstance(cfg.get(k), dict)
        }
        scope["includeViews"] = bool(cfg.get("includeViews", True))
        return {
            **summary,
            "description": svc.get("description") or "",
            "connection": connection_view(svc["serviceType"], (svc.get("connection") or {}).get("config") or {}),
            "scope": scope,
        }

    # ---------- 保存（FR-002 / FR-004） ----------

    def _validate(self, req: dict[str, Any]) -> None:
        if req["name"] in RESERVED_NAMES:
            raise _invalid(f"{req['name']} 为保留名，不可用作服务标识")
        if req["serviceType"] not in SERVICE_TYPES:
            raise _invalid(f"不支持的连接器：{req['serviceType']}")
        if req.get("createLineageTask") and not (req.get("scope") or {}).get("includeViews", True):
            raise _invalid("创建视图血缘任务需同时采集视图")
        metadata_source_config(req.get("scope") or {})

    async def _put_service(self, ctx: RequestContext, req: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": req["name"],
            "displayName": req["displayName"].strip(),
            "serviceType": req["serviceType"],
            "connection": {"config": om_connection(req["serviceType"], req["connection"])},
        }
        if existing and existing.get("description"):
            body["description"] = existing["description"]
        return dict(await self.om.request(ctx, "PUT", "/services/databaseServices", json_body=body))

    async def _put_pipeline(
        self,
        ctx: RequestContext,
        svc: dict[str, Any],
        kind: str,
        scope: dict[str, Any],
        schedule: dict[str, Any] | None,
        existing: dict[str, Any] | None,
    ) -> dict[str, Any]:
        config = metadata_source_config(scope) if kind == "metadata" else lineage_source_config(scope)
        body = {
            "name": existing["name"] if existing else pipeline_name(svc["name"], kind),
            "displayName": KIND_TITLE[kind],
            "pipelineType": _PIPELINE_TYPE[kind],
            "service": {"id": svc["id"], "type": "databaseService"},
            "sourceConfig": {"config": config},
            "airflowConfig": {"scheduleInterval": _cron(schedule), "pipelineTimezone": TIMEZONE},
        }
        method = "PUT" if existing else "POST"
        pipe = dict(await self.om.request(ctx, method, "/services/ingestionPipelines", json_body=body))
        try:
            await self.om.request(ctx, "POST", f"/services/ingestionPipelines/deploy/{pipe['id']}")
        except ContextureError as exc:
            if exc.code == "upstream.unavailable":
                raise
            raise ContextureError(
                "source.deploy_failed",
                exc.message,
                status_code=502,
                details={"pipeline": pipe["name"]},
            ) from exc
        return pipe

    async def create_source(self, ctx: RequestContext, req: dict[str, Any]) -> dict[str, Any]:
        self._validate(req)
        found = await self.om.request(
            ctx, "GET", f"/services/databaseServices/name/{req['name']}", allow_404=True
        )
        if found is not None:
            raise ContextureError("source.name_conflict", f"服务标识 {req['name']} 已存在", status_code=409)
        svc = await self._put_service(ctx, req, None)
        scope = req.get("scope") or {}
        await self._put_pipeline(ctx, svc, "metadata", scope, req.get("metadataSchedule"), None)
        if req.get("createLineageTask"):
            await self._put_pipeline(ctx, svc, "lineage", scope, req.get("lineageSchedule"), None)
        return await self.get_source(ctx, req["name"])

    async def update_source(self, ctx: RequestContext, name: str, req: dict[str, Any]) -> dict[str, Any]:
        existing = await self._service(ctx, name)
        if req["name"] != name or req["serviceType"] != existing["serviceType"]:
            raise ContextureError(
                "source.immutable_field", "服务标识与连接器类型不可修改，请新建数据源", status_code=400
            )
        self._validate(req)
        svc = await self._put_service(ctx, req, existing)
        pipes = {p["pipelineType"]: p for p in await self._pipelines(ctx, name)}
        scope = req.get("scope") or {}
        await self._put_pipeline(ctx, svc, "metadata", scope, req.get("metadataSchedule"), pipes.get("metadata"))
        if req.get("createLineageTask"):
            await self._put_pipeline(ctx, svc, "lineage", scope, req.get("lineageSchedule"), pipes.get("lineage"))
        elif "lineage" in pipes:
            # 关闭视图血缘任务：删除管道及其运行记录（OM 删除管道的原生行为）
            await self.om.request(
                ctx,
                "DELETE",
                f"/services/ingestionPipelines/{pipes['lineage']['id']}",
                params={"hardDelete": "true"},
            )
        return await self.get_source(ctx, name)

    # ---------- 测试连接（research R6） ----------

    async def start_test_connection(self, ctx: RequestContext, req: dict[str, Any]) -> dict[str, Any]:
        stype = req["serviceType"]
        if stype not in SERVICE_TYPES:
            raise _invalid(f"不支持的连接器：{stype}")
        request: dict[str, Any] = {
            "connection": {"config": om_connection(stype, req["connection"])},
            "serviceType": "Database",
            "connectionType": stype,
        }
        if req.get("serviceName"):
            request["serviceName"] = req["serviceName"]
        wf = await self.om.request(
            ctx,
            "POST",
            "/automations/workflows",
            json_body={
                "name": f"ctx-test-connection-{uuid.uuid4().hex[:12]}",
                "workflowType": "TEST_CONNECTION",
                "request": request,
            },
        )
        await self.om.request(ctx, "POST", f"/automations/workflows/trigger/{wf['id']}")
        return {"workflowId": wf["id"], "status": "Running", "steps": []}

    async def get_test_connection(self, ctx: RequestContext, workflow_id: str) -> dict[str, Any]:
        wf = await self.om.request(ctx, "GET", f"/automations/workflows/{workflow_id}", allow_404=True)
        if wf is None:
            raise ContextureError("source.not_found", "测试连接不存在或已结束", status_code=404)
        status = wf.get("status") or "Pending"
        if status not in ("Successful", "Failed"):
            return {"workflowId": workflow_id, "status": status, "steps": []}
        stype = wf["request"]["connectionType"]
        definition = await self.om.request(
            ctx, "GET", f"/services/testConnectionDefinitions/name/{stype}.testConnectionDefinition"
        )
        done = {s["name"]: s for s in (wf.get("response") or {}).get("steps") or []}
        steps = []
        for d in definition.get("steps") or []:
            hit = done.get(d["name"])
            step: dict[str, Any] = {
                "name": d["name"],
                "mandatory": bool(d.get("mandatory")),
                "passed": None if hit is None else bool(hit.get("passed")),
            }
            if hit and hit.get("message"):
                step["message"] = str(hit["message"])
            steps.append(step)
        await self.om.request(
            ctx, "DELETE", f"/automations/workflows/{workflow_id}", params={"hardDelete": "true"}, allow_404=True
        )
        return {"workflowId": workflow_id, "status": status, "steps": steps}

    # ---------- 运行（US2 在此扩展） ----------

    async def _pipeline(self, ctx: RequestContext, name: str, kind: str) -> dict[str, Any]:
        await self._service(ctx, name)
        pipe = next((p for p in await self._pipelines(ctx, name) if p["pipelineType"] == kind), None)
        if pipe is None:
            raise ContextureError("source.not_found", f"数据源 {name} 没有{KIND_TITLE[kind]}任务", status_code=404)
        return pipe

    async def trigger_when_ready(self, ctx: RequestContext, name: str, kind: str, timeout: float = 60) -> None:
        """部署后 Airflow 需扫描登记 DAG（research R11），登记前 OM 返回 400；在超时内重试。"""
        pipe = await self._pipeline(ctx, name, kind)
        deadline = time.monotonic() + timeout
        while True:
            try:
                await self.om.request(ctx, "POST", f"/services/ingestionPipelines/trigger/{pipe['id']}")
                return
            except ContextureError as exc:
                if exc.code != "upstream.rejected" or time.monotonic() >= deadline:
                    raise
                await asyncio.sleep(self.poll_interval)

    async def wait_for_run(self, ctx: RequestContext, name: str, kind: str, timeout: float = 600) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            pipe = await self._pipeline(ctx, name, kind)
            last = pipe.get("pipelineStatuses") or {}
            if last.get("pipelineState") in ("success", "partialSuccess", "failed", "stopped"):
                return run_view(last)
            if time.monotonic() >= deadline:
                raise ContextureError("source.run_timeout", f"{name} 的{KIND_TITLE[kind]}运行超时", status_code=504)
            await asyncio.sleep(self.poll_interval)


KIND_TITLE = {"metadata": "元数据采集", "lineage": "视图血缘"}
