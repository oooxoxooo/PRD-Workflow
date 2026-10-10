---
name: prd-workflow
description: Complete PRD workflow executed by the LLM reading this document as the pipeline. Deep interview → Requirement decomposition → PRD generation → Review → Flowchart → Quality gates → Word export. Deterministic steps call Python tools directly.
---

# PRD Workflow（WorkBuddy 原生化版 v2.2.0）

> **执行模型**：本文档即管线。没有可运行的 JS 工作流——LLM（你）按本文档逐步执行；确定性步骤用 Bash 调用 Python 工具（见第 8 节）。**禁止尝试运行 `legacy/` 下的任何 JS**（它们依赖上游宿主环境，在本环境不可用，仅作历史归档，详见 legacy/LEGACY-NOTE.md）。
> **溯源**：上游 v5.1.0（gotomanutd + 红曼为帆，MIT-0）。2.1.0 宿主原生化改造：JS 管线归档，方法论全量萃取至本文档。

---

## 1. 流程总览

```
阶段 0 访谈（LLM 与用户交互）
  → gate1 访谈门禁
  → 需求拆解 → gate2 拆解门禁
  → PRD 生成 → gate3 PRD 门禁
  → 评审（requirement-reviewer 引擎）→ gate4 评审门禁
  → 流程图（Mermaid）→ 设计/原型（product-designer 主链路）
  → 导出（export_engine.py → docx/md）→ 质量检查（checker.md）
```

**是否需要访谈的判断**：
```
interview.json 已存在？ ── 是 → 跳过访谈
        │否
有详细业务文档？ ── 是 → 简化访谈（3-5 个确认问题）
        │否
完整访谈（16-33 问，6 维度）
```

> 上游 v5.1.0 的 Wiki 知识库增强特性依赖上游宿主的 `wiki-ai/` 知识库目录，本环境不存在，**不可用**——不要尝试检索 Wiki，直接按标准访谈流程执行。

## 2. 阶段 0：访谈（LLM 亲自执行）

访谈需要与用户实时交互（逐题提问 → 等回答 → 追问），必须由直接面对用户的会话方执行；子代理只产出访谈提纲，不执行访谈。

**访谈维度（6 维度）**：

| 维度 | 问题数 | 示例问题 |
|------|--------|---------|
| 产品定位 | 3-5 | 目标用户是谁？使用场景？ |
| 核心功能 | 3-5 | 是否需要产品推荐？数据来源？ |
| 合规要求 | 3-5 | 是否需要风险测评？适当性管理？ |
| 技术约束 | 3-5 | 使用渠道？现有系统？上线时间？ |
| 业务目标 | 2-3 | 解决什么痛点？成功指标？ |
| 用户场景 | 2-5 | 谁在什么时候使用？使用频率？ |

**完成条件**（全部满足）：问题数 **16-33 问**（= 本节六维表 3-5×4 + 2-3 + 2-5 的上界；**该表是访谈问题数的唯一事实来源**，其他文档一律引用此处；有详细业务文档时 3-5 确认问题）；覆盖 6 维度；keyDecisions ≥12；用户确认理解正确。

**输出 interview.json**（落盘到项目工作目录）：

```json
{
  "sharedUnderstanding": {
    "summary": "需求总结",
    "productPositioning": { "targetUsers": "目标用户" },
    "coreFeatures": ["核心功能 1", "核心功能 2"],
    "complianceRequirements": ["合规要求 1"]
  },
  "keyDecisions": [
    { "id": "d1", "topic": "决策主题", "decision": "决策内容", "rationale": "决策理由" }
  ],
  "questions": [
    { "question": "问题", "answer": "答案", "followUp": "追问" }
  ]
}
```

**与团队成员的衔接**：团队协作时，requirement-analyst（柯明澈）模式 A 产出提纲、主理人逐题访谈；单点直调时柯明澈模式 B 直接访谈。本 skill 是两者的共同执行标准。

## 3. 执行模式（4 模式 + 3 快速通道）

| 模式 | 触发词示例 | 语义 |
|------|-----------|------|
| **auto**（默认） | "生成 XXX 的 PRD" | 完整流程：访谈（若需要）→ 全链路 |
| **iteration** | "迭代修改 PRD，追加新需求" | 现有 PRD 基础上追加/修改；**执行前自动备份当前版本到 `.versions/`**；复用已有 interview.json |
| **fresh** | "清空重来" | 删除所有中间结果重新生成（历史版本仍保留在 `.versions/`） |
| **rollback** | "回滚到版本 v1.0" | 从 `.versions/vN/` 恢复指定版本 |

