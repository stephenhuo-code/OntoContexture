# T006：兼容性检查与已确认方案

2026-11-02。T001–T005 完成；T006 尚未完成，未进入 T007，不调整产品运行依赖。

## 实际检查

使用项目 CI 锁定的 `tufin/oasdiff:v1.33.0`，基线为当前 HEAD 的 contracts，候选为工作区根 contracts；只读挂载。

```bash
docker run --rm -v /Users/yanwen/github/OntoContexture:/head:ro -v /private/tmp/contexture-004-o3l0thdk/base:/base:ro tufin/oasdiff:v1.33.0 breaking /base/contracts/openapi/bff.yaml /head/contracts/openapi/bff.yaml --fail-on ERR
```

第一轮退出码 1，3 个 error：code / state 的新增 minLength，以及 Me.display_name 响应从 string 变为可空。
取消无必要的 Schema 长度限制（处理器仍须对空值返回受控 303）后，第二轮退出码 1，只剩：

```text
response-property-became-nullable
GET /bff/v1/me, 200, display_name
```

此前 nullable 校正对齐了旧后端在姓名 / 用户名均缺失时返回 null 的事实，却仍改变已声明的 v1 响应保证。
不能把“旧实现已如此”当作兼容检查通过，不能关闭 oasdiff、降低严重性或填例外忽略该项。

## 推荐方案：修正 v1 后端响应，保留字符串保证

以下是可评审的拟实施变更，当前没有据此修改运行代码：

1. 根 Me Schema 恢复 `display_name: string`，仍为可选字段，字段集合与 v1 路径保持。重新生成 TS 类型，避免手改生成声明。
2. BFF `/me` 使用受信显示名 → 用户名 → user_id 的顺序，最终始终返回字符串；先补姓名 / 用户名都缺失的失败测试，再修复响应。
3. UI CurrentUser 仍可把线上缺省归一为 null 并回退 user_id；对历史 null 响应可保留防御处理，但不把 null 定义成 v1 的新响应承诺。
4. 同步 data-model、plan、BFF 契约及 T014 / T026 的 wire model 文字和测试矩阵：v1 Schema 的 null 应拒绝，缺省 / 字符串应通过；UI 防御性归一另测。
5. 重新生成类型并运行 oasdiff，确认绿色后再勾选 T006、进入 T007。

这个方案修复原来违反字符串契约的后端边界，保持界面所需的身份回退体验，不新增接口版本。

## 备选：坚持线上 nullable，发布版本化迁移

若必须将 null 作为正式线上类型，需提供新的版本化 Me 接口，并保留旧 v1 的字符串响应适配及迁移期；
Web / 生成客户端 / 测试迁移后再考虑废弃旧版本。应先修订 spec / plan / tasks，不能直接覆盖 v1 的保证。

## 当前状态

- 两轮 oasdiff 都真实执行，失败记录未删除或降级。
- 根契约和生成类型目前保留待决的 nullable；未擅自替负责人决定上述响应语义变更。
- T006 未勾选；根据 implement 的非并行失败规则和计划的兼容迁移门禁，后续依赖 / UI 产品实现等待决定。
- 本次未自动提交、合并、部署或修改上游；无 `.specify/extensions.yml`，没有待分派的实现后 hook。

## 负责人决定与测试先行修复

2026-11-02 负责人回复“可以”，确认姓名 → 用户名 → 用户 ID 兜底，保留 v1 字符串保证。先新增四组账号响应测试并运行：无姓名 / 无用户名、两者空字符串的两个用例按预期失败（实际返回 null / 空文本）；已有姓名 / 用户名两组通过。随后修复 get_me 回退并将 Pydantic display_name 约束为 string。根契约先恢复 string，再重新生成 TS；后续检查结果追加于下。此决定取代前文“等待确认”的状态，历史失败记录保留。

修复后：四组显示名用例全部通过；oasdiff 退出码 0（No breaking changes）。BFF 单元 / 契约批次 39 通过、1 失败；失败是新 callback 契约下旧实现对缺参仍返回 422 的预期红测，归 T014 / T023 修复，不豁免或关闭生成式检查。
