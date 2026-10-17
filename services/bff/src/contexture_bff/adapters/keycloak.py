"""Keycloak OIDC：授权码 + PKCE 登录、刷新与登出（Authlib）。"""

from dataclasses import dataclass
from typing import Any, Protocol

from authlib.integrations.httpx_client import AsyncOAuth2Client

from contexture_bff.settings import BffSettings


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str
    id_token: str
    expires_in: int
    refresh_expires_in: int


class Oidc(Protocol):
    def authorization_url(self, *, state: str, code_challenge: str, nonce: str) -> str: ...
    async def exchange_code(self, *, code: str, code_verifier: str) -> TokenSet: ...
    async def refresh(self, refresh_token: str) -> TokenSet: ...
    async def logout(self, refresh_token: str) -> None: ...


def _token_set(token: dict[str, Any], fallback_refresh: str = "") -> TokenSet:
    return TokenSet(
        access_token=str(token["access_token"]),
        refresh_token=str(token.get("refresh_token") or fallback_refresh),
        id_token=str(token.get("id_token", "")),
        expires_in=int(token.get("expires_in", 60)),
        refresh_expires_in=int(token.get("refresh_expires_in", 0)),
    )


class KeycloakOidc:
    def __init__(self, settings: BffSettings) -> None:
        self.settings = settings
        base = f"{settings.issuer}/protocol/openid-connect"
        self.authorize_endpoint = f"{base}/auth"
        self.token_endpoint = f"{base}/token"
        self.logout_endpoint = f"{base}/logout"

    def _client(self) -> Any:
        # Authlib 的 AsyncOAuth2Client 继承自动态导入的 httpx2.AsyncClient，类型检查器看不到其方法
        return AsyncOAuth2Client(
            client_id=self.settings.client_id,
            client_secret=self.settings.client_secret.get_secret_value(),
            redirect_uri=self.settings.redirect_uri,
            scope="openid profile email",
            timeout=10,
        )

    def authorization_url(self, *, state: str, code_challenge: str, nonce: str) -> str:
        client = self._client()
        url, _ = client.create_authorization_url(
            self.authorize_endpoint,
            state=state,
            nonce=nonce,
            code_challenge=code_challenge,
            code_challenge_method="S256",
        )
        return str(url)

    async def exchange_code(self, *, code: str, code_verifier: str) -> TokenSet:
        client = self._client()
        try:
            token = await client.fetch_token(
                self.token_endpoint, code=code, code_verifier=code_verifier
            )
        finally:
            await client.aclose()
        return _token_set(dict(token))

    async def refresh(self, refresh_token: str) -> TokenSet:
        client = self._client()
        try:
            token = await client.refresh_token(self.token_endpoint, refresh_token=refresh_token)
        finally:
            await client.aclose()
        return _token_set(dict(token), fallback_refresh=refresh_token)

    async def logout(self, refresh_token: str) -> None:
        """后端通道登出：结束 Keycloak 会话。"""
        client = self._client()
        try:
            await client.post(
                self.logout_endpoint,
                data={
                    "client_id": self.settings.client_id,
                    "client_secret": self.settings.client_secret.get_secret_value(),
                    "refresh_token": refresh_token,
                },
            )
        finally:
            await client.aclose()
