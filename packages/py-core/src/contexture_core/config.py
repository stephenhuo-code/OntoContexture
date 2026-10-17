"""配置加载：环境变量 + 挂载文件（Secret），提供部署级常量 tenant_id。

环境变量以 ``CTX_`` 为前缀；挂载文件的文件名为变量名（如 ``ctx_client_secret``），环境变量优先。
各服务继承 ``CoreSettings`` 增加自己的字段。
"""

import os
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRETS_DIR = Path("/run/secrets/contexture")


class CoreSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CTX_", extra="ignore")

    # Phase 1 单租户：部署常量，不来自令牌（ADR-0007）
    tenant_id: str
    service_name: str = "contexture"

    # Keycloak：验签与令牌交换
    keycloak_url: str = ""
    keycloak_realm: str = ""
    token_audience: str = ""
    client_id: str = ""
    client_secret: SecretStr = SecretStr("")

    # AI 网关（MCP 入口，ADR-0013）
    ai_gateway_audience: str = "contexture-ai-gateway"
    ai_gateway_mcp_url: str = ""

    # OpenMetadata：读取已审批的本体（ADR-0008）
    om_url: str = ""
    om_token: SecretStr = SecretStr("")
    om_glossary: str = "quality"

    # OTLP 导出地址；为空时不导出
    otel_exporter_otlp_endpoint: str = ""

    @property
    def issuer(self) -> str:
        return f"{self.keycloak_url.rstrip('/')}/realms/{self.keycloak_realm}"

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer}/protocol/openid-connect/certs"

    @property
    def token_url(self) -> str:
        return f"{self.issuer}/protocol/openid-connect/token"


def load_settings[T: CoreSettings](
    cls: type[T] = CoreSettings,  # type: ignore[assignment]
    secrets_dir: Path | None = None,
) -> T:
    """加载配置；缺少必填项（如 CTX_TENANT_ID）时抛出 ValidationError，服务启动失败。"""
    if secrets_dir is None:
        secrets_dir = Path(os.environ.get("CTX_SECRETS_DIR", DEFAULT_SECRETS_DIR))
    if secrets_dir.is_dir():
        return cls(_secrets_dir=secrets_dir)  # type: ignore[call-arg]
    return cls()  # type: ignore[call-arg]