| 快速通道 | 触发词示例 | 跳过 |
|---------|-----------|------|
| review-only | "只评审这份 PRD" | 访谈与生成，直接进评审 |
| export-only | "只导出 PRD（docx+md）" | 全部前置，直接导出 |
| design-only | "生成 UI 设计和原型" | 访谈，直接进设计（需已有 PRD） |

## 4. 质量门禁表（硬约束）

每个门禁未通过时：修复问题后重试，**重试上限 3 次**；超限即终止流程，向用户输出问题清单与已产出物路径（含 `.versions/` 最新备份位置）。禁止无限重试。

| 门禁 | 检查项 | 阈值 |
|------|--------|------|
| **gate1 访谈质量** | interview.json 的 keyDecisions 数量 | ≥12 |
| **gate2 拆解质量** | 用户故事格式（须含 As a / I want / So that 三要素） | 100% |
| | 验收标准格式（GWT：Given/When/Then） | 100% |
| | 每个功能的业务规则数量 | ≥3 条 |
| | 每个功能的约束条件（业务/技术/合规至少一类） | 必有 |
| | 需求分析报告 | 已生成 |
| **gate3 PRD 质量** | 章节完整性（对照第 7 节 PRD 结构） | ≥9 章，100% 覆盖 |
| | 规格设计完整性（输入输出/异常处理） | 是 |
| **gate4 评审质量** | requirement-reviewer 综合评分（第 8 节工具） | ≥80 |

补充标准（requirement-analyst 自检口径）：GWT 覆盖率 ≥90%、三要素完整率 100%、无重复验收标准。

## 5. 版本管理约定

- 版本目录：项目工作目录下 `.versions/vN/`（v1、v2、…按序递增）；
- **iteration 模式执行前必须备份**当前 PRD 全量文件到 `.versions/v(N+1)/`；
- rollback 按版本号恢复；fresh 不清除 `.versions/`（历史保留）；
- 能回滚的 PRD 才敢于迭代——这是需求侧的安全网。

## 6. 质量检查项

PRD 终稿的质量检查对照 **[docs/checker.md](docs/checker.md)** 执行（检查项事实来源，含 CORE/FORMAT 等分类的检查点与提问）。逐项核对，未通过项记入问题清单。

## 7. PRD 结构（模板强制）

模板：**[templates/PRD_TEMPLATE_v2.6.2.md](templates/PRD_TEMPLATE_v2.6.2.md)**（功能型变体：`PRD_TEMPLATE_v2.6.2_FUNCTION_BASED.md`）。骨架：

```
1. 需求概述（定位/目标用户/业务目标/功能列表）
2. 全局业务流程（Mermaid 主流程图 + 时序图〔PRD 含多参与者动态交互时必选〕/业务规则/数据定义）
3..N. 每个功能：概述/用户场景/业务流程/业务规则/输入输出定义/
     用户故事/GWT 验收标准/原型设计/异常处理
N+1. 非功能需求（性能/安全/兼容性）
N+2. 附录（术语表/参考资料）
```

约束：Markdown 结构化章节编号；每个功能模块独立生成 GWT，顶层不重复生成验收标准。

**图表完整性约束（强制）**：PRD 含以下任一特征时，对应图型为必选产出，缺项视为结构不完整——
- 多服务/多系统串联调用（如 AI 管线、支付链路）→ **时序图**（sequenceDiagram，含异常分支）
- 多角色跨端交互（如家长-孩子-后台-第三方）→ **时序图**
- 数据实体关系（≥3 实体且有关联）→ ER 图
- 实体生命周期状态迁移（≥4 状态）→ 状态图
- 其余场景 → flowgraph 必选（既有要求不变）

## 8. Python 工具矩阵（Bash 直接调用）

