"""测试夹具：内存版 OpenMetadata（只实现 005 用到的公开接口子集，行为按 OM 2.0.3 源码核实）。

仅用于单元与契约测试；生产代码不含任何示例数据（宪法 v2.2.0）。集成测试使用真实 OM。
"""

import json
import re
import uuid
from typing import Any

import httpx

MASK = "*********"
TEST_STEPS = {
    "Mysql": [("CheckAccess", True), ("GetSchemas", True), ("GetTables", True), ("GetViews", False), ("GetQueries", False)],
    "Postgres": [("CheckAccess", True), ("GetDatabases", True), ("GetSchemas", True), ("GetTables", True), ("GetViews", False)],
    "Doris": [("CheckAccess", True), ("GetSchemas", True), ("GetTables", True), ("GetViews", False)],
    "Mssql": [("CheckAccess", True), ("GetDatabases", True), ("GetSchemas", True), ("GetTables", True), ("GetViews", False), ("GetQueries", False)],
    "Oracle": [("CheckAccess", True), ("PackageAccess", False), ("GetSchemas", True), ("GetTables", True), ("GetViews", False)],
}


def _mask(config: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(config))
    if "password" in out:
        out["password"] = MASK
    if isinstance(out.get("authType"), dict) and "password" in out["authType"]:
        out["authType"]["password"] = MASK
    return out


