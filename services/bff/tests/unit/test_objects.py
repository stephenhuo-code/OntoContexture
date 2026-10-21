import pytest
from bff_fakes import FakeObjectData, FakeObjectTypes
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from contexture_bff.main import Services

URL = "/bff/v1/object-types/equipment/objects"


def test_combines_definition_and_rows(authed_client: TestClient, services: Services) -> None:
    resp = authed_client.get(URL, params={"limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["object_type"]["type_uri"] == "urn:ctx:object:quality:Equipment"
    assert [a["name"] for a in body["object_type"]["attributes"]] == ["code", "model"]
    assert body["items"][0] == {
        "object_uri": "urn:ctx:obj:local:Equipment:CNC-01",
        "type_uri": "urn:ctx:object:quality:Equipment",
        "attributes": {"code": "CNC-01", "model": "Mazak"},
        "source": "mcp:list_objects",
    }
    assert len(body["trace_id"]) == 32
    assert isinstance(services.object_data, FakeObjectData)
    assert services.object_data.calls == [
        {"user": "user-1-id", "type_key": "equipment", "limit": 5}
    ]


def test_default_limit_is_20(authed_client: TestClient, services: Services) -> None:
    authed_client.get(URL)
    assert isinstance(services.object_data, FakeObjectData)
    assert services.object_data.calls[-1]["limit"] == 20


@pytest.mark.parametrize("limit", [0, 101, -1])
def test_limit_out_of_range(authed_client: TestClient, limit: int) -> None:
    resp = authed_client.get(URL, params={"limit": limit})
    assert resp.status_code == 422
    assert resp.json()["code"] == "request.invalid"


@pytest.mark.parametrize("failing", ["om", "data"])
def test_upstream_failure_is_502_and_traced(
    authed_client: TestClient,
    services: Services,
    spans: InMemorySpanExporter,
    failing: str,
) -> None:
    if failing == "om":
        services.object_types = FakeObjectTypes(fail=True)
    else:
        services.object_data = FakeObjectData(fail=True)
    resp = authed_client.get(URL)
    assert resp.status_code == 502
    body = resp.json()
    assert body["code"] == "upstream.unavailable"
    traced = {format(s.context.trace_id, "032x") for s in spans.get_finished_spans() if s.context}
    assert body["trace_id"] in traced


def test_requires_authentication(settings: object, services: Services) -> None:
    from bff_fakes import FakeSessions

    from contexture_bff.main import create_app

    services.sessions = FakeSessions()
    client = TestClient(create_app(settings, services=services))  # type: ignore[arg-type]
    resp = client.get(URL)
    assert resp.status_code == 401
    assert resp.json()["code"] == "auth.invalid_token"


def test_get_object_type(authed_client: TestClient) -> None:
    resp = authed_client.get("/bff/v1/object-types/equipment")
    assert resp.status_code == 200
    assert resp.json()["type_uri"] == "urn:ctx:object:quality:Equipment"
    assert [a["name"] for a in resp.json()["attributes"]] == ["code", "model"]


def test_get_object_type_om_down(authed_client: TestClient, services: Services) -> None:
    services.object_types = FakeObjectTypes(fail=True)
    resp = authed_client.get("/bff/v1/object-types/equipment")
    assert resp.status_code == 502
    assert resp.json()["code"] == "upstream.unavailable"
