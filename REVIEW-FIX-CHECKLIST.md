# allan-team v2.4.x 评审修复清单

> 来源：2026-10-11 架构评审。每条含证据位置与修复动作，完成后打勾。
> 严重度：P0 = 发布阻断｜P1 = 高｜P2 = 中｜P3 = 低
> **进度：第一批（#1、#2、#5、#6、#7、#17）已于 2026-10-11 完成修复并验证，版本升至 2.4.1。**

---

## P0 — 发布阻断

### 1. 裁决 `skills/user-research/`（完工未接线）✅ 已修复（2.4.1）
- **现状**：目录完整（SKILL.md + 6 份 playbook + `voc_pipeline.py` 实测可用），但 git untracked、plugin.json 未注册、`agents/user-researcher.md` 是 7 个 agent 中唯一缺 `skills` 字段的、README 第 21 行仍写"内置方法论"。打包分发即丢失。
- **证据**：`skills/user-research/`；`.codebuddy-plugin/plugin.json` L18-26；`agents/user-researcher.md` L1-11；`README.md` L21
- **修复（二选一）**：
  - [x] **保留**（已选此项）：`user-researcher.md` frontmatter 加 `skills: [user-research]`；plugin.json `skills` 数组加 `"./skills/user-research"`；README 团队表改为 `user-research`，技能清单表补 user-research 行（v0.4.0），"6 个技能"改"7 个"；`git add skills/user-research/`（12 个文件已暂存，未 commit）；CHANGELOG 加 [2.4.1] 条目；plugin.json version → 2.4.1
  - [ ] ~~暂缓~~（未选）

---

## P1 — 高

### 2. 统一上下文中转规则（原文 vs 摘要矛盾）✅ 已修复
- **证据**：`agents/allan-team-lead.md:142, 213, 219`
- **修复**：
  - [x] WF-1 依赖（L142）与协作规则 2（L213）的"完整产出原文"已改为"回传摘要（四字段）+ 产物路径，登记 manifest，下一阶段按需自行读取原文"
  - [x] 规则 8 已补例外："主理人自身需直接消费的产出（访谈提纲、评审裁决清单）回传全文"
  - 验证：全文 grep 无残留冲突表述；规则编号与四字段模板未动

### 3. 工具宿主语义混用
- **现状**：TeamCreate / Agent 工具 `subagent_type` / SendMessage 三套术语分属不同宿主，无"哪个宿主哪套可用"声明；缺 TeamCreate 的宿主会静默退化为单上下文模拟多角色，恰为严禁行为第 1 条禁止。
- **证据**：`agents/allan-team-lead.md:82, 88, 216`
- **修复**：
  - [ ] 铁律前加宿主能力自检段："若当前宿主无 TeamCreate/SendMessage，向用户显式声明降级为顺序直调模式，不模拟多角色发言"

### 4. 主理人轮次预算保护
- **现状**：maxTurns=200，16-33 题逐题访谈 + 6 Phase 调度 + 复评回环，完整 WF-1 触顶风险真实，触顶处置未定义（成员侧却有 30 轮保护）。
- **证据**：`agents/allan-team-lead.md:50`；对比 `agents/requirement-analyst.md:35`
- **修复**：
  - [ ] 主理人文件加条款："接近轮次上限时在 Phase 边界落盘全部中间产物，建议用户新会话续跑，manifest 台账保证可恢复"

### 5. `mermaid_render.py` 批量模式必崩 ✅ 已修复（实测通过）
- **证据**：`prd-workflow/skills/mermaid-flow/scripts/mermaid_render.py:236`
- **修复**：
  - [x] `batch_render()` 增加 `puppeteer_config=None` 参数，main() batch 分支传值；实测 `--batch` 对 2 个 .mmd 真实渲染成功（mmdc 11.16.0），NameError 消除
  - [x] 新增 `test_batch_smoke.py`（3 个用例：无 NameError、参数透传、目录缺失返回 (0,0)），实测 `Ran 3 tests ... OK`

