"""bff 应用组装：配置、鉴权、追踪与错误处理一律来自公共库 contexture-core。"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.routing import Match
from sqlalchemy.ext.asyncio import create_async_engine

from contexture_bff.adapters.data import McpObjectData, ObjectData
from contexture_bff.adapters.keycloak import KeycloakOidc, Oidc
from contexture_bff.adapters.om import ObjectTypes, OmObjectTypes
from contexture_bff.adapters.om_client import OmClient
from contexture_bff.adapters.om_sources import SourcesService
from contexture_bff.adapters.om_users import OmUserSync
from contexture_bff.adapters.sessions import PostgresSessionStore, SessionStore
from contexture_bff.api import auth, deps, me, objects, sources
from contexture_bff.settings import BffSettings
from contexture_core.auth import Authenticator, TokenVerifier
from contexture_core.config import load_settings
from contexture_core.errors import install_error_handlers
from contexture_core.mcp import McpClient, TokenExchanger
from contexture_core.ontology import OntologyClient
from contexture_core.telemetry import configure_logging, setup_telemetry

logger = logging.getLogger(__name__)


@dataclass
class Services:
    sessions: SessionStore
    oidc: Oidc
    object_types: ObjectTypes | None
    object_data: ObjectData | None
    authenticator: Authenticator | None
    # 005：OM 用户同步（research R13）与源系统元数据采集（经用户委托令牌调用 OM）
    om_users: OmUserSync | None = None
    sources: SourcesService | None = None


def build_authenticator(settings: BffSettings) -> Authenticator:
    verifier = TokenVerifier(
        jwks_url=settings.jwks_url, issuer=settings.issuer, audience=settings.token_audience
    )
    return Authenticator(
        tenant_id=settings.tenant_id, verifier=verifier, token_source=deps.session_or_bearer
    )


async def _cleanup_loop(store: SessionStore, interval: int) -> None:
    while True:
        await asyncio.sleep(interval)
        try:
            removed = await store.cleanup()
            if removed:
                logger.info("清理过期会话 %d 条", removed)
        except Exception:
            logger.exception("清理过期会话失败")


def create_app(settings: BffSettings | None = None, *, services: Services | None = None) -> FastAPI:
    cfg = settings or load_settings(BffSettings)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if services is not None:
            yield
            return
        engine = create_async_engine(cfg.database_url, pool_pre_ping=True)
        store = PostgresSessionStore(engine)
        exchanger = TokenExchanger(
            token_url=cfg.token_url,
            client_id=cfg.client_id,
            client_secret=cfg.client_secret.get_secret_value(),
        )
        app.state.services = Services(
            sessions=store,
            oidc=KeycloakOidc(cfg),
            object_types=OmObjectTypes(
                OntologyClient(
                    om_url=cfg.om_url,
                    token=cfg.om_token.get_secret_value(),
                    glossary=cfg.om_glossary,
                )
            ),
            object_data=McpObjectData(
                McpClient(
                    url=cfg.ai_gateway_mcp_url,
                    exchanger=exchanger,
                    audience=cfg.ai_gateway_audience,
                )
            ),
            authenticator=build_authenticator(cfg),
            om_users=OmUserSync(
                om_url=cfg.om_url,
                token_url=cfg.token_url,
                client_id=cfg.client_id,
                client_secret=cfg.client_secret.get_secret_value(),
            ),
            sources=SourcesService(
                OmClient(om_url=cfg.om_url, exchanger=exchanger, audience=cfg.om_audience)
            ),
        )
        cleanup = asyncio.create_task(_cleanup_loop(store, cfg.session_cleanup_interval_seconds))
        try:
            yield
        finally:
            cleanup.cancel()
            await engine.dispose()

    app = FastAPI(title="织境 bff", version="0.1.0", lifespan=lifespan)
    app.state.settings = cfg
    if services is not None:
        if services.authenticator is None:
            services.authenticator = build_authenticator(cfg)
        # 令牌来源由 bff 统一决定：会话（浏览器）或 Bearer（直接调用）
        services.authenticator.token_source = deps.session_or_bearer
        app.state.services = services
    install_error_handlers(app)

    @app.middleware("http")
    async def allow_header(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """同一路径按方法拆成多个路由时，405 的 Allow 合并该路径全部方法（RFC 9110 §15.5.6）。"""
        response = await call_next(request)
        if response.status_code == 405:
            methods = [
                m
                for m in ("GET", "POST", "PUT", "PATCH", "DELETE")
                if any(
                    route.matches({**request.scope, "method": m})[0] == Match.FULL
                    for route in app.router.routes
                )
            ]
            if methods:
                response.headers["Allow"] = ", ".join(methods)
        return response

    setup_telemetry(cfg, app)
    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(objects.router)
    app.include_router(sources.router)
    return app


def run() -> None:
    """容器入口：结构化日志 + uvicorn。"""
    import uvicorn

    configure_logging()
    uvicorn.run(create_app(), host="0.0.0.0", port=8080, log_config=None)  # noqa: S104
