# Security & License Checklist: 004 织境 Web 外壳与设计系统

**Purpose**: 评审身份、会话、契约迁移、第三方集成与许可要求是否完整、明确且可验证；不评判实现是否通过。
**Created**: 2026-11-02
**Feature**: [spec.md](../spec.md)
**Depth / Audience**: 标准深度；实施前及 PR 评审者使用，范围为 004，007 / 012 仅检查交接边界。

**Note**: 本清单按 speckit-checklist 生成。
**Review Ownership**: 清单属于评审者；只有评审者认定需求质量满足时才可标记 `[x]`。
**Marker Semantics**: `[x]` 表示需求写清楚并通过评审，不表示代码、试验或产品验收通过；本次生成项全部未勾选。

## Requirement Completeness

- [ ] CHK001 Web 准入要求是否完整列出管理员、AI 工程师、仅业务用户、无准入角色和混合角色的规则？[Completeness, Spec §FR-001 / SC-001]
- [ ] CHK002 受保护 Web 接口、直接请求与登录 / 回调 / 退出的例外边界是否明确，且没有将 Web 角色限制扩散到其他客户端？[Coverage, Spec §FR-017, Plan §Design Decisions 2]
- [ ] CHK003 浏览器凭证、服务端会话、受信身份与未签名用户头的信任边界是否明确？[Completeness, Spec §FR-017, Data Model §CurrentUser / Existing SessionRecord]
- [ ] CHK004 登录返回目标的允许范围、不安全目标的回退与回调重放处理是否有完整要求？[Coverage, Spec §FR-002 / Edge Cases, Contract bff-session §登录导航失败与恢复]

## Requirement Clarity & Consistency

- [ ] CHK005 会话失效、无权限、身份依赖故障和内部故障的分类及恢复动作是否分别定义？[Clarity, Spec §FR-003, Contract bff-session §错误分类]
- [ ] CHK006 不调用 IdP logout、只结束当前织境会话的要求是否在澄清、边界情况、计划与契约之间一致，且明确了成功后的匿名入口与主动重新登录语义？[Consistency, Spec §FR-004 / Clarifications 2026-11-02 / Edge Cases, Plan §Design Decisions 3]
- [ ] CHK007 退出请求失败、响应丢失、再次尝试与成功后的重新登录语义是否有明确的需求边界？[Coverage, Spec §FR-004, Data Model §SessionView]
- [ ] CHK008 当前用户模型、线上响应与生成类型对缺省、null、空文本和角色缺省的约定是否一致？[Consistency, Spec §FR-002, Data Model §CurrentUser, Contract bff-session §Me 字段与缺省值]
- [ ] CHK009 角色收紧、退出策略和登录失败响应迁移是否明确要求消费者核对、兼容性判定及必要的版本 / 迁移期？[Consistency, Constitution §II, Plan §Validation & Migration]

## Exception & Recovery Coverage

- [ ] CHK010 登录取消、无效 / 过期 / 重放回调与依赖故障是否均定义了用户可理解的说明和重新进入路径？[Coverage, Spec §Edge Cases, Contract bff-session §登录导航失败与恢复]
- [ ] CHK011 登录失败页的参数是否明确只影响展示，且可接受的信息、禁止透传的信息和未认证可见内容均有边界？[Clarity, Spec §FR-003 / FR-017, Data Model §LoginFailurePresentation]
- [ ] CHK012 临时故障保留会话与明确无效身份终止会话的要求是否相容，且没有允许过期令牌继续提供业务内容？[Consistency, Spec §FR-003 / FR-017, Data Model §Existing SessionRecord]
- [ ] CHK013 刷新、后退、身份重新核验和迟到响应是否定义了前用户内容的清理边界？[Coverage, Spec §FR-004 / Edge Cases, Tasks T019 / T026]

## Dependencies & License Requirements

- [ ] CHK014 开源组件清单是否写明版本、许可、用途、所属服务与替代方案，并要求实施后核对传递依赖？[Completeness, Constitution §III, Plan §开源服务与主要库清单]
- [ ] CHK015 依赖冻结、前端实际打包依赖的 SBOM、许可和漏洞检查是否有明确交付与失败处理要求？[Measurability, Constitution §III, Tasks T007 / T041–T043]
- [ ] CHK016 配置、官方扩展、最小补丁的选择顺序，以及上游优先、源码隔离与补丁登记要求是否明确？[Consistency, Constitution §VI, Plan §Design Decisions 9]
- [ ] CHK017 原型和上游 UI 的复用禁区是否明确，是否避免把受限许可组件默认为可复制的前端依赖？[Coverage, Constitution §III / VI, Spec §FR-019 / D2]
- [ ] CHK018 004 宿主实测、自身身份验证、007 Omnigent 身份桥接与 012 安全执行的责任界线是否一致？[Consistency, Spec §Assumptions, Contract embed-readiness §004 四主题矩阵 / 007 交接矩阵]

## Acceptance Criteria Quality

- [ ] CHK019 五组角色和直接接口拒绝的成功标准是否可客观判定，且明确使用真实依赖集成而非模拟身份替代？[Measurability, Spec §SC-001, Constitution §I, Tasks T015 / T018 / T020]
- [ ] CHK020 开发示例与生产隔离的要求是否定义不同验证入口、真实认证准备及各自应验证的范围？[Measurability, Spec §FR-018 / SC-006, Contract browser-validation]
- [ ] CHK021 兼容性证据是否明确区分静态确认、运行通过、运行失败和未执行，并规定未完成项不能算通过？[Measurability, Spec §SC-007, Data Model §CompatibilityEvidence]
- [ ] CHK022 自动化、覆盖率、人工验收与最终完成的先后条件是否明确，环境限制和未完成评审是否要求如实记录？[Consistency, Spec §FR-021 / SC-008, Constitution §开发流程与质量门禁]

## Notes

- 来源：[plan.md](../plan.md)、[data-model.md](../data-model.md)、[tasks.md](../tasks.md)、[BFF 契约](../contracts/bff-session.md)、[浏览器验证约定](../contracts/browser-validation.md)。
- I1 已依据 2026-11-02 的明确决定完成文档修订；清单仍保持评审者所有，未勾选不表示已发现不满足，也不表示运行实现已通过。
- speckit-implement 读取本清单状态，不替评审者修改标记；不把生成清单当作许可、安全或产品实现验收通过。
