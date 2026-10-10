# Legacy 归档说明

> 归档时间：2026-10-10（mask-team v2.1.0 宿主原生化改造，方案 B）

## 这里是什么

- `workflows/`：上游 prd-workflow v5.1.0 的完整 JS 工作流（30 个文件：main.js 编排、ai_entry.js OpenClaw 入口、quality_gates.js 门禁、version_manager.js 版本管理、13 个 modules 等）
- `upstream-docs/`：上游发布物与安装文档（INSTALL.md、SKILL_USAGE.md、RELEASE 系列 ×4、clawhub.json、install.json、_meta.json、skill-card.md）

## 为什么归档

这些代码依赖 OpenClaw 宿主环境，在 WorkBuddy 中不可运行：

1. `sessions_spawn` 是 OpenClaw 注入的全局 API（非 Node 模块，无 require 声明）——`ai_entry.js`、`prototype_module.js`、`review_module.js` 直接调用即 ReferenceError；
2. `require('openclaw')` 为第三方宿主模块，本包无 package.json / node_modules；
3. 技能寻径搜索 `~/.openclaw/skills`、`/usr/local/lib/openclaw/skills` 等路径（utils.js）；
4. Wiki 增强硬编码 `~/.openclaw/workspace/wiki-ai`（wiki_search_module.js）；
5. 输出目录默认落 `__dirname/../../..`（插件缓存树内，版本升级即丢）——data_bus.js。

WorkBuddy 宿主不向子进程暴露 LLM API，上述依赖无法通过适配层绕过。改造决策：执行模型切换为"LLM 读 SKILL.md 执行 + Bash 调 Python 工具"，JS 中有价值的方法论（门禁阈值、版本约定、模式路由、interview schema）已全量萃取至新 SKILL.md。

## 可回滚性

- 本目录为纯归档，删除不影响新 SKILL.md 的任何功能；
- 若未来 WorkBuddy 提供子进程 LLM API（等价 sessions_spawn），可基于本目录恢复 JS 管线（对应 brainstorming 会话中的方案 A）；
- 2.0.3 版本（归档前的完整 JS 管线状态）曾留存于运行缓存 `cache/my-experts/mask-team/2.0.3/`；该快照已于 2026-10-10 随宿主 orphaned 缓存回收清除。归档前的**实质性内容（30 个 JS + 9 份上游文档）完整保留在本目录内**，因此回滚能力不受影响——需要恢复旧执行模型时，从本目录取用即可。

**禁止运行本目录下任何 JS。**
