"""以登录用户的委托令牌调用 OpenMetadata（005，research R5）。

- 令牌：用户令牌经 Keycloak 令牌交换收窄到受众 ``contexture-openmetadata``；OM 对非 bot 身份自动把密码脱敏，
  BFF 因此拿不到源库明文密码（FR-010）。
- 错误如实映射，不回退任何数据（宪法 v2.2.0）：连接失败与 5xx → ``upstream.unavailable``（502）；
  403 → ``auth.om_forbidden``；404 → ``upstream.not_found``（或 ``allow_404`` 时返回 None）；其他 4xx → ``upstream.rejected``，
  消息取 OM 原文。
- 防御：响应中任何 ``password`` 字段一律替换为掩码。
"""

import json
from typing import Any, Protocol

import httpx

from contexture_core import telemetry
from contexture_core.auth import RequestContext
from contexture_core.errors import ContextureError, UpstreamUnavailable

MASK = "*********"
OM_AUDIENCE = "contexture-openmetadata"


class Exchanger(Protocol):
    async def exchange(self, subject_token: str, audience: str) -> str: ...


def mask_passwords(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: MASK if k == "password" else mask_passwords(v) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_passwords(v) for v in value]
    return value


def _om_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:300] or f"HTTP {resp.status_code}"
    if isinstance(body, dict) and isinstance(body.get("message"), str):
        return str(body["message"])
    return resp.text[:300]


class OmClient:
    def __init__(
        self,
        *,
        om_url: str,
        exchanger: Exchanger,
        audience: str = OM_AUDIENCE,
        http: httpx.AsyncClient | None = None,
        timeout: float = 30,
    ) -> None:
        self.base = f"{om_url.rstrip('/')}/api/v1"
        self.exchanger = exchanger
        self.audience = audience
        self.http = http or telemetry.traced_client(timeout=timeout)

    async def request(
        self,
        ctx: RequestContext,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        patch: list[dict[str, Any]] | None = None,
        allow_404: bool = False,
    ) -> Any:
        token = await self.exchanger.exchange(ctx.token, self.audience)
        headers = {"Authorization": f"Bearer {token}"}
        content: bytes | None = None
        if patch is not None:
            headers["Content-Type"] = "application/json-patch+json"
            content = json.dumps(patch).encode()
        try:
            resp = await self.http.request(
                method,
                f"{self.base}{path}",
                params=params,
                json=json_body if patch is None else None,
                content=content,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise UpstreamUnavailable(
                "OpenMetadata 不可用", details={"upstream": "openmetadata"}
            ) from exc
        if resp.status_code >= 500:
            raise UpstreamUnavailable(
                "OpenMetadata 不可用", details={"upstream": "openmetadata", "status": resp.status_code}
            )
        if resp.status_code == 404:
            if allow_404:
                return None
            raise ContextureError("upstream.not_found", _om_message(resp), status_code=404)
        if resp.status_code in (401, 403):
            raise ContextureError(
                "auth.om_forbidden", _om_message(resp), status_code=403
            )
        if resp.status_code >= 400:
            raise ContextureError(
                "upstream.rejected", _om_message(resp), status_code=resp.status_code
            )
        if not resp.content:
            return None
        try:
            return mask_passwords(resp.json())
        except ValueError:
            return resp.text
