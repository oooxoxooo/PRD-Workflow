---
name: user-research
version: 0.4.0
description: 用户研究技能：用户画像、用户旅程图、VoC 反馈洞察、场景与频率分析、合成用户 panel。当需要回答"目标用户是谁""画用户旅程""分析这批用户反馈""验证访谈提纲"时使用。产出落盘 research/user-[slug].md，经主理人中转。
---

# user-research：用户研究技能

> 本技能是 user-researcher（闻众声）的绑定技能。本文档只做路由与硬约束，方法论全文在 `references/` 按需加载——**按任务类型只读对应的一份 playbook，不要全量读入**。

## 能力路由

| 任务类型 | 读取文件 | 产物 |
|---|---|---|
| 用户画像构建 | `references/persona-playbook.md` | `research/user-[slug].md`（画像节） |
| VoC 反馈洞察 | `references/voc-playbook.md`（模式 2 采集时配套读 `references/source-guides-zh.md`） | `research/user-[slug].md`（VoC 报告节） |
| 用户旅程图 | `references/journey-map-playbook.md` | `research/user-[slug].md`（旅程节） |
| 访谈提纲素材 | `references/interview-guide.md` | 维度素材，**不独立产出完整提纲** |
| 合成用户 panel | `references/synthetic-panel.md` | `research/panel-[slug].json` |
| 场景与频率分析 | 直接按本文件 §场景分析 执行，无需 playbook | `research/user-[slug].md`（场景节） |

`[slug]` 由主理人在任务书中指定，禁止自创目录结构。

## 场景分析（内置小能力，无 playbook）

回答"谁在什么时候/什么情境使用"：产出使用场景清单（触发条件 / 情境 / 替代方案）+ 使用频率分级（高频日常 / 中频周期 / 低频偶发），每个场景标注来源与置信度。字段少、无模板文件，直接写入产物对应小节。

## 硬约束（一票否决项，任何 playbook 不得豁免）

1. **禁止幻觉 URL**：禁止输出本会话未实际访问过的 URL；公开材料必须注明来源；信息不足处标注"假设待验证"。
2. **数据量门槛**：同一细分人群少于 5 个独立数据点时，禁止产出画像或结论，只能产出研究缺口清单。
3. **置信度标注**：所有洞察与画像字段必须标注 High / Medium / Low（口径见 voc-playbook §置信度）；**合成用户 panel 来源永久封顶 Low**，且必须与真实材料分节，禁止混排。
4. **原声纪律**：用户原声引用逐字保留，不润色、不改写；区分"用户说的"与"用户做的"，矛盾时同时呈现。
5. **隐私红线**：个人身份信息（姓名/手机号/账号/邮箱/证件号）在输出中脱敏；处理批量反馈材料时必须先过 `scripts/voc_pipeline.py` 的脱敏管道（占位符替换不可逆），禁止绕过脚本直接处理原始文件。
6. **决策边界**：只提供用户事实与洞察，不替产品团队做方案决策。

## 工具

| 工具 | 用途 | 状态 |
|---|---|---|
| `scripts/voc_pipeline.py` | 批量反馈材料预处理：清洗 → 脱敏 → 主题词频聚类草稿 → 候选原声提取（`--help` 查看用法） | ✅ 可用 |
| `assets/sentiment-lexicon-zh.txt` | 中文情感词表（脚本数据，项目根 `research/lexicon-zh.txt` 可覆盖） | ✅ 可用 |
| `examples/feedback-sample.csv` + `examples/themes-sample.txt` | 冒烟样例（含脱敏/去重/过短过滤测试用例） | ✅ 可用 |
| `scripts/panel_schema.json` | 合成 panel 单 persona 访谈结果的 JSON Schema（draft-07，`synthetic` 锁 `const: true` 防伪造真实证据） | ✅ 可用（实测 3 人 panel 通过） |

## 协作契约（与主理人约定一致）

- 长产出（画像/旅程图/VoC 报告）先落盘 `research/user-[slug].md`，panel 数据落盘 `research/panel-[slug].json`。
- 回传主理人固定四字段：

```
产物路径：<相对项目根的路径>
关键结论：≤5 条
未决问题：<阻塞项 / 待验证假设>
建议下一阶段输入：<需要什么、以什么形式>
```

- 衔接：画像与场景假设供 requirement-analyst 访谈设计取材；现状锚点供 product-strategist 对标；待验证假设清单供 growth-validator 收敛 MVP。
- 产出经 SendMessage 回传 mask-team-lead，不直接输出给用户。

## 版本

v0.4.0（M0：SKILL.md + voc-playbook + persona-playbook；M1：voc_pipeline.py + 情感词表 + 冒烟样例；M2：journey-map / interview-guide / synthetic-panel + panel_schema.json，3 人隔离 panel 实测通过；M3：自动化验收全绿；M4：source-guides-zh 中文信源操作手册 + voc-playbook 并入信源权重表与时效窗口）
