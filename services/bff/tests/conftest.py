from collections.abc import Iterator

import pytest
from bff_fakes import FakeObjectData, FakeObjectTypes, FakeOidc, FakeSessions, user_context
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from contexture_bff.api.deps import current_context
from contexture_bff.main import Services, create_app
from contexture_bff.settings import BffSettings

_EXPORTER = InMemorySpanExporter()
if not isinstance(trace.get_tracer_provider(), TracerProvider):
    _provider = TracerProvider()
    _provider.add_span_processor(SimpleSpanProcessor(_EXPORTER))
    trace.set_tracer_provider(_provider)
else:
    trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(_EXPORTER))  # type: ignore[attr-defined]


@pytest.fixture
def spans() -> Iterator[InMemorySpanExporter]:
    _EXPORTER.clear()
    yield _EXPORTER


@pytest.fixture
def settings() -> BffSettings:
    return BffSettings(tenant_id="local", public_url="http://testserver")


@pytest.fixture
def services() -> Services:
    return Services(
        sessions=FakeSessions(),
        oidc=FakeOidc(),
        object_types=FakeObjectTypes(),
        object_data=FakeObjectData(),
        authenticator=None,
    )


@pytest.fixture
def authed_client(settings: BffSettings, services: Services) -> TestClient:
    app = create_app(settings, services=services)
    app.dependency_overrides[current_context] = user_context
    return TestClient(app)


@pytest.fixture
def signed_client() -> TestClient:
    import httpx
    from bff_fakes import TokenOidc
    from support.jwt import ISSUER, JWKS_URL, LocalIssuer

    from contexture_core.auth import Authenticator, TokenVerifier

    issuer = LocalIssuer()
    svc = Services(
        sessions=FakeSessions(),
        oidc=TokenOidc(issuer),
        object_types=FakeObjectTypes(),
        object_data=FakeObjectData(),
        authenticator=Authenticator(
            tenant_id="local",
            verifier=TokenVerifier(
                jwks_url=JWKS_URL,
                issuer=ISSUER,
                audience="contexture-bff",
                http=httpx.Client(transport=issuer.transport()),
            ),
        ),
    )
    return TestClient(
        create_app(BffSettings(tenant_id="local", public_url="http://testserver"), services=svc),
        follow_redirects=False,
        raise_server_exceptions=False,
    )
