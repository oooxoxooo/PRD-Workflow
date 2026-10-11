# Changelog

本文件记录MASK产品天团（mask-team）的版本演进。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循语义化版本。

## [2.4.1] - 2026-10-11

### Fixed
- 接线 user-research 技能：注册进 plugin.json、绑定 user-researcher、更新 README
- **评审修复第一批（2026-10-11 架构评审 P0 组）**：
  - **访谈数口径算术修正**：六维表上下界复算为下界 3×4+2+2=16、上界 5×4+3+5=28，原文标称 16-33 系错误；prd-workflow/SKILL.md §2（唯一事实来源）、mask-team-lead 开场承诺、requirement-analyst frontmatter/流程/自检共 7 处同步为 16-28；RELEASE.md 检查单新增「数字口径可复算」项（防同类错误再生）
  - **manifest_cli.py 并发与一致性加固**（响应评审"机制服务于并行化但自身并发不安全"）：save 改「同目录临时文件 + os.replace」原子替换；register/check/refresh/exempt 四个写命令全程持 fcntl 排他锁（`.mask/manifest.lock`，无 fcntl 平台退化为仅原子写）；check 新增 stale 自愈（输入恢复后重置 fresh 并在输出中列 healed，消除 status 与退出码矛盾）；resolve_in_root 统一拦截绝对路径与 .. 越界（此前可登记包外任意文件）；重复 register 的 history 快照排除嵌套 history（防平方级膨胀）。15 项验收测试全过（含并发双写完整性、篡改→stale→恢复→自愈全链路）
  - **Phase 3/4/5 并行声明统一**：lead 的 Phase 4 标题原写「依赖 Phase 2/3」与「三者可同时下发」矛盾，现统一为「依赖 Phase 2；与 Phase 3/5 可并行，Phase 3 设计产出回传后对涉及章节增量补评」
  - **product-designer 脚本断链修复**：两处引用不存在的 `generate_design_system` 脚本，更正为 ui-ux-pro-max 实际入口 `scripts/search.py "<query>" --design-system --persist --output-dir <项目根>`

## [2.4.0] - 2026-10-10

### Changed
- **目录架构：prd-workflow 提升至包根**（`skills/prd-workflow/` → `prd-workflow/`，与 `agents/`、`skills/` 平级）。理由：该技能实为"方法论主链路 + 全包 Python 工具供给方 + 设计技能宿主"三重身份，并非普通能力技能；同时消除 `skills/prd-workflow/skills/` 三级嵌套。官方 `plugin-json-spec.md` 的 skills 示例即根级技能（`["./my-skill"]`），validate_expert.py 对 skills 仅校验"声明路径下存在 SKILL.md"，无目录位置强制——兼容性经官方校验器实测通过
- **联动修改（21 处 `skills/prd-workflow` 路径引用，非 legacy/CHANGELOG 全部归零，rg + 正样本控制验收）**：plugin.json skills 路径（`./prd-workflow`）；agents/mask-team-lead.md manifest_cli 调用路径；agents/product-designer.md 嵌套技能路径基准；README（技能清单标题、安装目录树、提示词安装检查项、运行依赖路径）；RELEASE（耦合检查范围扩为 `skills prd-workflow` 双目录、正样本基线路径、manifest 冒烟命令）；prd-workflow 内嵌套文档 14 处（htmlPrototype×8 / requirement-reviewer×2 / mermaid-flow C4_TEST×2 / prd-export×1 / ui-ux-pro-max×1 路径基准声明）
- **不改**：CHANGELOG 历史条目与 `legacy/` 上游归档中的旧路径属历史记录，按原样保留；prd-workflow 内部相对路径（SKILL.md §8 工具矩阵以技能根为基准）不受影响

### Migration
- 运行缓存快照 `cache/my-experts/mask-team/2.4.0/` 已按新布局同步，`installed_plugins.json` 指向 2.4.0；旧版本快照（≤2.3.0）保留旧布局不动

## [2.3.0] - 2026-10-10