### 6. 主 SKILL.md §8 工具矩阵 CLI 契约漂移 ✅ 已修复
- **证据**：`prd-workflow/SKILL.md:145-147`；`mermaid_render.py:263-273`；`review_cli.py:21`；`content_check_cli.py:28`
- **修复**：
  - [x] 矩阵命令已对照实际 argparse 修正（`review_cli --prd`、`mermaid_render -i/-o`、`content_check_cli --prd`）
  - [x] 依赖列已改正：mermaid_render 标注需 `mmdc`（npm 全局）+ Chrome；content_check_cli 标注需 `requests`
  - [x] `ai_checker.py` 顶层 `import requests` 已改惰性 import（`_import_requests()`），无 requests 时给出明确中文提示并降级，不再导入即崩；已实测 `--help` 与无 requests 模拟环境均正常

### 7. 评审评分口径两处自相矛盾 ✅ 已修复
- **证据**：`skills/requirement-review-simulator/SKILL.md:119, 45, 64`；`references/scoring-engine-deterministic.md:350-357, 99, 223`
- **修复**：
  - [x] SKILL.md 完成标准已对齐引擎：S(85-100, Go) / A(75-84.9, Conditional Go·少量条件) / B(65-74.9, Conditional Go·明确整改清单) / C(0-64.9, No Go·重写后再评)；Pass/Fail 术语全文清零
  - [x] SKILL.md 新增尺度区分注记："子项保守分 1（0/1/2 尺度）≠ 维度中性保守分 6（0-10 尺度），具体判定以评分引擎为准"
  - [x] 引擎文档内部矛盾（L99 维度级 6 分 vs L225 子项判 0，同场景会同时得出 6 和 0）已按适用场景区分并加交叉指引：整维度缺失→维度级 6 分兜底；个别子项缺失→子项判 0
  - ⚠️ 残留口径差异（待政策决策）：SKILL 的"缺失项保守分 1"（偏宽）与引擎"自有版缺失子项判 0"（偏严）数值上仍不等同，当前已将裁决权归引擎。彻底统一需二选一：SKILL 改为"缺失子项按引擎判定"，或引擎为草稿场景增设"判 1"宽限条款 —— 属评分政策决策，未擅自更改

### 8. `humanizer-zh` 与 `lieflat-less-ai-tone` 触发重叠 + 行为互斥
- **现状**：两者都响应"去 AI 味"；humanizer 激进（注入观点/第一人称），lieflat 保守（白名单逐字保留、禁增实词），同一文本结果方向相反；宿主系统技能索引还有第三个同名 humanizer-zh。
- **证据**：`skills/humanizer-zh/SKILL.md:4-5, 59-77`；`skills/lieflat-less-ai-tone/SKILL.md:3, 18-42`
- **修复**：
  - [ ] 二选一或分工（推荐：lieflat 为主，humanizer 降为 references 素材；或两边 description 首句写明"口语/社媒→humanizer、正式成稿→lieflat"）

### 9. settings.json 被 register_expert.py 剥离（已五次复发）
- **现状**：注册流程本身破坏包完整性，每次发版/重装依赖人工复检回填。
- **证据**：`README.md` L98, L119；CHANGELOG 多次记录
- **修复**：
  - [ ] 向宿主侧反馈该行为
  - [x] 短期兜底已完成：preflight.sh 已实现"settings.json 缺失或内容不符时自动重建并打印 ⚠️ 警告"

---

## P2 — 中

### 10. 成员侧缺 maxTurns 触顶自救协议
- **证据**：`agents/allan-team-lead.md:100, 102`；6 个成员文件（除 requirement-analyst 模式 B）
- **修复**：
  - [ ] 6 个成员文件统一加："预估剩余轮次不足时，先落盘已完成部分并按四字段回传，标注缺口清单"

