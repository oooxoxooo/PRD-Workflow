# 规避规则手册（PLAYBOOK）

> 由 self-evolution 技能维护。从 ISSUES.md 蒸馏出的可执行规避规则，任务启动时经 `evolution_cli.py inject` 注入团队上下文。
> 只有经用户批准晋升的规则才进入本文件；90 天未命中降级（demoted），120 天归档（archived），仅 active 参与注入。

<!-- 规则条目格式（追加在文件末尾）：

## [RUL-YYYYMMDD-XXX] 短标题（错误模式一句话）
- Phase: interview | decomposition | prd | design | review | mvp | assembly | any
- Scope: 适用对象（如 requirement-analyst / review 前自检 / 全队）
- Rule: 一句话可执行规则（做什么/不做什么，可检验）
- Source: ISS-YYYYMMDD-XXX（晋升来源）
- Created: YYYY-MM-DD
- Last-Hit: YYYY-MM-DD（初始同 Created；命中时刷新，独立成行 CLI 才能解析）
- Hits: 0（累计命中拦截次数：review-challenger 规则自检每命中一次 +1，主理人负责更新）
- Level: active（active | demoted | archived）
-->
