"""浏览器登录、恢复与应用内退出；身份令牌只在 BFF 会话库。"""

import base64
import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlencode, urlsplit

from authlib.integrations.base_client.errors import OAuthError
from authlib.oauth2.rfc6749 import OAuth2Error
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from contexture_bff.adapters.sessions import LoginRequest, SessionRecord
from contexture_bff.api.deps import services, settings

if TYPE_CHECKING:
    from contexture_bff.main import Services
from contexture_core.errors import (
    InvalidAudience,
    InvalidToken,
    UpstreamUnavailable,
    current_trace_id,
)

router = APIRouter(prefix="/bff/v1/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _safe_return_to(value: str | None) -> str:
    if not value:
        return "/home"
    decoded = unquote(value)
    if any(
        not target.startswith("/")
        or target.startswith("//")
        or "\\" in target
        or any(ord(char) < 32 or ord(char) == 127 for char in target)
        for target in (value, decoded)
    ):
        return "/home"
    if urlsplit(decoded).path.rstrip("/") == "/auth/error":
        return "/home"
    return value


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _failure(reason: str, target: str = "/home") -> RedirectResponse:
    query = urlencode(
        {"reason": reason, "trace_id": current_trace_id(), "return_to": _safe_return_to(target)}
    )
    return RedirectResponse(
        f"/auth/error?{query}",
        status_code=303,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


@router.get("/login", status_code=302)
async def login(request: Request, return_to: str | None = None) -> RedirectResponse:
    target = _safe_return_to(return_to)
    try:
        cfg = settings(request)
        login_request = LoginRequest(
            state=secrets.token_urlsafe(32),
            code_verifier=secrets.token_urlsafe(64),
            nonce=secrets.token_urlsafe(16),
            return_to=target,
            expires_at=datetime.now(UTC) + timedelta(seconds=cfg.login_ttl_seconds),
        )
        svc = services(request)
        await svc.sessions.create_login(login_request)
        url = svc.oidc.authorization_url(
            state=login_request.state,
            code_challenge=_challenge(login_request.code_verifier),
            nonce=login_request.nonce,
        )
        return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})
    except UpstreamUnavailable:
        return _failure("unavailable", target)
    except Exception as exc:
        logger.error("创建登录请求失败", extra={"error_type": type(exc).__name__})
        return _failure("internal", target)


async def sync_om_user(svc: "Services", claims: dict[str, Any]) -> None:
    """005：按令牌中的织境角色在 OpenMetadata 建档并同步团队（research R13）；OM 不可用则登录失败。"""
    if svc.om_users is None:
        return
    username = claims.get("preferred_username")
    if not isinstance(username, str) or not username:
        return
    roles = (claims.get("realm_access") or {}).get("roles") or []
    await svc.om_users.sync(username, [str(r) for r in roles])


@router.get("/callback", status_code=302)
async def callback(request: Request) -> RedirectResponse:
    target = "/home"
    try:
        svc = services(request)
        query = request.query_params
        states = query.getlist("state")
        if len(states) != 1 or not states[0]:
            return _failure("invalid_response")
        login_request = await svc.sessions.pop_login(states[0])
        if login_request is None:
            return _failure("invalid_response")
        target = _safe_return_to(login_request.return_to)
        if any(len(query.getlist(key)) != 1 for key in query):
            return _failure("invalid_response", target)
        code, error = query.get("code"), query.get("error")
        if ("code" in query) == ("error" in query) or not (code or error):
            return _failure("invalid_response", target)
        if error:
            return _failure("cancelled" if error == "access_denied" else "invalid_response", target)
        if not code or not code.strip():
            return _failure("invalid_response", target)
        tokens = await svc.oidc.exchange_code(code=code, code_verifier=login_request.code_verifier)
        assert svc.authenticator is not None  # noqa: S101
        claims = await svc.authenticator.verify(tokens.access_token)
        await sync_om_user(svc, claims)
        cfg = settings(request)
        ttl = cfg.session_ttl_seconds
        if tokens.refresh_expires_in:
            ttl = min(ttl, tokens.refresh_expires_in)
        now = datetime.now(UTC)
        session_id = await svc.sessions.create_session(
            SessionRecord(
                user_id=claims["sub"],
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                id_token=tokens.id_token,
                access_expires_at=now + timedelta(seconds=tokens.expires_in),
                expires_at=now + timedelta(seconds=ttl),
            )
        )
        response = RedirectResponse(
            target,
            status_code=302,
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )
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
    except UpstreamUnavailable:
        return _failure("unavailable", target)
    except (InvalidToken, InvalidAudience, OAuth2Error, OAuthError):
        return _failure("invalid_response", target)
    except Exception as exc:
        logger.error("登录回调处理失败", extra={"error_type": type(exc).__name__})
        return _failure("internal", target)


@router.post("/logout", status_code=204)
async def logout(request: Request) -> Response:
    cfg = settings(request)
    session_id = request.cookies.get(cfg.session_cookie)
    if session_id:
        await services(request).sessions.delete_session(session_id)
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(
        cfg.session_cookie, path="/", httponly=True, secure=cfg.cookie_secure, samesite="lax"
    )
    return response
