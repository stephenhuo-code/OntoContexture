"""006 资产搜索：调用 OpenMetadata 2.0.3 的搜索接口（research R1–R8、R11）。

BFF 只做结构化条件 → OM 参数的翻译、校验与结果投影；不自建索引，不打分（FR-018、FR-019）。
"""

from typing import Any

from contexture_bff.adapters.om_client import OmClient
from contexture_core.auth import RequestContext
from contexture_core.errors import ContextureError, UpstreamUnavailable

# OM 索引缺失：OpenSearch 404 → SearchIndexNotFoundException → HTTP 500「Failed to find index …」
# （OpenSearchSearchManager.java:1231-1237）
INDEX_MISSING_PREFIX = "Failed to find index"


async def search_request(
    om: OmClient, ctx: RequestContext, path: str, params: dict[str, Any]
) -> dict[str, Any]:
    """调用 OM /v1/search/*，把索引缺失与超时映射为 006 错误码（research R11）。"""
    try:
        body = await om.request(ctx, "GET", path, params=params)
    except UpstreamUnavailable as exc:
        message = str((exc.details or {}).get("message") or "")
        if message.startswith(INDEX_MISSING_PREFIX):
            raise ContextureError(
                "search.index_missing",
                f"OpenMetadata 搜索索引缺失：{message}",
                status_code=503,
                details={"upstream": "openmetadata"},
            ) from exc
        raise
    if isinstance(body, dict) and body.get("timed_out") is True:
        raise ContextureError(
            "search.timeout",
            "OpenMetadata 搜索超时（30 秒），未返回完整结果",
            status_code=504,
            details={"upstream": "openmetadata"},
        )
    return body if isinstance(body, dict) else {}
