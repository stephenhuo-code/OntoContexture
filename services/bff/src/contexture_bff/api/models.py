"""请求 / 响应模型，与 contracts/openapi/bff.yaml 一致。"""

from typing import Any

from pydantic import BaseModel

from contexture_core.ontology import ObjectTypeRef


class Me(BaseModel):
    tenant_id: str
    user_id: str
    display_name: str | None = None
    roles: list[str] = []


class ObjectInstance(BaseModel):
    object_uri: str
    type_uri: str
    attributes: dict[str, Any]
    source: str | None = None


class ObjectListView(BaseModel):
    object_type: ObjectTypeRef
    items: list[ObjectInstance]
    trace_id: str | None = None
