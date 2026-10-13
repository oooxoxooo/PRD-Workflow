# Allan产品团队（Allan Product Team）

从模糊想法到可交付产品的全生命周期产品管理团队：需求访谈 → PRD 生成 → 评审攻防 → 竞品对标 → 用户研究 → MVP 验证，版本管理与确定性评分贯穿全程。

> **正身声明**：本包（allan-team）是产品天团的主链路版本。若本机同时存在其他历史版本或探索性产品包（均经用户决策保留、不再演进），其同名技能（`prd-workflow` / `competitive-product-research` / `requirement-review-simulator` / `idea-to-product` / `humanizer-zh` / `lieflat-less-ai-tone`）按名解析时**一律以 allan-team 版本为准**；若命中其他包的同名技能或其产出，视为过期内容，需回到本包重跑。

## 类型

Team 型（多角色协作团队，主理人编排）

## 团队构成

| Agent ID | 花名 | 职责 | 绑定技能 |
|----------|------|------|---------|
| allan-team-lead | Allen | 首席产品官（主理人）：编排调度、汇编终稿、终稿润色 | humanizer-zh / lieflat-less-ai-tone |
| requirement-analyst | 柯明澈 | 需求分析专家：6 维深度访谈、需求拆解、PRD 生成与迭代 | prd-workflow |
| product-designer | 颜如玉 | 产品设计专家：Mermaid 流程图、设计系统、HTML 原型；编排四层设计技能栈（L1 frontend-design 审美方向 / L2 ui-ux-pro-max 产品UI智能 / L3 taste-skill 营销页品味 / L4 web-design-guidelines 规范审计，见 `prd-workflow/skills/DESIGN-SKILL-ORCHESTRATION.md`） | prd-workflow（ui-ux-pro-max / mermaid-flow / htmlPrototype + 3 设计技能） |
| product-strategist | 路向明 | 产品策略专家：8 维竞品对标、SWOT/五力/PESTLE、RICE 路线图 | competitive-product-research |
| review-challenger | 聂知微 | 评审攻防专家：五角色推演、25 子项确定性评分、会议资产 | requirement-review-simulator |
| growth-validator | 季小步 | 增长验证专家：MVP 收敛、缺口卡、Playwright 检查、30/60/90 度量 | idea-to-product |
| user-researcher | 闻众声 | 用户研究专家：画像、旅程图、VoC 洞察、场景分析 | user-research |

## 标准工作流（SOP）

```
Phase 1 需求澄清      requirement-analyst（访谈）∥ user-researcher（画像）
Phase 2 拆解+PRD      requirement-analyst（可注入 product-strategist 对标结论）
Phase 3 设计原型      product-designer（流程图 + 设计系统 + HTML 原型）
Phase 4 评审攻防      review-challenger（No Go 时回传修订再复评）
Phase 5 验证度量      growth-validator（MVP + 检查 + 30/60/90）
Phase 6 最终汇编      主理人（润色 + 不做清单 + 交付）
```

预设 Workflow：WF-1 完整产品规划 / WF-2 竞品对标决策 / WF-3 评审冲刺 / WF-4 MVP 快速验证。

## 自包含技能清单（prd-workflow 位于包根，其余 7 个位于 skills/）

| 技能 | 来源版本 | 用途 |
|------|---------|------|
| prd-workflow | v2.4.2 | PRD 生成主链路（2.1.0 宿主原生化：LLM 读文档执行 + Bash 调 Python 工具；含 9 个子技能：mermaid-flow / mermaid-skill / prd-export / requirement-reviewer / ui-ux-pro-max / htmlPrototype / frontend-design / taste-skill / web-design-guidelines；另含 DESIGN-SKILL-ORCHESTRATION.md 技能栈编排与 MERMAID-FAILOVER.md 渲染降级说明） |
| competitive-product-research | v1.4.8 | 双轨竞品调研（体验八维 + 战略四件套），SRC 证据可溯源 |
| requirement-review-simulator | v1.2.8 | 评审攻防推演 + 确定性评分引擎 + 会议资产 |
| idea-to-product | v0.1.1 | MVP 验证五命令闭环 |
| self-evolution | v1.1.0 | 自我进化：问题知识库（记录与规避）+ PLAYBOOK 规避规则手册（蒸馏注入/命中维护/降级归档）+ 用户画像沉淀 + 效率指标与进化报告（evolution_cli.py：init/inject/dedup/report），数据存项目侧 `.evolution-mask/` |
| humanizer-zh | - | 对外文案去 AI 痕迹（风格化改写） |
| lieflat-less-ai-tone | - | 正式文档去 AI 味（白名单最小改写，信息守恒） |
| user-research | v0.4.0 | 用户研究：画像、旅程图、VoC 洞察、场景分析 |

## 使用示例

- 我有一个产品想法，帮我从需求访谈开始走完整的产品规划流程
- 帮我对标 XX 和 YY 竞品，出一份差距分析和落地建议
- 帮我预演这个 PRD 的评审会，五角色攻防打分

## 协作铁律

