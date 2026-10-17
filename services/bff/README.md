# services/bff/

织境 Web 的后端（BFF 模式，ADR-0003），Phase 1 唯一的自建后端服务，也是代码分层的参考实现（ADR-0009 第 3 节）。

- 浏览器只持有会话 Cookie（`ctx_session`），令牌只在 bff；会话存 PostgreSQL 的独占 database `bff`。
- 直接调用（脚本、测试）可用 Bearer 令牌，受众须含 `contexture-bff`。
- 取数经 AI 网关以 MCP 调用（ADR-0013），对象定义经 OM 读取已审批内容（ADR-0008）。

## 目录

```text
src/contexture_bff/
  api/        # 路由与请求 / 响应模型，与 contracts/openapi/bff.yaml 一致
  adapters/   # 外部访问：sessions（PostgreSQL）、keycloak（OIDC）、om（对象定义）、data（MCP 取数）
  main.py     # 组装：配置、鉴权、追踪、错误处理全部来自 contexture-core
  migrate.py  # 会话库迁移（Alembic，脚本在 migrations/）
tests/unit/ tests/contract/ tests/integration/
```

## 本地运行测试

```bash
uv run pytest services/bff -m "not integration"   # 单元 + 契约
uv run pytest services/bff -m integration         # 需要 Docker：真实 Keycloak + PostgreSQL
```

## 新增一个接口（契约 → 测试 → 实现）

不写令牌验证、追踪、错误处理代码：鉴权用依赖项 `current_context`，错误直接抛公共库的异常，追踪自动生效。

1. **契约**：在 `contracts/openapi/bff.yaml` 增加路径与响应模型（错误响应引用 `#/components/responses/Error`）。
2. **测试**：在 `tests/unit/` 写接口测试（用 `authed_client` 夹具和 `bff_fakes` 中的替身）；运行确认失败。
   契约测试 `tests/contract/test_contract.py` 自动覆盖新路径，无需修改。
3. **实现**：在 `api/` 中加路由函数：

   ```python
   @router.get("/object-types/{type_key}")
   async def get_object_type(
       request: Request,
       type_key: str,
       ctx: Annotated[RequestContext, Depends(current_context)],  # 鉴权：401 / 403 由公共库返回
   ) -> ObjectTypeRef:
       return await services(request).object_types.get(type_key)  # 上游失败抛 UpstreamUnavailable → 502
   ```

   需要访问新的外部系统时，先在 `adapters/` 加适配器（定义 Protocol + 实现），在 `main.py` 的 `Services` 中注册。
4. **验证**：`uv run pytest services/bff -m "not integration"`、`make lint`。

### 演练记录（SC-001）

| 日期 | 新增接口 | 执行者 | 用时 | 是否写了跨切面代码 |
| --- | --- | --- | --- | --- |
| 2026-10-17 | `GET /bff/v1/object-types/{typeKey}`（契约 + 2 个测试 + 10 行实现） | Claude（AI） | 约 1 分钟 | 否 |

SC-001 的口径是“开发者 ≤ 30 分钟”，人工演练在 001 的手动验收中进行（`specs/001-engineering-foundation/acceptance.md`）。
