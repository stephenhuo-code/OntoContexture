# contexture-core（v0.1.0）

织境公共库。自建服务的跨切面能力一律来自这里，服务内不自写令牌验证、令牌交换、关联属性与错误格式（ADR-0009 第 4 节）。

## 模块

| 模块 | 用法 |
| --- | --- |
| `config` | `load_settings(MySettings)`：读取 `CTX_*` 环境变量与挂载文件（`CTX_SECRETS_DIR`，默认 `/run/secrets/contexture`，文件名如 `ctx_client_secret`）；缺少 `CTX_TENANT_ID` 时启动失败。服务继承 `CoreSettings` 增加字段 |
| `errors` | `install_error_handlers(app)`；抛 `InvalidToken`（401）、`InvalidAudience`（403）、`UpstreamUnavailable`（502）或 `ContextureError(code, message, status_code=…)`，输出符合 `contracts/schemas/error.json` |
| `auth` | `Authenticator(tenant_id=…, verifier=TokenVerifier(...))` 作为 FastAPI 依赖项，得到 `RequestContext`（`tenant_id` 取自配置，`user_id`=`sub`，`agent_id`=`azp`，`roles`，`token_id`=`jti`）。令牌来源可替换（`token_source`），如 bff 从会话取 |
| `telemetry` | `setup_telemetry(settings, app)`；鉴权后自动给 span、日志、出站请求带上 `ctx.*` 属性。出站 HTTP 用 `traced_client()`；日志用 `configure_logging()`（JSON） |
| `mcp` | `McpClient(url=…, exchanger=TokenExchanger(...), audience=…)`：以服务自己的 Keycloak 客户端做标准令牌交换（按人与受众缓存），经 AI 网关调用 MCP 工具；`list_objects(ctx, type_key=…, limit=…)`（`limit` ≤ 100） |
| `ontology` | `OntologyClient(om_url=…, token=…, glossary=…)`：`get_object_type("equipment")` 返回已审批的对象及其属性（`ObjectTypeRef`），本地缓存 |

## 最小示例

```python
from fastapi import Depends, FastAPI

from contexture_core.auth import Authenticator, RequestContext, TokenVerifier
from contexture_core.config import load_settings
from contexture_core.errors import install_error_handlers
from contexture_core.telemetry import configure_logging, setup_telemetry

settings = load_settings()
app = FastAPI()
install_error_handlers(app)
setup_telemetry(settings, app)
configure_logging()
authenticate = Authenticator(
    tenant_id=settings.tenant_id,
    verifier=TokenVerifier(
        jwks_url=settings.jwks_url, issuer=settings.issuer, audience=settings.token_audience
    ),
)


@app.get("/v1/hello")
async def hello(ctx: RequestContext = Depends(authenticate)) -> dict[str, str]:
    return {"user": ctx.user_id or ""}
```

## 版本

语义化版本；升级须在端到端骨架上回归通过。