### Added
- **产物依赖与失效台账机制（manifest）**：响应外部评审 P0——Phase 3/4/5 并行化后，Phase 4 No-Go 触发 PRD 修订时，下游产物（design/validation）没有任何失效标记机制。新增：
  - `skills/prd-workflow/scripts/manifest_cli.py`：六命令（`init` / `register` / `check` / `refresh` / `exempt` / `status`），零第三方依赖、Python 3.8+，风格对齐 `evolution_cli.py`；台账落盘于用户项目根 `.mask/manifest.json`，产物输入取 sha256 前 12 位哈希快照（`shasum -a 256` 可复算），目录型产物按文件逐个展开登记，`check` 退出码 0=全 fresh / 1=有 stale（供 Phase 6 汇编前硬断言脚本化）
  - 主理人三处条款落文（`agents/mask-team-lead.md`）：① 工作目录树新增 `.mask/manifest.json`；② 成员回传后、转交前须 `register` 登记；③ Phase 4 No-Go 修订后必须 `check` 并对 stale 产物逐个裁决（重跑 / `exempt` 理由必填），**stale 重跑每产物上限 1 次**（同一产物二次 stale 强制串行化），总重跑轮数（门禁+复评+stale）在 Phase 6 通报并入 METRICS.md；Phase 6 新增汇编前硬断言（check 非 0 禁止交付）
  - 失效语义：**stale ≠ 必重跑**——机器给信号、主理人按改动面裁决、豁免理由强制留痕；级联标记（输入节点 stale 则下游一并 stale）；本机制仅团队编排（TeamCreate 后）启用，单点直调不使用
  - 验收：临时项目全流程实测通过——init/register（文件+目录展开）/篡改输入后 check 报 3 节点 stale 且退出码 1/级联 `input_stale` 命中/exempt 留痕并拒绝非 stale 产物（退出码 2）/refresh 旧态入 history/汇编前 check 退出码 0/`prd_version` 从 `.versions/vN` 自动探测
  - 设计文档：工作区《2026-10-10 mask-team 产物依赖与失效机制设计文档》

### Changed
- **Mermaid 渲染默认值反转**（响应外部评审安全项）：原策略为"默认走 Kroki 出网、命中敏感关键词才强制本地"——关键词启发式漏检不可避免，PRD 属高敏文档，默认值方向错误。现改为**默认本地渲染（`mermaid_render.py`），Kroki 出网需用户在当次任务中显式同意（跨任务不继承）**；敏感特征规则保留并升级为额外防线（命中时即使已获许可也强制本地）。prd-workflow SKILL.md §8 与 skills/MERMAID-FAILOVER.md 同步落文
- RELEASE.md 检查单新增两项：① 根目录与 `skills/` 下无 `.DS_Store`（2.2.0 曾声明清理但根目录残留至今，说明旧检查单未覆盖——附正样本控制写法）；② manifest 机制冒烟（`manifest_cli.py init` 退出码 0）

### Fixed
- 仓库卫生：删除包根与 `skills/` 下 2 个 `.DS_Store`，新增 `.gitignore`（`.DS_Store` / `__pycache__/` / `*.pyc`）

## [2.2.6] - 2026-10-10

### Changed
- 按用户要求**清除包内对特定历史专家包的引用**（收件人无需知道本机还装着哪些同名包）：
  - 「正身声明」（主理人 MD + 包 README）移除具体包名与"更名为本包之前的旧版"的指涉，改为通用表述"其他历史版本或探索性产品包"，**保留全部缓解效力**（同名技能一律以 mask-team 版本为准）
  - CHANGELOG 2.2.0 / 2.2.3 条目中的包名同步改写为不点名表述
- **历史条目按"去指涉、留史实"原则保留**：2.0.0（更名重构）与 2.0.1（运行时数据目录隔离）条目不改写——旧名即本包曾用名，删去会使条目残缺并丢失 `mask-team-lead` 命名的溯源
- 核验：包内**无任何功能性耦合**（agent `skills:` 绑定、脚本路径、目录名均不含相关包名），本次改动纯文档层；`.evolution-mask/` 目录名保持不变（运行时数据契约，改名会破坏已有数据）
- 本次发版过程中**第五次复现** `settings.json` 被剥离，并首次定位触发时机：紧接 `register_expert.py` 注册动作之后（同时伴生 `.pending-preview-session` 的创建/消失竞争）。RELEASE.md 维护检查单据此补充顺序条款：「注册 → 复检 settings.json → 再同步缓存/打包」

## [2.2.5] - 2026-10-10

### Added
- README 新增「方式一：用 WorkBuddy 提示词安装（推荐）」：提供可直接复制粘贴的安装提示词，覆盖专家目录解析（`WORKBUDDY_CONFIG_DIR`）、同名目录先备份、解压结构断言、validate/register 调用、`settings.json` 复发故障的修复值、安装后**必须回报的事实清单**（版本/路径/文件数/两条结论/marketplace 条目）、失败时的诊断义务

