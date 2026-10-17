"""对象实例取数：经公共库 mcp 调用 AI 网关上的 list_objects 工具（ADR-0013）。"""

from typing import Protocol

from contexture_core.auth import RequestContext
from contexture_core.mcp import McpClient, Rows


class ObjectData(Protocol):
    async def list_objects(self, ctx: RequestContext, *, type_key: str, limit: int) -> Rows: ...


class McpObjectData:
    def __init__(self, client: McpClient) -> None:
        self.client = client

    async def list_objects(self, ctx: RequestContext, *, type_key: str, limit: int) -> Rows:
        return await self.client.list_objects(ctx, type_key=type_key, limit=limit)
