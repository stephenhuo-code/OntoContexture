"""织境登录时在 OpenMetadata 建档用户并同步团队成员（005，research R13）。

OM 的 API 调用不建档、不按令牌声明入组（只有 OM 自身界面登录才会），因此由 BFF 在织境登录回调与会话刷新时：
- 以 ``contexture-bff`` 服务账号（client credentials；OM 中为普通用户，角色 ContextureUserProvisioner）调用 OM；
- 用户不存在则创建（用户名 = preferred_username）；
- 按令牌中的织境角色计算应在的团队（admin、ai-engineer），加入应在的、移出不应在的；已一致时不写。
OM 或 Keycloak 不可用时抛出 ``upstream.unavailable``，登录失败，不静默跳过。
"""

import json
import time
from collections.abc import Iterable
from typing import Any

import httpx

from contexture_core import telemetry
from contexture_core.errors import ContextureError, UpstreamUnavailable

TEAMS = ("admin", "ai-engineer")
EMAIL_DOMAIN = "contexture.local"  # 与 OM authorizer.principalDomain 一致


class OmUserSync:
    def __init__(
        self,
        *,
        om_url: str,
        token_url: str,
        client_id: str,
        client_secret: str,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.base = f"{om_url.rstrip('/')}/api/v1"
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.http = http or telemetry.traced_client(timeout=15)
        self._token: tuple[str, float] | None = None

    async def _service_token(self) -> str:
        if self._token and self._token[1] > time.monotonic():
            return self._token[0]
        try:
            resp = await self.http.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
        except httpx.HTTPError as exc:
            raise UpstreamUnavailable("Keycloak 不可用", details={"upstream": "keycloak"}) from exc
        if resp.status_code != 200:
            raise UpstreamUnavailable("无法取得 BFF 服务账号令牌", details={"upstream": "keycloak"})
        body = resp.json()
        self._token = (str(body["access_token"]), time.monotonic() + float(body.get("expires_in", 60)) - 30)
        return self._token[0]

    async def _call(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        token = await self._service_token()
        headers = {"Authorization": f"Bearer {token}", **kwargs.pop("headers", {})}
        try:
            resp = await self.http.request(method, f"{self.base}{path}", headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise UpstreamUnavailable("OpenMetadata 不可用", details={"upstream": "openmetadata"}) from exc
        if resp.status_code >= 500:
            raise UpstreamUnavailable("OpenMetadata 不可用", details={"upstream": "openmetadata"})
        return resp

    async def _ensure_user(self, username: str, *, create: bool) -> str | None:
        resp = await self._call("GET", f"/users/name/{username}")
        if resp.status_code == 404:
            if not create:
                return None
            resp = await self._call(
                "POST", "/users", json={"name": username, "email": f"{username}@{EMAIL_DOMAIN}"}
            )
        if resp.status_code >= 400:
            raise ContextureError(
                "auth.om_provision_failed", f"无法在 OpenMetadata 中建档用户 {username}", status_code=502
            )
        return str(resp.json()["id"])

    async def sync(self, username: str, roles: Iterable[str]) -> None:
        wanted = set(roles) & set(TEAMS)
        # 无织境角色且 OM 中尚无此用户：无需建档
        uid = await self._ensure_user(username, create=bool(wanted))
        if uid is None:
            return
        for team in TEAMS:
            resp = await self._call("GET", f"/teams/name/{team}", params={"fields": "users"})
            if resp.status_code >= 400:
                raise ContextureError(
                    "auth.om_provision_failed", f"OpenMetadata 团队 {team} 不可用", status_code=502
                )
            body = resp.json()
            members = [str(u["id"]) for u in body.get("users") or []]
            if team in wanted and uid not in members:
                ops = [{"op": "add", "path": "/users/0", "value": {"id": uid, "type": "user"}}]
            elif team not in wanted and uid in members:
                ops = [{"op": "remove", "path": f"/users/{members.index(uid)}"}]
            else:
                continue
            patched = await self._call(
                "PATCH",
                f"/teams/{body['id']}",
                content=json.dumps(ops).encode(),
                headers={"Content-Type": "application/json-patch+json"},
            )
            if patched.status_code >= 400:
                raise ContextureError(
                    "auth.om_provision_failed", f"无法同步 OpenMetadata 团队 {team}", status_code=502
                )
