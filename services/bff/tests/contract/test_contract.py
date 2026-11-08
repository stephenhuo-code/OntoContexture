# pyright: basic
# Schemathesis 与 Hypothesis 的类型标注不完整，本文件按 basic 检查
"""契约测试：bff 的实际行为符合 contracts/openapi/bff.yaml（Schemathesis 按契约生成请求）。"""

import json
from pathlib import Path
from typing import Any

import httpx
import schemathesis
import yaml
from bff_fakes import FakeObjectData, FakeObjectTypes, FakeOidc, FakeSessions
from hypothesis import HealthCheck, settings
from om_fake import FakeOM
from schemathesis.specs.openapi.checks import positive_data_acceptance
from sources_helpers import service as sources_service
from support.jwt import ISSUER, JWKS_URL, LocalIssuer

from contexture_bff.main import Services, create_app
from contexture_bff.settings import BffSettings
from contexture_core.auth import Authenticator, TokenVerifier

CONTRACTS = Path(__file__).resolve().parents[4] / "contracts"


def load_contract() -> dict[str, Any]:
    """读取契约，并内联引用的错误 Schema（contracts/schemas/error.json）。"""
    spec: dict[str, Any] = yaml.safe_load((CONTRACTS / "openapi" / "bff.yaml").read_text())
    error = json.loads((CONTRACTS / "schemas" / "error.json").read_text())
    error.pop("$schema", None)
    error.pop("$id", None)
    spec["components"]["schemas"]["Error"] = error
    for response in spec["components"]["responses"].values():
        media = response.get("content", {}).get("application/json", {})
        if media.get("schema", {}).get("$ref") == "../schemas/error.json":
            media["schema"] = {"$ref": "#/components/schemas/Error"}
    return spec


issuer = LocalIssuer()
verifier = TokenVerifier(
    jwks_url=JWKS_URL,
    issuer=ISSUER,
    audience="contexture-bff",
    http=httpx.Client(transport=issuer.transport()),
)
app = create_app(
    BffSettings(tenant_id="local", public_url="http://testserver"),
    services=Services(
        sessions=FakeSessions(),
        oidc=FakeOidc(),
        object_types=FakeObjectTypes(),
        object_data=FakeObjectData(),
        authenticator=Authenticator(tenant_id="local", verifier=verifier),
        # 005：经内存 OM 夹具运行真实映射代码
        sources=sources_service(FakeOM()),
    ),
)

schema = schemathesis.openapi.from_dict(load_contract())
schema.app = app


@schema.auth()  # pyright: ignore[reportArgumentType]
class BearerAuth:
    """为需要鉴权的接口提供合法令牌；Schemathesis 另会用无效令牌检查是否被拒绝。"""

    def get(self, case: schemathesis.Case, context: object) -> str:
        return issuer.token(realm_access={"roles": ["ai-engineer"]})

    def set(self, case: schemathesis.Case, data: str, context: object) -> None:
        case.headers = {**(case.headers or {}), "Authorization": f"Bearer {data}"}  # pyright: ignore[reportAttributeAccessIssue]


@schema.parametrize()
@settings(
    max_examples=25,
    suppress_health_check=list(HealthCheck),  # pyright: ignore[reportArgumentType]
    deadline=None,
)
def test_bff_matches_contract(case: schemathesis.Case) -> None:
    # 005 的连接器级业务规则（如 MySQL 不提供 TLS、PostgreSQL 须填数据库、过滤规则须为合法正则）
    # 无法用 JSON Schema
    # 表达，按设计返回 400 source.invalid_request；由 test_sources_contract.py 与单元测试覆盖，
    # 此处不做“合法数据必被接受”检查
    # 治理属性 PATCH 同理：Tier 取值、ISO 8601 周期、互斥分类、域与产品一致性返回 400，由
    # test_governance*.py 覆盖
    business_rules = case.path.startswith("/bff/v1/sources") or (
        case.method == "PATCH" and case.path.startswith("/bff/v1/catalog")
    )
    excluded = [positive_data_acceptance] if business_rules else []
    case.call_and_validate(allow_redirects=False, excluded_checks=excluded)
