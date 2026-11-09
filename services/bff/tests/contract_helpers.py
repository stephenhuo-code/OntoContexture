"""005 契约测试共用：契约文档、错误 schema 与基于内存 OM 的测试应用。"""

import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml
from assets_helpers import reader, search_service
from bff_fakes import FakeObjectData, FakeObjectTypes, FakeOidc, FakeSessions, user_context
from fastapi.testclient import TestClient
from om_fake import FakeOM
from sources_helpers import service

from contexture_bff.api.deps import current_context
from contexture_bff.main import Services, create_app
from contexture_bff.settings import BffSettings

CONTRACTS = Path(__file__).resolve().parents[3] / "contracts"
SPEC = yaml.safe_load((CONTRACTS / "openapi" / "bff.yaml").read_text())
ERROR = json.loads((CONTRACTS / "schemas" / "error.json").read_text())


def schema(name: str) -> dict[str, Any]:
    return {"$ref": f"#/components/schemas/{name}", "components": SPEC["components"]}


def check(body: Any, name: str) -> None:
    jsonschema.validate(body, schema(name))


def make(om: FakeOM, roles: tuple[str, ...] = ("ai-engineer",)) -> TestClient:
    app = create_app(
        BffSettings(tenant_id="local", public_url="http://testserver"),
        services=Services(
            sessions=FakeSessions(),
            oidc=FakeOidc(),
            object_types=FakeObjectTypes(),
            object_data=FakeObjectData(),
            authenticator=None,
            sources=service(om),
            assets=search_service(om),
            asset_reader=reader(om),
        ),
    )
    app.dependency_overrides[current_context] = lambda: user_context(roles=roles)
    return TestClient(app)
