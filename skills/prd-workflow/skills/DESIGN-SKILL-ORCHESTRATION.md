# 设计技能编排参考（Design Skill Orchestration）

> 本文档是 `product-designer`（颜如玉）四层设计技能栈的路由与组合参考。上游 SKILL.md 保持原样不改动，编排规则集中在本文档与 agent 定义中，便于技能独立升级。

## 四层定位

| 层 | 技能 | 定位 | 核心产出 |
|---|------|------|---------|
| L1 审美方向 | `frontend-design/` | 设计工作室方法论：为每个产品建立有辨识度的视觉主张（token 系统、反模板默认值、两遍法：计划→review→构建→自评） | 4-6 命名色值 + 字体角色 + 布局概念 + 设计原则 |
| L2 产品 UI 智能库 | `ui-ux-pro-max/` | 产品界面实施智能：22 技术栈组件规范、UX Do/Don't 清单、`generate_design_system` 持久化引擎 | design-system/MASTER.md + tokens.json + 功能页实现 |
| L3 营销页品味 | `taste-skill/` | 反模板（anti-slop）方法论：Brief 推断→三旋钮（VARIANCE/MOTION/DENSITY）→AI Tells 禁令→重设计协议（§11） | Design Read 一句话 + 营销页实施纪律 |
| L4 规范审计 | `web-design-guidelines/` | Vercel Web Interface Guidelines 合规审查：可访问性/交互/性能/响应式 | `file:line` 问题清单 |

## 适用范围（冲突隔离的依据）

- **L2 ↔ L3 按页面类型分流**：taste-skill §13 明确 OUT OF SCOPE = dashboard/数据表/多步产品 UI——这些正是 ui-ux-pro-max 的主场；反之营销页/落地页/作品集走 L3
- **L1 是方向层不碰组件**：只定 token 与气质，不规定组件实现；组件模式回 L2 查
- **L4 是横向门禁**：只审不建，产出问题清单后修复路由回对应层

## 场景路由表

| 需求场景 | 路由 | 说明 |
|---------|------|------|
| 新产品设计原型（PRD 主链路） | L1 → L2 → (L4) | token 基调 → 设计系统+功能页 → 可选审计 |
| 界面优化/重设计 | L3 §11 → L2 | audit-first 重设计协议 → 组件模式补充 |
| 营销页/落地页 | L1 → L3 → L4 | 视觉主张 → 三旋钮实施 → 强制审计 |
| 设计规范审查 | L4 单独 | 问题清单路由回对应层 |
| 交互改进（表单/反馈/状态） | L2 → L4 | ux-guidelines 模式 → 可访问性验证 |
| 视觉风格升级（品牌感） | L1 → L3 §4 | 视觉识别 → 色彩/排版/材质校准 |

## 三条固定流水线

### 组合 A：全新产品
```
frontend-design（Design Read + token 系统，review 后再写码）
  → ui-ux-pro-max（generate_design_system 持久化 + 功能页实现 + Chart.js 原型）
  → web-design-guidelines（交付前审计，可选但推荐）
```

### 组合 B：营销页冲刺
```
frontend-design（视觉主张，防模板默认）
  → taste-skill（三旋钮 + AI Tells 禁令 + Hero 策略）
  → web-design-guidelines（强制审计）
```

### 组合 C：既有产品重设计
```
taste-skill §11（先审计、保留品牌资产、决策树：定向演进 vs 全面重设计）
  → ui-ux-pro-max（组件模式与设计系统更新）
  → web-design-guidelines（回归审计）
```

## 冲突处理规则

1. **L4 可访问性发现 > 一切**：不可妥协，优先修复
2. **L1 与 L3 审美冲突**：取更严格者（两份"AI 痕迹"清单精神一致，取并集）
3. **L3 三旋钮与 L2 设计系统冲突**：产品功能页以 L2 tokens 为准；营销页以 L3 旋钮为准（两者页面类型不重叠，实际很少冲突）
4. **不冲突的场景永远不叠加**：营销页不加载 L2 产品 UI 规则；产品页不套 L3 营销旋钮
