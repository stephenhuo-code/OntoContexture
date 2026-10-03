# **织境（****Onto****Contexture）**产品规划

Sep 27, 2026 · @coderyan

# 1. 执行摘要

**定位****和****价值****陈诉****：****织境（Contexture）****-****-****面向制造****页****的开放式 Agent 上下文层**。**产品****定位：**把企业系统数据、员工工作数据和 Agent 自身数据统一成一张带权限与血缘的工业语义图谱，通过 MCP / Context API / Skills 供企业自有数字员工平台调用。**价值****陈述****：**用一张可信的工业语义图，让人类员工和数字员工在同一上下文里协同——答得准、管得住、处处可用、越用越准。

**三大结论**

1. **趋势**：Context Layer 已成为 2026 年的产品研究热点（证据：Gartner 给出三件套定义、MCP 进入 Linux 基金会与 OSI 标准发布、OpenMetadata 2.0 改名 Open Context Layer、国内 ChatBI 转向“准不准”，详见第 2 节）。开源侧，OpenMetadata 是最合格的底座但不是产品——2026-08 它已改称 “Open Context Layer”，自带 MCP（15 个工具）、RDF 知识图谱、Context Center 记忆和 ODCS 数据契约，缺的是工业实体类型、指标语义模型（维度/度量/关联）、运行时查询、员工工作图谱、按 Agent 的请求级权限，且 AI SDK 不是 Apache 许可；这些缺口正是本产品要补的部分。
2. **竞争格局**：全球与国内玩家最多覆盖三类数据中的两类：语义层/目录厂商只有 IT 与经营数据，Work IQ / Glean / 飞书只有工作数据，mem0 / Zep 只有 Agent 记忆；工业平台（西门子、Cognite、卡奥斯、蓝卓）有工业语义但封闭在自家栈内。跨系统中立、懂设备/工单/BOM、又能喂给任意数字员工平台的“三域合一 + 工业 + 中立”产品，2026 年 9 月仍是空白。
3. **四个竞争力方向**：产品定位“面向离散制造的开放式 Agent 上下文层”，具体价值包括**：**① 数字员工答得准、做得对——只用已审批的指标口径和工业实体语义，解决“准不准”这个落地瓶颈；② 敢让 Agent 碰生产数据——按角色和数据级别授权、全程留痕，满足工业数据分类分级的监管要求；③ 人机同图、一次建设处处复用——人、系统、Agent 三域一张图，人的岗位、任务、决策和 Agent 的轨迹在同一语境里，人能看见并纠正 Agent 做了什么，Agent 按人的角色和工作语境行事；所有数字员工共用这张图，不用各自重做取数和语义；④ 越用越准——决策轨迹与人工纠正回流修正语义，人工维护成本随使用下降。开放接口和开源底座顺带保证不被单一厂商的栈锁定。
   1. **三域合一：人-岗-设备-工单-Agent 在同一 RDF 图谱**。① 每次 Agent 调用留下“用了哪些上下文 → 做了什么 → 人怎么改”的决策轨迹；② 工作数据域：从飞书的消息、文档、多维表格、审批、组织中提取人、岗、任务、决策；③ 系统数据域：从 ERP / MES / PLM 提取表、字段、指标口径与血缘。
   2. **可信语义：Agent 能用的每一条口径、记忆、数据和服务，都经过审批或授权并可追溯**。包含四个方面：① 系统指标语义审批模型——口径的提出、评审、生效、废弃有流程和版本，Agent 只能用已审批口径；② Agent 记忆与个人对话轨迹的统一审批语义——记忆、对话中沉淀的结论和自动装配的候选语义走同一套审批模型，经人审生效、带时效、来源可查；③ 系统数据权限按角色管理——数据分类分级，Agent 有独立身份，请求时按“人的角色权限 ∩ Agent 授权 ∩ 数据级别”求值；④ 对外服务权限统一管理——MCP / Context API / Skills 共用一套策略与审计，一次调用返回经策略过滤的上下文包，并留存谁在什么授权下拿到了什么。
   3. **工业本体**：标准为骨、场景为肉、客户适配——引入 ISA-95 / AAS / OPC UA / OSI 标准本体作骨架，按 POC 场景阶段逐个出领域包（质量 → 指标 → 供应链财务 → 工程变更），客户只做点位 / 字段 / 口径的映射与分支，行业包多厂复用。
   4. **能力****自演进：**把人对 Agent 的每一次纠正变成本体、口径、记忆和工具的提案，经可信语义的审批模型生效。分三阶段：① 语义与记忆自演进——从 Agent 调用轨迹和飞书对话中的人工纠正演进口径、术语、记忆和 Skill 提示词，由一个“自演进 Skill”驱动，演进判断用 Jev 类决策模型；② 工具与本体映射自演进——针对设备的 tools 描述、参数、点位→设备映射和新设备接入时的工具实例化；③ 模型自演进——用前两阶段积累的人审样本自训“工业决策模型”（意图识别 + 本体语义判断），定期重训发布。每一阶段都以人工纠正率下降为验收。

# 2. 机会分析

## 背景与趋势

"上下文层"在 2026 年已从概念变成厂商公开争夺的产品品类，但定义权还在争夺中。

**四个已发生的事实**

