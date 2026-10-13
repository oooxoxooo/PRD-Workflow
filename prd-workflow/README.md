# PRD Workflow（WorkBuddy 原生化版 v2.4.2）

一站式 PRD 生成技能——从模糊需求到完整 PRD 文档 + 流程图 + Word 导出。执行模型：LLM 读 [SKILL.md](SKILL.md) 作为管线逐步执行，确定性步骤（导出/评审/渲染）Bash 调用 Python 工具。

> v2.1.0 说明：原上游宿主 JS 工作流已从本包移除（2.4.2 起不再随包分发 legacy/ 归档）；质量门禁、版本管理、执行模式等方法论全量萃取至 SKILL.md。上游 v5.1.0（gotomanutd + 红曼为帆，MIT-0）。

快速入口：访谈标准 → SKILL.md §2 ｜ 质量门禁 → §4 ｜ Python 工具矩阵 → §8 ｜ 设计技能编排 → [skills/DESIGN-SKILL-ORCHESTRATION.md](skills/DESIGN-SKILL-ORCHESTRATION.md)