### Fixed
- **撤回未经证实的安装方式**：2.2.4 的 README 写有「方式二：专家中心导入——在 WorkBuddy 专家中心直接导入本 zip」，但经核查 expert-manager 技能及其 `references/` **均不存在该入口**（只有"放入专家目录 + register 写入 marketplace.json"这一条官方路径）。现替换为经核实的两种方式（提示词安装 / 命令行安装）
- 安装路径口径改为官方变量：硬编码 `~/.workbuddy/...` → `${WORKBUDDY_CONFIG_DIR:-$HOME/.workbuddy}/plugins/marketplaces/my-experts/plugins`，并明确"装到其他位置无法被检测到"

## [2.2.4] - 2026-10-10

### Fixed
- README 安装章节重写为**收件人视角**：原文给出的 `python3 scripts/register_expert.py <expert-dir>` 在包内并不存在（脚本由宿主 expert-manager 技能提供），zip 收件人按此执行必然失败。现补齐：解压路径与期望目录结构、注册命令的正确来源、专家中心导入方式、安装后自检步骤（validate 期望输出 + `settings.json` 缺失时的重建值）、运行依赖说明
- 「打包分享」章节改为引用宿主官方打包脚本 `package_expert.py`（内置先校验后打包 + 自动排除 `.DS_Store`/`__pycache__`/隐藏文件），替代原先的裸 `zip -r` 命令

## [2.2.3] - 2026-10-10

### Changed
- 「正身声明」覆盖面扩展（主理人 MD + 包 README）：由"仅针对单一历史版本"扩展为"主链路版本 + 所有保留的历史/探索性包"的统一口径，并列出 6 个实际存在跨包同名的技能名。原因：专家包清单审计发现同名技能空间涉及多个包，原声明的覆盖范围不足

## [2.2.2] - 2026-10-10

### Fixed
- `legacy/LEGACY-NOTE.md` 的缓存快照指针修正：原文指向 `cache/my-experts/mask-team/2.0.3/`，该快照已于同日随宿主 orphaned 缓存回收清除（清理由本包 2.2.1 发版流程一并执行）。现明确说明"归档前实质性内容（30 个 JS + 9 份上游文档）完整保留在 `legacy/` 内、回滚能力不受影响"，消除断链文档

## [2.2.1] - 2026-10-10

### Fixed
- 采集表单剪贴板降级路径（浏览器端实测发现）：review-simulator 的 `intake-form.html` 在 `navigator.clipboard.writeText` 被拒（如未授权剪贴板、非安全上下文）时会抛出未捕获的 `NotAllowedError`，用户点「确认清单并开始评审」后**无任何反馈**（表现为按钮失效）。现补齐 try/catch 降级：失败时提示"浏览器未授权剪贴板，请手动复制下方参数"，并动态插入只读文本框（`#payload-fallback`）展示完整 JSON 且自动选中，与 CPR 表单行为对齐
- 实测记录：两个表单在真实点击下均能成功写入剪贴板并显示正确文案（review-simulator「已复制到剪贴板」/ CPR「已复制。请粘贴给当前 Agent 继续调研。」）；CPR 表单原有降级路径验证正常（剪贴板被拒时显示 JSON 文本框 + 提示）

## [2.2.0] - 2026-10-10

