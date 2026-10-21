"""统一错误格式（contracts/schemas/error.json）与 FastAPI 异常处理器。"""

import logging
import re
from http import HTTPStatus
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from opentelemetry import trace
from starlette.exceptions import HTTPException as StarletteHTTPException

CODE_PATTERN = re.compile(r"^[a-z]+(\.[a-z_]+)+$")

logger = logging.getLogger(__name__)


class ContextureError(Exception):
    """带稳定错误码的业务异常；由异常处理器转换为统一错误格式。"""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        if not CODE_PATTERN.match(code):
            raise ValueError(f"错误 code 不合规范：{code}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class InvalidToken(ContextureError):
    def __init__(self, message: str = "令牌无效或已过期") -> None:
        super().__init__("auth.invalid_token", message, status_code=401)


class InvalidAudience(ContextureError):
    def __init__(self, message: str = "令牌受众不符") -> None:
        super().__init__("auth.invalid_audience", message, status_code=403)


class UpstreamUnavailable(ContextureError):
    def __init__(
        self, message: str = "上游服务不可用", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__("upstream.unavailable", message, status_code=502, details=details)


def current_trace_id() -> str:
    span_context = trace.get_current_span().get_span_context()
    return format(span_context.trace_id, "032x")


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message, "trace_id": current_trace_id()}
    if details:
        body["details"] = details
    return body


def _response(
    status: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    headers = dict(headers or {})
    if status == 401:
        headers.setdefault("WWW-Authenticate", "Bearer")
    return JSONResponse(error_body(code, message, details), status_code=status, headers=headers)


async def _handle_contexture(_: Request, exc: Exception) -> JSONResponse:
    err = cast(ContextureError, exc)
    return _response(err.status_code, err.code, err.message, err.details)


async def _handle_validation(_: Request, exc: Exception) -> JSONResponse:
    errors = [
        {"loc": list(e["loc"]), "msg": e["msg"]} for e in cast(RequestValidationError, exc).errors()
    ]
    return _response(422, "request.invalid", "请求参数不合法", {"errors": errors})


async def _handle_http(_: Request, exc: Exception) -> JSONResponse:
    http_exc = cast(StarletteHTTPException, exc)
    try:
        phrase = HTTPStatus(http_exc.status_code).phrase
    except ValueError:
        phrase = "error"
    slug = re.sub(r"[^a-z]+", "_", phrase.lower()).strip("_") or "error"
    # 保留原有响应头（如 405 的 Allow）
    return _response(
        http_exc.status_code,
        f"http.{slug}",
        str(http_exc.detail),
        headers=dict(http_exc.headers or {}),
    )


async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("未处理的异常", exc_info=exc)
    return _response(500, "internal.error", "服务内部错误")


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ContextureError, _handle_contexture)
    app.add_exception_handler(RequestValidationError, _handle_validation)
    app.add_exception_handler(StarletteHTTPException, _handle_http)
    app.add_exception_handler(Exception, _handle_unexpected)
