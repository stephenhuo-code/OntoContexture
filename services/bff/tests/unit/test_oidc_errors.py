from typing import Any

import httpx
import httpx2
import pytest
from authlib.oauth2.rfc6749 import OAuth2Error

from contexture_bff.adapters.keycloak import KeycloakOidc
from contexture_bff.settings import BffSettings
from contexture_core.errors import InvalidToken, UpstreamUnavailable


@pytest.mark.parametrize("operation", ["exchange", "refresh"])
@pytest.mark.parametrize(
    "error,expected",
    [
        (OAuth2Error(error="invalid_grant"), InvalidToken),
        (OAuth2Error(error="server_error"), UpstreamUnavailable),
        (httpx.ConnectError("offline"), UpstreamUnavailable),
        (httpx2.ConnectError("offline"), UpstreamUnavailable),
        (
            httpx.HTTPStatusError(
                "server unavailable",
                request=httpx.Request("POST", "https://sso.test/token"),
                response=httpx.Response(503),
            ),
            UpstreamUnavailable,
        ),
        (OAuth2Error(error="invalid_client"), OAuth2Error),
    ],
)
async def test_token_error_classification_and_client_cleanup(
    settings: BffSettings,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    error: Exception,
    expected: type[Exception],
) -> None:
    class Client:
        closed = False

        async def fetch_token(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise error

        async def refresh_token(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise error

        async def aclose(self) -> None:
            self.closed = True

    client = Client()
    oidc = KeycloakOidc(settings)
    monkeypatch.setattr(oidc, "_client", lambda: client)
    with pytest.raises(expected):
        if operation == "exchange":
            await oidc.exchange_code(code="test-code", code_verifier="test-verifier")
        else:
            await oidc.refresh("test-refresh")
    assert client.closed