### Fixed
- **验收机制失效（P0）**：维护检查单原用 `grep -rn "openclaw\|sessions_spawn"`（本机 grep 为 toybox 实现，不支持 BRE 交替，该命令**恒返回 0 行**）——据此得出的"零残留"结论为假阳性。改为 `rg` / `grep -E` 命令组，并新增**覆盖率自证**（正样本控制）条款
- **宿主耦合清理（P0，非 legacy 区由 105 行归零）**：9 个嵌套子技能去 OpenClaw 化（htmlPrototype ×6 文件、requirement-reviewer 安装块与措辞、mermaid-flow/C4_TEST 路径与输出目录、prd-export 集成块与契约描述）；`ai_checker.py` 删除硬编码 `~/.openclaw/...config.json`，改为「环境变量 `PRD_WORKFLOW_CONFIG` > 包内 `config.json`」探测；ui-ux-pro-max 的 11 处 `${CLAUDE_PLUGIN_ROOT}` 调用改包内相对路径并加「路径基准」说明，同步删除其 Claude 专属 path 回归测试；humanizer-zh README 去除 Claude 安装路径
- **归档扫尾**：删除 `prd-workflow/scripts/` 下 4 个指向已归档 `workflows/` 的上游维护脚本（update_version.py / test-workflow.sh / publish.sh / postinstall.js）；`generate_check_items.py` 输出改 `docs/check_items.py`；MERMAID-FAILOVER.md 的"实现位置"指向已归档文件的死引用改写
- 工具矩阵补明解释器：`export_engine.py` 依赖 `python-docx` + `pillow`，裸 `python3` 不可用——矩阵中标注本机可用解释器路径（`~/.workbuddy/binaries/python/envs/default/bin/python`），消除「按文档执行即报 ModuleNotFoundError」的隐性坑
- 访谈问题数口径收敛为**单一事实来源**（prd-workflow SKILL.md §2 六维表 = 16-33 问），主理人开场承诺与柯明澈能力/流程/自检三处同步（此前 lead 16-30 / analyst 16-50 / SKILL.md 16-50 三处不一，且与六维表上限 33 自相矛盾）
- 两个采集表单删除 `window.codex`/`window.openai` 死码分支（WorkBuddy 无宿主回传 API），改为剪贴板单路径；两份 SKILL.md 的提交行为描述同步
- CPR SKILL.md 的 `tests/test_intake_form_contracts.py` 断链改指向实际存在的 `scripts/test_intake_form.py`
- 上游 ClawHub 元数据清除（3 技能的 `_meta.json` / `claw.json` / `skill-card.md` / `package.json` 共 9 文件）；ClawAether 品牌残留清除；CHANGELOG 1.0.0 条目恢复史实（齐运筹 Qi Yunchou）并加更名注记
- 包卫生：删除 4 个 `.DS_Store`；RELEASE.md 的 git 恢复承诺改为 marketplace 源口径（安装副本无 `.git`）

### Added
- 主理人 Agent 新增「成员失败处置（鲁棒性条款）」：空回传重派 → 二次失败上报 → 用户同意的降级路径（严禁代写）→ 部分产出按缺口补充
- 主理人 Agent 新增「工作目录与产物约定（跨成员接口契约）」：固定目录结构 + 回传摘要四字段（产物路径 / 关键结论 / 未决问题 / 建议下一阶段输入）
- 主理人 Agent 新增「正身声明」：同名技能一律以 mask-team 版本为准（其他历史版本经用户决策保留、不再演进）
- Kroki 出网渲染升级为**可执行判定规则**（命中金额/合同/客户名等敏感特征即强制本地渲染并标注结论）
- requirement-analyst `maxTurns` 60 → 120（直调模式需承载 16-33 轮访谈 + 拆解 + PRD），模式 B 增加"超 30 轮建议分两次会话"

### Changed
- SOP 并行化：Phase 5 仅依赖 Phase 2，Phase 3 / 4 / 5 改为可并行下发（刻意串行需说明理由）；WF-1 编排同步
- prd-workflow 子技能版本 2.1.0 → 2.2.0；包版本 2.1.1 → 2.2.0

## [2.1.1] - 2026-10-10

### Fixed
- 评审 P1-1（技能名三体不一致）：requirement-review-simulator 的 SKILL.md frontmatter name（原 `pm-requirement-review-simulator`）对齐目录名；`_meta.json` slug、`claw.json` name、intake-form.html 提交路由标识同步；CPR research-playbook 交叉引用同步（上游 GitHub homepage URL 保留溯源）
- 评审 P1-2（映射表未同步 1.2.0 修复）：requirement-review-simulator SKILL.md 五角色表"🎨 设计 → 运营价值"更正为"逻辑自洽"（agent MD 已是正确值）
- 评审 P1-3（No-Go 复评无上限）：主理人 Phase 4 增加复评上限 2 轮条款——第 2 轮仍 No Go 则停止循环，输出剩余致命问题清单与"有条件结论"，由用户决策
- 评审 P2-1（访谈数口径不一致）：主理人开场承诺"共约 16-20 个"对齐柯明澈提纲规格"16-30 个（有业务文档时更少）"

## [2.1.0] - 2026-10-10

