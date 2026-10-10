# Mermaid 渲染主备切换机制（v2.0）

> 实现位置：上游渲染咽喉点已随 2.1.0 归档至 `legacy/workflows/image_renderer.js`（**不可运行**）。本环境的渲染主备切换由 `mermaid-flow/scripts/mermaid_render.py`（本地通道，自带 Chrome 检测）与 `mermaid-skill/scripts/mermaid_live_link.py`（零依赖备选）承担；下文的通道顺序、熔断语义与降级日志约定对这两个入口同样适用。

## 方案分层

```
主方案 mermaid-skill（skills/mermaid-skill/）
├── 通道 A：mmdc 本地渲染（Option 1，带 puppeteer-config）
└── 通道 B：Kroki API（Option 2，零本地依赖，SKILL.md 官方降级路径）

备方案 mermaid-flow（skills/mermaid-flow/）
└── 通道 C：mermaid_render.py 独立子进程（自带 Chrome 检测 + 环境注入 + 自动 puppeteer 配置）
```

## 瀑布逻辑

```
renderMermaid(code, out)
  │
  ├─ 熔断器关闭？
  │    ├─ 是 → 试 A（mmdc）→ 成功即返回（重置失败计数，若处于 half-open 则记录 primary-recovered）
  │    │        └─ A 失败 → 试 B（Kroki）→ 成功即返回
  │    └─ 否（熔断中）→ 跳过主方案
  │
  ├─ 主方案整体失败 → 失败计数 +1
  │    └─ 连续失败 ≥ 2 → 开闸熔断 10 分钟（circuit-opened 事件）
  │
  ├─ 试 C（mermaid_render.py 子进程）
  │    ├─ 成功 → 返回 success + fallback 元数据（fallback-used 事件）
  │    └─ 失败 → all-channels-failed 事件，返回聚合错误（主/备失败原因都带出）
  │
  └─ 熔断冷却期满 → 下次调用 half-open：先试主方案
       ├─ 成功 → 切回主方案（primary-recovered 事件）
       └─ 失败 → 重新熔断
```

## 错误检测覆盖

| 失败类型 | 捕获点 |
|---------|--------|
| 命令不存在 / execSync 抛错 | tryChannel 的 try/catch |
| 超时 | execSync `timeout`（默认 30s，Kroki 同）|
| 输出无效（不存在 / ≤100B） | 成功路径的产物校验 |
| HTTP 非 200（Kroki） | curl `--fail` + 响应体带出 |
| 语法错误 | A/B/C 全链路失败后聚合报错（附 Kroki 400 响应详情）|

## 日志

JSONL 追加写入 `<output>/logs/render-fallback.jsonl`，事件类型：

- `fallback-used` — 本次由备方案承接（含 circuitOpen 状态、失败原因、全通道耗时）
- `circuit-opened` — 熔断开启（含连续失败次数、冷却时长）
- `primary-recovered` — 主方案恢复切回（含 halfOpen 标记）
- `all-channels-failed` — 全部失败（含完整 attempts 数组：channel/ok/durationMs/error）

## 配置（构造参数 `options.failover` 可覆盖）

```js
{
  FAILURE_THRESHOLD: 2,          // 连续失败阈值
  COOLDOWN_MS: 10 * 60 * 1000,  // 熔断冷却 10 分钟
  TIMEOUT_MS: 30000,             // 本地通道超时
  KROKI_TIMEOUT_MS: 30000,       // Kroki 超时
  KROKI_URL: 'https://kroki.io/mermaid/png'
}
```

## Chrome 检测优先级（A/C 共用策略）

1. `PUPPETEER_EXECUTABLE_PATH` 环境变量
2. puppeteer 缓存 `chrome-headless-shell`（与 GUI Chrome 完全隔离，官方推荐）
3. 系统 Chrome / Chromium / Edge

> 本机实测注记：GUI Chrome 运行中时 mmdc 可能间歇性 `ConnectionClosedError`（CdpPage.close 阶段）。此时通道 B（Kroki）自动接管——这正是三级瀑布的实战价值。

## 已验证场景（2026-10-07）

| 场景 | 结果 |
|------|------|
| 主路径正常（A 直出） | ✅ PNG 产出 |
| 非法语法 | ✅ 全链路失败 + 聚合错误（357 字符详情） |
| 主方案双通道失败 ×2 → 熔断 | ✅ 第二次直接走 C，circuitOpen=true |
| 冷却期满 half-open → 主恢复 | ✅ 切回主方案，计数清零 |
| E2E 真实链路（A 因 Chrome 崩溃失败） | ✅ B Kroki 真实接管出图，上层无感知 |
