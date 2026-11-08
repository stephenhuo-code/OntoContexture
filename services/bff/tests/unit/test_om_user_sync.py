"""织境登录时在 OM 建档并同步团队（research R13）：按令牌角色入组 admin / ai-engineer，其余角色忽略；
已一致时不写；OM 不可用时登录失败，不静默跳过。"""

import json
from typing import Any

import httpx
import pytest

from contexture_bff.adapters.om_users import TEAMS, OmUserSync
from contexture_core.errors import ContextureError


class FakeOM:
    def __init__(self, users: dict[str, str], members: dict[str, list[str]]) -> None:
        self.users = dict(users)  # name -> id
        self.members = {k: list(v) for k, v in members.items()}  # team -> [user id]
        self.writes: list[tuple[str, str, Any]] = []
        self.down = False

    def transport(self) -> httpx.MockTransport:
        def handler(req: httpx.Request) -> httpx.Response:
            if self.down:
                return httpx.Response(503)
            if req.url.path.endswith("/protocol/openid-connect/token"):
                assert b"grant_type=client_credentials" in req.content
                return httpx.Response(200, json={"access_token": "sa-token", "expires_in": 300})
            assert req.headers["authorization"] == "Bearer sa-token"
            path = req.url.path.removeprefix("/api/v1")
            if req.method == "GET" and path.startswith("/users/name/"):
                name = path.rsplit("/", 1)[1]
                if name not in self.users:
                    return httpx.Response(404, json={})
                return httpx.Response(200, json={"id": self.users[name], "name": name})
            if req.method == "POST" and path == "/users":
                body = json.loads(req.content)
                self.writes.append(("POST", path, body))
                self.users[body["name"]] = f"id-{body['name']}"
                return httpx.Response(201, json={"id": self.users[body["name"]], **body})
            if req.method == "GET" and path.startswith("/teams/name/"):
                team = path.rsplit("/", 1)[1]
                users = [{"id": u} for u in self.members[team]]
                return httpx.Response(
                    200, json={"id": f"team-{team}", "name": team, "users": users}
                )
            if req.method == "PATCH" and path.startswith("/teams/"):
                team = path.removeprefix("/teams/team-")
                ops = json.loads(req.content)
                assert req.headers["content-type"] == "application/json-patch+json"
                self.writes.append(("PATCH", team, ops))
                for op in ops:
                    if op["op"] == "add":
                        self.members[team].append(op["value"]["id"])
                    elif op["op"] == "remove":
                        idx = int(op["path"].rsplit("/", 1)[1])
                        self.members[team].pop(idx)
                return httpx.Response(200, json={})
            raise AssertionError(f"unexpected {req.method} {req.url.path}")

        return httpx.MockTransport(handler)


def sync(om: FakeOM) -> OmUserSync:
    return OmUserSync(
        om_url="http://om:8585",
        token_url="http://kc/realms/r/protocol/openid-connect/token",
        client_id="contexture-bff",
        client_secret="secret",
        http=httpx.AsyncClient(transport=om.transport()),
    )


async def test_creates_user_and_joins_teams_for_roles() -> None:
    om = FakeOM(users={}, members={t: [] for t in TEAMS})
    await sync(om).sync("newbie", ["ai-engineer", "default-roles-x", "business-user"])
    assert om.users["newbie"] == "id-newbie"
    create = next(w for w in om.writes if w[0] == "POST")
    assert create[2] == {"name": "newbie", "email": "newbie@contexture.local"}
    assert om.members == {"admin": [], "ai-engineer": ["id-newbie"]}


async def test_removes_membership_when_role_revoked() -> None:
    om = FakeOM(users={"eng": "u1"}, members={"admin": ["u1", "u2"], "ai-engineer": ["u1"]})
    await sync(om).sync("eng", ["ai-engineer"])
    assert om.members == {"admin": ["u2"], "ai-engineer": ["u1"]}


async def test_no_writes_when_already_consistent() -> None:
    om = FakeOM(users={"adm": "u9"}, members={"admin": ["u9"], "ai-engineer": []})
    await sync(om).sync("adm", ["admin"])
    assert om.writes == []


async def test_om_unavailable_fails_login() -> None:
    om = FakeOM(users={}, members={t: [] for t in TEAMS})
    om.down = True
    with pytest.raises(ContextureError) as exc:
        await sync(om).sync("x", ["admin"])
    assert exc.value.code == "upstream.unavailable"