### Changed
- **prd-workflow 宿主原生化改造（方案 B）**：执行模型从"JS 管线自动执行"切换为"LLM 读 SKILL.md 执行 + Bash 调 Python 工具"，与包内其余 6 技能执行模型统一
  - `skills/prd-workflow/workflows/`（30 个 JS）与 9 个上游文档归档至 `skills/prd-workflow/legacy/`（含 LEGACY-NOTE.md：归档原因/OpenClaw 耦合点清单/可回滚说明，禁止运行）
  - SKILL.md 重写（523 行 → 约 200 行，10 节）：流程总览与访谈判断、6 维访谈标准 + interview.json schema、4 模式 + 3 快速通道、**质量门禁表**（从 quality_gates.js v2.6.0 全量萃取：gate1 ≥12 决策 / gate2 故事格式 100% + 业务规则 ≥3 + 约束必有 / gate3 章节 ≥9 / gate4 评审 ≥80，重试上限 3）、版本管理约定（.versions/vN/ + iteration 前备份）、checker.md 指向、PRD 结构、Python 工具矩阵（8 脚本依赖与调用示例）、子技能索引、溯源注记
  - README.md 重写为精简入口；Wiki 增强特性标注本环境不可用（依赖 OpenClaw wiki-ai 目录），防幻觉调用
  - requirement-analyst.md 质量自检行改指向（interview_module → SKILL.md 质量门禁表）；包 README 技能表 prd-workflow 行版本口径同步 v2.1.0

### Fixed
- 评审 P0-1（JS 管线宿主不兼容）：非 legacy 路径零 openclaw/sessions_spawn/.openclaw 引用
- 评审 P1-5（维护检查单盲区）：RELEASE.md 自包含检查项补入"legacy 外零 openclaw 引用"

## [2.0.3] - 2026-10-08

### Fixed
- 主理人花名大小写纠正：elon mask → Elon Mask（9 处 / 4 文件：agent frontmatter + 正文 + plugin.json members[0] + README + CHANGELOG）

## [2.0.2] - 2026-10-08

### Changed
- **lead 更名**：主理人花名 齐运筹 / Qi Yunchou → Elon Mask（agent md frontmatter + 正文称呼 + plugin.json members[0].displayName + README 团队表 + CHANGELOG 历史条目同步），lead agent ID（`mask-team-lead`）与头衔（首席产品官）保持不变

## [2.0.1] - 2026-10-08

### Changed
- **双包并存隔离**：self-evolution 运行时数据目录 `.evolution/` → `.evolution-mask/`（CLI 路径常量 + SKILL.md/README/lead agent 文档同步），与 trea-pm-expert-team（沿用 `.evolution/`）在同一项目使用时数据完全隔离、互不污染；CLI status 冒烟验证通过

## [2.0.0] - 2026-10-08

### Changed
- **更名重构**：trea-pm-expert-team → mask-team（TREA产品天团 → MASK产品天团）
  - plugin.json：name/plugin/agentName/leadAgent → mask-team / mask-team-lead，version 1.2.1 → 2.0.0
  - lead agent 文件：`agents/trea-pm-expert-team-team-lead.md` → `agents/mask-team-lead.md`（含头像同名替换）
  - 6 个成员 agent 回传目标、README/RELEASE/CHANGELOG、self-evolution SKILL.md 中全部 trea 引用同步改写
  - 团队结构、七技能、SOP 六阶段、工作流与自我进化协议零改动

## [1.2.0] - 2026-10-07

### Added
- 新增 self-evolution 技能（v1.1.0）：专家团自我进化能力
  - 问题记录与规避：`.evolution-mask/ISSUES.md` 问题知识库，四类分类（需求理解偏差/沟通歧义/产出缺陷/流程效率），复发合并计数（Recurrence-Count，`dedup` 输出合并候选），任务启动时预算内注入
  - 规避规则手册：`.evolution-mask/PLAYBOOK.md` 蒸馏层——ISSUES 原文供追溯、注入只用蒸馏规则；Hits/Last-Hit 命中维护；90 天未命中降级 / 120 天归档防膨胀；仅脱敏规则可随项目 git 共享
  - 用户画像沉淀：`.evolution-mask/USER_PROFILE.md` 四区画像（偏好/历史需求特征/反馈记录/协作习惯），写入需证据、冲突需确认、超 30 天未观察进入待复验（显式偏好不衰减）、用户可审计可删除
  - 效率优化：`.evolution-mask/METRICS.md` 七指标跟踪（访谈轮次/返工/一次通过率/存活率/规则命中等），`report --save` 生成进化报告（趋势/晋升候选/规则健康度/画像复验）
  - 新增 `evolution_cli.py`（init/inject/dedup/report/status，Python 标准库零依赖）：确定性操作脚本化，注入包预算 ≤4000 字符；`.evolution-mask/` 被清理后一条命令自愈
  - 晋升机制：复发 ≥3 次且跨 2 任务、30 天内的规则，经用户批准后**优先写入 PLAYBOOK.md**（项目级即时生效）；跨项目通用规则才进 agent 定义/技能模板（git 提交可回滚）