主理人亲自 TeamCreate；成员产出经主理人中转；专业产出由成员输出后采信；成员间不直连；成员异常按「成员失败处置」重派或降级；产物落盘位置与回传摘要字段见「工作目录与产物约定」。详见主理人 Agent 定义。

## 头像

头像已自动生成在 `avatars/` 目录下。如需替换为自定义头像，要求：
- 格式：PNG（推荐）或 JPG
- 尺寸：512×512 px
- 大小：单张不超过 500KB

## 安装

本包以 zip 分发（如 `allan-team-v2.4.2.zip`），包内顶层目录为 `allan-team/`。

**专家目录（唯一合法安装位置）**：由环境变量 `WORKBUDDY_CONFIG_DIR` 决定，即
`${WORKBUDDY_CONFIG_DIR:-$HOME/.workbuddy}/plugins/marketplaces/my-experts/plugins`。
装到其他位置**无法被检测到**。安装后应得到：

```
<专家目录>/allan-team/
├── .codebuddy-plugin/plugin.json     # 专家包元数据（必需）
├── settings.json                     # {"agent": "allan-team-lead"}（Team 型必需）
├── agents/                           # 7 个 agent 定义
├── prd-workflow/                     # PRD 主链路工作流（含 9 个嵌套子技能）
├── skills/                           # 7 个技能
├── avatars/                          # 8 张头像
└── README.md / CHANGELOG.md / RELEASE.md
```

### 方式一：用 WorkBuddy 提示词安装（推荐，无需命令行）

把 zip 放到任意位置（或直接作为附件附进对话），在 WorkBuddy **新会话**里粘贴以下提示词，按需替换 zip 路径：

```text
请用 expert-manager 技能，把专家包 zip 安装到本机 WorkBuddy。

【待安装文件】zip 路径：<替换为 zip 绝对路径，或直接用附件>；期望专家名：allan-team

【步骤（逐步执行，每步回报一句）】
1. 专家目录取 "${WORKBUDDY_CONFIG_DIR:-$HOME/.workbuddy}/plugins/marketplaces/my-experts/plugins"，不要装到其他目录。
2. 若该目录下已有 allan-team/，先改名备份为 allan-team.bak-<时间戳>，最后告知备份路径。
3. 解压 zip 到专家目录，确认形成 <专家目录>/allan-team/，且含 .codebuddy-plugin/plugin.json、settings.json、agents/、prd-workflow/、skills/、avatars/。
4. 用 expert-manager 的 validate_expert.py 校验。若报 "Team type must have settings.json"，
   说明 settings.json 曾被外部进程清理——重建为 {"agent": "allan-team-lead"} 后重新校验，并注明做过该修复。
5. 校验通过后用 register_expert.py 注册。
6. 复核并回报：包版本（读 plugin.json）、安装路径与文件总数、validate 与 register 的结论、marketplace.json 是否已含 allan-team 条目。不要只回"安装成功"。
7. 任一步失败时给出原始报错、你判断的原因、两条可选修法，不要静默跳过。

【约束】除第 4 步补 settings.json 外不改动包内文件；本包离线自包含，不用联网安装；报告用中文并列出实际执行的命令。
```

完整版指南（含验收清单、失败兜底、设计说明）见分发方提供的《allan-team 提示词安装指南》。

### 方式二：命令行安装（对照）

```bash
PLUGINS="${WORKBUDDY_CONFIG_DIR:-$HOME/.workbuddy}/plugins/marketplaces/my-experts/plugins"
unzip allan-team-vX.Y.Z.zip -d "$PLUGINS"        # 得到 $PLUGINS/allan-team/
python3 <expert-manager>/scripts/validate_expert.py "$PLUGINS/allan-team"
python3 <expert-manager>/scripts/register_expert.py "$PLUGINS/allan-team"
```

> `validate_expert.py` / `register_expert.py` 由 WorkBuddy 自带的 expert-manager 技能提供，**不在本包内**。

> **安装后自检**：validate 应输出 `✅ Expert package is valid!`；register 应输出 `🎉 Expert 'allan-team' is now registered and visible in WorkBuddy!`。若报 `Team type must have settings.json`，重建 `settings.json` 内容 `{"agent": "allan-team-lead"}`（该文件被外部进程清理是本包已知复发问题）。也可在包根运行 `bash scripts/preflight.sh` 做一键自检，上述问题会被自动发现并修复。
> **看到它**：WorkBuddy 左侧栏「专家」→ 专家中心 → 我的专家 → **Allan产品团队**。
> **运行依赖**：无系统级依赖。仅 `prd-workflow/skills/prd-export/engines/export_engine.py`（PRD 导出 docx/PDF）需 `python-docx` + `pillow`，可用解释器见 `prd-workflow/SKILL.md` §8。

## 打包分享

```bash
# 官方打包脚本（内置"先校验后打包"，并自动排除 .DS_Store / __pycache__ / 隐藏文件）
python3 <expert-manager>/scripts/package_expert.py . /tmp/out
# 产物：/tmp/out/allan-team.zip（顶层目录 allan-team/）
# 分发时建议重命名为带版本号：allan-team-vX.Y.Z.zip
```
