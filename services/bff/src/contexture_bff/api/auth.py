"""登录、回调与登出（BFF 模式：令牌只在 bff，浏览器只持有会话 Cookie）。"""

import base64
import contextlib
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import RedirectResponse

from contexture_bff.adapters.sessions import LoginRequest, SessionRecord
from contexture_bff.api.deps import services, settings
from contexture_core.errors import ContextureError

router = APIRouter(prefix="/bff/v1/auth", tags=["auth"])


def _safe_return_to(value: str | None) -> str:
    """只允许站内相对路径，防止开放重定向。"""
    if value and value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    return "/"


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


@router.get("/login", status_code=302)
async def login(request: Request, return_to: str | None = None) -> RedirectResponse:
    cfg = settings(request)
    login_request = LoginRequest(
        state=secrets.token_urlsafe(32),
        code_verifier=secrets.token_urlsafe(64),
        nonce=secrets.token_urlsafe(16),
        return_to=_safe_return_to(return_to),
        expires_at=datetime.now(UTC) + timedelta(seconds=cfg.login_ttl_seconds),
    )
    await services(request).sessions.create_login(login_request)
    url = services(request).oidc.authorization_url(
        state=login_request.state,
        code_challenge=_challenge(login_request.code_verifier),
        nonce=login_request.nonce,
    )
    return RedirectResponse(url, status_code=302)


@router.get("/callback", status_code=302)
async def callback(
    request: Request,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
) -> RedirectResponse:
    cfg = settings(request)
    svc = services(request)
    login_request = await svc.sessions.pop_login(state)
    if login_request is None:
        raise ContextureError("auth.invalid_state", "登录请求无效或已过期", status_code=401)
    tokens = await svc.oidc.exchange_code(code=code, code_verifier=login_request.code_verifier)
    # 用公共库验签，确保令牌有效并取得用户
    assert svc.authenticator is not None  # noqa: S101
    claims = await svc.authenticator.verify(tokens.access_token)
    now = datetime.now(UTC)
    ttl = cfg.session_ttl_seconds
    if tokens.refresh_expires_in:
        ttl = min(ttl, tokens.refresh_expires_in)
    session_id = await svc.sessions.create_session(
        SessionRecord(
            user_id=str(claims["sub"]),
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            id_token=tokens.id_token,
            access_expires_at=now + timedelta(seconds=tokens.expires_in),
            expires_at=now + timedelta(seconds=ttl),
        )
    )
    response = RedirectResponse(login_request.return_to, status_code=302)
    response.set_cookie(
        cfg.session_cookie,
        session_id,
        max_age=ttl,
        httponly=True,
        secure=cfg.cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/logout", status_code=204)
async def logout(request: Request) -> Response:
    cfg = settings(request)
    svc = services(request)
    session_id = request.cookies.get(cfg.session_cookie)
    if session_id:
        record = await svc.sessions.get_session(session_id)
        await svc.sessions.delete_session(session_id)
        if record is not None:
            # Keycloak 登出失败不影响本地会话清除
            with contextlib.suppress(Exception):
                await svc.oidc.logout(record.refresh_token)
    response = Response(status_code=204)
    response.delete_cookie(cfg.session_cookie, path="/", httponly=True, samesite="lax")
    return response
