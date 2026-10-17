"""bff 单元与契约测试用的替身：内存会话、假 Keycloak、假 OM 与取数。"""

import secrets
from datetime import UTC, datetime
from typing import Any

from contexture_bff.adapters.keycloak import TokenSet
from contexture_bff.adapters.sessions import LoginRequest, SessionRecord
from contexture_core.auth import RequestContext
from contexture_core.errors import UpstreamUnavailable
from contexture_core.mcp import Rows
from contexture_core.ontology import AttributeRef, ObjectTypeRef

EQUIPMENT = ObjectTypeRef(
    type_uri="urn:ctx:object:quality:Equipment",
    name="Equipment",
    display_name="设备",
    version="0.3",
    attributes=[
        AttributeRef(name="code", data_type="string", required=True, data_level=1),
        AttributeRef(name="model", data_type="string", required=False, data_level=2),
    ],
)

ROWS = Rows(columns=["code", "model"], rows=[["CNC-01", "Mazak"], ["CNC-02", "DMG"]])


def user_context(token: str = "access-token") -> RequestContext:
    return RequestContext(
        tenant_id="local",
        user_id="user-1-id",
        agent_id="contexture-bff",
        roles=("business-user",),
        token_id="jti-1",
        token=token,
        username="user1",
        display_name="User One",
    )


class FakeSessions:
    def __init__(self) -> None:
        self.logins: dict[str, LoginRequest] = {}
        self.sessions: dict[str, SessionRecord] = {}

    async def create_login(self, login: LoginRequest) -> None:
        self.logins[login.state] = login

    async def pop_login(self, state: str) -> LoginRequest | None:
        login = self.logins.pop(state, None)
        if login and login.expires_at > datetime.now(UTC):
            return login
        return None

    async def create_session(self, record: SessionRecord) -> str:
        session_id = secrets.token_urlsafe(32)
        self.sessions[session_id] = record
        return session_id

    async def get_session(self, session_id: str) -> SessionRecord | None:
        record = self.sessions.get(session_id)
        if record and record.expires_at > datetime.now(UTC):
            return record
        return None

    async def update_session(self, session_id: str, record: SessionRecord) -> None:
        self.sessions[session_id] = record

    async def delete_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)

    async def cleanup(self) -> int:
        return 0


class FakeOidc:
    def __init__(self) -> None:
        self.logged_out: list[str] = []
        self.refreshed: list[str] = []

    def authorization_url(self, *, state: str, code_challenge: str, nonce: str) -> str:
        return f"https://sso.test/auth?state={state}&code_challenge={code_challenge}"

    async def exchange_code(self, *, code: str, code_verifier: str) -> TokenSet:
        return TokenSet(
            access_token=f"access-{code}",
            refresh_token="refresh-1",
            id_token="id-1",
            expires_in=300,
            refresh_expires_in=1800,
        )

    async def refresh(self, refresh_token: str) -> TokenSet:
        self.refreshed.append(refresh_token)
        return TokenSet(
            access_token="access-refreshed",
            refresh_token="refresh-2",
            id_token="id-2",
            expires_in=300,
            refresh_expires_in=1800,
        )

    async def logout(self, refresh_token: str) -> None:
        self.logged_out.append(refresh_token)


class FakeObjectTypes:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def get(self, type_key: str) -> ObjectTypeRef:
        if self.fail:
            raise UpstreamUnavailable("OM 不可用", details={"upstream": "openmetadata"})
        return EQUIPMENT


class FakeObjectData:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def list_objects(self, ctx: RequestContext, *, type_key: str, limit: int) -> Rows:
        self.calls.append({"user": ctx.user_id, "type_key": type_key, "limit": limit})
        if self.fail:
            raise UpstreamUnavailable("AI 网关不可用", details={"upstream": "ai-gateway"})
        return ROWS
