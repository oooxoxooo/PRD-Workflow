---
name: self-evolution
description: >-
  Self-evolution engine for the PM expert team: logs requirement-generation issues
  (misunderstanding, ambiguity, output defects) into a traceable knowledge base,
  maintains a user profile (preferences, historical requirement traits, feedback),
  and feeds both back into interviews and PRD generation to avoid repeats and
  improve efficiency. Use when the user corrects the team, asks to「记住我的偏好」
  「记录这个问题」「复盘这次产出」, or at phase boundaries of any workflow.
---

# 自我进化（Self-Evolution）

> 让专家团越用越懂你：问题记录与规避 · 用户画像沉淀 · 效率持续优化。

**When / 何时用：**
- 用户纠正了团队的理解或产出（"不是这个意思""这里错了""我要的是……"）
- 需求访谈/PRD 生成中出现返工、歧义澄清超过 2 轮、评审存活率不达标
- 用户表达长期偏好（"我喜欢……""以后都按……来"）
- 每个任务（Workflow）结束时做轻量复盘，向 METRICS.md 追加一行指标
- 启动新任务前：加载用户画像与未解决问题，规避同类错误

**Not / 不用：**
- 替代具体业务技能（PRD 生成、评审、对标等仍由对应技能完成）
- 存储用户隐私敏感信息（见「隐私与边界」）
- 未经用户确认就改写 agent 定义文件（晋升需批准）

## 核心机制：记录 → 应用 → 晋升 三环闭环

```text
记录 Capture        应用 Apply               晋升 Promote
────────────        ──────────               ────────────
问题 → ISSUES.md    任务开始前 inject 注入：   复发 ≥3 次的规则
规则 → PLAYBOOK.md   PLAYBOOK active 规则      → PLAYBOOK.md（项目级，默认）
画像 → USER_PROFILE  + 高优未决问题            → agent 定义/技能模板（跨项目通用）
指标 → METRICS.md    + 画像偏好预填            （均需用户批准）
```

## 数据存储

运行时数据全部存放在**用户项目根目录**的 `.evolution-mask/` 下（不写入插件目录，插件升级不丢数据）：

| 文件 | 内容 | 模板 |
|------|------|------|
| `.evolution-mask/ISSUES.md` | 问题知识库：需求理解偏差 / 沟通歧义 / 产出缺陷 / 流程效率 | [assets/ISSUES.md](assets/ISSUES.md) |
| `.evolution-mask/PLAYBOOK.md` | 规避规则手册：从 ISSUES 蒸馏的可执行规则（注入用，非原文） | [assets/PLAYBOOK.md](assets/PLAYBOOK.md) |
| `.evolution-mask/USER_PROFILE.md` | 用户画像：偏好、历史需求特征、反馈记录 | [assets/USER_PROFILE.md](assets/USER_PROFILE.md) |
| `.evolution-mask/METRICS.md` | 效率指标：每次任务的轮次、返工、存活率、规则命中等 | [assets/METRICS.md](assets/METRICS.md) |

首次使用（或数据目录被清理后）一条命令自愈初始化，任何子命令也会自动补齐缺失文件：

```bash
python3 <插件目录>/skills/self-evolution/scripts/evolution_cli.py init
```

### 存放位置的约定（重要）

- **数据在项目，模板在插件**：`.evolution-mask/` 属于用户项目，可随项目 git 追踪或加入 .gitignore（用户自选）；插件目录只存模板与方法论。
- **多项目隔离**：每个项目独立一份 `.evolution-mask/`；跨项目通用的画像条目可标注 `[全局]`，由用户决定是否手动同步到其他项目。

## 一、问题记录与规避（ISSUES.md）

### 记录格式

```markdown
## [ISS-YYYYMMDD-XXX] 分类

**Logged**: ISO-8601 时间戳
**Priority**: low | medium | high | critical
**Status**: open | mitigating | resolved | promoted
**Phase**: interview | decomposition | prd | design | review | mvp | assembly

### 现象
一句话描述发生了什么偏差/缺陷

### 上下文
- 当时的输入（用户原话要点）
- 团队的产出/行为
- 用户的纠正或不良后果

### 根因
理解偏差 | 信息缺失 | 假设未验证 | 模板不适配 | 沟通歧义 | 其他

### 规避规则
下次同类场景下，团队应该怎么做（一句话、可执行、可检验）

### Metadata
- Recurrence-Count: 1
- First-Seen / Last-Seen: YYYY-MM-DD
- Related: ISS-xxx（关联条目）
- Tags: 访谈, PRD, 评审, ...
---
```

### 问题分类（四类 + 扩展）