- 主理人 Agent 新增「自我进化协议」章节：任务启动 `inject` 注入包（画像预填 + 规则分发）、过程统一记录、阶段结束记指标与命中、晋升需批准、隐私红线
- review-challenger 新增「规则自检」能力：按注入的 PLAYBOOK 规则清单在推演前核对 PRD，命中标注「规则命中 RUL-xxx」回传
- 运行时数据约定存用户项目根目录 `.evolution-mask/`（模板在插件 `skills/self-evolution/assets/`，插件升级不丢数据；画像建议入 .gitignore）

### Fixed
- review-challenger 五角色↔五维映射错位：设计角色误映射"运营价值"，更正为"逻辑自洽"
- 主理人 Agent frontmatter 补充 `skills: [humanizer-zh, lieflat-less-ai-tone]` 声明，与 README 绑定表及 Phase 6 润色用途对齐
- settings.json 第三次被外部清理丢失，再次恢复（沿用 c14495a 处理）
- README 修正 prd-workflow 子技能清单（实为 9 个子技能 + 2 份机制文档）；安装路径去除本机绝对路径硬编码
- WF-1 编排补注 Phase 5（growth-validator 验证度量，按需），与 SOP 六阶段对齐
- 全队回传规范统一：长产出先落盘、回传文件路径+要点摘要（原仅 product-designer 采用），缓解主理人上下文瓶颈

## [1.1.0] - 2026-10-07

### Added
- 产品设计四层技能栈编排：frontend-design（L1 审美方向）/ ui-ux-pro-max（L2 产品 UI 智能库，升级至 GitHub main 最新版 73 文件）/ taste-skill（L3 营销页品味）/ web-design-guidelines（L4 规范审计），含场景路由表与 3 条固定组合流水线（`DESIGN-SKILL-ORCHESTRATION.md` + product-designer 重写）
- Mermaid 渲染主备自动切换机制（`image_renderer.js` v2.0）：三级瀑布（A mmdc 本地 → B Kroki API → C mermaid-flow 子进程）+ 熔断器（连败 2 次开闸 10 分钟，半开探测切回）+ JSONL 降级日志（`MERMAID-FAILOVER.md`）
- mermaid-skill 技能（17+ 图表类型，mmdc/Kroki 双通道）
- git 仓库与版本管理（.gitignore / RELEASE.md / CHANGELOG.md）

### Fixed
- ui-ux-pro-max 新版 persist 返回结构兼容（design_module.js Step 3 展开嵌套 persistence 字段）
- mermaid_render.py 裸调 mmdc 的 Chrome ConnectionClosed 崩溃（自动 puppeteer 配置 + chrome-headless-shell 优先检测 + `-p` 参数）
- settings.json 丢失问题（手动替换技能目录时遗漏，已恢复并纳入发版检查单）

## [1.0.0] - 2026-10-07

### Added
- 初始发布：Team 型专家团（主理人**齐运筹 Qi Yunchou**/首席产品官 + 6 团员；该花名于 2.0.2 更名为 Elon Mask——本条保留史实，不作追溯改写）
  - requirement-analyst 柯明澈（需求分析）、product-designer 颜如玉（产品设计）、product-strategist 路向明（产品策略）、review-challenger 聂知微（评审攻防）、growth-validator 季小步（增长验证）、user-researcher 闻众声（用户研究）
- 6 个自包含技能：prd-workflow v5.1.0（含 5 子技能）、competitive-product-research v1.4.8、requirement-review-simulator v1.2.8、idea-to-product v0.1.1、humanizer-zh、lieflat-less-ai-tone
- SOP 6 Phase（需求澄清 → 拆解+PRD → 设计原型 → 评审攻防 → 验证度量 → 最终汇编）+ 4 个预设 Workflow
- 8 张统一风格头像（512×512）
- 行业分类 01-ProductDesign，注册于 my-experts marketplace
