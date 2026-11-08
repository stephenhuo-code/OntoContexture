"""依赖项：服务实例与请求上下文。令牌来源为会话（浏览器）或 Bearer（直接调用）。"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated, cast

from fastapi import Depends, Request

from contexture_core.auth import RequestContext, bearer_token
from contexture_core.errors import ContextureError, InvalidToken

if TYPE_CHECKING:
    from contexture_bff.main import Services
    from contexture_bff.settings import BffSettings

REFRESH_MARGIN = timedelta(seconds=30)


def services(request: Request) -> "Services":
    return cast("Services", request.app.state.services)


def settings(request: Request) -> "BffSettings":
    return cast("BffSettings", request.app.state.settings)


async def session_or_bearer(request: Request) -> str | None:
    """有会话 Cookie 时取会话中的令牌（过期前自动刷新），否则取 Bearer 令牌。"""
    session_id = request.cookies.get(settings(request).session_cookie)
    if not session_id:
        return await bearer_token(request)
    store = services(request).sessions
    record = await store.get_session(session_id)
    if record is None:
        return None
    if record.access_expires_at - REFRESH_MARGIN <= datetime.now(UTC):
        try:
            tokens = await services(request).oidc.refresh(record.refresh_token)
        except InvalidToken:
            await store.delete_session(session_id)
            raise
        authenticator = services(request).authenticator
        if authenticator is not None:
            # 005：会话刷新时按最新角色同步 OM 团队（research R13）
            from contexture_bff.api.auth import sync_om_user

            await sync_om_user(services(request), await authenticator.verify(tokens.access_token))
        record = replace(
            record,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            id_token=tokens.id_token or record.id_token,
            access_expires_at=datetime.now(UTC) + timedelta(seconds=tokens.expires_in),
        )
        await store.update_session(session_id, record)
    return record.access_token


async def current_context(request: Request) -> RequestContext:
    authenticator = services(request).authenticator
    assert authenticator is not None, "create_app 应已创建 authenticator"  # noqa: S101
    return await authenticator(request)


async def require_web_context(
    ctx: Annotated[RequestContext, Depends(current_context)],
) -> RequestContext:
    if not {"admin", "ai-engineer"}.intersection(ctx.roles):
        raise ContextureError("auth.web_access_denied", "当前账号无权访问织境", status_code=403)
    return ctx