- Gartner 把"context layer"定义为三件套：语义（本体、知识图谱、机器可读策略）+ 运行态（API/事件的实时数据）+ 溯源（血缘/审计），并预测到 2027 年 AI-ready 语义数据可使 Agent 准确率提升最多 80%（[Gartner via Mexico Business News](https://mexicobusiness.news/cloudanddata/news/context-layer-key-scalable-ai-agents-gartner)）。
- MCP 于 2025-12-09 捐给 Linux 基金会 AAIF，成为 Agent 获取上下文的事实接口（[MCP blog](https://blog.modelcontextprotocol.io/posts/2025-12-09-mcp-joins-agentic-ai-foundation/)）；Open Semantic Interchange（OSI）v0.1 于 2026-01-27 发布，31+ 成员，正在 Apache 孵化为 "Ossie"，成为指标/语义互换标准（[Snowflake](https://www.snowflake.com/en/blog/open-semantic-interchanges-specs-finalized/)，[Ossie](https://ossie.apache.org/updates/osi-april-2026-community-update/)）。
- OpenMetadata 2.0（2026-08-24）直接把自己重新命名为 "The Open Context Layer for Data and AI"，以 Context / Ontology / Memory 三个原语重构产品（[OpenMetadata 2.0](https://blog.open-metadata.org/announcing-openmetadata-2-0-the-open-context-layer-for-ai-agents-83b8ce8b9dde)）。这既验证了选型，也意味着"通用 context layer"这个位置已被底座自己占据，产品必须在工业、工作数据、Agent 数据上差异化。
- 国内 ChatBI 竞争已从"能不能问"转到"准不准"，共识路径是 Text2SQL → 语义层/指标本体 → Data Agent；帆软 CEO 把瓶颈总结为"AI 应该相信什么"（[搜狐](https://www.sohu.com/a/1076821823_100246910)）。

**国内政策把工业数据目录和智能体绑在一起**

- 《工业互联网和人工智能融合赋能行动方案》（2026-01）：到 2028 年建立全国工业数据目录、推进工业数据可信流通空间、依托平台打造工业智能体（[新华网](https://www.news.cn/tech/20260109/90d2eea9e07848828f51a43033ffaaad/c.html)）。
- 国务院目标 2027 年重点行业智能体普及率超 70%；工业侧三大障碍是时序耦合难建模、企业不愿提供生产数据、中小企业成本（[数字中国峰会](https://www.szzg.gov.cn/2025/xwzx/szkx/202603/t20260320_5298681.htm)）。
- 数据资产入表：截至 2026-04-30 共 136 家 A 股公司入表 37.86 亿元，制造业以 32 家居首（[中国金融信息网](https://www.cnfin.com/gs-lb/detail/20260625/4431468_1.html)）；汽车行业可信数据空间已有 18PB 数据池、33 个场景（[国家数据局](https://www.nda.gov.cn/sjj/ywpd/sjzy/0119/20260119090956496597471_pc.html)）。

**工业场景与通用企业场景的五点不同**

| 维度 | 通用企业上下文层 | 离散制造上下文层 |
| --- | --- | --- |
| 核心实体 | 客户、订单、指标 | 设备、工序、BOM、工单、批次、物料（ISA-95 / AAS） |
| 数据形态 | 关系表 + 文档 | 加上时序、OPC UA / UNS、图纸、检测记录 |
| 系统形态 | SaaS 为主 | ERP+MES+PLM+WMS+QMS 多厂商、多代际、多无接口老系统 |
| 合规 | 个人信息 | 工业数据分类分级（五域三级）、信创、数据不出厂 |
| 消费方 | 分析师 | 产线/计划/质量/设备一线员工 + 数字员工 |
|  |  |  |

## 客户场景

&#91;embedded content: 客户场景路标 · 3 个优先级 5 个场景 2 道门槛\]

五个 POC 场景按“只读 → 可信 → 写回 → 深本体 → 自演进”递进，归成三个优先级：先用 P1 / P2 验证答得准（三域合一 + 可信语义），再用 P3 / P4 验证管得住（动作写回 + 工业本体），最后 P5 验证越用越准（自演进）；每个场景复用前一个场景已建的本体与数据，详细设计见《织境 POC 场景路线图》。

<https://claude.ai/artifact/UDJw7zsRBPCvRzqbfSotNp>

## 竞争格局

四类玩家各占一角，右上角"跨系统中立 + 工业实体"只有边缘接入产品，没有上下文层产品。

&#91;embedded content: 市场地图 · 覆盖范围 × 工业深度\]

横轴是能否作为中立层供客户已有平台调用，纵轴是语义是否深入到设备、工序、工单；位置为定性判断，依据各家 2025-26 公开资料。

**四类玩家的代表动作与不覆盖的部分**

| 类别 | 代表 | 2025-26 关键动作 | 不覆盖 |
| --- | --- | --- | --- |
| 语义层 / 数据云 | Snowflake、Databricks、Microsoft、dbt、Cube | Cortex Sense 从查询历史自动装配上下文，内部基准准确率 24%→86%（[Snowflake](https://www.snowflake.com/en/blog/enterprise-ai-agents-grounded-context/)）；Fabric IQ 本体 + Work IQ API GA（[Microsoft](https://www.microsoft.com/en-us/microsoft-365/blog/2026/06/02/announcing-the-new-work-iq-apis/)）；dbt / Cube 均出 MCP 并共建 OSI | 只覆盖自家数据驻留；无 OT；无跨套件工作数据 |
| 元数据目录 | DataHub、Atlan、Alation、Collibra、OpenMetadata | DataHub "Context Platform" 四支柱（Ingestion / Intelligence / Hub / Activation），Pinterest Agent 用量 10x（[DataHub](https://datahub.com/blog/inside-the-context-platform-june-2026-town-hall-highlights/)）；Atlan 自称 "missing context layer"；Alation 发布 AIOS（[Blocks & Files](https://www.blocksandfiles.com/ai-ml/2026/07/14/alation-builds-ai-agent-operating-system/5271050)） | 无工业实体，无员工工作图谱，记忆薄弱；深度功能多为云版收费 |
| 工作 / 记忆 / 上下文平台 | Glean、Work IQ、mem0、Zep、Letta、Airbyte Agents、Sema4 | Glean 企业图谱 275+ 连接器（[Glean](https://www.glean.com/enterprise-context/enterprise-graph)）；Airbyte Agents Context Store 2026-05 发布（[BusinessWire](https://www.businesswire.com/news/home/20260505801702/en/Airbyte-Agents-Launched-to-Fix-the-Data-Problem-Breaking-AI-Agents)）；Foundation Capital 提出 "context graph = 决策轨迹"（[Foundation Capital](https://foundationcapital.com/ideas/context-graphs-ais-trillion-dollar-opportunity)） | 无业务语义与指标口径；无 OT；工作数据绑定单一套件 |
| 工业平台 | Siemens、Cognite、AVEVA、Velotic、Sight Machine、HighByte、卡奥斯、蓝卓、树根、格创东智 | Sight Machine 2026-06 发布语义模型 + Agent Crews（[PR Newswire](https://www.prnewswire.com/news-releases/sight-machine-launches-agentic-manufacturing-platform-that-understands-your-plant--and-improves-it-every-run-302797542.html)）；Velotic ThingWorx 10.2 出 MCP Server（[Velotic](https://www.financialcontent.com/article/bizwire-2026-9-16-velotic-advances-thingworx-with-new-agentic-ai-capabilities)）；AVEVA 知识图谱要到 2027 Q1；卡奥斯以"工业本体图谱"做大模型知识锚点（[新浪](https://finance.sina.com.cn/roll/2026-07-19/doc-iniiirzc3491164.shtml)）；蓝卓 supOS X 推"数据连接 Agent"（[TOM](https://life.tom.com/202604/4347444555.html)） | 绑定自家 IIoT / MES；Cognite 偏流程工业且价格高；无员工工作数据、无中立开放 |
| 国内数字员工平台 | 用友 YonClaw、金蝶苍穹 Agent 2.0、钉钉、飞书、百炼、实在、来也 | 金蝶把数千 SaaS API 封装为 MCP（[金蝶](https://www.kingdee.com/article/1913102603487625217.html)）；百炼 NL2SQL 明文"单表、不支持多表关联"（[阿里云](https://help.aliyun.com/zh/model-studio/data-connection)）；实在智能对接 SAP / MES / PLM 十余套系统但为执行层（[实在智能](https://www.ai-indeed.com/aboutNews/20814.html)） | 上下文 = 自家对象 + 文档 RAG + 工具目录，无统一口径 / 本体 / 血缘 |
| 国内语义 / 本体产品 | 数势 SwiftMetrics、衡石 SENSE 6.0、滴普 FastData Foil、Datablau DOM | 数势"指标语义本体"（[数势](https://www.digitforce.com/product/hm/)）；衡石定义 Agentic BI 并出 CLI / skills（[衡石](https://www.hengshi.com/News/1341.html)）；滴普 108 个业务本体 + AI 员工（[新华网](http://www.news.cn/tech/20260313/ce40d89867134383ae0720ac1100a3a6/c.html)）；Datablau DOM "AI 原生本体建模"（[新浪](https://finance.sina.com.cn/cj/2026-02-03/doc-inhkpvfe3683374.shtml)） | 全部是经营指标 / IT 建模出身，无设备、工艺、时序 |

**最需要盯住的三个对手**：Microsoft（Work IQ + Fabric IQ + Digital Twin Builder 是最完整的封闭栈）、DataHub / Snowflake 的"自动装配上下文"（会变成标配）、蓝卓 / 卡奥斯（国内工业语义，但封闭）。

# 4. 关键竞争力和路标

## 关键竞争力

| 优先级 | 方向 | 具体做什么 | 为什么是壁垒 | 对手现状 |
| --- | --- | --- | --- | --- |
| 1 | **三域合一** | 人-岗-设备-工单-Agent 在同一 RDF 图谱；每次 Agent 调用记录"用了哪些上下文 → 做了什么 → 人怎么改"，形成可查询的决策轨迹；工作数据语义层：从飞书（消息、文档、多维表格、审批、组织）提取人、岗、任务、决策；系统数据语义层：ERP / MES / PLM 的表、字段、指标口径与血缘；两层用共同实体（人、设备、工单）对齐，合成统一知识图谱 | 每家对手最多覆盖两域；Gartner 三件套的"溯源"无人做到 Agent 级；Foundation Capital 把决策轨迹称为万亿机会；飞书自称有"最完整的工作上下文"但不接生产系统 | Work IQ / Glean 只有工作域且绑定套件；Semantica 有决策溯源但无工作域与工业；mem0 / Zep 只有记忆域 |
| 2 | **可信语义** | 定义：Agent 能用的每一条口径、记忆、数据和服务都经过审批或授权并可追溯。① 系统指标语义审批模型：口径的提出、评审、生效、废弃有流程和版本，Agent 只能用已审批口径；② Agent 记忆与个人对话轨迹的统一审批语义：记忆、对话中沉淀的结论和自动装配的候选语义走同一套审批模型，经人审生效、带时效、来源可查；③ 系统数据权限按角色管理：数据分类分级，Agent 有独立身份，请求时按“人的角色权限 ∩ Agent 授权 ∩ 数据级别”求值；④ 对外服务权限统一管理：MCP / Context API / Skills 共用一套策略与审计，一次调用返回经策略过滤的上下文包，并留存谁在什么授权下拿到了什么 | 国内 ChatBI 的购买动机已是"准不准"；工业数据分类分级是监管硬要求；OpenMetadata 权限只到人，契约无 Agent 级策略 | 数势 / 衡石有指标本体但无审批流与分级；Databricks Unity Gateway 开始管 Agent 但限自家湖仓 |
| 3 | **工业本体** | **标准为骨、场景为肉、客户适配：**引入 ISA-95 / AAS / OPC UA / OSI 标准本体作骨架，按 POC 场景阶段逐个出领域包（质量 → 指标 → 供应链财务 → 工程变更，累计约 50 对象类型 / 70 关系），到具体客户只做其点位 / 字段 / 口径到本体的映射并单独开分支，不重建本体，再由自演进回流持续修正。 | 语义层 / 目录厂商没有工业实体；OPC 基金会已把 430+ 伴随规范转为 MCP/RAG 可用格式（[OPC Foundation](https://opcfoundation.org/news/press-releases/opc-foundation-advances-opc-ua-for-the-ai-era-with-companion-specifications-optimized-for-agentic-ai/)）；标准本体预装 + 行业包让多厂复用，对手的本体每家重建 | 卡奥斯、蓝卓有本体但封闭；Palantir 无 OWL / ISA-95 / AAS；语义层厂商无工业实体 |
| 4 | **能力****自演进** | 把人对 Agent 的每一次纠正变成提案，经审批模型生效。三阶段：① 语义与记忆（口径 / 术语 / 记忆 / Skill 提示词，自演进 Skill + Jev 类判断模型）② 工具与本体映射（设备 tools 描述 / 参数 / 点位→设备映射 / 工具实例化）③ 模型（自训工业决策模型：意图识别 + 本体语义判断，定期重训）。分阶段规划见下表 | 本体和口径在工厂里天天变，人工维护不可持续；纠正样本只有在三域一图上才收得到，对手拿不到这份数据 | Cortex Sense / DataHub 的自动装配无工业映射、无人机纠正闭环；Sight Machine Blueprint 为专有；Jev 闭源且不可私有化 |

## 产品路标

&#91;embedded content: 功能架构 · 4 个能力域 22 个功能模块，按 3 阶段标记\]

| 竞争力方向 | 阶段一 | 阶段二 | 阶段三 |
| --- | --- | --- | --- |
| **三域合一** | **三域只读一张图**（P1 / P2）<br>• 系统域：MES / QMS / ERP 的批次、工单、设备、检验；数仓表 / 字段 / 血缘、帆软现有报表 SQL<br>• 工作域：飞书客诉群、审批、8D 负责人、需求提出人、指标 owner<br>• Agent 域：草稿 + 人工修改、探索轨迹、确认记录，决策轨迹作为一等公民<br>• 能力：人-岗-设备-工单-Agent 同一 RDF 图谱（只读）、OKF 知识包、两域以共同实体对齐<br>• 验收：8D 出具周期、追溯查询耗时、需求到首次见数时间 | **三域扩到供应链与工程，轨迹带写回**（P3 / P4）<br>• 系统域：IQC、供应商主数据、PO、发票；PLM eBOM / mBOM、工艺、ERP 成本<br>• 工作域：采购审批流、供应商沟通、变更评审会、APQP 门控<br>• Agent 域：建议 + 审批结果、评估包 + 评审结论，轨迹回传到 tool call 级（Webhook / OpenTelemetry）<br>• 能力：决策轨迹记录“用了哪些上下文 → 做了什么 → 写回了什么 → 人怎么改”，What-if 在图上遍历 BOM / 工艺<br>• 验收：来料不良处置周期、建议接受率、变更评审周期、漏评影响项数 | **三域图成为纠正样本的来源**（P5）<br>• 系统域：AOI / Novel Issue 结果；工作域：质量工程师审核；Agent 域：提议与被采纳率<br>• 能力：人对 Agent 的每次纠正在三域图上归因到实体 / 口径 / 记忆，成为自演进的输入；跨工厂同一张图复用<br>• 验收：纠正样本量达到自训模型门槛（5k–20k 条）、跨厂复用缺陷类型数 |
| **可信语义** | **口径审批 + 只读权限**（P1 / P2）<br>• ① 指标语义审批模型上线：口径提出 / 评审 / 生效 / 废弃有流程和版本，P2 首批 30–50 个审批指标，Agent 只用已审批口径<br>• ③ 数据权限按角色：分类分级标签、Agent 独立身份、请求时按“人的角色 ∩ Agent 授权 ∩ 数据级别”求值（只读）<br>• ④ 受治理查询网关 + 带权限的 Context API / MCP，留存谁在什么授权下拿到了什么<br>• 验收：同一指标 SQL 版本数下降、进入开发的需求占比、越权取数为零 | **写回纳入策略，记忆开始审批**（P3 / P4）<br>• ③ 动作类型与事务写回纳入请求时策略求值，写回必须经人审批（P3 扣款 / PO 调整，P4 评审结论 / PPAP 重做 / 切换日期）<br>• ① P3 约 10 个、P4 约 8 个成本与质量口径经财务 / 质量 owner 审批生效<br>• ② 记忆与对话轨迹审批语义启动：建议、评审结论沉淀为记忆，带时效和来源，经人审生效<br>• ④ 对外服务统一策略扩到动作类工具，审计覆盖读与写<br>• 验收：扣款准确率、AI 建议接受率、写回零越权 | **四类语义同一套审批，跨厂复用**（P5）<br>• ② 记忆、对话结论、自动装配的候选语义和本体提案走同一套审批模型（演进 30–50 条 / 期），人审生效、带时效、来源可查<br>• ① 口径和缺陷 / 根因类型的审批与合并支持跨工厂分支<br>• ③④ 策略与审计扩展到多工厂、多数字员工平台共用一套<br>• 验收：提案采纳率 ≥ 50%、审计可追溯覆盖全部读写调用 |
| **工业本体** | **标准层 + 质量 / 指标包**（P1 / P2）<br>• 引入 ISA-95 层级、AAS 子模型、OPC UA 伴随规范、OSI / ODCS，在 OpenMetadata 上建工业实体类型机制<br>• 质量包：批次 / 工序 / 设备 / 检验 / NCR / 8D，14–16 类、约 20 关系<br>• 指标包：指标、探索会话，接数仓表 / 字段 / 血缘<br>• 验收：P1 / P2 验收达标；本体对象类型约 18 | **供应链财务包 + 工程变更包**（P3 / P4）<br>• 供应链财务包：供应商 / IQC / PO / 发票 / 扣款，8 类、12 关系，带动作类型<br>• 工程变更包：零件版本 / eBOM / mBOM / 工艺路线 / ECN / PFMEA / 控制计划 / 成本卷，12 类、18 关系；接口类型“可变更项”“成本载体”<br>• 实例层：零件 10⁵、BOM 项 10⁶ 级多版本，属性图上验证图遍历性能<br>• 验收：P3 / P4 验收达标；累计约 50 对象类型、70 关系类型 | **行业包沉淀 + 本体即代码**（接 P5）<br>• 质量 / 财务 / 工程包沉淀为行业模板，第二家工厂复用<br>• 每客户一个本体分支：提案 / 审批 / 合并 / 版本，与 Skill 、标签集联动版本<br>• 映射小模型做点位归类、实体对齐、缺陷归类，提案经审批生效<br>• 验收：本体提案采纳率、跨厂复用的类型数 |
| **能力自演进** | **语义与记忆自演进**（P1 / P2 上线后启动）<br>• 演进什么：指标口径、术语与同义词、Agent 记忆（时效 / 降权 / 废弃）、Skill 提示词与口径说明，全是文本级修改<br>• 输入：Agent 调用轨迹、飞书对话中的人工纠正（草稿 diff、驳回理由）、被反复使用的临时口径<br>• 机制：“自演进 Skill”读轨迹 → 归因到本体元素 → 生成提案 → 进审批队列；指标 owner 和质量工程师审核<br>• 模型：Jev 类决策模型回答四个封闭选项问题（是否纠正 / 归因到哪类元素 / 是否值得人审 / 是否重复冲突），数据不可出厂时用大模型零样本代替；提案文本由大模型起草；每次判断 + 人审结果存成训练样本<br>• 验收：提案采纳率 ≥ 50%，纠正率半年 -30% | **工具与本体映射自演进**（P3 写回、OT 连接器就绪后）<br>• 演进什么：设备 tools 的描述与参数说明、点位 / 字段→设备属性映射、新设备接入时按设备类型自动实例化工具；只演进工具元数据和映射，不让 Agent 写工具代码<br>• 输入：工具调用成败、人工改参数记录、选错工具的纠正（轨迹回传到 tool call 级）<br>• 机制：同一套自演进 Skill 和审批模型，审核人换成本体工程师和设备工程师<br>• 模型：样本累积到 5k–20k 条后自训“工业决策模型”替换托管判断模型——编码器基座（Qwen3-Embedding / bge-m3）或 1.5B–3B 小解码器加分类头，选项集可变，temperature scaling 校准，同时承担演进判断和工业意图识别；单卡训、CPU 推理、可私有化，每客户一个 adapter<br>• 验收：新设备接入工时下降、工具误调率下降；自训模型准确率 ≥ 托管模型、ECE 校准达标、成本低一个量级 | **模型自演进**（阶段二样本达标后）<br>• 演进什么：模型本身——同一基座上加本体映射任务头（或 8B–14B LoRA，参考 Jellyfish、LLMs4OL），做点位 / 字段归类、实体对齐、缺陷归类；定期用新样本重训、评测达标后发布<br>• 输入：阶段二的映射人审样本 + OPC UA 伴随规范 / AAS 合成数据，之后持续回流<br>• 机制：模型纳入本体版本管理，Skill / 标签集变化时联动版本；权重与训练配方开源，作为织境的社区资产（Jev、Sight Machine Blueprint 均不开源）<br>• 不做：工业大模型或工艺 / 时序模型，那是中控、西门子的战场<br>• 验收：映射任务达到大模型 90% 以上准确率；新缺陷类型至少在第二家工厂复用一次 |

上图是路标表的图形版：行是四个竞争力方向，列是三个阶段，每格是该阶段要建成的功能模块。阶段一（P1 / P2）建 11 个，让数字员工在只读前提下答得准；阶段二（P3 / P4）补 8 个，打通写回与深本体；阶段三（P5）补 3 个，让本体和模型自己长。

工业本体按四层构建，阶段与客户场景的三个优先级对齐（阶段一 = P1 / P2，阶段二 = P3 / P4，阶段三 = P5）：L0 标准层（引入不自造：ISA-95 层级、AAS 子模型、OPC UA 伴随规范、OSI / ODCS，在 OpenMetadata 上以 JSON Schema 新增实体类型，本体层用 RDF / OWL）；L1 领域包（按场景逐个出包、后一个复用前一个，跨包用“可变更项”“成本载体”等接口类型对齐）；L2 客户实例层（点位 / 表字段 → 实体属性映射、口径绑定，每客户一个本体分支）；L3 演进层（P5 回流与映射小模型，提案经可信语义审批生效）。

**准入条件（必须做，但不作为卖点）**：MCP 渐进披露 + Skills + Context API 的多平台交付；达梦 / 金仓 / OceanBase / GaussDB 与国产时序库适配、离线部署、国产模型；核心 Apache 2.0 开源并对齐 OSI / AAS 国标。

**不建议做的**：自建 ChatBI 前端（交给数字员工平台）、自建边缘采集（接 HighByte / UMH / 国产网关）、自建向量数据库（复用 OpenSearch 混合检索）、通用 RPA 执行层。

# 5. 产品详细说明

- ## 产品功能架构

&#91;embedded content: 产品架构 · 四层 16 个模块\]

- ## 关键竞争力特性&#32;

**第一期 Top 10 特性（P1 质量追溯与 8D · P2 探索式报表）**：按“没有它场景跑不通”排序，前四条支撑 P1，五到十支撑 P2 和交付。

| # | 特性 | 服务场景 | 一句话说明 | 验收指标 |
| --- | --- | --- | --- | --- |
| 1 | 三域合一知识图谱 | P1 / P2 | 人-岗-设备-工单-Agent 在同一 RDF 图谱，以共同实体对齐，是追溯链路一次拉通的基础 | 追溯查询耗时 |
| 2 | 企业系统连接器与元数据血缘 | P1 / P2 | MES / QMS / ERP 的批次、工单、设备、检验，数仓表 / 字段 / 血缘入库 | 接入系统数、血缘覆盖率 |
| 3 | 工作数据连接器 | P1 | 飞书客诉群、审批、8D 负责人、组织关系提取为人、岗、任务、决策 | 责任班组 / 负责人识别准确率 |
| 4 | 决策轨迹 | P1 | 每次 Agent 调用留下“用了哪些上下文 → 做了什么 → 人怎么改”，8D 草稿人改后留痕 | 8D 出具周期 |
| 5 | 指标语义审批模型 | P2 | 口径提出 / 评审 / 生效 / 废弃有流程和版本，首批 30–50 个，Agent 只用已审批口径 | 同一指标 SQL 版本数下降 |
| 6 | 受治理查询网关 | P2 | 按已审批口径从数仓直接出 ad hoc 结果，每次取数前求值策略并留存审计 | 需求到首次见数时间 |
| 7 | 分类分级与角色权限 · Agent 身份 | P1 / P2 | 数据分级标签，Agent 独立身份，请求时按“人的角色 ∩ Agent 授权 ∩ 数据级别”求值（只读） | 越权取数为零 |
| 8 | Context API（OKF 知识包）+ MCP 服务 | P1 / P2 | 一次调用返回经策略过滤的上下文包，MCP 渐进披露，供飞书 / 自研 Agent 平台调用 | 平台接入数、调用成功率 |
| 9 | 本体建模管理器（含标准本体层 + 质量包） | P1 | 定义实体类型与关系、导入 ISA-95 / AAS / OPC UA 标准本体、把表字段 / 点位映射到实体属性、分支 / 提案 / 合并 / 版本（本体即代码）；第一期用它建质量包：批次 / 工序 / 设备 / 检验 / NCR / 8D（14–16 类） | 本体对象类型数、映射覆盖率 |
| 10 | Notebook 开发工作台 | P2 | 业务和 Agent 在 Notebook（SQL / Python）里经查询网关按已审批口径边问边看，确认有用后一键上线为定时任务 / 数据集，帆软报表只是其中一种输出；现有报表 SQL 反向解析为口径 | 探索到上线的周期、进入传统开发的需求占比 |

纠正采集与归因（自演进的起点）不在 Top 10，但从 P1 上线第一天起就要存样本。

**关键竞争力特性（1）：三类上下文，共用一张图**

三类上下文共用一张图谱和一套权限模型，差别在实体、来源和新鲜度要求。

|  | 企业系统数据 Context | 员工工作数据 Context | Agent 数据 Context |
| --- | --- | --- | --- |
| 回答的问题 | "这个数据是什么、口径是什么、能不能用" | "谁在做什么、为什么这样决定、找谁" | "哪个 Agent 用了什么上下文做了什么、结果如何" |
| 核心实体 | 设备 / 产线 / 工位（ISA-95 层级）、物料 / BOM / 工艺路线、工单 / 批次 / 质量记录、指标口径、表 / 字段 / 点位 | 人员 / 岗位 / 班组、任务 / 工单 / 审批、会议 / 消息 / 文档、SOP / 交接班记录、决策轨迹（异常、例外、审批理由） | Agent 身份与授权、会话 / 长期记忆、工具调用日志、评估与反馈、Skills / 提示词版本 |
| 来源 | ERP / MES / PLM / WMS / QMS 元数据与样本，OPC UA / UNS / 时序库点位树，数仓 / 数据湖 | 飞书、OA / 工单系统、HR、文档库、MES 操作日志 | 数字员工平台回传（Webhook / OpenTelemetry traces）、本平台 MCP 调用记录 |
| 现有方案 | 元数据目录 + ChatBI 语义层（只到表和经营指标） | Work IQ / Glean / 飞书（绑定套件） | mem0 / Zep / Letta（无业务语义）；OpenMetadata Context Center（无溯源） |
| 本产品要做的 | 工业实体类型 + 指标语义模型 + 数据契约 + 分类分级标签 + 受治理查询 | 人-岗-设备-工单关联图谱；决策轨迹作为一等公民；权限随人走 | Agent 身份与策略、记忆带时效与溯源、上下文使用审计、评估回流改进语义 |
| 新鲜度 | 元数据小时级；运行态数据经网关实时 | 分钟级 | 实时写入 |
| 合规要求 | 工业数据分级（三级数据默认不出境不出厂） | 个人信息 + 部门权限 | 审计可追溯（对应 Gartner "provenance"） |

**三类上下文之间的连接才是价值所在**：一个"设备异常处置"数字员工需要同时知道设备在哪条线、当前工单和批次（系统数据）、这个班组上次怎么处理、谁有权审批停线（工作数据）、自己上次建议的结果和人工纠正（Agent 数据）。国内现有平台要三个系统分别问，这是产品存在的理由。

**关键****竞争力****特性****（****2****）****：****Context API 格式：OKF（重点建设）**

OKF 是 Google Cloud 2026-06-16 发布的厂商中立规范（当前 v0.2）：知识以 Markdown 文件 + YAML frontmatter 表示，目录即知识包，`index.md` 做渐进披露，`log.md` 记变更；唯一必填字段是 `type`，可选 `resource`、`sources`（来源与可信度信号）、`generated`、`verified`（区分人工 / 机器确认）、`status`、`stale_after`，以及用于"可认证计算"的 `runtime` / `parameters` / `computation` / `attester`（[OKF SPEC](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)，[MarkTechPost](https://www.marktechpost.com/2026/06/16/google-cloud-introduces-open-knowledge-format-okf-a-vendor-neutral-markdown-spec-for-giving-ai-agents-curated-context/)）。

选它作 Context API 格式的理由：

- Agent 和人都能直接读写，不需要 SDK；任何数字员工平台把知识包当文件塞进上下文即可。
- `sources` / `verified` / `stale_after` 天然承载"可信语义"的溯源、审批状态和时效；已审批指标口径可作为"Attested Computation"概念输出，Agent 填参数、网关执行、回执可验。
- Git 可 diff，决策轨迹和自演进的人工纠正可以直接落为知识包的版本历史。

需要自建的部分（OKF 未定义）：工业 `type` 词表（Equipment / WorkOrder / Metric / SOP 等）与指向 RDF 本体的 `resource` URI 约定；链接的关系类型（OKF 链接无类型，需在 frontmatter 加 `relations` 扩展）；权限——OKF 的 trust tier 只是建议不是访问控制，策略求值必须在生成知识包之前完成；从 RDF 图谱到知识包的按需物化与缓存。

**反向链路**：Agent 事件与轨迹回传——数字员工平台通过 Webhook 或 OpenTelemetry traces 将每次任务的上下文使用、工具调用、结果与人工纠正回传，写入 Agent 记忆与决策轨迹；这是"Agent 数据 Context"的唯一来源，也是"自演进"方向的输入：反馈事件经人审后修正口径、实体映射与记忆。

## 产品技术架构

&#91;embedded content: 技术架构 · 5 组微服务 24 个组件，自建 7 个\]

许可红线：OM 核心 Apache 2.0，但 AI SDK 和 openmetadata-ui 目录为 [Collate Community License 1.0](https://github.com/open-metadata/OpenMetadata/blob/main/openmetadata-ui/LICENSE)（源码可用，禁止用于与 Collate 竞争的 SaaS / PaaS 在线服务，不可转授权）。本产品只做私有化部署、不做在线服务，所以这条限制不触发：AI SDK 和 openmetadata-ui 可以在客户现场使用，交付时保留版权声明、客户按同一许可使用即可。仍建议记忆和工具调用直接走 Apache 2.0 的 OM REST / MCP 接口，把 AI SDK 当可替换的客户端而非依赖，避免被 Collate 的路线图和许可变更牵制。

**部署形态**：K8s 一套集群，分五组服务——OM 底座（server + ingestion + MySQL / PG + OpenSearch + Fuseki）、图与时序（NebulaGraph + IoTDB）、查询与开发（Trino + JupyterHub）、治理与 Agent（OpenFGA + Langfuse + Skill 运行时 + 模型推理）、交互（MCP / Context API / Skills 网关）；离线部署时外部依赖只有数据源和数字员工平台。

**选型风险**：OM RDF 仍是 Beta 且只有 Fuseki，属性图要承担运行态负载；OM 2.1 将移除内置 Airflow，摄取调度要提前解耦；openmetadata-ui 为源码可用许可，产品 UI 应自建或仅在管理端复用；Langfuse 附加功能许可边界需逐项确认。

技术架构以 OpenMetadata 2.0 为必选底座，其余模块按“有 Apache 2.0 的开源件就复用、许可有雷就自建”选型：底座复用 OM 的元数据 / 血缘 / 契约 / RDF 图谱 / MCP，指标语义用 MetricFlow，权限用 OpenFGA，OT 接入用 PLC4X + IoTDB，轨迹用 OpenTelemetry + Langfuse，属性图用 NebulaGraph；工业本体建模管理器、语义审批中心、Context API（OKF）、Agent 记忆和自演进 Skill 自建。两条许可红线：OM 的 AI SDK 和 openmetadata-ui 目录是 Collate Community License 1.0（源码可用、非开源，禁止用于与 Collate 竞争的在线服务），记忆与 Agent 侧不依赖它们；TDengine 是 AGPL-3.0，时序库优先 Apache IoTDB。

### 功能模块 × 开源选型（一期微服务与二期演进）

| 能力域 | 功能模块 | 一期微服务 | 一期开源选型 / 实现 | 二期演进 | 许可 |
| --- | --- | --- | --- | --- | --- |
| 三域合一 | 系统数据连接器 | OM Ingestion | **OpenMetadata 2.0** 130+ 连接器，Airflow 3.3.2 调度，摄取 MES / QMS / ERP / 数仓表字段血缘，帆软 SQL 反向解析（[2.0 Release](https://docs.open-metadata.org/v2.0.x/releases/2.0-release)） | OM 2.1 移除内置 Airflow，调度提前解耦 | Apache 2.0 |
| 三域合一 | 工作数据连接器 | 工作数据连接器（自建） | 封装飞书官方 **lark-cli**（11 个业务域 200+ 命令，应用 / 用户双身份），提取人、岗、任务、决策并回收人工纠正 | 增加 OA / 工单系统 | MIT |
| 三域合一 | OT / PLM 连接器 | — | 一期设备、点位仅作为元数据实体入 OM | **Apache PLC4X** + Eclipse Milo 采集 OPC UA / Modbus / S7，**Apache IoTDB** 存时序（TDengine 为 AGPL-3.0，不选）；边缘采集接 HighByte / UMH | Apache 2.0 |
| 三域合一 | 统一知识图谱 | OpenMetadata Server + Jena Fuseki | OM 实体关系表（MySQL / PG）+ RDF 镜像（**Apache Jena Fuseki** 6.2，Beta，JSON-LD 映射 DCAT，SPARQL 端点；[RDF 文档](https://docs.open-metadata.org/v1.13.x/deployment/rdf-knowledge-graph)） | 增加 **NebulaGraph** 属性图承载决策轨迹、人-岗-设备-工单和多版本 BOM 遍历 | Apache 2.0 |
| 三域合一 | 决策轨迹 · 轨迹回传 | 轨迹采集 + 轨迹存储 | **OpenTelemetry Collector** 收 OTLP，**Langfuse** 自托管（ClickHouse）存 tool call 级 trace 与人工标注（[self-hosting](https://langfuse.com/self-hosting)） | 归因结果写属性图，轨迹带写回结果 | OTel Apache 2.0；Langfuse 开源自托管，部分附加功能需许可 |
| 可信语义 | 指标语义审批 | 指标语义 + 语义审批中心（自建） | **OM Metric** 实体（metricExpression / 粒度 / 单位 / 关联），审批流走 OM Governance Workflow / Intake Forms，自建队列、审核人路由和版本 | 增加 **MetricFlow**（OSI 对齐）做维度 / 度量模型和多方言 SQL 生成（[Apache 2.0](https://www.getdbt.com/blog/open-source-metricflow-governed-metrics)） | Apache 2.0 |
| 可信语义 | 分级与角色权限 | 身份 · SSO | **Keycloak** OIDC 做人和 Agent 身份、角色组；权限判定用 OM Policy / Role（资源级 RBAC + 分级标签条件） | **OpenFGA** 策略服务（CNCF，ReBAC + 条件）请求时按“人 ∩ Agent ∩ 数据级别”求值（[Apache 2.0](https://startwithidentity.com/vendors/authorization/openfga/)） | Apache 2.0 |
| 可信语义 | 受治理查询网关 | 受治理查询执行（自建） | 按已审批口径生成 SQL，执行前按 OM Policy 拦截，直连数仓，留存审计 | 执行引擎换 **Trino** 联邦（关系库 + 时序库 + API），拦截与审计不变 | Apache 2.0 |
| 可信语义 | 写回动作策略 | — | 一期只读 | 动作类型纳入 OpenFGA 策略，事务写回需人审批 | — |
| 可信语义 | 记忆与轨迹审批 | Agent 记忆服务（自建薄层） | 存储用 OM 2.0 **Organizational Memory**（Apache 2.0，挂在资产 / 概念上并继承权限），自建审批状态 / 时效 / 来源字段；不用 Collate 许可的 AI SDK | 对话结论与自动装配候选语义走同一套审批 | Apache 2.0 |
| 可信语义 | 本体提案审批 | 语义审批中心 | 同一套审批模型 | 分支 / 合并 / 跨厂（三期） | — |
| 工业本体 | 标准本体层 · 质量包 | 本体建模管理器（自建） | OM JSON Schema 新增实体类型 + OWL Import 导入 ISA-95 / AAS / OPC UA 伴随规范；类型 / 关系 / 映射 / 分支 / 合并界面自建，一期产出质量包（14–16 类） | 供应链财务包、工程变更包、接口类型；行业包沉淀 | 自建（上游 PR + 本地扩展双轨） |
| 自演进 | 纠正采集与归因 · 自演进 Skill | 自演进 Skill 运行时（自建） | 读 Langfuse trace 和飞书纠正，归因生成提案进审批队列；**LangGraph** 编排 + MCP 官方 SDK，闭环和技能格式借鉴 **Hermes Agent**（[MIT](https://github.com/nousresearch/hermes-agent)，agentskills.io） | 工具与本体映射自演进（设备 tools 描述、点位→设备） | MIT / Apache 2.0 |
| 自演进 | 工业决策模型 | 判断模型调用 | 托管 / 私有化大模型（通义 / DeepSeek / GLM）零样本回答四个封闭问题，判断 + 人审结果存样本 | 样本 5k–20k 后自训（Qwen3-Embedding / bge-m3 + 分类头），**vLLM / ONNX** 推理，每客户 adapter；三期本体映射小模型 | Apache 2.0 / MIT |
| 交付 | MCP 服务 | MCP Server | **OM MCP Server**（2.0 默认开启），只加工业实体工具描述 | — | Apache 2.0 |
| 交付 | Context API（OKF） | Context API（自建） | 一次调用返回经权限过滤的 OKF 知识包，`type` 词表与 `resource` URI 自定 | 改调 OpenFGA | 自建 |
| 交付 | Skills 市场 | Skills 市场（自建） | agentskills.io 格式存放、授权、版本化 | — | 自建 |
| 交付 | Notebook 工作台 | Notebook 工作台 | **JupyterHub** 接查询执行服务，确认后上线为 Airflow DAG / 数据集 | — | BSD |
| 存储 | 元数据 · 搜索 · 本体 · 轨迹 | 4 个存储 | **MySQL / PostgreSQL**（可换达梦 / 金仓 / OceanBase 兼容模式）、**OpenSearch**（搜索 + 向量）、**Jena Fuseki**（RDF）、**ClickHouse**（Langfuse） | + NebulaGraph、Apache IoTDB | Apache 2.0 |

### OpenMetadata 底座评估

结论：OpenMetadata 2.0.2（2026-09-16）已提供 Agent 上下文层所需的图谱、MCP、契约和记忆骨架，适合作为底座；但它是"元数据中心的 IT 语义"，工业实体、运行时查询、工作图谱、Agent 级权限都要自建。

**能力盘点（只列与本产品相关的）**

| 能力 | 当前状态 | 对产品的价值 | 缺口 |
| --- | --- | --- | --- |
| MCP 服务 | 内置 `/mcp`，2.0.2 整合为 15 个工具（search / semantic\_search / company\_context / get\_persona\_context / lineage / RCA / patch 等），按调用者 RBAC 执行，游标分页（[MCP reference](https://docs.open-metadata.org/latest/how-to-guides/mcp/reference)） | 直接可接数字员工平台 | 权限是"人的角色"，没有 Agent 身份、请求级策略；company\_context 目前只返回文档提取的知识片，不含手工记忆（[Context Center](https://docs.open-metadata.org/v2.0.x/how-to-guides/context-center)） |
| 知识图谱 / 本体 | 1.13 起 Apache Jena RDF 索引、Ontology Explorer、10 种 SKOS 式术语关系；2.0 支持 OWL 导入、DCAT / PROV-O（[1.13](https://docs.open-metadata.org/v2.0.x/releases/1.13-release)，[2.0](https://docs.open-metadata.org/v2.0.x/releases/2.0-release)） | 可直接导入 ISA-95 / AAS 本体 | 本体只能挂在术语上，不能定义新实体类型；SHACL 仅结构校验 |
| 记忆 | Context Center：Articles / Documents / Memories，文档经 LLM 抽取"knowledge pills"，支持 OpenAI / Azure / Bedrock / Google / Anthropic | 可作为 Agent 长期记忆存储 | 记忆无时效、溯源、作者权限模型（[Datapace 分析](https://datapace.ai/blog/openmetadata-context-layer-data-catalog)） |
| 数据契约 / 质量 | 原生契约（schema / 语义 / SLA），ODCS 3.1 导入导出，DQ as Code，RCA | "AI 应该相信什么"的基础 | 无运行时数据访问，开源版不能执行查询（SQL Studio / text-to-SQL 仅 Collate） |
| 指标 | Metric 实体含表达式、类型、单位、粒度（[Metric schema](https://docs.open-metadata.org/latest/main-concepts/metadata-standard/schemas/entity/data/metric)） | 可登记口径 | 无维度 / 度量 / 关联，不是 dbt / Cube 意义上的语义模型，不兼容 OSI |
| 实体模型 | Table / Dashboard / Pipeline / Topic / MLModel / API / Metric / Glossary 等 19 类，911 个 JSON Schema，16 种自定义属性 | 覆盖 IT 资产 | **无用户自定义实体类型**，无设备 / 产线 / 时序点位 / 人员工作实体 |
| 连接器 | 官方称 130+；2026 新增 SAP S/4HANA、SuccessFactors、ServiceNow、Google Drive、TimescaleDB、QuestDB | ERP / HR 侧可用 | 无 MES / PLM / OPC UA / UNS / 国产时序库；无国产关系库（达梦 / 金仓 / OceanBase / GaussDB） |
| 架构 | MySQL 8 / PostgreSQL 15 + Elasticsearch 9 / OpenSearch 3，1.12 起 Kubernetes 编排去 Airflow（[最低要求](https://docs.open-metadata.org/latest/deployment/minimum-requirements)） | 可私有化、可 K8s | 信创需适配元数据库本身 |
| 许可与社区 | 核心 Apache 2.0，约 15.1k stars，4000+ 部署；Collate 2025-07 完成 1000 万美元 A 轮（[GitHub](https://github.com/open-metadata/OpenMetadata)，[Collate](https://www.getcollate.io/blog/how-collates-series-a-will-transform-agentic-data-intelligence-1)） | 可商用分发 | **AI SDK（Context Memories、Dynamic Agents）为 Collate Community License，禁止竞争性 SaaS**（[LICENSE](https://github.com/open-metadata/ai-sdk/blob/main/LICENSE)）；国内尚无公开以其为内核的商业产品 |

**建议的使用方式**

- 直接复用：元数据存储与 JSON Schema 机制、血缘、RDF 图谱、数据契约、DQ、MCP 服务框架、Domains / Data Products。
- 自建（不依赖 Collate 许可的部分）：工业实体扩展（基于 JSON Schema 的新实体类型，需改核心）、指标语义模型、受治理查询网关、Agent 身份与策略、自建记忆 SDK（避开 Collate Community License）。
- 升级风险：2.0 已废弃 Knowledge Center URL，2.1 将移除内置 Airflow；二次开发应以插件/扩展方式为主，避免深改核心导致无法跟随上游。

### 技术选型要点

- 工业实体以 OpenMetadata JSON Schema 新增实体类型实现（需改核心，建议以上游 PR + 本地扩展双轨推进），而不是堆自定义属性。
- 记忆与 Agent SDK 自研，避开 Collate Community License。
- 查询网关可基于 Trino / StarRocks 联邦查询加时序库适配，所有查询经语义模型生成并留存审计。
- 嵌入与抽取模型可插拔，默认支持通义 / DeepSeek / GLM 私有化。
- 统一知识图谱逻辑上是一张图，存储不绑死：本体层固定用 RDF / OWL（标准与 OpenMetadata 一致）；实例图可选 OpenMetadata 内置 RDF（Fuseki，Beta、默认关闭，[部署文档](https://docs.open-metadata.org/v1.13.x/deployment/rdf-knowledge-graph)）或属性图（Neo4j / FalkorDB / NebulaGraph / TuGraph），决策轨迹和人-岗-设备关系这类边上带时间与来源的关系在属性图上更顺手；国产化优先考虑 NebulaGraph / TuGraph。

## 9. 风险与下一步建议

## 10. 参考来源

正文内已逐条链接；以下为主要一手来源，均为 2025-09 至 2026-09 间发布。

- OpenMetadata：[2.0 发布博客](https://blog.open-metadata.org/announcing-openmetadata-2-0-the-open-context-layer-for-ai-agents-83b8ce8b9dde)、[2.0 发布说明](https://docs.open-metadata.org/v2.0.x/releases/2.0-release)、[1.13 发布说明](https://docs.open-metadata.org/v2.0.x/releases/1.13-release)、[MCP 工具参考](https://docs.open-metadata.org/latest/how-to-guides/mcp/reference)、[Context Center](https://docs.open-metadata.org/v2.0.x/how-to-guides/context-center)、[AI SDK 许可](https://github.com/open-metadata/ai-sdk/blob/main/LICENSE)、[Collate 定价](https://www.getcollate.io/pricing)
- 标准与分析：[MCP 加入 AAIF](https://blog.modelcontextprotocol.io/posts/2025-12-09-mcp-joins-agentic-ai-foundation/)、[OSI v0.1](https://www.snowflake.com/en/blog/open-semantic-interchanges-specs-finalized/)、[Apache Ossie 进展](https://ossie.apache.org/updates/osi-april-2026-community-update/)、[Gartner context layer](https://mexicobusiness.news/cloudanddata/news/context-layer-key-scalable-ai-agents-gartner)、[OPC UA 面向 Agentic AI](https://opcfoundation.org/news/press-releases/opc-foundation-advances-opc-ua-for-the-ai-era-with-companion-specifications-optimized-for-agentic-ai/)、[Foundation Capital context graph](https://foundationcapital.com/ideas/context-graphs-ais-trillion-dollar-opportunity)
- 海外厂商：[Snowflake Cortex Sense](https://www.snowflake.com/en/blog/enterprise-ai-agents-grounded-context/)、[Microsoft Work IQ API](https://www.microsoft.com/en-us/microsoft-365/blog/2026/06/02/announcing-the-new-work-iq-apis/)、[Fabric IQ](https://community.fabric.microsoft.com/blog/fbc_fabricupdatesblogs/from-data-platform-to-intelligence-platform-introducing-microsoft-fabric-iq/5172484)、[Databricks Unity Catalog 2026](https://www.databricks.com/blog/whats-new-unity-catalog-data-ai-summit-2026)、[DataHub Context Platform](https://datahub.com/blog/inside-the-context-platform-june-2026-town-hall-highlights/)、[Atlan](https://atlan.com/)、[Alation AIOS](https://www.blocksandfiles.com/ai-ml/2026/07/14/alation-builds-ai-agent-operating-system/5271050)、[Glean Enterprise Graph](https://www.glean.com/enterprise-context/enterprise-graph)、[Airbyte Agents](https://www.businesswire.com/news/home/20260505801702/en/Airbyte-Agents-Launched-to-Fix-the-Data-Problem-Breaking-AI-Agents)、[Sight Machine](https://www.prnewswire.com/news-releases/sight-machine-launches-agentic-manufacturing-platform-that-understands-your-plant--and-improves-it-every-run-302797542.html)、[Velotic ThingWorx 10.2](https://www.financialcontent.com/article/bizwire-2026-9-16-velotic-advances-thingworx-with-new-agentic-ai-capabilities)、[Cognite 2026-05](https://www.cognite.com/en/resources/blog/cognite-may-2026-release-where-industrial-ai-meets-the-frontline)、[Siemens CES 2026](https://press.siemens.com/global/en/pressrelease/siemens-unveils-technologies-accelerate-industrial-ai-revolution-ces-2026)、[AVEVA World 2026](https://www.aveva.com/en/about/news/press-releases/2026/aveva-announces-new-capabilities-to-embed-ai-across-industrial-organizations-and-data-infrastructure-at-aveva-world-2026/)、[HighByte Industrial MCP](https://www.highbyte.com/news/press-releases/highbyte-releases-industrial-mcp-server-for-agentic-ai)、[UMH](https://tech.eu/2026/03/11/this-open-source-bet-is-paying-off-as-united-manufacturing-hub-takes-on-industrial-giants/)
- 国内厂商：[用友 YonClaw](https://finance.sina.com.cn/tech/roll/2026-06-17/doc-inicsvwv3880935.shtml)、[金蝶 MCP](https://www.kingdee.com/article/1913102603487625217.html)、[金蝶 Agent 2.0](https://www.kingdee.com/article/1925506968693325826.html)、[百炼数据连接](https://help.aliyun.com/zh/model-studio/data-connection)、[飞书 2026-03](https://www.qbitai.com/2026/03/389311.html)、[实在智能制造业](https://www.ai-indeed.com/aboutNews/20814.html)、[卡奥斯 WAIC 2026](https://finance.sina.com.cn/roll/2026-07-19/doc-iniiirzc3491164.shtml)、[蓝卓 supOS X](https://life.tom.com/202604/4347444555.html)、[格创东智章鱼智脑](https://tech.china.com/articles/20260522/202605221875961.html)、[美云智数](https://cn.chinadaily.com.cn/a/202601/15/WS6968a882a310942cc499b692.html)、[数势 SwiftMetrics](https://www.digitforce.com/product/hm/)、[衡石 SENSE 6.0](https://www.hengshi.com/News/1341.html)、[滴普 DeepexiOS](http://www.news.cn/tech/20260313/ce40d89867134383ae0720ac1100a3a6/c.html)、[Datablau DOM](https://finance.sina.com.cn/cj/2026-02-03/doc-inhkpvfe3683374.shtml)、[帆软访谈](https://www.sohu.com/a/1076821823_100246910)、[Smartbi AIChat](https://www.smartbi.com.cn/aichat)、[DataWorks MCP](https://www.alibabacloud.com/help/zh/dataworks/user-guide/dataworks-agent-with-mcp)
- 政策与标准：[工业互联网与 AI 融合行动方案](https://www.news.cn/tech/20260109/90d2eea9e07848828f51a43033ffaaad/c.html)、[汽车行业可信数据空间](https://www.nda.gov.cn/sjj/ywpd/sjzy/0119/20260119090956496597471_pc.html)、[数据资产入表统计](https://www.cnfin.com/gs-lb/detail/20260625/4431468_1.html)、[智能体普及目标与障碍](https://www.szzg.gov.cn/2025/xwzx/szkx/202603/t20260320_5298681.htm)、[AAS 国标计划](https://std.samr.gov.cn/gb/search/gbDetailed?id=28F53BF293F6A8D3E06397BE0A0AF10B)、[工业数据分类分级](https://www.isz.org.cn/news/12/3/12981.html)、[国产数据库兼容性](https://www.modb.pro/db/2044721705831698432)
