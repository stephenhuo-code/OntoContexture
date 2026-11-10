# Quickstart：验证资产搜索与摘要（006）

本指南用于开发自测，以及验收前的核对。正式的手动验收以实施收尾时交付的 `acceptance.md` 为准。

- 接口：[contracts/openapi.yaml](contracts/openapi.yaml)
- 投影与校验规则：[data-model.md](data-model.md)
- 技术决策：[research.md](research.md)

断言一律依据导入工具的 fixture（`testdata/mockfactory`）和 OM 的实际数据。原型中的数字和名称不作为预期结果。

## 0. 环境前置（D11，先于一切搜索验证）

```bash
make up                                   # 平台组件（OM 2.0.3、OpenSearch 3.4.0、Keycloak、BFF、Web）
make seed                                 # OM 团队 / 角色（admin、ai-engineer）、示例本体
kubectl -n contexture get pod opensearch-cluster-master-0 \
  -o jsonpath='{.status.containerStatuses[0].restartCount}{"\n"}'
```

- 记录重启次数。等 10 分钟后再查一次：数字不增长，才进入后续步骤。
- 如果数字增长，按 research R15 排查：`kubectl -n contexture describe pod opensearch-cluster-master-0`、`kubectl -n contexture logs opensearch-cluster-master-0 --previous`，重点看 OOMKilled、探针失败、磁盘。排查结论写入 `acceptance.md` 的环境前置项。
- 问题未解决时，依赖搜索的集成测试和 e2e 一律按「环境阻塞」如实记录，不用假实现代替。

## 1. 开发态元数据导入（FR-016、FR-017、SC-008）

```bash
make dev-metadata                         # = 读取 .env.local 中的 provisioner 凭证 → python -m mockfactory om-import --target local
make dev-metadata                         # 再运行一次，检查幂等
python -m mockfactory om-import           # 不带 --target：预期拒绝写入，并提示原因
```

预期结果：

- 第一次运行输出新建、更新、未变化三项数量，新建数大于 0。
- 第二次运行新建数为 0，OM 中测试资产的数量不变。
- 不带 `--target` 时退出码非 0，OM 中没有任何写入。
- 005 采集的服务（如 `mock-mes`）的 `updatedAt` 和版本号都没有变化。用 OM 的 `GET /v1/services/databaseServices/name/mock-mes` 对比导入前后。
- 在织境「数据源管理」中，导入的服务显示为「待配置」，不显示为已连通（research R12）。

撤除：

```bash
make dev-metadata-remove                  # 只删除带开发态标识的服务、术语表、分类、业务域
```

撤除后，导入的资产在搜索中消失，005 采集的资产仍然存在。

## 2. 场景 US1：关键词搜索与摘要

登录织境 Web（`engineer1`），进入一级导航「资产」，地址应为 `/assets`，不再是占位页。

1. 在顶栏搜索框输入 fixture 中某张表的英文名，停顿约 0.4 秒。
   - 预期：出现按类型分组的建议，每组最多 5 条。
2. 回车。
   - 预期：排序变为「相关性」；页头显示总数；左栏变成类型列表，只列计数大于 0 的类型，并选中默认类型（FR-007）；卡片中命中的词高亮。
3. 检查第一条结果。
   - 预期：自动选中，右侧显示摘要；切到「Schema」页签，字段清单与 OM 的表实体一致。
4. 检查导入的资产。
   - 预期：卡片显示「开发态测试元数据」；005 采集的资产显示「真实采集来源」。
5. 输入一个不存在的词。
   - 预期：显示「无匹配结果」，摘要关闭。
6. 搜索范围选择「表」再搜索。
   - 预期：结果中只有表。
7. 按 SC-009 的固定中文关键词清单（取自 003 表定义的中文注释）逐个搜索，记录命中数和前 3 条结果。这一步只作观察记录，不判定通过或失败。

## 3. 场景 US2：浏览树、快速筛选、条件条、排序分页

1. 清空关键词。
   - 预期：左栏是浏览树，根节点只有有数据的大类；条件条显示操作提示。
