"""OTel 初始化与关联属性注入（contracts/otel/attributes.md）。

- 每个 span 自动带 ``ctx.tenant.id``，鉴权后再带 ``ctx.user.id`` 等（经 W3C Baggage 传递）；
- 结构化日志带同样的属性与 trace_id；
- 出站 HTTP 由 ``traced_client`` 创建的客户端自动携带 ``traceparent`` 与 Baggage。
"""

import json
import logging
from collections.abc import Mapping, MutableMapping
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import FastAPI
from opentelemetry import baggage, context, propagate, trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from contexture_core.config import CoreSettings

if TYPE_CHECKING:
    from contexture_core.auth import RequestContext

# 属性名只能取自 contracts/otel/attributes.md
TENANT_ID = "ctx.tenant.id"
USER_ID = "ctx.user.id"
AGENT_ID = "ctx.agent.id"
RUN_ID = "ctx.run.id"
SESSION_ID = "ctx.session.id"
TOKEN_ID = "ctx.token.id"  # noqa: S105 属性名，不是凭证
PREFIX = "ctx."

_tenant_id: str | None = None


class CorrelationSpanProcessor(SpanProcessor):
    """span 开始时写入租户常量，并从 Baggage 复制 ctx.* 属性。"""

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id

    def on_start(self, span: Span, parent_context: context.Context | None = None) -> None:
        span.set_attribute(TENANT_ID, self.tenant_id)
        for key, value in baggage.get_all(parent_context).items():
            if key.startswith(PREFIX):
                span.set_attribute(key, str(value))

    def on_end(self, span: ReadableSpan) -> None:
        return None


def setup_telemetry(settings: CoreSettings, app: FastAPI | None = None) -> TracerProvider:
    """初始化追踪并插桩 FastAPI 应用；可重复调用（全局 TracerProvider 只设置一次）。"""
    global _tenant_id
    current = trace.get_tracer_provider()
    if isinstance(current, TracerProvider):
        provider = current
    else:
        provider = TracerProvider(resource=Resource.create({"service.name": settings.service_name}))
        if settings.otel_exporter_otlp_endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            exporter = OTLPSpanExporter(
                endpoint=f"{settings.otel_exporter_otlp_endpoint.rstrip('/')}/v1/traces"
            )
            provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
    if _tenant_id is None:
        provider.add_span_processor(CorrelationSpanProcessor(settings.tenant_id))
    _tenant_id = settings.tenant_id
    if app is not None:
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    return provider


def bind_context(ctx: "RequestContext") -> None:
    """把请求上下文写入当前 span 与 Baggage，之后的 span、日志、出站请求都会带上。"""
    values = {
        TENANT_ID: ctx.tenant_id,
        USER_ID: ctx.user_id,
        AGENT_ID: ctx.agent_id,
        TOKEN_ID: ctx.token_id,
        SESSION_ID: ctx.session_id,
        RUN_ID: ctx.run_id,
    }
    current = context.get_current()
    span = trace.get_current_span(current)
    for key, value in values.items():
        if value:
            span.set_attribute(key, value)
            current = baggage.set_baggage(key, value, current)
    context.attach(current)


def correlation() -> dict[str, str]:
    """当前上下文中的关联属性（含租户常量）。"""
    values = {k: str(v) for k, v in baggage.get_all().items() if k.startswith(PREFIX)}
    if _tenant_id and TENANT_ID not in values:
        values[TENANT_ID] = _tenant_id
    return values


def inject_headers(headers: MutableMapping[str, str]) -> MutableMapping[str, str]:
    """写入 traceparent 与 Baggage，用于不经 httpx 插桩的出站调用（如 MCP SDK）。"""
    propagate.inject(headers)
    return headers


def traced_client(**kwargs: Any) -> httpx.AsyncClient:
    """创建已插桩的 httpx 客户端：出站请求生成 span，并携带 traceparent 与 Baggage。"""
    client = httpx.AsyncClient(**kwargs)
    HTTPXClientInstrumentor.instrument_client(client)
    return client


class JsonFormatter(logging.Formatter):
    """结构化日志：每行一个 JSON，带 trace_id 与 ctx.* 关联属性。"""

    def format(self, record: logging.LogRecord) -> str:
        span_context = trace.get_current_span().get_span_context()
        entry: dict[str, Any] = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": format(span_context.trace_id, "032x"),
            "span_id": format(span_context.span_id, "016x"),
        }
        entry.update(correlation())
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def configure_logging(level: int = logging.INFO, extra: Mapping[str, int] | None = None) -> None:
    """把根日志改为结构化 JSON 输出。"""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    for name, lvl in (extra or {}).items():
        logging.getLogger(name).setLevel(lvl)