| 分类 | 典型场景 |
|------|---------|
| 需求理解偏差 | 把"导出报表"理解成"在线看板"；漏掉合规约束 |
| 沟通歧义 | 一词多义未澄清就动手；访谈问题让用户反复解释 |
| 产出缺陷 | PRD 缺验收标准；原型缺少失败态；评审材料缺 RACI |
| 流程效率 | 访谈轮次过多；返工 2 次以上；重复问已知信息 |

### 规避规则手册（PLAYBOOK.md，蒸馏层）

ISSUES 原文供追溯，**注入一律用蒸馏规则**：复发达标并经用户批准的规避规则晋升到 `PLAYBOOK.md`（条目格式见 [assets/PLAYBOOK.md](assets/PLAYBOOK.md)），带三个维护字段：

- **Hits / Last-Hit**：review-challenger 规则自检每命中拦截一次，主理人更新 `Hits +1` 与 `Last-Hit`——衡量规则是否真在产出价值
- **Level**：`active`（参与注入）→ 90 天未命中降为 `demoted`（保留不注入）→ 120 天归档 `archived`，防止手册膨胀稀释注意力
- **共享边界**：PLAYBOOK 是蒸馏后的脱敏规则，**可**随项目 git 追踪共享团队；ISSUES 原文与 USER_PROFILE 永不共享（见隐私与边界）

### 规避机制（关键差异化）

问题知识库不是死档案，**必须被消费**，四道防线：

1. **任务启动注入（预算内）**：主理人在 TeamCreate 后、Phase 1 前执行 `evolution_cli.py inject`，得到注入包 = PLAYBOOK active 规则 Top-15（按 Hits 排序，含 Phase 与 Scope 供分发给对应成员）+ ISSUES 高优未决 ≤5 条 + 画像偏好预填，全文 ≤4000 字符（含包装，超预算自动从低价值端裁剪并标注裁剪条数）——上下文开销可控
2. **产出前自检**：进入 review 前由 review-challenger 按注入的 PLAYBOOK 规则清单逐条核对 PRD，命中即在报告中标注「规则命中 RUL-xxx」并拦截；主理人据此更新 Hits/Last-Hit，计入 METRICS
3. **同类场景匹配**：进入某 Phase 前，检索该 Phase 标签下的历史问题（如进入评审前查 `Phase: review` 的条目）
4. **复发检测**：记录新问题前先跑 `evolution_cli.py dedup` 看合并候选；命中已有条目时不新建，改为 `Recurrence-Count +1`、更新 `Last-Seen`、升优先级

## 二、用户画像沉淀（USER_PROFILE.md）

画像分四个区，**只记用户确认过或反复观察到的内容**，单次数说不进画像：

1. **偏好 Preferences**：输出格式（HTML/Markdown/PPT）、详略程度、语言、文档风格（如"不要 AI 腔"）、决策风格（数据导向/直觉导向）
2. **历史需求特征 Requirement Traits**：所在行业、常见产品形态、常用技术栈、典型约束（合规/预算/周期）、常做的需求类型
3. **反馈记录 Feedback Log**：用户对历次产出的明确表扬/批评（带日期与出处），作为偏好证据
4. **协作习惯 Collaboration**：喜欢的访谈节奏（一次问完 vs 逐题）、评审参与度、对"建议确认"的接受度

### 画像更新规则

- **写入需证据**：每条画像条目必须有来源（用户原话或 ≥2 次观察），标注 `Source` 与 `Updated` 日期
- **置信度衰减**：行为类条目（协作习惯/需求特征）`Updated` 超 30 天未再观察 → 标注 ⚠️ 待复验、暂停用于预填（`evolution_cli.py report` 自动列出候选）；用户显式偏好（Source 含「用户原话」）永不衰减
- **冲突即澄清**：新观察与已有画像冲突时，不静默覆盖——向用户确认后更新，并在 Feedback Log 留痕
- **应用点**：Phase 1 访谈前用画像**预填**已知维度（行业/技术栈/格式偏好），只问增量问题；Phase 6 汇编时按偏好选择输出格式与风格
- **可审计**：用户随时可以说"让我看看你对我的了解"，主理人输出画像全文；用户可直接要求删除任意条目

## 三、效率优化（METRICS.md）

### 每次任务记录一行指标

| 指标 | 含义 | 优化目标 |
|------|------|---------|
| 访谈轮次 | Phase 1 完成共识所需的问答轮数 | ↓（画像预填后应减少） |
| 澄清返工次数 | 因歧义/理解偏差导致的重做次数 | ↓ |
| PRD 一次通过率 | review-challenger 首轮 Go 占比 | ↑ |
| 评审存活率 | 25 子项评分均值 | ↑ |
| 阶段耗时（粗粒度） | 各 Phase 的相对耗时感受（快/正常/慢） | ↓ |
| 用户纠正条数 | 当次任务新产生的 ISS 条目数 | ↓ |
| 规则命中拦截 | review-challenger 自检命中 PLAYBOOK 规则并拦截的次数 | ↑（规则在产出价值） |

