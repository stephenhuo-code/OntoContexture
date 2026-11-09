# 006 资产搜索与摘要：验收文档

- 特性分支：`006-asset-search-summary`（未推送、未合并到 main）
- 规格：[spec.md](spec.md)；计划：[plan.md](plan.md)；调研与实测结论：[research.md](research.md)
- 预计用时：约 40 分钟（第 1 节准备约 10 分钟，第 2～5 节逐步操作约 30 分钟）
- 本文所有数字都来自本地集群实测；原型中的数字只是演示，不作为预期结果。

---

## 1. 前置条件与数据准备

在仓库根目录执行。本地集群为 kind，部署环境为 `lite`。

> **注意 kubectl 上下文**：2026-11-09 实施期间，本机 kubectl 当前上下文曾被切到 `do-sfo2-…`（DigitalOcean 集群）。下面的集群命令都显式指定 `--context kind-contexture`；`make` 目标中的 kubectl 会使用当前上下文，执行前请先确认它指向本地集群：
>
> ```bash
> kubectl config use-context kind-contexture
> ```

```bash
make up ENV=lite          # 平台组件（已部署的可跳过）
make seed                 # OM 团队 / 角色、数据级别分类
make dev-metadata         # 导入开发态测试元数据（可重复执行）
make dev-metadata         # 再执行一次，检查幂等
make ports                # 转发组件界面端口
```

**预期结果**：
- 第一次 `make dev-metadata` 输出「新建 50，更新 0，未变化 0」（环境中已有导入数据时为「新建 0」）；
- 第二次输出「新建 0，更新 0，未变化 50」（SC-008）。

**拒绝写入的检查**（FR-017）：

```bash
uv run python -m mockfactory om-import --om-url http://localhost:18585; echo "退出码=$?"
```

预期输出「未显式指定开发态目标环境（--target local），拒绝写入。」，退出码为 1。

**本次部署的 BFF 与 Web**：验收前开发方已把本分支代码构建为 `contexture/bff:dev` 和 `contexture/web:dev`，并部署到本地集群。如果需要重新部署：

```bash
docker build -f services/bff/Dockerfile -t contexture/bff:dev . && docker build -f apps/web/Dockerfile -t contexture/web:dev .
kind load docker-image --name contexture contexture/bff:dev contexture/web:dev
kubectl --context kind-contexture -n contexture rollout restart deployment/contexture-bff deployment/web-web
```

**登录**：浏览器打开 <http://localhost:8080/assets>，用 `engineer1` / `engineer1` 登录。

---

## 2. 环境前置（D11）排查结论

| 阶段 | 配置（`deploy/components/opensearch/values/lite.yaml`） | 结果 |
| --- | --- | --- |
| 开工前 | 堆 384m，上限 1Gi | 重启 321 次，`OOMKilled`（exit 137） |
| 第 1 次调整 | 堆 384m，上限 1280Mi | 空载 10 分钟不重启；完整 e2e 负载下堆接近占满（约 370MB/384MB），再次 OOMKilled |
| 第 2 次调整 | 堆 512m，上限 1536Mi | 完整 e2e 期间仍 OOMKilled 6 次，同期 OM 返回 502 |
| 第 3 次调整（当前） | 堆 512m，直接内存 256m，requests 1Gi，上限 2Gi | 完整验证（集群集成测试 + 全部 e2e，约 12 分钟）期间重启 0 次 |

- 每次调整都只改配置，并先补失败测试（`deploy/components/opensearch/tests/test_values.py`）。
- 节点各有 32GB 内存，已申请约 20%，2Gi 上限对节点没有压力。
- 是否把同样的调整用到 `base.yaml`（local 环境），由负责人决定。

**仍存在的环境问题**（不属于 006，未处理）：
- Airflow `airflow-dag-processor` 处于 CrashLoopBackOff（重启 236 次以上），`airflow-scheduler` 反复 OOMKilled（114 次以上），导致 005 的采集触发偶发失败（见第 7 节）；
- 001 的 Langfuse 追踪查询返回 422，与 005 验收时的记录相同。