2. 逐层展开「数据库 → 服务类型 → 导入的服务 → 库 → Schema」，点击 Schema。
   - 预期：页面不跳转；列表只剩该 Schema 下的资产；条件条逐层列出位置。
   - 删除「服务」这一层：服务和其下的库、Schema 条件一起消失。
3. 分级（Tier）选择 fixture 中的两个值，业务域选择一个值。
   - 预期：结果满足「(值1 或 值2) 且 值3」；选项计数不受本维度自身选择的影响。
   - 与直接调用 OM `/v1/search/query` 时同条件的总数一致（SC-004）。
4. 负责人选择「无」。
   - 预期：只剩没有负责人的资产，与 fixture 中声明的缺失样例一致。
5. 切换排序和升降序。
   - 预期：回到第 1 页。
   - 切换每页 15 / 25 / 50 条并翻页，结果总数不变。
6. 搜索 fixture 中的同名表。
   - 预期：每张卡片的面包屑都能区分服务和 Schema（SC-005）。
7. 点「清除全部」。
   - 预期：回到无关键词的浏览状态。

## 4. 场景 US3：子视图与 005 不退化

1. 点页头的「数据源管理」和「添加数据源」。
   - 预期：分别进入 `/assets/sources` 的列表和接入向导，按 005 `acceptance.md` 的主要步骤重走（SC-007）。
2. 点一张表卡片的名称。
   - 预期：进入 `/assets/table/<FQN>`，即 005 的表详情；属性卡片和编辑弹窗中的文案为「分级（Tier）」（Q4）。
   - 返回后，关键词、位置、筛选、排序、页码都保持不变。
3. 搜索字段名，在「列」类型下点一条结果。
   - 预期：进入所属表的详情，并定位、高亮该列（Q3）。
4. 点一个业务术语和一个分类标签结果。
   - 预期：进入只读详情页，没有编辑入口；内容与 OM 实体一致；可以返回探索视图。
5. 在详情页点浏览树中的节点。
   - 预期：回到 `/assets`，并以该节点作为位置条件。
6. 直接打开下列旧地址，确认都转到新地址：
   - `/sources`
   - `/sources/mock-mes`
   - `/sources/mock-mes/assets/table/<FQN>`
7. 刷新 `/assets`。
   - 预期：回到初始的浏览状态。这是预期行为（D9）。

## 5. 状态与错误（FR-015、SC-006）

| 场景 | 操作 | 预期 |
| --- | --- | --- |
| OM 不可用 | `kubectl -n contexture scale deploy/openmetadata --replicas=0` 后搜索；结束后恢复为 1 | 显示 `upstream.unavailable` 和重试入口，不出现任何示例数据 |
| 索引缺失 | 由契约测试（模拟 OM 返回 500 `Failed to find index`）与组件测试覆盖。真实环境不模拟，避免破坏共享索引；acceptance 中写明「真实环境未验证」 | `search.index_missing` 与重试入口 |
| 零资产 | 由组件测试覆盖；如果有一套空环境，可以手动验证，否则 acceptance 中写明「真实环境未验证」 | 显示零资产空状态和「添加数据源」入口 |
| 窄屏 | 视口 390 / 768 / 1280 | ≤850px 时浏览树收进「目录」抽屉，摘要以覆盖层显示；整页没有横向溢出 |

## 6. 自动化验证

```bash
uv sync --all-packages && pnpm install
pnpm --filter @contexture/ts-api check    # 契约与生成类型一致
make lint
make test                                 # 单元、契约测试；覆盖率 ≥ 80%（含 make coverage-check 的变更行覆盖率）
uv run pytest -m cluster services/bff/tests/integration testdata/tests   # 真实 OM / OpenSearch（需完成第 0、1 节）
pnpm --filter @contexture/web test
make e2e                                  # 需要已部署的本地集群，并已执行 make dev-metadata
```

SC-003 的性能观察：e2e 中统计搜索、筛选、翻页从操作到结果出现的耗时，取 p95 写入 `acceptance.md`。因环境故障导致的失败单独记录。
