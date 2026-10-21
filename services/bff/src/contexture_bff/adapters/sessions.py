"""会话存储：PostgreSQL 的独占 database ``bff``（表结构见 migrations/）。

浏览器只持有会话 ID；库中只存会话 ID 的 SHA-256，令牌只在服务端。
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine

metadata = sa.MetaData()

sessions_table = sa.Table(
    "sessions",
    metadata,
    sa.Column("id_hash", sa.String(64), primary_key=True),
    sa.Column("user_id", sa.String(255), nullable=False),
    sa.Column("access_token", sa.Text, nullable=False),
    sa.Column("refresh_token", sa.Text, nullable=False),
    sa.Column("id_token", sa.Text, nullable=False),
    sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
)

login_requests_table = sa.Table(
    "login_requests",
    metadata,
    sa.Column("state", sa.String(128), primary_key=True),
    sa.Column("code_verifier", sa.String(128), nullable=False),
    sa.Column("nonce", sa.String(128), nullable=False),
    sa.Column("return_to", sa.Text, nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
)


@dataclass
class SessionRecord:
    user_id: str
    access_token: str
    refresh_token: str
    id_token: str
    access_expires_at: datetime
    expires_at: datetime


@dataclass
class LoginRequest:
    state: str
    code_verifier: str
    nonce: str
    return_to: str
    expires_at: datetime


class SessionStore(Protocol):
    async def create_login(self, login: LoginRequest) -> None: ...
    async def pop_login(self, state: str) -> LoginRequest | None: ...
    async def create_session(self, record: SessionRecord) -> str: ...
    async def get_session(self, session_id: str) -> SessionRecord | None: ...
    async def update_session(self, session_id: str, record: SessionRecord) -> None: ...
    async def delete_session(self, session_id: str) -> None: ...
    async def cleanup(self) -> int: ...


def _hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


class PostgresSessionStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def create_login(self, login: LoginRequest) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(
                login_requests_table.insert().values(
                    state=login.state,
                    code_verifier=login.code_verifier,
                    nonce=login.nonce,
                    return_to=login.return_to,
                    expires_at=login.expires_at,
                )
            )

    async def pop_login(self, state: str) -> LoginRequest | None:
        t = login_requests_table
        async with self.engine.begin() as conn:
            row = (await conn.execute(t.delete().where(t.c.state == state).returning(*t.c))).first()
        if row is None or row.expires_at <= _now():
            return None
        return LoginRequest(
            state=row.state,
            code_verifier=row.code_verifier,
            nonce=row.nonce,
            return_to=row.return_to,
            expires_at=row.expires_at,
        )

    async def create_session(self, record: SessionRecord) -> str:
        session_id = secrets.token_urlsafe(32)
        async with self.engine.begin() as conn:
            await conn.execute(
                sessions_table.insert().values(id_hash=_hash(session_id), **record.__dict__)
            )
        return session_id

    async def get_session(self, session_id: str) -> SessionRecord | None:
        t = sessions_table
        async with self.engine.connect() as conn:
            row = (
                await conn.execute(
                    sa.select(t).where(t.c.id_hash == _hash(session_id), t.c.expires_at > _now())
                )
            ).first()
        if row is None:
            return None
        return SessionRecord(
            user_id=row.user_id,
            access_token=row.access_token,
            refresh_token=row.refresh_token,
            id_token=row.id_token,
            access_expires_at=row.access_expires_at,
            expires_at=row.expires_at,
        )

    async def update_session(self, session_id: str, record: SessionRecord) -> None:
        t = sessions_table
        async with self.engine.begin() as conn:
            await conn.execute(
                t.update().where(t.c.id_hash == _hash(session_id)).values(**record.__dict__)
            )

    async def delete_session(self, session_id: str) -> None:
        t = sessions_table
        async with self.engine.begin() as conn:
            await conn.execute(t.delete().where(t.c.id_hash == _hash(session_id)))

    async def cleanup(self) -> int:
        """删除过期的会话与登录请求，返回删除条数。"""
        now = _now()
        async with self.engine.begin() as conn:
            a = await conn.execute(
                sessions_table.delete().where(sessions_table.c.expires_at <= now)
            )
            b = await conn.execute(
                login_requests_table.delete().where(login_requests_table.c.expires_at <= now)
            )
        return int(a.rowcount or 0) + int(b.rowcount or 0)
