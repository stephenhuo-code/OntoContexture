"""令牌验签与请求上下文（data-model.md 的 RequestContext）。

以 FastAPI 依赖项提供：验签失败或过期返回 401，受众不符返回 403，业务代码不处理。
"""

import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import anyio
import httpx
import jwt
from fastapi import Request

from contexture_core import telemetry
from contexture_core.errors import InvalidAudience, InvalidToken, current_trace_id

ALGORITHMS = ["RS256", "RS384", "RS512", "ES256", "ES384", "PS256"]


@dataclass(frozen=True)
class RequestContext:
    tenant_id: str
    user_id: str | None
    agent_id: str | None
    roles: tuple[str, ...]
    token_id: str
    token: str = field(repr=False)
    username: str | None = None
    display_name: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    # 二期授权求值时使用（data-model.md）
    agent_owner_id: str | None = None
    agent_scopes: tuple[str, ...] = ()
    data_level_ceiling: int | None = None

    @property
    def trace_id(self) -> str:
        return current_trace_id()


class TokenVerifier:
    """按 JWKS 验签，缓存公钥；遇到未知 kid 时刷新（限频）。"""

    def __init__(
        self,
        *,
        jwks_url: str,
        issuer: str,
        audience: str,
        http: httpx.Client | None = None,
        cache_seconds: int = 300,
        leeway_seconds: int = 30,
    ) -> None:
        self.jwks_url = jwks_url
        self.issuer = issuer
        self.audience = audience
        self.http = http or httpx.Client(timeout=5)
        self.cache_seconds = cache_seconds
        self.leeway = leeway_seconds
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at = 0.0
        self._lock = threading.Lock()

    def _refresh(self, force: bool = False) -> None:
        with self._lock:
            age = time.monotonic() - self._fetched_at
            if self._keys and age < (10 if force else self.cache_seconds):
                return
            resp = self.http.get(self.jwks_url)
            resp.raise_for_status()
            keyset = jwt.PyJWKSet.from_dict(resp.json())
            self._keys = {k.key_id: k for k in keyset.keys if k.key_id}
            self._fetched_at = time.monotonic()

    def _key(self, kid: str) -> jwt.PyJWK:
        self._refresh()
        if kid not in self._keys:
            self._refresh(force=True)
        if kid not in self._keys:
            raise InvalidToken("未知的签名密钥")
        return self._keys[kid]

    def verify(self, token: str) -> dict[str, Any]:
        try:
            kid = jwt.get_unverified_header(token).get("kid", "")
            key = self._key(kid)
            claims: dict[str, Any] = jwt.decode(
                token,
                key=key.key,
                algorithms=ALGORITHMS,
                issuer=self.issuer,
                options={"verify_aud": False, "require": ["exp", "iss", "sub", "jti"]},
                leeway=self.leeway,
            )
        except InvalidToken:
            raise
        except (jwt.PyJWTError, httpx.HTTPError, ValueError) as exc:
            raise InvalidToken() from exc
        aud = claims.get("aud", [])
        audiences = aud if isinstance(aud, list) else [aud]
        if self.audience not in audiences:
            raise InvalidAudience()
        return claims


def context_from_claims(claims: dict[str, Any], *, tenant_id: str, token: str) -> RequestContext:
    realm_access = claims.get("realm_access") or {}
    return RequestContext(
        tenant_id=tenant_id,
        user_id=claims.get("sub"),
        agent_id=claims.get("azp"),
        roles=tuple(realm_access.get("roles", [])),
        token_id=claims["jti"],
        token=token,
        username=claims.get("preferred_username"),
        display_name=claims.get("name"),
        session_id=claims.get("sid"),
    )


TokenSource = Callable[[Request], Awaitable[str | None]]


async def bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() == "bearer" and value:
        return value.strip()
    return None


class Authenticator:
    """FastAPI 依赖项：取令牌 → 验签 → 构建请求上下文 → 写入追踪与日志关联属性。"""

    def __init__(
        self,
        *,
        tenant_id: str,
        verifier: TokenVerifier,
        token_source: TokenSource = bearer_token,
    ) -> None:
        self.tenant_id = tenant_id
        self.verifier = verifier
        self.token_source = token_source

    async def verify(self, token: str) -> dict[str, Any]:
        """验签并返回令牌声明（JWKS 获取在线程中执行，不阻塞事件循环）。"""
        return await anyio.to_thread.run_sync(self.verifier.verify, token)

    async def __call__(self, request: Request) -> RequestContext:
        token = await self.token_source(request)
        if not token:
            raise InvalidToken("缺少令牌")
        claims = await self.verify(token)
        ctx = context_from_claims(claims, tenant_id=self.tenant_id, token=token)
        telemetry.bind_context(ctx)
        request.state.ctx = ctx
        return ctx
