#!/usr/bin/env bash
# allan-team 发版前自动检查（与 RELEASE.md 维护检查单配套）
# 用法：在包根目录运行 bash scripts/preflight.sh
set -euo pipefail

fail() { echo "❌ preflight failed: $*" >&2; exit 1; }

cd "$(dirname "$0")/.."   # 始终在包根执行
echo "== preflight: $(pwd) =="

# a. .DS_Store：先删后查，查后必须零输出
find . -name ".DS_Store" -not -path "./.git/*" -delete
leftovers="$(find . -name ".DS_Store" -not -path "./.git/*")"
[ -z "$leftovers" ] || fail ".DS_Store 删除后仍有残留: $leftovers"
echo "✅ .DS_Store 已清零"

# b. 目录权限：找出权限为 700 的目录（排除 .git）并修正为 755
fixed=0
while IFS= read -r d; do
  chmod 755 "$d"
  echo "🔧 chmod 755: $d"
  fixed=$((fixed + 1))
done < <(find . -type d -perm 700 -not -path "./.git*" -not -path "./.git/*")
echo "✅ 目录权限检查完成（修正 ${fixed} 个 700 目录）"

# c. settings.json 存在且含 "agent": "allan-team-lead"（本包已知复发问题：被外部进程清理）
if [ ! -f settings.json ]; then
  echo '{"agent": "allan-team-lead"}' > settings.json
  echo "⚠️  settings.json 缺失，已自动重建为 {\"agent\": \"allan-team-lead\"}"
elif ! grep -q '"agent"[[:space:]]*:[[:space:]]*"allan-team-lead"' settings.json; then
  echo '{"agent": "allan-team-lead"}' > settings.json
  echo "⚠️  settings.json 内容不含 \"agent\": \"allan-team-lead\"，已自动重建"
else
  echo "✅ settings.json 正常"
fi

# d. plugin.json 合法 JSON，且 skills 数组每个路径下存在 SKILL.md
python3 - <<'PY'
import json, os, sys

plugin_path = ".codebuddy-plugin/plugin.json"
try:
    with open(plugin_path, encoding="utf-8") as f:
        plugin = json.load(f)
except FileNotFoundError:
    print(f"❌ preflight failed: 缺少 {plugin_path}", file=sys.stderr); sys.exit(1)
except json.JSONDecodeError as e:
    print(f"❌ preflight failed: {plugin_path} 不是合法 JSON: {e}", file=sys.stderr); sys.exit(1)

skills = plugin.get("skills")
if not isinstance(skills, list) or not skills:
    print("❌ preflight failed: plugin.json 缺少非空 skills 数组", file=sys.stderr); sys.exit(1)

missing = [p for p in skills if not os.path.isfile(os.path.join(p, "SKILL.md"))]
if missing:
    print(f"❌ preflight failed: 以下技能路径缺少 SKILL.md: {missing}", file=sys.stderr); sys.exit(1)

print(f"✅ plugin.json 合法，{len(skills)} 个技能 SKILL.md 齐备")
PY

echo "✅ preflight passed"
