"""bff 配置：在公共库配置之上增加会话与登录相关字段。"""

from contexture_core.config import CoreSettings


class BffSettings(CoreSettings):
    service_name: str = "bff"
    client_id: str = "contexture-bff"
    token_audience: str = "contexture-bff"  # noqa: S105 受众，不是凭证

    # 织境 Web 的对外地址，用于登录回调 {public_url}/bff/v1/auth/callback
    public_url: str = "http://localhost:8080"
    # 会话库（PostgreSQL 的独占 database bff），如 postgresql+asyncpg://bff:***@host/bff
    database_url: str = ""
    session_cookie: str = "ctx_session"
    session_ttl_seconds: int = 8 * 3600
    login_ttl_seconds: int = 600
    session_cleanup_interval_seconds: int = 600

    @property
    def redirect_uri(self) -> str:
        return f"{self.public_url.rstrip('/')}/bff/v1/auth/callback"

    @property
    def cookie_secure(self) -> bool:
        return self.public_url.startswith("https://")