---

## 3. 逐步操作与预期结果

### US1：用关键词搜索资产并查看摘要（SC-001、SC-002、SC-005、SC-009）

| # | 操作 | 预期结果 |
| --- | --- | --- |
| 1 | 打开 `/assets` | 页面为「数据资产」，不是「尚未开放」；顶栏左侧面包屑以「数据资产」开头，中间是搜索框，右侧是账户 |
| 2 | 点搜索范围下拉 | 默认「全部资产」，其余选项只列当前有数据的类型 |
| 3 | 在搜索框输入 `work_order`，停顿约半秒 | 出现按类型分组的输入建议，每组不超过 5 条，每条显示名称与完整位置 |
| 4 | 回车 | 排序变为「相关性」；左栏变成类型列表（只列计数大于 0 的类型），默认选中「数据表」；页头显示「共 N 条」 |
| 5 | 看结果卡片 | 面包屑能区分 `devtest-mes / default / mes` 与 `devtest-mes / default / mes_archive` 两张同名表（SC-005）；业务域、负责人、「分级（Tier）」「数据安全级别」分开显示；导入的资产显示「开发态测试元数据」 |
| 6 | 看右侧摘要 | 自动选中第一条；页签为「概览」「Schema」；概览依次为描述、负责人、业务域、分级（Tier）、数据安全级别、认证、业务术语、分类标签、数据产品、来源 |
| 7 | 点「Schema」页签 | 列出字段：名称、类型、主键或唯一约束、描述、分类标签；`wo_no` 显示「主键」 |
| 8 | 按 Esc | 摘要关闭 |
| 9 | 搜索一个不存在的词，例如 `zzzz不存在` | 显示「无匹配结果」和「清除条件」，摘要关闭 |
| 10 | 搜索范围选「数据表」，再搜索 `工单` | 结果只有数据表 |

### US2：浏览树、快速筛选、条件条、排序分页（SC-001、SC-004）

| # | 操作 | 预期结果 |
| --- | --- | --- |
| 1 | 点「清除全部」或刷新 `/assets` | 左栏为浏览树，只显示有数据的大类（如「数据库」「数据治理」），条件条显示操作提示 |
| 2 | 依次展开「数据库 → Mysql → devtest-mes → default」，点「mes」 | 页面不跳转；列表只剩 `devtest-mes / default / mes` 下的资产；条件条逐层显示位置 |
| 3 | 在条件条中删除「devtest-mes」 | 「devtest-mes」及其下层的位置条件一起删除 |
| 4 | 快速筛选「分级（Tier）」勾选两个取值，再在「业务域」勾选一个取值 | 结果满足「(取值 1 或 取值 2) 且 业务域」；各下拉中的计数不受本维度自身选择的影响 |
| 5 | 「负责人」勾选「无」 | 只剩没有负责人的资产；「无」不显示计数 |
| 6 | 搜索范围选「数据表」 | 快速筛选增加「库」「Schema」「列」「表类型」「列描述」 |
| 7 | 排序切换为「名称」，再点 ↓ 切换为升序 | 页码回到第 1 页，按新顺序展示 |
| 8 | 每页条数改为 50，翻页 | 总数不变；超过 10000 条时显示「仅显示前 10000 条，请缩小条件」 |

### US3：同一页面中的子视图（SC-007）

