import json
from pathlib import Path

import jsonschema
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from contexture_core.errors import (
    ContextureError,
    InvalidAudience,
    InvalidToken,
    UpstreamUnavailable,
    install_error_handlers,
)

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[3] / "contracts" / "schemas" / "error.json").read_text()
)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/token")
    def token() -> None:
        raise InvalidToken("令牌已过期")

    @app.get("/audience")
    def audience() -> None:
        raise InvalidAudience()

    @app.get("/upstream")
    def upstream() -> None:
        raise UpstreamUnavailable("OM 不可用", details={"upstream": "om"})

    @app.get("/custom")
    def custom() -> None:
        raise ContextureError("ontology.not_found", "对象类型不存在", status_code=404)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("内部细节不应外泄")

    @app.get("/items/{n}")
    def items(n: int) -> int:
        return n

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [
        ("/token", 401, "auth.invalid_token"),
        ("/audience", 403, "auth.invalid_audience"),
        ("/upstream", 502, "upstream.unavailable"),
        ("/custom", 404, "ontology.not_found"),
        ("/boom", 500, "internal.error"),
        ("/items/abc", 422, "request.invalid"),
        ("/missing", 404, "http.not_found"),
    ],
)
def test_errors_match_contract(client: TestClient, path: str, status: int, code: str) -> None:
    resp = client.get(path)
    assert resp.status_code == status
    body = resp.json()
    jsonschema.validate(body, SCHEMA)
    assert body["code"] == code
    assert body["trace_id"]


def test_internal_error_hides_details(client: TestClient) -> None:
    assert "内部细节" not in client.get("/boom").text


def test_details_are_returned(client: TestClient) -> None:
    assert client.get("/upstream").json()["details"] == {"upstream": "om"}


def test_invalid_code_rejected() -> None:
    with pytest.raises(ValueError, match="code"):
        ContextureError("Bad-Code", "x")


def test_http_error_keeps_headers(client: TestClient) -> None:
    resp = client.post("/items/1")
    assert resp.status_code == 405
    assert resp.json()["code"] == "http.method_not_allowed"
    assert resp.headers["allow"] == "GET"
