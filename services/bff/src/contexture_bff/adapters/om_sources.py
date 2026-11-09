"""005 源系统元数据采集：数据源、采集任务、运行、测试连接的 OM 适配（research R6–R9）。

全部经 OpenMetadata 公开 API、以登录用户的委托令牌调用（OmClient）；BFF 不连源库、不调 Airflow、
不写运行状态，
不内置任何示例数据（宪法 v2.2.0）。实体映射见 specs/005-source-metadata-ingestion/data-model.md。
"""

import asyncio
import re
import secrets
import string
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

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
            raise _invalid(
                f"OpenMetadata 的 {service_type} 连接器需上传 CA 证书才能启用 TLS，本期不提供"
            )
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


_SECRET_RE = re.compile(
    r"""(?i)(["']?(?:password|passwd|pwd|secret|token)["']?\s*[:=]\s*)(["']?)[^\s,;"'}]+\2"""
)


def redact(text: str) -> str:
    """日志脱敏（防御性）：密码、密钥、令牌类字段值替换为掩码。OM 采集框架本身已对凭证脱敏。"""
    return _SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{MASK}{m.group(2)}", text)


def _step_message(step: dict[str, Any]) -> str | None:
    """测试连接步骤说明：OM 的 message 优先；为空时用 diagnosis（标题：处理建议），
    再用 errorLog 首行。OM 2.0.3 实测可选步骤失败时 message 为 null（2026-11-08）。均脱敏。"""
    if step.get("message"):
        return redact(str(step["message"]))
    diagnosis = step.get("diagnosis") or {}
    if diagnosis.get("title"):
        parts = [diagnosis["title"], diagnosis.get("remediation")]
        return redact("：".join(str(p) for p in parts if p))
    log = str(step.get("errorLog") or "").strip()
    return redact(log.splitlines()[0]) if log else None


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


def latest_status(p: dict[str, Any]) -> dict[str, Any] | None:
    """OM 的 pipelineStatuses 是“最近执行记录”数组（ingestionPipeline.json:175），
    取开始时间最新的一条。"""
    runs: list[dict[str, Any]] = [
        r for r in p.get("pipelineStatuses") or [] if isinstance(r, dict) and r.get("runId")
    ]

    def started(r: dict[str, Any]) -> int:
        return int(r.get("startDate") or r.get("timestamp") or 0)

    return max(runs, key=started) if runs else None


def _pipeline_view(p: dict[str, Any]) -> dict[str, Any]:
    cron = (p.get("airflowConfig") or {}).get("scheduleInterval")
    last = latest_status(p)
    return {
        "kind": p["pipelineType"],
        "name": p["name"],
        "fullyQualifiedName": p["fullyQualifiedName"],
        "deployed": bool(p.get("deployed")),
        "schedule": {"cron": cron or None},
        # 手动任务无调度可启停；有 cron 时以 OM enabled 为准（toggleIngestion）
        "scheduleEnabled": bool(cron) and bool(p.get("enabled", True)),
        "lastRun": run_view(last) if last else None,
    }