### 11. 依赖声明与运行环境缺口
- **修复**：
  - [ ] `export_engine.py:16-20` docx/PIL 改惰性 import（md-only 路径零依赖）
  - [ ] `idea-to-product/SKILL.md` 补"环境前提"小节（Node + `npx playwright install`），或明示"只产出检查规格，执行依赖宿主浏览器自动化"
  - [ ] `test_intake_form.py` 补 macOS/Linux Chrome 候选路径，或在 SKILL.md 标注"仅 Windows 开发机"（证据：`skills/competitive-product-research/scripts/test_intake_form.py:14-21`）

### 12. MERMAID-FAILOVER 有文档无实现
- **现状**：三级降级 + 熔断器 + JSONL 日志的实现已归档进 legacy，现行代码无 Kroki 通道、无熔断器；敏感特征出网拦截只剩文档自觉。
- **证据**：`prd-workflow/skills/MERMAID-FAILOVER.md:3`；`legacy/workflows/image_renderer.js`；`prd-workflow/SKILL.md:154`
- **修复**：
  - [ ] 二选一：文档降级重命名为 RENDER-POLICY.md（纯约定）；或在 mermaid_render.py 实现最小 Kroki 备援 + 敏感特征检查函数

### 13. requirement-reviewer 双份 checker 已分叉 + DEPRECATED 文件现役
- **证据**：`prd-workflow/skills/requirement-reviewer/engines/` 平层 vs `engines/core/`（diff 确认 completeness、acceptance_criteria 已不一致）；`semantic/ai_checker.py:5` 自称 DEPRECATED 但 `content_check_cli.py:28,30` 仍 import、SKILL.md:431 仍教学
- **修复**：
  - [ ] 删平层重复 checker，保留 `core/`
  - [ ] ai_checker.py 删除或复活二选一（注：2.4.1 已先修其惰性 import，删除决策仍待定）
  - [ ] 修 SKILL.md 中不存在的 `check_environment.py` / `requirements.txt` 引用（L32, L41）

### 14. export_engine.py 功能缺陷
- **证据**：`prd-workflow/skills/prd-export/engines/export_engine.py:138-173`（TOC 死参数，add_toc 追加到文末且未被调用）；`:53, 116-133`（页脚 `{page}` 字面输出）
- **修复**：
  - [ ] 接通或删除 `include_toc` / `add_toc`
  - [ ] 页脚换真实 PAGE 域或改静态文案

### 15. htmlPrototype 健壮性
- **证据**：`prd-workflow/skills/htmlPrototype/main.py:468`（`os.system(f"open {html_path}")` 无引号、macOS 专属、注入面）；`:340`（默认输出落 `~/Desktop` 脱离版本管理）；SKILL.md:136-154 文件结构图列了不存在的文件
- **修复**：
  - [ ] 改 `subprocess.run(["open", str(html_path)])` + 平台判断
  - [ ] 默认输出改到项目工作目录（接入 `.versions/`）
  - [ ] 修 SKILL.md 文件结构图

### 16. 版本号体系混乱
- **证据**：prd-workflow 三处三值（`SKILL.md:6` v2.4.0 / `prd-workflow/README.md:1` v2.1.0 / `allan-team/README.md:40` v2.2.0）；技能版本声明位置不一（frontmatter / 仅 CHANGELOG / 无）
- **修复**：
  - [ ] 版本号只留 SKILL.md §10 一处事实来源，README 改引用不抄写
  - [ ] 各技能版本统一进 frontmatter
  - [ ] README zip 示例改 `vX.Y.Z` 占位；技能清单表注明"上游基线版本"
  - 注：2.4.1 已将包 README 安装示例统一为占位符口径的进展见 git diff，剩余 prd-workflow 内部版本对齐待做