| # | 操作 | 预期结果 |
| --- | --- | --- |
| 1 | 点页头「数据源管理」 | 进入 `/assets/sources`，面包屑为「数据资产 / 数据源管理」，005 的数据源列表功能不变 |
| 2 | 回到 `/assets`，点「添加数据源」 | 打开 005 的接入向导 |
| 3 | 搜索 `work_order`，点卡片名称「生产工单」 | 进入 `/assets/table/…` 的 005 表详情，属性卡片与编辑弹窗显示「分级（Tier）」（Q4） |
| 4 | 点面包屑「数据资产」 | 回到探索视图，关键词、筛选、排序、页码保持不变 |
| 5 | 搜索 `wo_no`，左栏选「列」，点一条列结果 | 进入所属表的详情，`wo_no` 所在行高亮（Q3），地址中不含列名 |
| 6 | 搜索 `工单`，左栏选「业务术语」，点「工单」 | 进入业务术语只读详情：14 项字段，没有编辑按钮，有「返回探索视图」 |
| 7 | 打开 `/assets/tag/数据级别.一级` | 分类标签只读详情：10 项字段 |
| 8 | 在详情页点左侧浏览树中的任一节点 | 回到 `/assets`，并以该节点作为位置条件 |
| 9 | 依次打开 `/sources`、`/sources/devtest-mes`、`/sources/devtest-mes/assets/table/devtest-mes.default.mes.work_order` | 分别转到 `/assets/sources`、`/assets/sources/devtest-mes`、`/assets/table/devtest-mes.default.mes.work_order` |
| 10 | 刷新 `/assets` | 回到初始浏览状态（D9，不保存搜索条件），属于预期 |

### 页面状态与窄屏（FR-015、SC-006）

| # | 操作 | 预期结果 |
| --- | --- | --- |
| 1 | 在 `/assets` 执行 `kubectl --context kind-contexture -n contexture scale deploy/openmetadata --replicas=0`，等约 1 分钟后刷新页面 | 结果区显示「搜索失败 · upstream.unavailable」和「重试」按钮，不出现任何结果卡片或示例数据 |
| 2 | 执行 `kubectl --context kind-contexture -n contexture scale deploy/openmetadata --replicas=1 && kubectl --context kind-contexture -n contexture rollout status deploy/openmetadata --timeout=480s`，再点「重试」 | 结果恢复 |
| 3 | 浏览器窗口宽度缩到 390px | 浏览树收进「目录」按钮；摘要以覆盖层显示，按 Esc 可关闭；整页没有横向滚动条 |

### 开发态元数据的撤除（FR-017，可选，验收最后执行）

```bash
make dev-metadata-remove
```

预期：导入的 3 个服务、术语表、业务域和 2 个分类被删除，搜索不到 `devtest-` 开头的资产；005 采集的资产不受影响。之后执行 `make dev-metadata` 可恢复。

---

## 4. 与用户故事和成功标准的对应

| 成功标准 | 验证方式 | 结论 |
| --- | --- | --- |
| SC-001 可搜到、可浏览 | 集成测试：29 张 fixture 表都能按英文表名搜到，并都能经浏览树逐层定位；类型计数、浏览树计数与直接调用 OM 一致；手动 US1、US2 | 通过 |
| SC-002 主路径效率 | e2e：搜索路径 3 步 / 395ms；浏览路径 5 步 / 500ms（都在 5 次操作、30 秒以内）；手动计时一次 | 通过（待手动计时） |
| SC-003 响应速度 | e2e 各 20 次：搜索 p95 332ms、筛选 p95 75ms、翻页 p95 89ms（都在 2 秒以内），环境故障样本 0 个；完整负载期间的另一次测量：搜索 p95 804ms、筛选 182ms、翻页 546ms | 通过 |
| SC-004 组合条件正确 | 集成测试：关键词、位置、同维度多选、跨维度组合、「无」5 组用例，总数与 ID 集合都和直接调用 OM 一致 | 通过 |
| SC-005 同名可辨 | 集成测试与 e2e：两张 `work_order` 的面包屑分别为 `…/mes` 与 `…/mes_archive` | 通过 |
| SC-006 不造数据 | 契约测试（OM 500 / 索引缺失 / 超时 / 不可达）、组件测试（错误、零资产、加载中）、e2e（OM 缩容后显示 `upstream.unavailable`，恢复后正常）；代码审查确认生产代码中没有示例数据和出错回退 | 通过；索引缺失与零资产只在契约测试和组件测试中验证（见第 6 节） |
| SC-007 005 不退化 | 005 Web 单元测试在新路径下全部通过；005 e2e 在新路径下 20 个用例全部通过过一轮；新增旧地址重定向 e2e | 通过；最后一轮中 1 个 005 e2e 受 Airflow 环境影响失败（见第 7 节） |
| SC-008 导入幂等 | 集群测试：第二次导入新建 0，测试资产总数不变，005 服务 `mock-mes` 的 version 与 updatedAt 不变；撤除后可重新导入 | 通过 |
| SC-009 中文检索观察 | 见第 5 节 | 待负责人按 D10 判定 |