class FakeOM:
    def __init__(self) -> None:
        self.services: dict[str, dict[str, Any]] = {}
        self.secrets: dict[str, str] = {}  # 服务名 -> 明文密码（模拟 SecretsManager）
        self.pipelines: dict[str, dict[str, Any]] = {}  # id -> pipeline
        self.statuses: dict[str, list[dict[str, Any]]] = {}  # pipeline fqn -> runs（新到旧）
        self.workflows: dict[str, dict[str, Any]] = {}
        self.tables: list[dict[str, Any]] = []
        self.calls: list[tuple[str, str]] = []
        self.fail_deploy = False
        self.test_connection_ok = True
        self.down = False

    # ---------- 测试辅助 ----------
    def add_tables(self, service: str, database: str, schema: str, tables: dict[str, list[str]]) -> None:
        for name, cols in tables.items():
            self.tables.append(
                {
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "fullyQualifiedName": f"{service}.{database}.{schema}.{name}",
                    "service": {"name": service},
                    "columns": [{"name": c, "dataTypeDisplay": "varchar"} for c in cols],
                }
            )

    def add_run(self, pipeline_fqn: str, state: str, start: int, end: int | None = None) -> str:
        run_id = str(uuid.uuid4())
        self.statuses.setdefault(pipeline_fqn, []).insert(
            0,
            {
                "runId": run_id,
                "pipelineState": state,
                "startDate": start,
                "timestamp": start,
                "endDate": end,
                "status": [
                    {"name": "Mysql", "records": 15, "updated_records": 0, "warnings": 0, "errors": 0, "filtered": 0},
                    {"name": "OpenMetadata", "records": 15, "updated_records": 0, "warnings": 0, "errors": 0, "filtered": 0},
                ],
            },
        )
        return run_id

    def pipeline_by_name(self, name: str) -> dict[str, Any]:
        return next(p for p in self.pipelines.values() if p["name"] == name)

    # ---------- 传输 ----------
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, req: httpx.Request) -> httpx.Response:
        if self.down:
            return httpx.Response(503, text="down")
        path = req.url.path.removeprefix("/api/v1")
        self.calls.append((req.method, path))
        body = json.loads(req.content) if req.content else None
        q = dict(req.url.params)
        m = req.method

        if path == "/services/databaseServices" and m == "GET":
            return self._ok({"data": [self._service_view(s) for s in self.services.values()], "paging": {"total": len(self.services)}})
        if path == "/services/databaseServices" and m == "PUT":
            assert body is not None
            name = body["name"]
            cfg = body["connection"]["config"]
            pw = cfg.get("password") or (cfg.get("authType") or {}).get("password")
            if pw and pw != MASK:
                self.secrets[name] = pw
            existing = self.services.get(name)
            sid = existing["id"] if existing else str(uuid.uuid4())
            self.services[name] = {**(existing or {}), **body, "id": sid, "fullyQualifiedName": name}
            return self._ok(self._service_view(self.services[name]), 201 if not existing else 200)
        if mm := re.fullmatch(r"/services/databaseServices/name/(.+)", path):
            svc = self.services.get(mm.group(1))
            return self._ok(self._service_view(svc)) if svc else httpx.Response(404, json={"message": "not found"})

        if path == "/services/ingestionPipelines" and m == "GET":
            data = [p for p in self.pipelines.values() if not q.get("service") or p["service"]["name"] == q["service"]]
            return self._ok({"data": [self._pipeline_view(p) for p in data], "paging": {"total": len(data)}})
        if path == "/services/ingestionPipelines" and m in ("POST", "PUT"):
            assert body is not None
            svc = next(s for s in self.services.values() if s["id"] == body["service"]["id"])
            existing = next((p for p in self.pipelines.values() if p["name"] == body["name"]), None)
            pid = existing["id"] if existing else str(uuid.uuid4())
            fqn = f"{svc['name']}.{body['name']}"
            self.pipelines[pid] = {
                **body,
                "id": pid,
                "fullyQualifiedName": fqn,
                "service": {"id": svc["id"], "name": svc["name"], "type": "databaseService"},
                "deployed": existing["deployed"] if existing else False,
                "enabled": existing["enabled"] if existing else True,
            }
            return self._ok(self._pipeline_view(self.pipelines[pid]), 201)
        if mm := re.fullmatch(r"/services/ingestionPipelines/deploy/(.+)", path):
            if self.fail_deploy:
                return httpx.Response(400, json={"message": "Failed to deploy Ingestion Pipeline due to airflow API returned Internal Server Error"})
            self.pipelines[mm.group(1)]["deployed"] = True
            return self._ok({"code": 200, "reason": "deployed"})
        if mm := re.fullmatch(r"/services/ingestionPipelines/trigger/(.+)", path):
            p = self.pipelines[mm.group(1)]
            self.add_run(p["fullyQualifiedName"], "queued", 1_794_000_000_000)
            return self._ok({"code": 200})
        if mm := re.fullmatch(r"/services/ingestionPipelines/toggleIngestion/(.+)", path):
            p = self.pipelines[mm.group(1)]
            p["enabled"] = not p["enabled"]
            return self._ok(self._pipeline_view(p))
        if mm := re.fullmatch(r"/services/ingestionPipelines/logs/(.+)/last", path):
            return self._ok({"ingestion_task": "INFO 采集完成（测试夹具日志）", "total": "1"})
        if mm := re.fullmatch(r"/services/ingestionPipelines/(.+)/pipelineStatus", path):
            return self._ok({"data": list(self.statuses.get(mm.group(1), []))})
        if mm := re.fullmatch(r"/services/ingestionPipelines/(.+)", path):
            if m == "DELETE":
                self.pipelines.pop(mm.group(1), None)
                return self._ok({})
        if mm := re.fullmatch(r"/services/testConnectionDefinitions/name/(\w+)\.testConnectionDefinition", path):
            steps = TEST_STEPS[mm.group(1)]
            return self._ok({"steps": [{"name": n, "mandatory": mand} for n, mand in steps]})

        if path == "/automations/workflows" and m == "POST":
            assert body is not None
            wid = str(uuid.uuid4())
            self.workflows[wid] = {**body, "id": wid, "status": "Pending"}
            return self._ok(self.workflows[wid], 201)
        if mm := re.fullmatch(r"/automations/workflows/trigger/(.+)", path):
            wf = self.workflows[mm.group(1)]
            ctype = wf["request"]["connectionType"]
            steps = TEST_STEPS[ctype]
            if self.test_connection_ok:
                result = [{"name": n, "mandatory": mand, "passed": True} for n, mand in steps]
                wf["status"] = "Successful"
            else:
                result = [{"name": "CheckAccess", "mandatory": True, "passed": False, "message": "Access denied for user"}]
                wf["status"] = "Failed"
            wf["response"] = {"status": wf["status"], "steps": result}
            return self._ok({"code": 200})
        if mm := re.fullmatch(r"/automations/workflows/(.+)", path):
            wid = mm.group(1)
            if m == "DELETE":
                self.workflows.pop(wid, None)
                return self._ok({})
            wf = self.workflows.get(wid)
            return self._ok(wf) if wf else httpx.Response(404, json={"message": "not found"})

        if path == "/databases" and m == "GET":
            # OM：DatabaseResource 支持 service 过滤
            fqns = sorted({".".join(t["fullyQualifiedName"].split(".")[:2]) for t in self.tables
                           if t["service"]["name"] == q.get("service")})
            data = [{"name": f.split(".")[1], "fullyQualifiedName": f} for f in fqns]
            return self._ok({"data": data, "paging": {"total": len(data)}})
        if path == "/tables" and m == "GET":
            # OM：TableResource 只支持 database / databaseSchema 过滤，不支持 service
            assert "service" not in q, "OM /tables 不支持 service 过滤"
            db = q.get("database")
            data = [t for t in self.tables if t["fullyQualifiedName"].startswith(f"{db}.")]
            return self._ok({"data": data, "paging": {"total": len(data)}})
        return httpx.Response(404, json={"message": f"fake OM: {m} {path}"})

    def _service_view(self, svc: dict[str, Any]) -> dict[str, Any]:
        out = json.loads(json.dumps(svc))
        out["connection"] = {"config": _mask(svc["connection"]["config"])}
        return out

    def _pipeline_view(self, p: dict[str, Any]) -> dict[str, Any]:
        out = json.loads(json.dumps(p))
        runs = self.statuses.get(p["fullyQualifiedName"]) or []
        if runs:
            out["pipelineStatuses"] = runs[:5]  # OM：最近执行记录数组
        return out

    @staticmethod
    def _ok(body: Any, status: int = 200) -> httpx.Response:
        return httpx.Response(status, json=body)