class SourcesService:
    def __init__(
        self, om: OmClient, *, poll_interval: float = 1.0, settle_seconds: float = 20.0
    ) -> None:
        self.om = om
        self.poll_interval = poll_interval
        # Airflow 3 + managed-apis：部署后 DAG 先出现、任务稍后才由 dag-processor 登记；
        # 其间触发会得到
        # “无任务即成功”的空运行，OM 收不到任何状态（2026-11-08 实测，research R14）。
        # 触发前等待部署满此秒数
        self.settle_seconds = settle_seconds

    # ---------- 读取 ----------

    async def _paged(
        self, ctx: RequestContext, path: str, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
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
        """OM /tables 只能按 database / databaseSchema 过滤（TableResource），
        先按服务列出数据库再计数。"""
        databases = await self._paged(ctx, "/databases", {"service": service})
        tables: list[dict[str, Any]] = []
        for db in databases:
            tables += await self._paged(
                ctx, "/tables", {"database": db["fullyQualifiedName"], "fields": "columns"}
            )
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
            "connection": connection_view(
                svc["serviceType"], (svc.get("connection") or {}).get("config") or {}
            ),
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

    async def _put_service(
        self, ctx: RequestContext, req: dict[str, Any], existing: dict[str, Any] | None
    ) -> dict[str, Any]:
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
        config = (
            metadata_source_config(scope) if kind == "metadata" else lineage_source_config(scope)
        )
        body = {
            "name": existing["name"] if existing else pipeline_name(svc["name"], kind),
            "displayName": KIND_TITLE[kind],
            "pipelineType": _PIPELINE_TYPE[kind],
            "service": {"id": svc["id"], "type": "databaseService"},
            "sourceConfig": {"config": config},
            "airflowConfig": {"scheduleInterval": _cron(schedule), "pipelineTimezone": TIMEZONE},
        }
        method = "PUT" if existing else "POST"
        pipe = dict(
            await self.om.request(ctx, method, "/services/ingestionPipelines", json_body=body)
        )
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
            raise ContextureError(
                "source.name_conflict", f"服务标识 {req['name']} 已存在", status_code=409
            )
        svc = await self._put_service(ctx, req, None)
        scope = req.get("scope") or {}
        await self._put_pipeline(ctx, svc, "metadata", scope, req.get("metadataSchedule"), None)
        if req.get("createLineageTask"):
            await self._put_pipeline(ctx, svc, "lineage", scope, req.get("lineageSchedule"), None)
        return await self.get_source(ctx, req["name"])

    async def update_source(
        self, ctx: RequestContext, name: str, req: dict[str, Any]
    ) -> dict[str, Any]:
        existing = await self._service(ctx, name)
        if req["name"] != name or req["serviceType"] != existing["serviceType"]:
            raise ContextureError(
                "source.immutable_field",
                "服务标识与连接器类型不可修改，请新建数据源",
                status_code=400,
            )
        self._validate(req)
        svc = await self._put_service(ctx, req, existing)
        pipes = {p["pipelineType"]: p for p in await self._pipelines(ctx, name)}
        scope = req.get("scope") or {}
        await self._put_pipeline(
            ctx, svc, "metadata", scope, req.get("metadataSchedule"), pipes.get("metadata")
        )
        if req.get("createLineageTask"):
            await self._put_pipeline(
                ctx, svc, "lineage", scope, req.get("lineageSchedule"), pipes.get("lineage")
            )
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

    async def start_test_connection(
        self, ctx: RequestContext, req: dict[str, Any]
    ) -> dict[str, Any]:
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
        wf = await self.om.request(
            ctx, "GET", f"/automations/workflows/{workflow_id}", allow_404=True
        )
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
            if hit and (message := _step_message(hit)):
                step["message"] = message
            steps.append(step)
        await self.om.request(
            ctx,
            "DELETE",
            f"/automations/workflows/{workflow_id}",
            params={"hardDelete": "true"},
            allow_404=True,
        )
        return {"workflowId": workflow_id, "status": status, "steps": steps}

    # ---------- 运行（US2：FR-005） ----------

    async def list_runs(
        self, ctx: RequestContext, name: str, kind: str, state: str | None = None
    ) -> list[dict[str, Any]]:
        pipe = await self._pipeline(ctx, name, kind)
        page = await self.om.request(
            ctx,
            "GET",
            f"/services/ingestionPipelines/{pipe['fullyQualifiedName']}/pipelineStatus",
            params={"startTs": 0, "endTs": int(time.time() * 1000) + 86_400_000},
        )
        runs = [run_view(r) for r in (page or {}).get("data") or [] if r.get("runId")]
        runs.sort(key=lambda r: r.get("startDate") or 0, reverse=True)
        return [r for r in runs if not state or r["pipelineState"] == state]

    async def trigger(self, ctx: RequestContext, name: str, kind: str) -> None:
        pipe = await self._pipeline(ctx, name, kind)
        last = latest_status(pipe)
        if last and last.get("pipelineState") in ("queued", "running"):
            raise ContextureError(
                "source.pipeline_in_flight",
                "该任务已有排队中或运行中的运行，请勿重复触发",
                status_code=409,
            )
        deployed_ms = pipe.get("updatedAt")
        if isinstance(deployed_ms, int | float):
            wait = self.settle_seconds - (time.time() * 1000 - deployed_ms) / 1000
            if wait > 0:
                await asyncio.sleep(min(wait, self.settle_seconds))
        # 刚保存的任务需 Airflow 扫描登记 DAG（research R11），短时重试
        await self.trigger_when_ready(ctx, name, kind, timeout=20)

    async def set_schedule(
        self, ctx: RequestContext, name: str, kind: str, *, enabled: bool
    ) -> dict[str, Any]:
        pipe = await self._pipeline(ctx, name, kind)
        if not (pipe.get("airflowConfig") or {}).get("scheduleInterval"):
            raise ContextureError(
                "source.schedule_not_set",
                "该任务为手动触发，请先在采集配置中设置定时计划",
                status_code=400,
            )
        # 刚保存的任务在 Airflow 登记 DAG 前，OM 的 toggle 会因 Airflow 404 而不改状态（2026-11-08
        # 实测）；
        # 切换后以 OM 回读结果为准，未生效则在超时内重试，超时如实返回，不伪造已切换
        deadline = time.monotonic() + 20
        while bool(pipe.get("enabled", True)) != enabled:
            if time.monotonic() >= deadline:
                raise ContextureError(
                    "source.pipeline_not_ready",
                    "Airflow 尚未登记该任务，暂时无法切换调度，请稍后重试",
                    status_code=409,
                )
            await self.om.request(
                ctx, "POST", f"/services/ingestionPipelines/toggleIngestion/{pipe['id']}"
            )
            pipe = await self._pipeline(ctx, name, kind)
            if bool(pipe.get("enabled", True)) != enabled:
                await asyncio.sleep(self.poll_interval)
        return _pipeline_view(pipe)

    async def last_logs(self, ctx: RequestContext, name: str, kind: str) -> dict[str, Any]:
        """OM 只提供最近一次运行日志（DefaultLogStorage 忽略 runId，research R7）。"""
        pipe = await self._pipeline(ctx, name, kind)
        body = await self.om.request(
            ctx, "GET", f"/services/ingestionPipelines/logs/{pipe['id']}/last"
        )
        parts = [
            str(v)
            for k, v in (body or {}).items()
            if k not in ("total", "after") and isinstance(v, str)
        ]
        last = latest_status(pipe)
        return {"runId": last.get("runId") if last else None, "logs": redact("\n".join(parts))}

    async def _pipeline(self, ctx: RequestContext, name: str, kind: str) -> dict[str, Any]:
        await self._service(ctx, name)
        pipe = next(
            (p for p in await self._pipelines(ctx, name) if p["pipelineType"] == kind), None
        )
        if pipe is None:
            raise ContextureError(
                "source.not_found", f"数据源 {name} 没有{KIND_TITLE[kind]}任务", status_code=404
            )
        return pipe

    async def trigger_when_ready(
        self, ctx: RequestContext, name: str, kind: str, timeout: float = 60
    ) -> None:
        """部署后 Airflow 需扫描登记 DAG（research R11），登记前 OM 返回 400；在超时内重试。"""
        pipe = await self._pipeline(ctx, name, kind)
        deadline = time.monotonic() + timeout
        while True:
            try:
                await self.om.request(
                    ctx, "POST", f"/services/ingestionPipelines/trigger/{pipe['id']}"
                )
                return
            except ContextureError as exc:
                if exc.code != "upstream.rejected" or time.monotonic() >= deadline:
                    raise
                await asyncio.sleep(self.poll_interval)

    async def wait_for_run(
        self,
        ctx: RequestContext,
        name: str,
        kind: str,
        timeout: float = 600,
        after_run_id: str | None = None,
    ) -> dict[str, Any]:
        """等待最近一次运行结束；after_run_id 为触发前的最近运行，新运行登记前不把它当作结果。"""
        deadline = time.monotonic() + timeout
        while True:
            pipe = await self._pipeline(ctx, name, kind)
            last = latest_status(pipe) or {}
            fresh = after_run_id is None or last.get("runId") != after_run_id
            if fresh and last.get("pipelineState") in (
                "success",
                "partialSuccess",
                "failed",
                "stopped",
            ):
                return run_view(last)
            if time.monotonic() >= deadline:
                raise ContextureError(
                    "source.run_timeout", f"{name} 的{KIND_TITLE[kind]}运行超时", status_code=504
                )
            await asyncio.sleep(self.poll_interval)

    # ---------- US3 目录（OM 实体层级 DatabaseService → Database → DatabaseSchema → Table）
    # ----------
    async def _total(self, ctx: RequestContext, path: str, params: dict[str, Any]) -> int:
        page = await self.om.request(ctx, "GET", path, params={**params, "limit": 1})
        total = (page.get("paging") or {}).get("total")
        return int(total) if isinstance(total, int) else len(page.get("data") or [])

    async def _raw_entity(self, ctx: RequestContext, entity_type: str, fqn: str) -> dict[str, Any]:
        spec = CATALOG[entity_type]
        raw = await self.om.request(
            ctx,
            "GET",
            f"{spec['path']}/name/{quote(fqn, safe='')}",
            params={"fields": spec["fields"]},
            allow_404=True,
        )
        if raw is None or (
            entity_type == "databaseService" and raw.get("serviceType") not in SERVICE_TYPES
        ):
            raise ContextureError("catalog.not_found", f"目录中不存在 {fqn}", status_code=404)
        return dict(raw)

    async def _governance(
        self, ctx: RequestContext, entity_type: str, raw: dict[str, Any]
    ) -> dict[str, Any]:
        """本级单独设置的值优先；未设置时按 OM 继承规则（INHERIT）取最近一个单独设置的上级，
        并标注来源。"""
        g = governance_view(raw)
        g["inheritedFrom"] = {}
        missing = [f for f in INHERIT.get(entity_type, {}) if not g[f]]
        if not missing:
            return g
        chain = _ancestors(entity_type, raw["fullyQualifiedName"])
        cache: dict[str, dict[str, Any]] = {}
        for field in missing:
            for anc_type, anc_fqn in chain:
                if anc_type not in INHERIT[entity_type][field]:
                    continue
                if anc_fqn not in cache:
                    cache[anc_fqn] = governance_view(await self._raw_entity(ctx, anc_type, anc_fqn))
                if cache[anc_fqn][field]:
                    g[field] = cache[anc_fqn][field]
                    g["inheritedFrom"][field] = {
                        "entityType": anc_type,
                        "fullyQualifiedName": anc_fqn,
                    }
                    break
        return g

    async def governance_options(self, ctx: RequestContext) -> dict[str, Any]:
        """治理选项实时读取 OM；本期不创建治理实体。Tier / Certification 在 OM 中是独立属性，
        不列入分类标签。"""
        users, teams, domains, products, classes, terms = await asyncio.gather(
            self._paged(ctx, "/users", {"isBot": "false"}),
            self._paged(ctx, "/teams", {}),
            self._paged(ctx, "/domains", {}),
            self._paged(ctx, "/dataProducts", {"fields": "domains"}),
            self._paged(ctx, "/classifications", {}),
            self._paged(ctx, "/glossaryTerms", {}),
        )
        classes = [c for c in classes if c["name"] not in ("Tier", "Certification")]
        tags = await asyncio.gather(
            *(self._paged(ctx, "/tags", {"parent": c["name"]}) for c in classes)
        )
        return {
            "users": [_ref({**u, "type": "user"}) for u in users if not u.get("isBot")],
            # OM 只允许 Group 类型团队作为负责人
            "teams": [_ref({**t, "type": "team"}) for t in teams if t.get("teamType") == "Group"],
            "domains": [_ref({**d, "type": "domain"}) for d in domains],
            "dataProducts": [
                {
                    **_ref({**p, "type": "dataProduct"}),
                    "domains": [
                        _ref({**d, "type": d.get("type") or "domain"})
                        for d in p.get("domains") or []
                    ],
                }
                for p in products
            ],
            "classifications": [
                {
                    "name": c["name"],
                    "mutuallyExclusive": bool(c.get("mutuallyExclusive")),
                    "tags": [t["fullyQualifiedName"] for t in ts],
                }
                for c, ts in zip(classes, tags, strict=True)
            ],
            "glossaryTerms": [t["fullyQualifiedName"] for t in terms],
        }

    async def patch_catalog_entity(
        self, ctx: RequestContext, entity_type: str, fqn: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """治理属性 → OM JSON Patch。body 只含要改的字段；值为 None 表示清空（恢复继承）。"""
        raw = await self._raw_entity(ctx, entity_type, fqn)
        keys = set(body) - {"columnName"}
        column = body.get("columnName")
        base: dict[str, Any] = raw
        prefix = ""
        if column is not None:
            if entity_type != "table" or keys - COLUMN_FIELDS:
                raise _governance_error(
                    "governance.field_not_allowed",
                    "字段属性只能修改显示名称、描述、分类标签与业务术语",
                )
            idx = next(
                (i for i, c in enumerate(raw.get("columns") or []) if c["name"] == column), None
            )
            if idx is None:
                raise ContextureError(
                    "catalog.column_not_found", f"{fqn} 中不存在字段 {column}", status_code=404
                )
            base, prefix = raw["columns"][idx], f"/columns/{idx}"
        elif "retentionPeriod" in keys and entity_type == "databaseService":
            raise _governance_error("governance.field_not_allowed", "数据源不设置保留周期")
        await self._validate_governance(ctx, entity_type, raw, body, keys)

        ops: list[dict[str, Any]] = []
        for field in ("displayName", "description", "retentionPeriod"):
            if field in keys:
                if body[field] is None:
                    if base.get(field) is not None:
                        ops.append({"op": "remove", "path": f"{prefix}/{field}"})
                else:
                    ops.append({"op": "add", "path": f"{prefix}/{field}", "value": body[field]})
        for field, om_field in (("owners", "owners"), ("dataProducts", "dataProducts")):
            if field in keys:
                value = [{"id": r["id"], "type": r["type"]} for r in body[field] or []]
                ops.append({"op": "add", "path": f"/{om_field}", "value": value})
        if "domain" in keys:
            d = body["domain"]
            ops.append(
                {
                    "op": "add",
                    "path": "/domains",
                    "value": [{"id": d["id"], "type": d["type"]}] if d else [],
                }
            )
        if keys & {"tier", "tags", "glossaryTerms"}:
            ops.append(
                {
                    "op": "add",
                    "path": f"{prefix}/tags",
                    "value": _merge_tags(base.get("tags"), body, keys),
                }
            )
        if ops:
            await self.om.request(
                ctx, "PATCH", f"{CATALOG[entity_type]['path']}/{raw['id']}", patch=ops
            )
        return await self.get_catalog_entity(ctx, entity_type, raw["fullyQualifiedName"])

    async def _validate_governance(
        self,
        ctx: RequestContext,
        entity_type: str,
        raw: dict[str, Any],
        body: dict[str, Any],
        keys: set[str],
    ) -> None:
        if body.get("tier") is not None and not TIER.fullmatch(body["tier"]):
            raise _governance_error(
                "governance.invalid_tier", "分级（Tier）须为 Tier.Tier1–Tier.Tier5"
            )
        if body.get("retentionPeriod") is not None and not ISO_DURATION.fullmatch(
            body["retentionPeriod"]
        ):
            raise _governance_error(
                "governance.invalid_retention", "保留周期须为 ISO 8601 时长，例如 P30D 或 PT24H"
            )
        owners = body.get("owners") or []
        types = {o["type"] for o in owners}
        if owners and not (types == {"user"} or (types == {"team"} and len(owners) == 1)):
            raise _governance_error(
                "governance.owners_invalid", "负责人须为一名或多名用户，或单个团队"
            )
        by_class: dict[str, list[str]] = {}
        for tag in body.get("tags") or []:
            by_class.setdefault(tag.split(".", 1)[0], []).append(tag)
        for name, tags in by_class.items():
            if len(tags) > 1:
                cls = await self.om.request(
                    ctx, "GET", f"/classifications/name/{quote(name, safe='')}", allow_404=True
                )
                if cls and cls.get("mutuallyExclusive"):
                    raise _governance_error(
                        "governance.exclusive_tags",
                        f"分类 {name} 互斥，只能选择一个标签：{'、'.join(tags)}",
                    )
        if keys & {"domain", "dataProducts"}:
            products = body["dataProducts"] if "dataProducts" in keys else raw.get("dataProducts")
            if not products:
                return
            if "domain" in keys and body["domain"]:
                domain: str | None = body["domain"]["id"]
            else:
                current = await self._governance(
                    ctx,
                    entity_type,
                    {**raw, "domains": [] if "domain" in keys else raw.get("domains")},
                )
                domain = (current["domains"] or [{}])[0].get("id")
            catalog = {
                p["id"]: p for p in await self._paged(ctx, "/dataProducts", {"fields": "domains"})
            }
            for p in products:
                own = {d["id"] for d in (catalog.get(p["id"]) or {}).get("domains") or []}
                if domain not in own:
                    raise _governance_error(
                        "governance.domain_mismatch",
                        "数据产品与业务域不匹配，请调整业务域或数据产品",
                    )

    async def get_catalog_entity(
        self, ctx: RequestContext, entity_type: str, fqn: str
    ) -> dict[str, Any]:
        raw = await self._raw_entity(ctx, entity_type, fqn)
        out: dict[str, Any] = {
            "entityType": entity_type,
            "id": raw["id"],
            "name": raw["name"],
            "fullyQualifiedName": raw["fullyQualifiedName"],
            "governance": await self._governance(ctx, entity_type, raw),
        }
        rfqn = raw["fullyQualifiedName"]
        if entity_type == "databaseService":
            dbs = await self._paged(ctx, "/databases", {"service": rfqn})
            counts = await asyncio.gather(
                *(
                    self._total(ctx, "/databaseSchemas", {"database": d["fullyQualifiedName"]})
                    for d in dbs
                )
            )
            out["children"] = [_child("database", d, n) for d, n in zip(dbs, counts, strict=True)]
        elif entity_type == "database":
            schemas = await self._paged(ctx, "/databaseSchemas", {"database": rfqn})
            counts = await asyncio.gather(
                *(
                    self._total(ctx, "/tables", {"databaseSchema": x["fullyQualifiedName"]})
                    for x in schemas
                )
            )
            out["children"] = [
                _child("databaseSchema", x, n) for x, n in zip(schemas, counts, strict=True)
            ]
        elif entity_type == "databaseSchema":
            tables = await self._paged(
                ctx, "/tables", {"databaseSchema": rfqn, "fields": "columns"}
            )
            out["children"] = [_child("table", t, len(t.get("columns") or [])) for t in tables]
        else:
            out["table"] = table_view(raw)
        return out


KIND_TITLE = {"metadata": "元数据采集", "lineage": "视图血缘"}

CATALOG: dict[str, dict[str, str]] = {
    "databaseService": {
        "path": "/services/databaseServices",
        "fields": "owners,tags,domains,dataProducts",
    },
    "database": {"path": "/databases", "fields": "owners,tags,domains,dataProducts"},
    "databaseSchema": {"path": "/databaseSchemas", "fields": "owners,tags,domains,dataProducts"},
    "table": {
        "path": "/tables",
        "fields": "columns,tableConstraints,tags,owners,domains,dataProducts,schemaDefinition",
    },
}


def _child(entity_type: str, e: dict[str, Any], count: int) -> dict[str, Any]:
    return {
        "entityType": entity_type,
        "name": e["name"],
        "fullyQualifiedName": e["fullyQualifiedName"],
        "displayName": e.get("displayName"),
        "description": e.get("description"),
        "childCount": count,
    }


def _tag_fqns(tags: list[dict[str, Any]] | None, glossary: bool) -> list[str]:
    """OM 的标签与术语同存于 tags，按 source（Classification / Glossary）区分；Tier 单独展示。"""
    out = []
    for t in tags or []:
        fqn = t.get("tagFQN") or ""
        if (t.get("source") == "Glossary") == glossary and not fqn.startswith("Tier."):
            out.append(fqn)
    return out


# 006：开发态测试元数据标识（testdata/mockfactory/om_import/fixture.py 的 MARKER_FQN，research R12）
DEV_TEST_MARKER = "ContextureDevTest.DevTestMetadata"
# 数据安全级别：OM 分类「数据级别」下的标签（ADR-0008 第 2.4 节；tools/seed.py DATA_LEVEL）
DATA_LEVEL_PREFIX = "数据级别."


@dataclass(frozen=True)
class TagSplit:
    tier: str | None
    data_level: str | None
    origin: str  # collected | devTest
    glossary_terms: list[str]
    tags: list[str]


def split_tags(tags: list[dict[str, Any]] | None) -> TagSplit:
    """006 data-model 第 3 节：按 Tier、数据级别、开发态标识、业务术语、其余标签拆分 OM 的 tags。

    005 的属性编辑仍使用 governance_view（数据级别作为普通分类标签可编辑），行为不变。
    """
    tier = data_level = None
    origin = "collected"
    glossary: list[str] = []
    rest: list[str] = []
    for t in tags or []:
        fqn = t.get("tagFQN") or ""
        if t.get("source") == "Glossary":
            glossary.append(fqn)
        elif fqn.startswith("Tier."):
            tier = tier or fqn
        elif fqn.startswith(DATA_LEVEL_PREFIX):
            data_level = data_level or fqn
        elif fqn == DEV_TEST_MARKER:
            origin = "devTest"
        else:
            rest.append(fqn)
    return TagSplit(tier, data_level, origin, glossary, rest)


def _ref(r: dict[str, Any]) -> dict[str, Any]:
    return {
        k: r[k]
        for k in ("id", "type", "name", "displayName", "fullyQualifiedName")
        if r.get(k) is not None
    }


# 继承规则（OM 2.0.3 DatabaseRepository / DatabaseSchemaRepository /
# TableRepository.setInheritedFields）：
# 域 服务 → 库 → Schema → 表；负责人与保留周期 库 → Schema → 表（数据库不继承服务负责人）
_UP_TO_SERVICE = ("databaseService", "database", "databaseSchema")
_UP_TO_DATABASE = ("database", "databaseSchema")
INHERIT: dict[str, dict[str, tuple[str, ...]]] = {
    "database": {"domains": _UP_TO_SERVICE},
    "databaseSchema": {
        "domains": _UP_TO_SERVICE,
        "owners": _UP_TO_DATABASE,
        "retentionPeriod": _UP_TO_DATABASE,
    },
    "table": {
        "domains": _UP_TO_SERVICE,
        "owners": _UP_TO_DATABASE,
        "retentionPeriod": _UP_TO_DATABASE,
    },
}
COLUMN_FIELDS = {"displayName", "description", "tags", "glossaryTerms"}
TIER = re.compile(r"Tier\.Tier[1-5]")
# ISO 8601 时长：周单独使用，或 年月日 + T 时分秒（秒可带小数）
ISO_DURATION = re.compile(
    r"P\d+W|P(?=\d|T\d)(?:\d+Y)?(?:\d+M)?(?:\d+D)?(?:T(?=\d)(?:\d+H)?(?:\d+M)?(?:\d+(?:\.\d+)?S)?)?"
)
_LEVELS = ("databaseService", "database", "databaseSchema", "table")


def _governance_error(code: str, message: str) -> ContextureError:
    return ContextureError(code, message, status_code=400)


def _split_fqn(fqn: str) -> list[str]:
    """OM FQN：以点分隔，含点的名称以双引号包裹。"""
    parts, cur, quoted = [], "", False
    for ch in fqn:
        if ch == '"':
            quoted = not quoted
        if ch == "." and not quoted:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


split_fqn = _split_fqn  # 006 复用（om_assets）


def _ancestors(entity_type: str, fqn: str) -> list[tuple[str, str]]:
    """上级链（最近的在前）。"""
    parts = _split_fqn(fqn)
    depth = _LEVELS.index(entity_type)
    return [(_LEVELS[i], ".".join(parts[: i + 1])) for i in range(depth - 1, -1, -1)]


def _label(tag_fqn: str, source: str) -> dict[str, Any]:
    return {"tagFQN": tag_fqn, "source": source, "labelType": "Manual", "state": "Confirmed"}


def _merge_tags(
    current: list[dict[str, Any]] | None, body: dict[str, Any], keys: set[str]
) -> list[dict[str, Any]]:
    """OM 的 Tier、分类标签与术语同存于 tags；只替换本次修改的类别，其余标签原样保留。"""

    def category(t: dict[str, Any]) -> str:
        if t.get("source") == "Glossary":
            return "glossaryTerms"
        return "tier" if (t.get("tagFQN") or "").startswith("Tier.") else "tags"

    out = [t for t in current or [] if category(t) not in keys]
    if "tier" in keys and body["tier"]:
        out.append(_label(body["tier"], "Classification"))
    if "tags" in keys:
        out += [_label(t, "Classification") for t in body["tags"] or []]
    if "glossaryTerms" in keys:
        out += [_label(t, "Glossary") for t in body["glossaryTerms"] or []]
    return out


def governance_view(e: dict[str, Any]) -> dict[str, Any]:
    tier = next(
        (t["tagFQN"] for t in e.get("tags") or [] if (t.get("tagFQN") or "").startswith("Tier.")),
        None,
    )
    return {
        "displayName": e.get("displayName"),
        "description": e.get("description"),
        # OM 把继承得到的引用标为 inherited；这里只取本级单独设置的值，继承由 _governance
        # 计算并标注来源
        "owners": [_ref(r) for r in e.get("owners") or [] if not r.get("inherited")],
        "domains": [_ref(r) for r in e.get("domains") or [] if not r.get("inherited")],
        "tier": tier,
        "tags": _tag_fqns(e.get("tags"), glossary=False),
        "glossaryTerms": _tag_fqns(e.get("tags"), glossary=True),
        "dataProducts": [_ref(r) for r in e.get("dataProducts") or []],
        "retentionPeriod": e.get("retentionPeriod"),
    }


def table_view(t: dict[str, Any]) -> dict[str, Any]:
    """只读结构：只投影 OM 实际返回的类型、约束与字段，源未提供的不补造。"""
    return {
        "tableType": t.get("tableType"),
        "constraints": [
            {"constraintType": c.get("constraintType"), "columns": list(c.get("columns") or [])}
            for c in t.get("tableConstraints") or []
        ],
        "schemaDefinition": t.get("schemaDefinition"),
        "columns": [
            {
                "name": c["name"],
                "dataTypeDisplay": c.get("dataTypeDisplay") or c.get("dataType"),
                "constraint": c.get("constraint"),
                "displayName": c.get("displayName"),
                "description": c.get("description"),
                "tags": _tag_fqns(c.get("tags"), glossary=False),
                "glossaryTerms": _tag_fqns(c.get("tags"), glossary=True),
            }
            for c in t.get("columns") or []
        ],
    }
