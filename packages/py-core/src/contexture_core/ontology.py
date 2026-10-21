"""经 OM REST 读取已审批的本体（ADR-0008）。

对象、属性都是 OM 术语：对象经 ``hasProperty`` 关系关联属性；类型、必填等写在术语的自定义属性
（``ctx_kind``、``ctx_data_type``、``ctx_required``、``ctx_uri``）；数据级别为分类“数据级别”的标签。
只返回审批状态为 Approved 的术语（宪法 IV），结果在本地缓存。
"""

import time
from typing import Any

import httpx
from pydantic import BaseModel

from contexture_core import telemetry
from contexture_core.errors import ContextureError, UpstreamUnavailable

APPROVED = "Approved"
HAS_PROPERTY = "hasProperty"
DATA_LEVEL_CLASSIFICATION = "数据级别"
DATA_LEVELS = {"一级": 1, "二级": 2, "三级": 3}
YES = {"是", "yes", "true", "True"}
FIELDS = "relatedTerms,extension,tags"


class AttributeRef(BaseModel):
    name: str
    data_type: str
    required: bool = False
    data_level: int | None = None


class ObjectTypeRef(BaseModel):
    type_uri: str
    name: str
    display_name: str | None = None
    version: str
    attributes: list[AttributeRef]


def _not_found(type_key: str) -> ContextureError:
    return ContextureError(
        "ontology.not_found", f"对象类型 {type_key} 不存在或未审批", status_code=404
    )


def _data_level(term: dict[str, Any]) -> int | None:
    for tag in term.get("tags") or []:
        classification, _, level = str(tag.get("tagFQN", "")).partition(".")
        if classification == DATA_LEVEL_CLASSIFICATION and level in DATA_LEVELS:
            return DATA_LEVELS[level]
    return None


def _extension(term: dict[str, Any]) -> dict[str, Any]:
    """术语的自定义属性；枚举型在 OM 中以数组存值，取第一个值。"""
    ext: dict[str, Any] = term.get("extension") or {}
    return {k: (v[0] if isinstance(v, list) and v else v) for k, v in ext.items()}


class OntologyClient:
    def __init__(
        self,
        *,
        om_url: str,
        token: str,
        glossary: str,
        http: httpx.AsyncClient | None = None,
        cache_seconds: int = 300,
        page_size: int = 500,
    ) -> None:
        self.base = om_url.rstrip("/") + "/api/v1"
        self.glossary = glossary
        self.http = http or telemetry.traced_client(timeout=10)
        self.headers = {"Authorization": f"Bearer {token}"}
        self.cache_seconds = cache_seconds
        self.page_size = page_size
        self._cache: dict[str, tuple[ObjectTypeRef, float]] = {}

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        try:
            resp = await self.http.get(f"{self.base}{path}", params=params, headers=self.headers)
        except httpx.HTTPError as exc:
            raise UpstreamUnavailable("OM 不可用", details={"upstream": "openmetadata"}) from exc
        if resp.status_code >= 500 or resp.status_code in (401, 403):
            raise UpstreamUnavailable("OM 不可用", details={"upstream": "openmetadata"})
        return resp

    async def _approved_terms(self, type_key: str) -> list[dict[str, Any]]:
        resp = await self._get(f"/glossaries/name/{self.glossary}")
        if resp.status_code == 404:
            raise _not_found(type_key)
        glossary_id = resp.json()["id"]
        terms: list[dict[str, Any]] = []
        after: str | None = None
        while True:
            params: dict[str, Any] = {
                "glossary": glossary_id,
                "fields": FIELDS,
                "entityStatus": APPROVED,
                "limit": self.page_size,
            }
            if after:
                params["after"] = after
            body = (await self._get("/glossaryTerms", params)).json()
            terms += body.get("data", [])
            after = (body.get("paging") or {}).get("after")
            if not after:
                break
        # 服务端已按状态过滤，这里再校验一次，确保不返回未审批内容
        return [t for t in terms if t.get("entityStatus") == APPROVED]

    async def get_object_type(self, type_key: str) -> ObjectTypeRef:
        cached = self._cache.get(type_key)
        if cached and cached[1] > time.monotonic():
            return cached[0]
        terms = await self._approved_terms(type_key)
        by_id = {t["id"]: t for t in terms}
        obj = next(
            (
                t
                for t in terms
                if _extension(t).get("ctx_kind") == "object"
                and str(t["name"]).lower() == type_key.lower()
            ),
            None,
        )
        if obj is None:
            raise _not_found(type_key)
        attributes = [
            AttributeRef(
                name=prop["name"],
                data_type=str(_extension(prop).get("ctx_data_type", "string")),
                required=str(_extension(prop).get("ctx_required", "")) in YES,
                data_level=_data_level(prop),
            )
            for rel in obj.get("relatedTerms") or []
            if rel.get("relationType") == HAS_PROPERTY
            and (prop := by_id.get(rel["term"]["id"])) is not None
            and _extension(prop).get("ctx_kind") == "property"
        ]
        ref = ObjectTypeRef(
            type_uri=_extension(obj).get("ctx_uri")
            or f"urn:ctx:object:{self.glossary}:{obj['name']}",
            name=obj["name"],
            display_name=obj.get("displayName"),
            version=str(obj.get("version", "")),
            attributes=attributes,
        )
        self._cache[type_key] = (ref, time.monotonic() + self.cache_seconds)
        return ref
