"""经 AI 网关的 MCP 客户端（ADR-0013）。

以服务自己的 Keycloak 客户端身份做标准令牌交换（受众 = AI 网关），按人与受众缓存；
用 MCP SDK 的 Streamable HTTP 客户端调用工具，请求带 Bearer 令牌、traceparent 与 Baggage。
"""

import hashlib
import json
import time
from typing import Any

import httpx
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent
from opentelemetry import trace
from pydantic import BaseModel

from contexture_core import telemetry
from contexture_core.auth import RequestContext
from contexture_core.errors import ContextureError, InvalidToken, UpstreamUnavailable

TOKEN_EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"  # noqa: S105
ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"  # noqa: S105
MAX_LIMIT = 100

tracer = trace.get_tracer(__name__)


class TokenExchanger:
    """标准令牌交换（RFC 8693），结果缓存到过期前 ``skew_seconds``。"""

    def __init__(
        self,
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        http: httpx.AsyncClient | None = None,
        skew_seconds: int = 30,
    ) -> None:
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.http = http or telemetry.traced_client(timeout=10)
        self.skew = skew_seconds
        self._cache: dict[tuple[str, str], tuple[str, float]] = {}

    async def exchange(self, subject_token: str, audience: str) -> str:
        key = (hashlib.sha256(subject_token.encode()).hexdigest(), audience)
        cached = self._cache.get(key)
        now = time.monotonic()
        if cached and cached[1] > now:
            return cached[0]
        try:
            resp = await self.http.post(
                self.token_url,
                data={
                    "grant_type": TOKEN_EXCHANGE,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "subject_token": subject_token,
                    "subject_token_type": ACCESS_TOKEN_TYPE,
                    "audience": audience,
                },
            )
        except httpx.HTTPError as exc:
            raise UpstreamUnavailable("Keycloak 不可用", details={"upstream": "keycloak"}) from exc
        if resp.status_code >= 500:
            raise UpstreamUnavailable("Keycloak 不可用", details={"upstream": "keycloak"})
        if resp.status_code != 200:
            raise InvalidToken("令牌交换被拒绝")
        body = resp.json()
        token = str(body["access_token"])
        ttl = float(body.get("expires_in", 60)) - self.skew
        self._cache[key] = (token, now + max(ttl, 0))
        self._evict(now)
        return token

    def _evict(self, now: float) -> None:
        if len(self._cache) > 10_000:
            self._cache = {k: v for k, v in self._cache.items() if v[1] > now}


class Rows(BaseModel):
    """取数工具的结果（contracts/mcp/list_objects.yaml）。"""

    columns: list[str]
    rows: list[list[Any]]
    truncated: bool = False


def _rows_from_result(result: CallToolResult) -> Rows:
    if result.structured_content is not None:
        data: Any = result.structured_content
        if isinstance(data, dict) and "result" in data and len(data) == 1:
            data = data["result"]
    else:
        text = "".join(c.text for c in result.content if isinstance(c, TextContent))
        data = text if text.strip() else "[]"
    if isinstance(data, str):  # 如 Toolbox：以 JSON 文本返回对象数组
        data = json.loads(data)
    if isinstance(data, dict):
        return Rows.model_validate(data)
    if isinstance(data, list):
        records: list[dict[str, Any]] = [r for r in data if isinstance(r, dict)]
        columns = list(records[0].keys()) if records else []
        return Rows(columns=columns, rows=[[r.get(c) for c in columns] for r in records])
    raise ValueError("无法解析的工具结果")


class McpClient:
    def __init__(
        self,
        *,
        url: str,
        exchanger: TokenExchanger,
        audience: str,
        timeout_seconds: float = 30,
    ) -> None:
        self.url = url
        self.exchanger = exchanger
        self.audience = audience
        self.timeout = timeout_seconds

    async def call_tool(
        self, ctx: RequestContext, name: str, arguments: dict[str, Any]
    ) -> CallToolResult:
        with tracer.start_as_current_span(f"mcp.call_tool {name}") as span:
            span.set_attribute("mcp.tool.name", name)
            token = await self.exchanger.exchange(ctx.token, self.audience)
            headers = telemetry.inject_headers({"Authorization": f"Bearer {token}"})
            try:
                async with (
                    httpx2.AsyncClient(headers=dict(headers), timeout=self.timeout) as http,
                    Client(streamable_http_client(self.url, http_client=http)) as client,
                ):
                    result = await client.call_tool(name, arguments)
            except ContextureError:
                raise
            except Exception as exc:
                raise UpstreamUnavailable(
                    "AI 网关不可用", details={"upstream": "ai-gateway", "tool": name}
                ) from exc
            if result.is_error:
                raise UpstreamUnavailable("工具执行失败", details={"tool": name})
            return result

    async def call_rows(self, ctx: RequestContext, name: str, arguments: dict[str, Any]) -> Rows:
        result = await self.call_tool(ctx, name, arguments)
        try:
            return _rows_from_result(result)
        except ValueError as exc:
            raise UpstreamUnavailable("工具结果格式不符", details={"tool": name}) from exc

    async def list_objects(self, ctx: RequestContext, *, type_key: str, limit: int = 20) -> Rows:
        if not 1 <= limit <= MAX_LIMIT:
            raise ValueError(f"limit 须在 1–{MAX_LIMIT} 之间，实际为 {limit}")
        return await self.call_rows(ctx, "list_objects", {"type_key": type_key, "limit": limit})