---

## 5. SC-009 中文检索观察（D10）

- 环境：EN 映射，未安装中文分词插件。
- 关键词：固定 10 个，取自 003 表定义的中文说明。
- 搜索范围：开发态测试表，按相关性排序。
- 完整结果：`services/bff/tests/integration/test_sc009_chinese_cluster.py` 的输出，以及 `test-results/006-sc009.json`。

| 关键词 | 命中数 | 应命中的表 | 前 3 条 | 应命中的表在前 3 |
| --- | --- | --- | --- | --- |
| 生产工单 | 3 | work_order | work_order、work_order、dwd_operation_report | 是 |
| 产线 | 5 | production_line 等 5 张 | production_line、dws_line_monthly_quality、dim_line | 是 |
| 设备事件 | 3 | equipment_event | equipment_event、dim_equipment、equipment | 是 |
| 物料批次 | 4 | material_lot | material_lot、dwd_inspection_value、production_batch | 是 |
| 供应商 | 1 | supplier | supplier | 是 |
| 检验实测值 | 2 | inspection_value、dwd_inspection_value | inspection_value、dwd_inspection_value | 是 |
| 不合格报告 | 1 | ncr | ncr | 是 |
| 缺陷码 | 1 | defect_code | defect_code | 是 |
| 质量汇总 | 2 | dws_line_daily/monthly_quality | dws_line_monthly_quality、dws_line_daily_quality | 是 |
| 投料记录 | 1 | material_consumption | material_consumption | 是 |

- 10 个关键词中，应命中的表全部排在前 3 位。
- EN 映射把中文拆成单字，高亮也是逐字的（例如「工」「单」分别高亮）。
- 是否另立项改用中文分词，请负责人判定。

---

## 6. 开发方已执行的自动化验证（2026-11-09）

| 检查 | 结果 |
| --- | --- |
| `make lint`（ruff、pyright、eslint、prettier） | 通过 |
| `make test`（Python） | 544 passed，总覆盖率 90.06% |
| 新增与修改代码的行覆盖率（`tools.coverage_gate --base main`） | 1200/1282 = 93.60%（≥ 80%） |
| `pnpm --filter @contexture/ts-api check` | 通过（契约与生成类型一致） |
| `pnpm --filter @contexture/web test` | 23 个文件，142 passed；行覆盖率 91.32% |
| 006 集群集成测试（`-m cluster`：搜索、摘要、浏览、实测项、导入、SC-009） | 全部通过 |
| `pytest -m cluster services/bff/tests/integration testdata/tests` 全量 | 33 passed / 1 failed（005 视图血缘，Airflow 触发失败，见第 7 节） |
| `make e2e` pytest 阶段（`deploy/components`、`tests/e2e`） | 13 passed / 1 failed（001 追踪，Langfuse 422） |
| `make e2e` 浏览器阶段（`pnpm e2e:browser`） | 25 passed / 1 failed（005 US3 触发采集时 OM 返回 502，Airflow 不稳定）；同一用例在上一轮通过 |
| `make e2e` 组件示例阶段（`pnpm e2e:ui`） | 1 passed |
| 006 e2e（`tests/e2e/assets.spec.ts`，10 个用例） | 全部通过 |

---

## 7. 已知限制与环境阻塞

