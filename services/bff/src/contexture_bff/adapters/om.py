"""对象定义读取：经公共库 ontology 从 OM 读取已审批的对象与属性。"""

from typing import Protocol

from contexture_core.ontology import ObjectTypeRef, OntologyClient


class ObjectTypes(Protocol):
    async def get(self, type_key: str) -> ObjectTypeRef: ...


class OmObjectTypes:
    def __init__(self, client: OntologyClient) -> None:
        self.client = client

    async def get(self, type_key: str) -> ObjectTypeRef:
        return await self.client.get_object_type(type_key)
