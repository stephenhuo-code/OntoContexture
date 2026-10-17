import io
import json
import logging

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from support.jwt import ISSUER, JWKS_URL, LocalIssuer

from contexture_core.auth import Authenticator, RequestContext, TokenVerifier
from contexture_core.config import CoreSettings
from contexture_core.errors import install_error_handlers
from contexture_core.telemetry import JsonFormatter, setup_telemetry, traced_client

CTX_KEYS = ("ctx.tenant.id", "ctx.user.id", "ctx.agent.id", "ctx.token.id")


@pytest.fixture
def outbound() -> list[httpx.Request]:
    return []


@pytest.fixture
def log_stream() -> io.StringIO:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test.telemetry")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return stream


@pytest.fixture
def client(outbound: list[httpx.Request]) -> TestClient:
    issuer = LocalIssuer()
    verifier = TokenVerifier(
        jwks_url=JWKS_URL,
        issuer=ISSUER,
        audience="contexture-bff",
        http=httpx.Client(transport=issuer.transport()),
    )
    app = FastAPI()
    install_error_handlers(app)
    setup_telemetry(CoreSettings(tenant_id="local", service_name="test-svc"), app=app)
    authenticate = Authenticator(tenant_id="local", verifier=verifier)

    def record(request: httpx.Request) -> httpx.Response:
        outbound.append(request)
        return httpx.Response(200, json={})

    @app.get("/work")
    async def work(ctx: RequestContext = Depends(authenticate)) -> str:  # noqa: B008
        logging.getLogger("test.telemetry").info("doing work")
        async with traced_client(transport=httpx.MockTransport(record)) as http:
            await http.get("http://downstream.test/x")
        return "ok"

    test_client = TestClient(app)
    test_client.headers["Authorization"] = f"Bearer {issuer.token(jti='jti-9')}"
    return test_client


def test_spans_carry_correlation_attributes(
    client: TestClient, spans: InMemorySpanExporter
) -> None:
    assert client.get("/work").status_code == 200
    finished = spans.get_finished_spans()
    server = [s for s in finished if s.kind.name == "SERVER"]
    outgoing = [s for s in finished if s.kind.name == "CLIENT"]
    assert server and outgoing
    for span in (server[0], outgoing[0]):
        attrs = span.attributes or {}
        assert attrs["ctx.tenant.id"] == "local"
        assert attrs["ctx.user.id"] == "user-1-id"
        assert attrs["ctx.agent.id"] == "contexture-bff"
        assert attrs["ctx.token.id"] == "jti-9"


def test_logs_carry_correlation_attributes(client: TestClient, log_stream: io.StringIO) -> None:
    client.get("/work")
    record = json.loads(log_stream.getvalue().strip().splitlines()[-1])
    assert record["message"] == "doing work"
    for key in CTX_KEYS:
        assert key in record
    assert record["ctx.user.id"] == "user-1-id"
    assert len(record["trace_id"]) == 32


def test_outbound_carries_traceparent_and_baggage(
    client: TestClient, outbound: list[httpx.Request], spans: InMemorySpanExporter
) -> None:
    client.get("/work")
    headers = outbound[-1].headers
    version, trace_id, _span_id, _flags = headers["traceparent"].split("-")
    assert version == "00"
    server = next(s for s in spans.get_finished_spans() if s.kind.name == "SERVER")
    assert server.context is not None
    assert trace_id == format(server.context.trace_id, "032x")
    baggage = dict(item.split("=", 1) for item in headers["baggage"].split(","))
    assert baggage["ctx.user.id"] == "user-1-id"
    assert baggage["ctx.tenant.id"] == "local"


def test_unauthenticated_spans_still_carry_tenant(spans: InMemorySpanExporter) -> None:
    app = FastAPI()
    setup_telemetry(CoreSettings(tenant_id="local"), app=app)

    @app.get("/health")
    def health() -> str:
        return "ok"

    TestClient(app).get("/health")
    server = next(s for s in spans.get_finished_spans() if s.kind.name == "SERVER")
    assert (server.attributes or {})["ctx.tenant.id"] == "local"
