# Quickstart: 验证源系统元数据采集（005）

本指南用于开发自测与验收前核对；正式手动验收以实施收尾交付的 `acceptance.md` 为准。接口见
[contracts/openapi.yaml](contracts/openapi.yaml)，实体映射见 [data-model.md](data-model.md)。

## 前置条件

```bash
make up                 # 平台组件：OM（已开启 pipeline service client）、织境 Airflow 镜像、Keycloak 等
make seed               # 示例本体与 OM 团队 / 角色（admin、ai-engineer）
make mock-data          # 003 模拟库 + 只读元数据账号 + viewlab 视图测试库
make ports              # 转发界面端口
```

登录织境 Web（`admin1` 或 `engineer1`），打开 `/sources`。初始状态应为空列表与空状态提示（不出现任何示例数据源）。

## 场景 A：基础设施链路（阶段 A 完成标志）

1. OM 界面 → Settings → Services 健康检查显示 Airflow 可连接，版本 3.3.2。
2. 在 Airflow 界面看不到任何 `ctx005_*` 或示例 DAG。
3. 完成场景 B 后，Airflow 中出现与任务同名的 DAG，运行在 KubernetesExecutor 任务 Pod 中完成。

## 场景 B：接入 MES 并首次采集（US1）

1. 添加数据源：显示名称 `MES 生产执行系统`、服务标识 `mock-mes`、连接器 MySQL。
2. 第 2 步填写 MES 只读账号（`make ports` 输出中给出），数据库填 `mes`（MySQL 选填；同一实例还有 `viewlab` 库，填写后只采 MES），点击测试连接。
   - 预期：逐项显示 `CheckAccess`、`GetSchemas`、`GetTables`、`GetViews`、`GetQueries` 的真实结果。
   - 把密码改错再测：`CheckAccess` 失败并给出 OM 返回的原因，后续步骤显示“未执行”，不能进入下一步。
3. 第 3 步：过滤规则全部留空；保持“采集视图”开启，不创建视图血缘任务。
4. 第 4 步：每天 02:00；保存。预期：详情页出现 1 条元数据采集任务，名称形如 `mock_mes_metadata_xxxxxxxx`。
5. 进入任务运行页点击“立即运行”。预期：状态依次为排队中 → 采集中 → 成功，开始时间与耗时为真实值；运行编号为 UUID。
6. 校验：目录树 `mock-mes → default → mes` 下 13 张表；详情统计 13 张表 / 79 个字段（003 金标准）；表详情显示主键 `PK`。
7. 浏览器开发者工具中，任何响应都不含 MES 密码明文（连接信息为 `*********`）。

QMS（PostgreSQL，数据库必填 `qms`，第 3 步 Schema 包含 `^public$`——OM 2.0.3 的 PostgreSQL 采集默认包含系统 Schema `information_schema`，原生无默认排除）与数仓（Doris，数据库 `mock_dw`）同样接入，合计 28 张表、198 个字段（SC-001）；Doris 键列显示为 `PK`。

## 场景 C：任务控制（US2）

1. 在 MES 元数据采集任务上点击“暂停调度”并确认：Airflow 中对应 DAG 变为暂停；仍可“立即运行”。
2. 运行中再次点击“立即运行”：按钮禁用；直接调用触发接口返回 `409 source.pipeline_in_flight`。
3. 打开最近一次运行详情：显示步骤 `Mysql` 与 `OpenMetadata` 的记录 / 更新 / 警告 / 错误 / 过滤数，以及脱敏日志；打开更早的运行：注明仅提供最近一次日志。

## 场景 D：视图血缘（US5）

1. 新建独立数据源接入 `viewlab`（MySQL，数据库填 `viewlab`）：使用可读视图定义的账号，开启“采集视图”并创建视图血缘任务。
2. 先运行元数据采集，再运行视图血缘。
3. 用 OM 血缘接口核对每个视图的上游表与 `columnsLineage`，与 `testdata/` 中 viewlab 的标准答案一致（SC-005）。
4. 换用受限账号（无 `SHOW VIEW`）重新采集：表与字段仍入库；运行记录如实反映视图定义不可读（状态与失败对象以 OM 实际返回为准）；不出现新的血缘边。

## 场景 E：治理属性（US4）

在 MES 服务、`default` 库、`mes` Schema、任一表与字段上编辑属性，保存后回显；清空单独设置后恢复继承；重新运行元数据采集后人工属性保持不变。

## 场景 F：依赖异常（宪法 v2.2.0）

临时将 OM 缩容到 0 副本后刷新 `/sources`：页面显示真实错误（upstream.unavailable）与重试入口，不显示任何示例数据源或伪造状态。恢复 OM 后页面恢复。

## 自动化验证

```bash
make lint
make test                         # 单元、契约（含 contracts 增量）、真实依赖集成测试与覆盖率
pnpm --filter @contexture/web test
make e2e                          # 含 /sources 端到端与 1280 / 768 / 390 视口溢出检查
```

断言以 003 金标准（28 张表 / 198 个字段）与 viewlab 标准答案为准，不断言原型中的示例数值。