**OM 默认行为，006 不调整**：
- 只命中字段名时，表卡片上没有高亮：OM searchSettings 中表的高亮字段只有 name、displayName、description（research R8）。
- 按「负责人」筛选时不包含列：列的索引文档没有 `ownerDisplayName`（research R4）。
- 结果窗口最多 10000 条：总数超过时只能翻到前 10000 条，界面会提示（research R6）。
- 无关键词浏览全部资产时，列表中包含列文档，与 OM Explore 一致；按「数据表」类型查看时不包含列（research R2）。
- 权限范围：OM `enableAccessControl=false`，`/aggregate` 和 `/entityTypeCounts` 也不按权限过滤，所有登录用户（admin、ai-engineer）看到相同的资产范围。这符合宪法 IV 的 Phase 1 例外（只做到角色一级）。

**开发态测试数据的影响**：
- 开发态标识标签「开发态测试元数据」（`ContextureDevTest.DevTestMetadata`）会出现在「分类标签」筛选中。这是 OM 中的真实数据，也可以用它排除测试数据。
- 导入的 3 个服务 `devtest-mes`、`devtest-qms`、`devtest-dw` 不带连接，在数据源管理中显示为「待配置」，不会表现为已连通的源库。

**验证范围的限制**：
- SC-006 中「索引缺失」与「零资产」两种情况只在契约测试和组件测试中验证，没有在真实环境中模拟，以免删除共享索引或清空资产。
- OpenSearch 搜索超时（30 秒）在本地数据量下无法复现：`size=10000` 的查询约 140–190ms，`timed_out=false`。超时映射为 `504 search.timeout` 的逻辑由契约测试保证。
- 写入后短暂搜不到：撤除后重新导入，导入完成后第一次查询即可搜到全部 29 张表（0.0s），未观察到延迟。OM 写索引失败会进入重试队列，用户级搜索缓存也可能造成短暂不可见；这两种情况本地都未出现。

**research 中原 UNCONFIRMED 项的实测结论**（详见 research.md 各节与「实施中的修正」）：
- 结果窗口超限时，OM 返回 HTTP 500；BFF 先行返回 422。
- 无 displayName 的实体，索引中回退为 name。
- `database.displayName` 可以直接聚合；`/search/aggregate` 必须传 `value=.*`，否则返回空桶。
- 快速筛选每次取 10 个选项，与 OM 界面相同。
- 库与 Schema 接受 `fields=certification`。

**环境阻塞**（不属于 006 代码问题）：
- **Airflow 不稳定**：dag-processor CrashLoopBackOff、scheduler 反复 OOMKilled。005 的采集部署或触发因此偶发失败：最后一轮中，005 视图血缘集成测试与 005 e2e US3 各失败 1 次，而 005 e2e 的全部 20 个用例在上一轮通过。
- **001 追踪测试**：Langfuse 公共 API 返回 422，与 005 验收时的记录相同。
- **OpenSearch 内存**：见第 2 节，当前配置下完整验证期间未再重启。

**实施中对计划的调整**（详见 research.md「实施中的修正」）：
- Web 构建产物改放 `/static/`，因为原 `/assets/` 与数据资产页的地址冲突，部署后 `/assets/sources` 为 404；
- 005 的左侧目录树由数据资产浏览树取代：点击节点不再跳转详情页，节点显示服务的显示名称；005 中按目录树逐层进入库和 Schema 详情的 e2e 步骤，改为在浏览树中逐层展开并经新地址进入；
- `/assets/*` 的页头一级标题统一为「数据资产」，子视图由面包屑区分；
- 修正了 005 采集链路 e2e 中一处原有缺陷：OM `/tables` 不支持 `service` 过滤，原测试在环境中有其他表时计数错误。

---

## 8. 验收记录

发现问题时，请记录：所在页面、做了什么、实际出现什么、期望是什么。可以附截图。

| 日期 | 验收人 | 实际用时 | 步骤 | 结果 | 问题 |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |
