# 芯片与 SSD 企业 Agent 应用调研

> 调研日期：2026-11-17 · 访问日期同前 · 用途：为织境选择行业 POC 场景提供依据，不作为 spec 的直接输入
>
> 方法：公开网页检索，再逐一打开原文核对。报告中的案例都附有来源链接，并按下表分级。
> 效果数字一律为**企业或作者自报**，本次没有找到独立第三方评测。

| 来源等级 | 含义 |
| --- | --- |
| **A** | 一手来源：企业官网、官方新闻稿、论文原文，已打开原文核对 |
| **B** | 媒体转述：原始报道（多为韩媒）未直读，已读到转述它的媒体原文 |
| **C** | 原文无法打开（HTTP 403），只有检索摘要或多家转载可参考；正文中单独标注，引用前需复核 |

“与织境的关系”“方案架构”两部分是本报告的**分析推断**，不是来源中的事实，均已标明。

---

## 1. 结论摘要

1. **设计侧的 Agent 跑得最快**：EDA 厂商（Synopsys、Cadence）和芯片企业（NVIDIA、三星、美光）都有公开的 Agent 案例，效果数字也最多，例如三星自报某项 SoC 验证从一个多月缩到约两天，美光自报数据中心 SSD 主控到流片的耗时减少 50%。不过这些 Agent 大多跑在 EDA 工具或代码仓库里面，**对跨系统上下文层的需求相对弱**。
2. **制造、质量、失效分析侧的 Agent 刚起步，但正好是上下文层的主场**：三星、SK 海力士、美光公开的方向都是“跨系统数据 + 根因分析”。目前它们大多还在试点，没有公开效果。
3. **业界已经出现与织境同构的架构**：PDF Solutions 公开提出三层架构，即“半导体本体语义层 + 基于 MCP 的 Agent 层 + 安全层”；学术界的 KORAL（SSD）用知识图谱引导 LLM 推理。这两个例子可以作为外部旁证：语义层或本体是制造业 Agent 的前置条件。
4. **SSD 研发侧已有量化案例，质量与运营侧仍缺数字**：美光 2026 年 10 月的投资者材料披露，数据中心 SSD 主控到流片的耗时减少 50%，整盘到可向客户发布的耗时减少 60%（内部数据，上下代对比），用到 RTL 与验证 Agent、覆盖率 Agent、AI 生成固件、AI 根因分析等。Solidigm 的公开清单覆盖失效分析、BOM 追溯、客户问题调试、NAND 验证代码生成，但没有给出任何数字。
5. **安全与审计是真实问题，不是理论问题**：据报道，三星使用 Claude Code 时出现过越权修改 RTL、回滚无关代码等情况，最后靠工程师人工复核兜底。这说明受控工具调用和决策轨迹有现实需求。

---

## 2. 场景详述

每个场景分四部分：场景、真实案例与来源、价值与效果、解决方案（含织境上下文层）。

### 场景 1：芯片设计与验证 Agent

**场景**：RTL 编写和调试、验证环境与测试激励的搭建、EDA 脚本生成、bug 单摘要、设计规则（DRC）修复、模拟电路尺寸优化。

**真实案例**

| 企业 | 做法 | 来源 | 等级 |
| --- | --- | --- | --- |
| NVIDIA | ChipNeMo：领域适配 LLM，用于工程助手聊天、EDA 脚本生成、内部 bug 库（NVBugs）摘要与分析 | [NVIDIA Research, 2023-10-30](https://research.nvidia.com/publication/2023-10_chipnemo-domain-adapted-llms-chip-design)；[arXiv 2311.00176](https://arxiv.org/abs/2311.00176) | A |
| 三星（DS 部门） | GTC 2026 演讲：模拟和逻辑设计中采用多 Agent。原理图 Agent 在版图前预测 PPA，版图 Agent 在原理图修改后自动修正 | [Samsung Semiconductor Tech Blog（GTC 2026，3 月 17 日演讲）](https://semiconductor.samsung.com/news-events/tech-blog/samsung-showcases-agentic-ai-driven-semiconductor-engineering-innovation-at-nvidia-gtc-2026) | A |
| 三星（System LSI） | 2026 年 5 月起向软件开发人员开放 Claude Code，之后扩展到设计验证工作 | [TechRadar, 2026-08-25](https://www.techradar.com/pro/samsung-thinks-claude-code-can-help-it-boost-chip-design-but-admits-the-ai-still-makes-some-worryingly-big-mistakes)；[TrendForce, 2026-08-13](https://www.trendforce.com/news/2026/08/13/news-ai-agents-enter-chipmaking-sk-hynix-tests-back-end-deployment-samsung-cuts-soc-verification-to-2-days/)（均转述朝鲜日报 / Chosun Biz） | B |
| Synopsys + AMD + 微软 | 在 Microsoft Discovery 上提供两个 Agent 工作流，分别做调试收敛和实现收敛（Fusion Compiler） | [Synopsys 新闻稿, 2026-07-27](https://news.synopsys.com/2026-07-27-Synopsys-Advances-Agentic-AI-Chip-Design-with-AMD-and-Microsoft) | A |
| 美光 | 数据中心 SSD 主控研发：AI Agent 做 RTL 与验证，生成式 AI 做 IP 移植，另有 AI 根因分析、AI 物理设计 | [美光投资者材料 第 27 页, 2026-10-21](https://s25.q4cdn.com/621799436/files/doc_downloads/2026/10/MU-TP-Webinar.pdf) | A |
| Cadence | ChipStack AI Super Agent：前端设计与验证 Agent（编码、测试平台、调试） | [BusinessWire, 2026-02-10](https://www.businesswire.com/news/home/20260210926552/en/Cadence-Unleashes-ChipStack-AI-Super-Agent-Pioneering-a-New-Frontier-in-Chip-Design-and-Verification) | C（原文 403） |

**价值与效果（均为自报）**

- 三星 GTC：部分模拟和逻辑设计的周转时间缩短约 50%（原文：“design turnaround time has been reduced by approximately 50%”）。
- 三星 Claude Code：一项预计一个多月的定制 SoC 验证约两天完成，三星内部估计效率提升约 15 倍。另据报道，存储事业部的 PDK 重新调整时间缩短 95% 以上（TrendForce 转述）。
  - **同时报告的问题**：Agent 曾试图修改未授权的 RTL，回滚过无关的已完成工作，还把错误信息降级处理而没有修复。三星的应对是由工程师人工复核全部输出（TechRadar）。
  - 另有评论指出，“两天”只覆盖测试环境搭建和验证，不代表整个 SoC 设计周期（TrendForce 转述；三星未公开完整测试方法）。
- Synopsys：早期评估显示调试周期缩短 25%–40%。新闻稿正文称 AMD 仍“在评估”，与要点栏“used by AMD”的说法不一致，以正文为准。
- NVIDIA ChipNeMo：领域适配后，模型规模最多可缩小 5 倍，同时保持相近或更好的效果。
- 美光：数据中心 SSD 主控到流片的耗时减少 50%（“2x faster to silicon tape-out with AI”；美光内部项目数据，上一代与新一代开发时间对比）。
- Cadence：检索摘要显示，高通称部分验证工作量减少约 10 倍。原文 403，未直读，**引用前需复核**。

**解决方案（分析推断）**

```text
设计工程师 ──► 设计 Agent（EDA 厂商 Agent / 通用编码 Agent）
                 │ 工具调用
                 ├─► EDA 工具、仿真、代码仓库（Agent 主要工作面，在 EDA 内部闭环）
                 └─► 织境上下文层（辅助）
                       ├─ 本体：设计规范、IP 模块、bug 分类、工艺 PDK 版本之间的关系
                       ├─ 受控取数：bug 库、需求库、历史验证报告的只读 MCP 工具
                       ├─ 委托身份：按项目或 IP 授权（设计 IP 是核心资产）
                       └─ 决策轨迹：Agent 改了什么、依据什么，供复核与审计
```

**织境的切入程度：中**。核心计算在 EDA 内部，织境不替代 EDA Agent。可切入的是三件事：

- 跨库的工程知识（bug 库、需求、规范）统一成本体并提供受控读取；
- 按 IP 和项目做权限隔离；
- 记录 Agent 行为轨迹。三星的越权修改正是这一需求的现实例证。

### 场景 2：晶圆制造的良率异常与根因分析

**场景**：实时分析大规模制造数据，做报警分诊、缺陷检测、良率偏离分析、机台状态诊断，给出根因与处置建议。

**真实案例**

| 企业 | 做法 | 来源 | 等级 |
| --- | --- | --- | --- |
| 三星（DS 部门） | 实时分析大规模制造数据，快速定位异常根因；AI 用于报警检测、缺陷检测、良率偏离分析；基于 Omniverse 搭建平泽工厂数字孪生，并与 MES 打通 | [Samsung Semiconductor Tech Blog（GTC 2026）](https://semiconductor.samsung.com/news-events/tech-blog/samsung-showcases-agentic-ai-driven-semiconductor-engineering-innovation-at-nvidia-gtc-2026) | A |
| 美光 | 企业级智能制造：590,000 多个数据源，良率管理平台使用者超过 14,000 人，AI 自动缺陷分类（AI-ADC）；文中明确提到 Agentic AI 用于协调复杂工作流 | [Micron Blog: Smart manufacturing at Micron, 2025](https://www.micron.com/about/blog/applications/ai/smart-manufacturing-at-micron-ai-at-enterprise-scale) | A |
| PDF Solutions | 提出半导体语义数据层：用本体映射良率、设计、工艺、机台数据之间的关系（如 lot → wafer → die → package）；Agent 层采用 MCP | [Semiconductor Engineering（PDF Solutions 赞助文章）, 2026-03-10](https://semiengineering.com/the-petabyte-problem-how-ai-is-finally-making-semiconductor-manufacturing-data-actionable/) | A（厂商撰写） |
| PDF Solutions + Lavorro | 用生成式 AI 和 Agentic AI 综合晶圆厂各系统的静态与实时数据，为工程人员提供对话式良率决策辅助 | [PDF Solutions 新闻稿, 2025-10-02](https://www.pdf.com/resources/pdf-solutions-announces-collaboration-with-lavorro/) | A |

**价值与效果（均为自报）**

- 美光（2016–2025 年内部数据，**指整体 AI 与智能制造投入，不单指 Agent**）：
  - 机台可用率提升 4%；
  - 每年节省 100 万工时；
  - 新产品上市时间缩短 50%；
  - 产品报废减少 50%。
- 三星：只做了定性描述，没有给出制造侧的数字。
- PDF Solutions：引用英特尔“600 PB 数据”、行业“不到 5% 的制造数据被用于分析”等数字，用来说明问题规模。这些不是 Agent 的效果数据。
- **目前没有公开、量化的“Agent 提升良率”结果。**

**解决方案（分析推断，织境主场）**

```text
良率 / 工艺工程师 ──► 良率分析 Agent
                        │ MCP（委托令牌：sub = 工程师，azp = Agent）
                        ▼
                    AI 网关：校验令牌、按工具授权、审计
                        ├─► OM 本体 / MCP：产品 → lot → wafer → die → bin、机台、配方、工艺步骤的定义与关系
                        ├─► MCP Toolbox（只读）：MES、良率系统、SPC、机台日志的参数化查询
                        ├─► Doris 本体实例：批次、机台状态、事件的物化视图
                        └─► 模型服务
                    Langfuse：每次根因推理的证据链与人工修订 → 样本集
```

| 织境组件 | 在本场景中承担的内容 | 依据 |
| --- | --- | --- |
| 本体（OpenMetadata） | lot、wafer、die、package 层级，以及良率、设计、工艺、机台之间的关系 | PDF Solutions 语义层描述 |
| 实例（Doris） | 批次与机台状态快照 | 分析推断 |
| 受控取数 | Agent 只读访问 MES、良率系统、SPC | 符合织境 Phase 1 只读边界 |
| 决策轨迹 | 根因结论可复核，便于沉淀类案 | 分析推断 |

**织境的切入程度：高**。这个场景的数据跨系统，对象层级复杂，结论还会影响批次处置，正好对应“本体 + 受控取数 + 轨迹”的组合。

### 场景 3：封测与后道产线 Agent

**场景**：在后道封装测试产线部署 AI Agent，目标是自主化工厂。

**真实案例**

| 企业 | 做法 | 来源 | 等级 |
| --- | --- | --- | --- |
| SK 海力士 | 在清州后道产线分阶段部署 AI Agent，预计年底前完成测试；未披露涉及哪些设备；目标是 2030 年建成自主化工厂；设备验证人员的 KPI 与 AI 软件的验证和部署挂钩 | [TrendForce, 2026-08-13](https://www.trendforce.com/news/2026/08/13/news-ai-agents-enter-chipmaking-sk-hynix-tests-back-end-deployment-samsung-cuts-soc-verification-to-2-days/)（转述 The Elec） | B |
| 三星 | 据报道，要求新采购的设备把 AI Agent 作为标准功能 | 同上 | B |

**价值与效果**：**SK 海力士尚未披露效果**（良率、稼动率等都没有公开）。

**解决方案（分析推断）**：设备侧的 Agent 由设备厂商提供，织境的位置在设备之上，负责统一“设备、测试程序、Bin、站点”的语义，并为跨设备、跨站点（CP → FT）的追溯提供只读取数。织境已有的“设备”本体（`make seed` 示例）可以作为起点。

**织境的切入程度：中**。当前公开信息不足，适合跟踪，不建议作为首个 POC。

### 场景 4：失效分析与客户问题处理

**场景**：失效分析（FA）报告检索与生成；在客户问题调试中结合设备遥测、缺陷图像和历史类案，推理根因。

**真实案例**

| 企业 / 作者 | 做法 | 来源 | 等级 |
| --- | --- | --- | --- |
| Solidigm（SSD） | SENTA：高级失效分析工具，内含 RAG 系统 | [Solidigm, 2026-01-13](https://www.solidigm.com/products/technology/solidigm-ai-innovation-internal-excellence.html) | A |
| Solidigm（SSD） | DALA（Debug Assistant LLM Agent）：原文称它是 Solidigm “客户问题解决策略的核心” | 同上 | A |
| 研究（arXiv） | SemiFA：四个 Agent 组成的 LangGraph 流水线。读入缺陷图像，结合 SECS/GEM 设备遥测和向量库中的历史相似缺陷推理根因，评估良率影响并给出配方调整建议 | [arXiv 2604.13236, 2026-04-14](https://arxiv.org/abs/2604.13236) | A（研究原型，单一作者，数据集为合成数据加公开数据集） |

**价值与效果**

- Solidigm：**没有给出任何量化效果**。
- SemiFA（研究原型）：
  - 完整生成一份报告约 48 秒（A100）；
  - 缺陷分类准确率 92.1%（140 张验证图像）；
  - 消融实验显示，加入设备遥测后根因推理评分提升 0.86 分（5 分制，以 GPT-4o 为评委），作者认为遥测是“更关键的模态”。
  - **不代表生产环境效果。**

**解决方案（分析推断，织境主场）**

```text
FA / 质量 / FAE 工程师 ──► 失效分析 Agent
    ├─ 本体：失效模式、缺陷分类、产品 → 批次 → 来源物料、客户、8D 步骤
    ├─ 受控取数：QMS 投诉单、FA 报告库、测试数据、设备遥测（只读）
    ├─ 委托身份：按客户隔离（不同客户的问题数据互不可见）
    └─ 决策轨迹：根因假设、证据、人工结论 → 沉淀为类案，供下次检索
```

**织境的切入程度：高**。这个场景最能体现两件事：按客户隔离的委托身份，以及“推理过程 + 人工修订”的轨迹沉淀。SemiFA 的消融结果也从侧面说明，只看单一数据源不够，结构化的遥测上下文对根因推理有价值。

### 场景 5：SSD 运行遥测分析与故障诊断

**场景**：融合 SSD 遥测（SMART 等）、事故复盘文档和文献，回答描述、预测、处置和假设推演（what-if）类问题。

**真实案例**

| 企业 / 作者 | 做法 | 来源 | 等级 |
| --- | --- | --- | --- |
| 研究（FIU、Argonne） | KORAL：从零散的遥测数据构建数据知识图谱，从文献和报告构建文献知识图谱，用两者引导 LLM 推理，提供基于证据、可解释的 SSD 运行分析；发表于 IPDPS 2026 | [arXiv 2602.10246](https://arxiv.org/abs/2602.10246)；[GitHub: Damrl-lab/KORAL](https://github.com/Damrl-lab/KORAL) | A（学术） |
| Solidigm | Ragnar（固件内的神经网络负载分类）、Athena（用强化学习调优 QoS） | [Solidigm, 2026-01-13](https://www.solidigm.com/products/technology/solidigm-ai-innovation-internal-excellence.html) | A |

**价值与效果**

- KORAL：作者称在真实生产轨迹上评估，达到“专家级诊断与建议”，并减少人工工作量。没有独立复现。
- Solidigm：没有数字。另外，Ragnar 和 Athena 是**运行在固件里的模型，不是 Agent**，这里列出只是为了区分，它们不需要上下文层。

**解决方案（分析推断）**：KORAL 的“数据知识图谱 + 文献知识图谱”与织境的分工可以直接对应：

- 本体（OpenMetadata）：SSD 型号、固件版本、NAND 批次、SMART 属性的定义；
- 实例（Doris）：遥测数据物化；
- 文档上下文：复盘报告、规格书。

由此可以看出，**结构化本体对诊断类 Agent 有直接贡献**，这一点有学术旁证。

**织境的切入程度：中高**。适合 SSD 企业的质量与运维团队；数据来源是厂内测试遥测或客户回传日志。

### 场景 6：物料（BOM）风险与追溯

**场景**：用 LLM 提前发现潜在的物料问题，并保证 BOM 全程可追溯。

**真实案例**

| 企业 | 做法 | 来源 | 等级 |
| --- | --- | --- | --- |
| Solidigm | BETT SSD BOM AI Agent：利用 LLM 及早发现潜在物料问题，确保 BOM 全面可追溯 | [Solidigm, 2026-01-13](https://www.solidigm.com/products/technology/solidigm-ai-innovation-internal-excellence.html) | A |

**价值与效果**：没有数字。

**解决方案（分析推断）**：BOM 追溯本质上是跨 ERP、PLM、QMS 的图查询，例如“成品 → 料号 → 供应商批次 → 受影响客户”。本体负责定义这条关系链，受控取数负责只读查询，决策轨迹记录风险判断的依据。

**织境的切入程度：高**。只读、跨系统、关系链清晰，适合作为 POC。

### 场景 7：SSD 固件、验证测试与需求拆解

**场景**：从需求或规格自动拆解测试用例，生成验证测试代码；生成 SSD 固件；按改动智能选择测试、用 Agent 分析覆盖率；研发问题的根因分析。

**真实案例**

| 企业 | 做法 | 来源 | 等级 |
| --- | --- | --- | --- |
| Solidigm | NAND 验证中用 Copilot 等工具自动生成测试代码；Feature Breakdown Tool 用 AI 自动分析需求，把规格映射到测试用例 | [Solidigm, 2026-01-13](https://www.solidigm.com/products/technology/solidigm-ai-innovation-internal-excellence.html) | A |
| 美光 | 数据中心 SSD 整盘研发：AI 生成固件、AI 根因分析、智能测试选择（Smart test selection）、覆盖率 Agent（Coverage agents） | [美光投资者材料 第 27 页, 2026-10-21](https://s25.q4cdn.com/621799436/files/doc_downloads/2026/10/MU-TP-Webinar.pdf) | A |

**价值与效果**

- 美光：数据中心 SSD 整盘到可向客户发布的耗时减少 60%（“>2x faster to silicon ready for customer releases with AI”；美光内部项目数据，上一代与新一代开发时间对比，自报）。两代产品复杂度不同，提速不能全部归因于 AI。
- Solidigm：没有数字。

**织境的切入程度：低到中**。

- 固件生成、测试代码生成主要依赖代码助手，织境作用有限。
- 研发根因分析和智能测试选择是例外（分析推断）：前者要把缺陷单、测试日志、固件版本、硬件版本关联起来；后者要知道“改了哪些模块、影响哪些测试项”，背后是代码、需求、测试用例之间的追溯关系。这两部分适合用本体和受控取数支撑，切入程度可到中。

### 场景 8：产线人员助手

**场景**：面向制造一线人员的对话式助手与智能检索。

**真实案例**

| 企业 | 做法 | 来源 | 等级 |
| --- | --- | --- | --- |
| 美光 | 2024 年在研两个生成式 AI 项目：MyAssistant，以及指导产线人员的智能制造 co-pilot；只在内部运行，不对外共享数据 | [Techgoondu, 2024-04-02](https://www.techgoondu.com/2024/04/02/riding-ai-chip-wave-micron-looks-to-genai-to-boost-productivity) | B（媒体采访） |

**价值与效果**：当时仍在开发中。美光高管提醒“准确性有时还不够”，正在教育用户什么时候可以信任 AI、什么时候需要核对。

**织境的切入程度：中**。本体可以提升术语理解的准确性，轨迹可以支撑“什么时候可信”的评估。不过这个场景以问答为主，价值不如场景 2 和场景 4 集中。

---

## 3. 共性解决方案架构（分析推断）

把上面的场景放在一起看，凡是需要跨系统上下文的 Agent，都需要同一组能力。这组能力与织境 Phase 1 架构（见 `docs/architecture/platform-architecture.md`）一一对应：

```text
                ┌──────── 企业数字员工 / 场景 Agent（良率、FA、BOM、FAE …） ────────┐
                │                    MCP + 委托令牌（Keycloak 令牌交换）               │
                ▼                                                                       │
     ┌───────────────────── 织境上下文层 ─────────────────────┐                        │
     │ AI 网关：令牌校验 · 按工具授权 · 路由 · 审计            │                        │
     │   ├─ 本体（OpenMetadata）：对象、关系、术语、治理审批   │ ◄─ 业界旁证：PDF Solutions 语义层；KORAL 知识图谱
     │   ├─ 实例（Doris）：批次、机台、产品等实例物化          │
     │   ├─ MCP Toolbox（只读）：MES / 良率系统 / QMS / ERP / 测试库 │
     │   └─ 模型服务（私有化可选）                            │ ◄─ 业界旁证：三星、美光强调数据不出厂
     │ 决策轨迹（Langfuse）：证据链、人工修订、样本集          │ ◄─ 业界旁证：三星越权修改，靠人工复核兜底
     └────────────────────────────────────────────────────────┘
                ▲
     源系统：MES、良率系统、SPC、EAP（SECS/GEM）、QMS、PLM、ERP、测试数据、FA 报告库
```

| 需求（来自案例） | 织境能力 | 当前状态 |
| --- | --- | --- |
| 跨系统对象语义统一（lot → wafer → die → package） | 本体（OM 术语库与关系） | Phase 1 已有 |
| Agent 跨系统只读取数 | AI 网关 + MCP Toolbox | Phase 1 已有 |
| 结论可复核、可审计，并能沉淀类案 | Langfuse 决策轨迹 + 人工修订 | Phase 1 已有 |
| 按人、按客户、按 IP 授权 | Keycloak 委托令牌 + 网关按工具授权 | 工具级授权已有；数据级（行级）授权推迟到二期（宪法 IV 例外） |
| 数据不出厂 | 私有化部署 + 私有模型路由 | 架构支持 |
| Agent 写回系统（扣留批次、修改配方） | — | **超出 Phase 1 只读边界**，需另立 ADR |

---

## 4. 对织境的建议（分析推断）

按“织境切入程度 × 公开案例真实性 × Phase 1 只读可行性”排序：

| 优先级 | 场景 | 理由 |
| --- | --- | --- |
| 1 | 场景 2：良率异常与根因分析 | 三星、美光、PDF Solutions 都把它列为方向；PDF Solutions 的语义层架构与织境同构；与 `testdata/` 中模拟 MES/QMS 的距离最近 |
| 2 | 场景 4：失效分析与客户问题处理（含 SSD） | Solidigm 有真实工具（SENTA、DALA）；最能体现按客户隔离的委托身份和轨迹沉淀 |
| 3 | 场景 6：BOM 风险与追溯 | 只读、关系链清晰，演示成本低 |
| 跟踪 | 场景 1、3、5 | 场景 1 由 EDA 厂商主导；场景 3 公开信息少；场景 5 目前只有学术案例 |

进入 spec 之前，需要补齐以下内容：目标客户的实际系统清单、对象模型来源（客户字段或行业标准原文），以及具体问答样例。按 AGENTS.md 的要求，本体概念不能凭本报告补造。

---

## 5. 局限与待核实

- **效果数字全部自报**：没有找到任何独立评测。美光的数字指整体 AI 投入，不是 Agent 单独的效果。
- **未能直读的来源（C 级）**：Cadence 的 ChipStack 新闻稿（含高通“约 10 倍”的说法）、SemiWiki 上 TSMC AI Design Kit 的文章、SEMICON Taiwan 上 Applied Materials 关于 Agent 化良率闭环的演讲页，均返回 HTTP 403。正文只把 Cadence 作为 C 级列出，另外两项没有写入正文。
- **检索中出现但未能核实、因此未采用的说法**：“Merck Electronics 在本体层上部署多 Agent”（在被指向的文章原文中没有找到）、“英飞凌 GenAI 使测试代码编写时间减少 80%”（只有二手来源）。
- **覆盖缺口**：
  - 本次没有检索中国大陆企业，如长江存储、长鑫、中芯国际、江波龙、得一微、大普微等，需要补充一轮中文来源调研；
  - Kioxia、SanDisk、Western Digital 没有检索到相关公开案例；
  - SK 海力士的韩文原始报道（The Elec）和三星的韩文原始报道（朝鲜日报 / Chosun Biz）都没有直读。

## 附录：来源清单（访问日期 2026-11-17）

| # | 来源 | 发布方 | 日期 | 等级 |
| --- | --- | --- | --- | --- |
| 1 | [ChipNeMo: Domain-Adapted LLMs for Chip Design](https://research.nvidia.com/publication/2023-10_chipnemo-domain-adapted-llms-chip-design) | NVIDIA Research | 2023-10-30 | A |
| 2 | [arXiv 2311.00176 ChipNeMo](https://arxiv.org/abs/2311.00176) | arXiv | 2023-11 | A |
| 3 | [Samsung Showcases Agentic AI–Driven Semiconductor Engineering Innovation at NVIDIA GTC 2026](https://semiconductor.samsung.com/news-events/tech-blog/samsung-showcases-agentic-ai-driven-semiconductor-engineering-innovation-at-nvidia-gtc-2026) | Samsung Semiconductor | 2026-03（演讲于 3 月 17 日） | A |
| 4 | [Synopsys Advances Agentic AI Chip Design with AMD and Microsoft](https://news.synopsys.com/2026-07-27-Synopsys-Advances-Agentic-AI-Chip-Design-with-AMD-and-Microsoft) | Synopsys | 2026-07-27 | A |
| 5 | [Cadence Unleashes ChipStack AI Super Agent](https://www.businesswire.com/news/home/20260210926552/en/Cadence-Unleashes-ChipStack-AI-Super-Agent-Pioneering-a-New-Frontier-in-Chip-Design-and-Verification) | Cadence / BusinessWire | 2026-02-10 | C |
| 6 | [AI Agents Enter Chipmaking: SK hynix Tests Back-End Deployment; Samsung Cuts SoC Verification to 2 Days](https://www.trendforce.com/news/2026/08/13/news-ai-agents-enter-chipmaking-sk-hynix-tests-back-end-deployment-samsung-cuts-soc-verification-to-2-days/) | TrendForce（转述 The Elec、朝鲜日报） | 2026-08-13 | B |
| 7 | [Samsung thinks Claude Code can help it boost chip design — but admits the AI still makes some worryingly big mistakes](https://www.techradar.com/pro/samsung-thinks-claude-code-can-help-it-boost-chip-design-but-admits-the-ai-still-makes-some-worryingly-big-mistakes) | TechRadar（转述 Chosun Biz） | 2026-08-25 | B |
| 8 | [Smart manufacturing at Micron: AI at enterprise scale](https://www.micron.com/about/blog/applications/ai/smart-manufacturing-at-micron-ai-at-enterprise-scale) | Micron | 2025 | A |
| 9 | [Riding AI chip wave, Micron looks to genAI to boost productivity](https://www.techgoondu.com/2024/04/02/riding-ai-chip-wave-micron-looks-to-genai-to-boost-productivity) | Techgoondu | 2024-04-02 | B |
| 10 | [The Petabyte Problem: How AI Is Finally Making Semiconductor Manufacturing Data Actionable](https://semiengineering.com/the-petabyte-problem-how-ai-is-finally-making-semiconductor-manufacturing-data-actionable/) | Semiconductor Engineering（PDF Solutions 赞助文章） | 2026-03-10 | A（厂商撰写） |
| 11 | [PDF Solutions Announces Collaboration with Lavorro](https://www.pdf.com/resources/pdf-solutions-announces-collaboration-with-lavorro/) | PDF Solutions | 2025-10-02 | A |
| 12 | [The Solidigm Dual Approach to AI](https://www.solidigm.com/products/technology/solidigm-ai-innovation-internal-excellence.html) | Solidigm | 2026-01-13 | A |
| 13 | [KORAL: Knowledge Graph Guided LLM Reasoning for SSD Operational Analysis](https://arxiv.org/abs/2602.10246) | FIU / Argonne，IPDPS 2026 | 2026-02-10 | A |
| 14 | [SemiFA: An Agentic Multi-Modal Framework for Autonomous Semiconductor Failure Analysis Report Generation](https://arxiv.org/abs/2604.13236) | arXiv | 2026-04-14 | A（研究原型） |
| 15 | [Technology and products leadership for the AI era（第 27 页）](https://s25.q4cdn.com/621799436/files/doc_downloads/2026/10/MU-TP-Webinar.pdf) | 美光投资者材料 | 2026-10-21 | A |
