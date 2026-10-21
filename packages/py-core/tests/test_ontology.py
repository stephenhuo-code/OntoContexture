from typing import Any

import httpx
import pytest

from contexture_core.errors import ContextureError, UpstreamUnavailable
from contexture_core.ontology import AttributeRef, ObjectTypeRef, OntologyClient

OM = "http://om.test"


def term(
    id_: str,
    name: str,
    kind: str,
    status: str = "Approved",
    *,
    related: list[str] | None = None,
    data_type: str | None = None,
    required: str | None = None,
    level: str | None = None,
    uri: str | None = None,
) -> dict[str, Any]:
    ext: dict[str, Any] = {"ctx_kind": kind}
    if uri:
        ext["ctx_uri"] = uri
    if data_type:
        ext["ctx_data_type"] = data_type
    if required:
        ext["ctx_required"] = required
    return {
        "id": id_,
        "name": name,
        "displayName": name.title(),
        "fullyQualifiedName": f"quality.{name}",
        "version": 0.3,
        "entityStatus": status,
        "extension": ext,
        "tags": [{"tagFQN": f"数据级别.{level}"}] if level else [],
        "relatedTerms": [
            {"relationType": "hasProperty", "term": {"id": r, "type": "glossaryTerm"}}
            for r in related or []
        ]
        + [{"relationType": "relatedTo", "term": {"id": "t-other", "type": "glossaryTerm"}}],
    }


TERMS = [
    term(
        "t-eq",
        "Equipment",
        "object",
        related=["t-code", "t-model", "t-price"],
        uri="urn:ctx:object:quality:Equipment",
    ),
    term("t-code", "code", "property", data_type="string", required="是", level="一级"),
    term("t-model", "model", "property", data_type="string", required="否", level="二级"),
    term("t-price", "purchase_price", "property", status="Draft", data_type="decimal"),
    term("t-draft", "Fixture", "object", status="In Review"),
    term("t-other", "other", "property", data_type="string"),
]


class FakeOM:
    def __init__(self, terms: list[dict[str, Any]], page_size: int = 4) -> None:
        self.terms = terms
        self.page_size = page_size
        self.requests: list[httpx.Request] = []

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            assert request.headers["authorization"] == "Bearer om-token"
            if request.url.path == "/api/v1/glossaries/name/quality":
                return httpx.Response(200, json={"id": "g-quality", "name": "quality"})
            if request.url.path == "/api/v1/glossaries/name/missing":
                return httpx.Response(404, json={"message": "not found"})
            assert request.url.path == "/api/v1/glossaryTerms"
            assert request.url.params["glossary"] == "g-quality"
            assert request.url.params["entityStatus"] == "Approved"
            assert "relatedTerms" in request.url.params["fields"]
            start = int(request.url.params.get("after") or 0)
            page = self.terms[start : start + self.page_size]
            nxt = start + self.page_size
            paging: dict[str, Any] = {"total": len(self.terms)}
            if nxt < len(self.terms):
                paging["after"] = str(nxt)
            return httpx.Response(200, json={"data": page, "paging": paging})

        return httpx.MockTransport(handler)


def make_client(om: FakeOM, glossary: str = "quality") -> OntologyClient:
    return OntologyClient(
        om_url=OM,
        token="om-token",
        glossary=glossary,
        http=httpx.AsyncClient(transport=om.transport()),
    )


async def test_returns_approved_object_with_approved_attributes() -> None:
    ref = await make_client(FakeOM(TERMS)).get_object_type("equipment")
    assert ref == ObjectTypeRef(
        type_uri="urn:ctx:object:quality:Equipment",
        name="Equipment",
        display_name="Equipment",
        version="0.3",
        attributes=[
            AttributeRef(name="code", data_type="string", required=True, data_level=1),
            AttributeRef(name="model", data_type="string", required=False, data_level=2),
        ],
    )


async def test_unapproved_object_is_not_returned() -> None:
    with pytest.raises(ContextureError) as exc:
        await make_client(FakeOM(TERMS)).get_object_type("fixture")
    assert exc.value.status_code == 404
    assert exc.value.code == "ontology.not_found"


async def test_enum_values_stored_as_arrays() -> None:
    """OM 的枚举型自定义属性以数组存值。"""
    obj = term("t-x", "Batch", "object", related=["t-p"])
    obj["extension"]["ctx_kind"] = ["object"]
    prop = term("t-p", "lot", "property", data_type="string", required="是")
    prop["extension"].update(
        {"ctx_kind": ["property"], "ctx_data_type": ["string"], "ctx_required": ["是"]}
    )
    ref = await make_client(FakeOM([obj, prop])).get_object_type("batch")
    assert ref.attributes == [AttributeRef(name="lot", data_type="string", required=True)]


async def test_uri_defaults_from_glossary_and_name() -> None:
    terms = [term("t-x", "Batch", "object")]
    ref = await make_client(FakeOM(terms)).get_object_type("batch")
    assert ref.type_uri == "urn:ctx:object:quality:Batch"
    assert ref.attributes == []


async def test_results_are_cached() -> None:
    om = FakeOM(TERMS)
    client = make_client(om)
    await client.get_object_type("equipment")
    count = len(om.requests)
    await client.get_object_type("equipment")
    assert len(om.requests) == count


async def test_unknown_glossary_is_not_found() -> None:
    with pytest.raises(ContextureError) as exc:
        await make_client(FakeOM(TERMS), glossary="missing").get_object_type("equipment")
    assert exc.value.code == "ontology.not_found"


async def test_om_unreachable_is_upstream_unavailable() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = OntologyClient(
        om_url=OM,
        token="om-token",
        glossary="quality",
        http=httpx.AsyncClient(transport=httpx.MockTransport(down)),
    )
    with pytest.raises(UpstreamUnavailable):
        await client.get_object_type("equipment")