### 17. 分发卫生 ✅ 已修复（含新增 preflight）
- **修复**：
  - [x] 清除 `.DS_Store`（共 5 个，含修复期间系统复发的 1 个，复跑零残留）
  - [x] 权限统一：`prd-workflow`、`skills/competitive-product-research`、`skills/idea-to-product`、`skills/requirement-review-simulator` 四个 700 目录已 chmod 755
  - [x] 打包口径统一：RELEASE.md 第 6 步裸 `zip -r` 已替换为 `package_expert.py`（与 README 同一口径）
  - [x] 新建 `scripts/preflight.sh`（已 chmod +x）：.DS_Store 清零、700 目录自动修正、settings.json 缺失自动重建、plugin.json 合法性 + 8 个技能 SKILL.md 齐备校验，实测 `✅ preflight passed`；RELEASE.md 检查单与 README 安装后自检均已接入
  - [ ] 遗留验证项：确认 `package_expert.py` 确实排除 `.git`（若不排除需显式加 `-x`）

---

## P3 — 低

- [ ] **18. Phase 4∥5 并行成本提示**：`allan-team-lead.md:72` 补"并行期若 Phase 4 判 No Go，Phase 5 产物判 stale 重跑（限 1 次）；验证范围敏感的对象建议先串行评审"
- [ ] **19. 职责重叠闭环**：user-researcher 核心能力 5 补"仅提供维度素材，完整提纲归 requirement-analyst"（`agents/user-researcher.md:23`）；lead 明确"RICE 排序为建议输入，PRD 功能优先级以 requirement-analyst + 用户确认为准"（`agents/product-strategist.md:23`）
- [ ] **20. 正身声明降级**：`allan-team-lead.md:18` / README L5 改"建议卸载历史版本"的提示性表述（宿主解析层无机制保障）
- [ ] **21. 更换 "Allen" 花名**：消除名人影射的合规风险（plugin.json `members[0]` + avatars 引用同步改）
- [ ] **22. 嵌套技能发现策略**：宿主不递归 → 强化主 SKILL.md §9 触发表；宿主递归 → 统一 taste-skill 目录名与 frontmatter name、消除 mermaid-flow / mermaid-skill 描述重叠
- [x] **23. legacy/ 瘦身**（✅ 2026-10-13 v2.4.2：legacy/ 归档已整体从包中移除，活性文档死链同步修正）
- [ ] **24. humanizer-zh 坏示例**：修 L318/L321（改写前后逐字节相同）与 L289-293；485 行拆为"索引 + references 示例库"
- [ ] **25. 上下文分层推广**：humanizer-zh / lieflat 改造为 user-research 式"按需读 playbook"结构（当前两者同时触发仅 SKILL.md 即 940 行）
- [ ] **26. evolution_cli.py 写入子命令**：加 `bump-hit` / `set-level` / `add-pref`，减少 LLM 手工编辑 Markdown 导致的字段静默漂移
- [ ] **27. plugin.json 双结构合并**（若宿主 schema 允许）：teamInfo 与 members 二留一，消除双写漂移面
- [ ] **28.（修复中新发现）权限归一**：`prd-workflow/skills/` 下 14 个目录为 775（mermaid-skill、taste-skill、ui-ux-pro-max、web-design-guidelines 及子目录），建议统一为 755 并纳入 preflight
- [ ] **29.（修复中新发现）mmdc 冷启动超时**：`check_mermaid_cli()` 的 `mmdc --version` 10s 超时在冷启动时可能误杀（预热后实测 6.2s），建议加大超时或加重试

---

## 执行记录

- **2026-10-11 第一批（#1、#2、#5、#6、#7、#17）**：全部完成，版本升至 2.4.1。验证：preflight.sh 全绿（8 个技能 SKILL.md 齐备）；test_batch_smoke.py 3 用例通过；`--batch` 真实渲染成功；plugin.json 合法。改动文件：plugin.json / CHANGELOG / README / RELEASE / allan-team-lead.md / user-researcher.md / prd-workflow SKILL.md / mermaid_render.py / ai_checker.py / review-simulator SKILL.md + 引擎文档 / 新增 preflight.sh + test_batch_smoke.py / user-research 12 文件已 git add（未 commit）。

## 剩余批次建议

1. **第二批（本周）**：#3 → #4 → #8 → #9（宿主侧反馈）→ #10-#16
2. **第三批（择机）**：#18-#29