| 工具 | 用途 | 依赖 | 调用示例 |
|------|------|------|---------|
| `skills/prd-export/engines/export_engine.py` | PRD.md → docx/PDF/HTML | `python-docx` + `pillow`；**本机已装好的解释器**：`~/.workbuddy/binaries/python/envs/default/bin/python`（裸 `python3` 无此依赖） | `<上述解释器> engines/export_engine.py PRD.md --formats docx,md` |
| `skills/requirement-reviewer/engines/review_cli.py` | PRD 结构化评审（gate4 评分来源） | 标准库 | `python3 engines/review_cli.py <prd路径>` |
| `skills/requirement-reviewer/engines/content_check_cli.py` | 内容检查问答引导 | 标准库 | 见脚本内 help |
| `skills/mermaid-flow/scripts/mermaid_render.py` | Mermaid → 图片（本地渲染，自带 Chrome 检测） | 标准库 + Chrome | `python3 mermaid_render.py in.mmd out.png` |
| `skills/mermaid-skill/scripts/mermaid_live_link.py` | 生成 Mermaid Live 链接（零本地依赖备选） | 标准库 | 见脚本内 help |
| `skills/ui-ux-pro-max/scripts/design_system.py` | 设计系统持久化（MASTER.md + tokens.json） | 标准库 | product-designer 主链路 |
| `skills/htmlPrototype/main.py` | 原型平台分析/截图 | 标准库 | 见脚本内 help |
| `scripts/generate_check_items.py` | `docs/checker.md` → `docs/check_items.py` 再生 | 标准库 | 维护用 |
| `scripts/manifest_cli.py` | 产物依赖与失效台账（stale 检查 / 豁免 / 重新登记） | 标准库 | `python3 scripts/manifest_cli.py check`（退出码 0=全 fresh） |

Mermaid 渲染主备切换（mmdc → Kroki → 子进程备援 + 熔断器）详见 **[skills/MERMAID-FAILOVER.md](skills/MERMAID-FAILOVER.md)**。**渲染通道默认本地，Kroki 出网需用户显式开启（可执行）**：Mermaid 渲染默认走本地通道（`mermaid_render.py`，需本机 Chrome）；仅当用户在本次任务中**显式同意外发**（例如"可以用在线渲染"）才允许走 Kroki，且同意仅当次任务有效、跨任务不继承。敏感特征规则作为额外防线**继续生效**：图表源码、标题或所在 PRD 段落命中任一敏感特征——「合同 / 金额 / 报价 / 客户名 / 账号 / 密钥 / 内部字段 / 未公开指标」——则**无论是否已获出网许可，一律跳过 Kroki、强制本地渲染**。判定结论须在渲染说明中标注（例如"本地渲染：默认策略"／"本地渲染：命中敏感特征『金额』"／"Kroki：用户显式同意且未命中敏感特征"）。

## 9. 子技能索引（skills/ 下，独立可用）

| 子技能 | 用途 |
|--------|------|
| [skills/mermaid-flow](skills/mermaid-flow/SKILL.md) | Mermaid 渲染（17+ 图表类型双通道） |
| [skills/mermaid-skill](skills/mermaid-skill/SKILL.md) | Mermaid 语法与 mmdc/Kroki 双通道 |
| [skills/prd-export](skills/prd-export/SKILL.md) | 导出引擎（docx/md/飞书） |
| [skills/requirement-reviewer](skills/requirement-reviewer/SKILL.md) | 结构化评审引擎 |
| [skills/ui-ux-pro-max](skills/ui-ux-pro-max/SKILL.md) | 产品 UI 智能库（22 技术栈） |
| [skills/htmlPrototype](skills/htmlPrototype/SKILL.md) | HTML 原型生成 |
| [skills/frontend-design](skills/frontend-design/SKILL.md) | L1 审美方向 |
| [skills/taste-skill](skills/taste-skill/SKILL.md) | L3 营销页品味 |
| [skills/web-design-guidelines](skills/web-design-guidelines/SKILL.md) | L4 规范审计 |

设计技能四层编排（L1-L4 路由与组合）→ **[skills/DESIGN-SKILL-ORCHESTRATION.md](skills/DESIGN-SKILL-ORCHESTRATION.md)**

## 10. 版本与溯源

- 本版：v2.3.0（2026-10-10，mask-team 2.3.0）——新增产物依赖与失效台账机制（`scripts/manifest_cli.py`，§8）；Mermaid 渲染默认值反转：本地渲染为默认，Kroki 出网需用户显式同意，敏感特征规则降级为额外防线（§8）
- 上一版：v2.2.0（2026-10-10，mask-team 2.2.0 收口）——访谈问题数口径收敛为单一事实来源（16-33，§2）、Kroki 出网判定规则可执行化（§8）、工具矩阵同步归档后实际脚本
- 上一版：v2.1.0（2026-10-10，宿主原生化改造）——JS workflows 归档至 `legacy/`，方法论萃取至本文档；执行模型从"JS 管线自动执行"切换为"LLM 读文档执行 + Bash 调脚本"
- 上游：v5.1.0（2026-04-20，gotomanutd + 红曼为帆，MIT-0）——Wiki 增强 / AI 驱动原型 / 设计系统持久化三大特性中的 Wiki 增强依赖上游宿主知识库（详见 legacy/LEGACY-NOTE.md），本环境不可用；其余能力经原生化改造后保留
- 改造依据：《2026-10-09 prd-workflow 宿主原生化改造设计文档》（方案 B）
