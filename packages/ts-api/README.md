# packages/ts-api/

织境前端 API 客户端。类型由 `contracts/openapi/bff.yaml` 生成到 `src/bff.d.ts`（`pnpm --filter @contexture/ts-api generate`），
不手工编辑；`pnpm --filter @contexture/ts-api check` 校验生成结果与契约一致（CI 使用）。