### 优化动作

- **趋势回顾**：每 5 次任务或每周（取先到者），主理人执行 `evolution_cli.py report --save` 生成进化报告（指标趋势/晋升候选/规则健康度/画像待复验），恶化的指标必须关联到 ISSUES 条目与规避规则，没有则补录
- **画像反哺访谈**：访谈轮次居高时，检查画像预填是否被使用，把高频问答沉淀为画像条目
- **模板改进建议**：同类产出缺陷复发时，建议修改对应技能的模板/清单（晋升流程）

## 晋升规则（Promote）

当一条规避规则满足以下**全部**条件，晋升为永久规则：

- `Recurrence-Count >= 3`
- 出现在至少 2 个不同任务中
- 最近 30 天内仍在发生

晋升目标（**必须先向用户展示 diff 并获得批准**，严禁静默改写），两级优先：

1. **`.evolution-mask/PLAYBOOK.md`（默认）**：本项目规避规则写入 PLAYBOOK（Source 关联原 ISS），即时生效、随项目保留，不触碰插件文件
2. **插件 agent 定义 / 技能模板**（仅限跨项目通用规则，走 git 提交、可回滚）：

| 目标文件 | 适合晋升的内容 |
|---------|--------------|
| `agents/allan-team-lead.md` | 编排层规则（如"Phase 1 前必须先加载画像"） |
| 对应成员 agent 文件 | 专业层规则（如"PRD 必须含失败态验收标准"） |
| 对应技能的 SKILL.md / 模板 | 模板缺陷类规则 |

晋升后：原 ISS 条目 `Status` 改为 `promoted`，记录晋升目标（RUL-xxx 或插件文件路径）。

## 触发器（自动记录时机）

**用户纠正**（→ ISS 条目，分类：需求理解偏差/沟通歧义）：
- "不是这个意思" "你理解错了" "我要的是……" "其实……"

**偏好表达**（→ USER_PROFILE）：
- "我喜欢……" "以后都……" "别用……" "记住……"

**产出缺陷**（→ ISS 条目）：
- 评审 No Go / Conditional Go 的致命问题
- 用户指出的遗漏、错误、格式不符

**任务完成**（→ METRICS 一行 + 按需 ISS）：
- 每次任务结束记录一行指标；过程中有返工或用户纠正随时补 ISS

## 工具（evolution_cli.py）

确定性操作交给脚本（Python 3.8+，零依赖，仅标准库），语义操作（记录条目、复验对话、晋升决策）由主理人完成：

```bash
CLI=<插件目录>/skills/self-evolution/scripts/evolution_cli.py

python3 $CLI init            # 自愈初始化：目录/文件缺失时从模板补齐（幂等；所有子命令都会自动补齐）
python3 $CLI inject          # 生成注入包：PLAYBOOK Top-15 + 高优未决 ≤5 + 偏好预填，≤4000 字符
python3 $CLI dedup           # 复发检测：按 Phase+分类 输出合并候选（只建议，不改文件）
python3 $CLI report --save   # 进化报告：指标趋势/晋升候选/规则健康度/画像待复验（--save 落盘 .evolution-mask/）
python3 $CLI status          # 一行概览：条目数/规则数/命中数/最近记录
```

- 所有命令默认作用于**当前项目根**（`--root DIR` 可指定）；即使 `.evolution-mask/` 被外部清理，一条 `inject` 即恢复骨架——数据韧性不依赖人记住流程

## 隐私与边界

1. **本地存储**：`.evolution-mask/` 只存在用户项目目录，不上传、不联网同步
2. **最小化原则**：不记录密码、密钥、个人隐私（手机号/身份证等）、未公开的商业机密细节；画像只记"服务所需的偏好与特征"
3. **用户主权**：查看、修改、删除任意条目的权利永远在用户；说"清空画像"即删除 USER_PROFILE.md 内容（保留文件头）
4. **git 自选**：默认建议把 `.evolution-mask/USER_PROFILE.md` 加入 `.gitignore`（个人画像不进团队仓库），ISSUES.md 与 METRICS.md 可追踪以共享团队知识

## 最佳实践

1. **即时记录**：被纠正的当轮就记，上下文最新鲜
2. **规避规则要可执行**：写"访谈时先确认'导出'指文件还是页面"，不写"加强理解"
3. **宁缺毋滥**：琐碎一次性问题记 low 优先级即可，不必全部晋升
4. **先查后记**：记录前先检索，复发条目合并计数——知识库的价值在密度不在数量
