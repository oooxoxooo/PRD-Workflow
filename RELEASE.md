# 版本管理与发布流程

> 本仓库是MASK产品天团（mask-team）的源码仓库。专家包目录本身即仓库根，安装方式为整目录放入 `~/.workbuddy/plugins/marketplaces/my-experts/plugins/`。

## 版本策略（语义化版本）

| 位 | 含义 | 本仓库示例 |
|---|------|-----------|
| MAJOR | 成员增删 / SOP 结构变化 / 技能栈层级调整 | 1.0.0 → 2.0.0（如新增团员、Workflow 重构） |
| MINOR | 新增技能 / 新增能力 / 兼容性改动 | 1.0.0 → 1.1.0（如新增设计技能、主备切换机制） |
| PATCH | 修复 / 文案 / 头像 / 配置微调 | 1.1.0 → 1.1.1 |

**版本号位置**：`.codebuddy-plugin/plugin.json` 的 `version` 字段（唯一事实来源）。发版时同步更新。

## 提交规范

```
<type>(<scope>): <subject>

# type: feat | fix | docs | chore | refactor | revert
# scope: agent | skill | avatar | config | release（可选）
```

示例：
- `feat(skill): mermaid 渲染主备自动切换（image_renderer v2.0 + 熔断器）`
- `fix(skill): mermaid_render.py 自动 puppeteer 配置修复 ConnectionClosed`
- `docs: 新增 MERMAID-FAILOVER 机制文档`
- `release: v1.1.0`

## 发布流程

```bash
# 1. 校验
python3 "$EXPERT_MANAGER/scripts/validate_expert.py" .

# 2. 更新版本号（plugin.json version 字段）并写 CHANGELOG

# 3. 注册为专家（版本号递增后执行）
python3 "$EXPERT_MANAGER/scripts/register_expert.py" .

# 4. 同步运行缓存并核验（五步闭环的第 4-5 步）
rsync -a --exclude='.DS_Store' --exclude='.codebuddy-plugin' --exclude='.in_use' \
  ./ ~/.workbuddy/plugins/cache/my-experts/mask-team/X.Y.Z/
cp .codebuddy-plugin/plugin.json ~/.workbuddy/plugins/cache/my-experts/mask-team/X.Y.Z/.codebuddy-plugin/plugin.json
diff -rq . ~/.workbuddy/plugins/cache/my-experts/mask-team/X.Y.Z/ \
  -x '.DS_Store' -x '.in_use' -x '.codebuddy-plugin' -x '.pending-preview-session'

# 5. 提交与打 tag（仅当已初始化 git 仓库时；marketplace 安装副本不含 .git，此项可选）
git add -A && git commit -m "feat(scope): xxx" && git tag vX.Y.Z && git push origin main --tags

# 6. 打包分发（zip）
zip -r mask-team-vX.Y.Z.zip . -x "*.git*" ".DS_Store"
```

## 维护检查单（每次发版前）

- [ ] `validate_expert.py` 校验通过（零 error）
- [ ] `settings.json` 存在且 `agent` 字段 = `agentName`（历史上曾被外部进程反复清理丢失——**实测执行 `register_expert.py` 之后即会触发剥离**；因此顺序必须是「注册 → 复检 settings.json → 再同步缓存/打包」，缺失时重建 `{"agent": "<agentName>"}` 或从缓存快照回填）
- [ ] 版本号已更新，tag 已打
- [ ] 变更已写入 CHANGELOG.md
- [ ] 头像完整（8 张，≤500KB/张）
- [ ] 技能目录自包含：**必须用 `rg` 或 `grep -E`（本机 `grep` 为 toybox 实现，不支持 BRE 交替 `\|`，`grep "a\|b"` 恒返回 0 行，会造成假阴性）**
  ```bash
  rg -c -i "openclaw|sessions_spawn" skills --glob '!**/legacy/**'   # 期望 0
  rg -c "CLAUDE_PLUGIN_ROOT|\.claude" skills --glob '!**/legacy/**' # 期望 0
  rg -c "window\.codex|window\.openai" skills                      # 期望 0
  rg -n "workflows/" skills --glob '!**/legacy/**' | rg -v "legacy/workflows"  # 期望 0
  rg -c -i "clawaether|clawhub|chris1wang3|hammerroom|whyy9527" skills --glob '!**/legacy/**'  # 期望 0
  ```
  允许保留：上游作者署名（如 `gotomanutd`）出现在 SKILL.md 的「上游来源/溯源」行、`legacy/` 内任意内容、契约 JSON 的第三方 npm 包名。
  **覆盖率自证（防止检查器恒真）**：任选上述一条命令，对 `skills/prd-workflow/legacy/` 跑同款模式，命中数**必须 >0**（当前基线：OpenClaw 残留 79 行）——若正样本为 0，说明命令失效，本次验收结论无效。
- [ ] 源 ↔ 运行缓存一致（五步闭环第 5 步 `diff -rq` 无差异，排除 `.DS_Store` / `.codebuddy-plugin` / `.in_use`）

## 日常维护速查

```bash
# marketplace 源目录即唯一事实来源（安装副本不含 .git，git 命令在安装态不可用）
SRC=~/.workbuddy/plugins/marketplaces/my-experts/plugins/mask-team

# 文件被外部进程误删：从备份或运行缓存中同名文件恢复
cp -R /tmp/mask-team-backup-<版本>/<相对路径> "$SRC/<相对路径>"

# 查看发布历史与变更
cat "$SRC/CHANGELOG.md"

# 回退到历史版本：cache 内各版本快照仍保留，可直接取用（勿删源目录）
ls ~/.workbuddy/plugins/cache/my-experts/mask-team/
```

## 历史版本

见 [CHANGELOG.md](CHANGELOG.md)
