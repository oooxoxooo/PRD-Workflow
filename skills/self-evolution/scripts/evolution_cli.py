#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""self-evolution 运行时数据工具（零第三方依赖，Python 3.8+）。

在用户项目根目录下维护 .evolution-mask/ 数据（ISSUES / PLAYBOOK / USER_PROFILE / METRICS），
为专家团主理人提供四类确定性操作，LLM 只负责语义部分（记录条目、执行建议）：

  init    自愈初始化：确保 .evolution-mask/ 存在，缺失文件从插件模板补齐（幂等）
  inject  生成注入包：PLAYBOOK active 规则（预算内 Top-N）+ ISSUES 高优未决 + 画像偏好预填
  dedup   复发检测：按 Phase+分类 聚类，输出合并候选（不自动改文件）
  report  进化报告：指标趋势 + 问题统计 + 晋升候选 + 规则健康度 + 画像待复验
  status  一行概览

用法：
  python3 <插件目录>/skills/self-evolution/scripts/evolution_cli.py <command> [--root DIR]
"""

import argparse
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR.parent / "assets"
DATA_FILES = ["ISSUES.md", "PLAYBOOK.md", "USER_PROFILE.md", "METRICS.md"]

ISS_HEADER = re.compile(r"^## \[(ISS-\d{8}-\d{3})\]\s*(.*)$", re.M)
RUL_HEADER = re.compile(r"^## \[(RUL-\d{8}-\d{3})\]\s*(.*)$", re.M)
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
SECTION_RE = re.compile(r"^## .+$", re.M)


def parse_date(text):
    """从任意文本中取第一个合法日期；失败返回 None。"""
    if not text:
        return None
    m = DATE_RE.search(text)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def field(entry, key):
    """从条目正文取字段：优先行首 `- Key: v` / `**Key**: v` 写法（全角/半角冒号均可）；
    兼容旧模板同行 `- A: v / Key: v` 写法（值取到下一个 / 或行尾）。"""
    m = re.search(r"(?:^\s*(?:-\s+)?\*\*%s\*\*|^\s*-\s+%s)\s*[：:/]*\s*(.+)$"
                  % (key, key), entry, re.M | re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"[/／|]\s*(?:\*\*%s\*\*|%s)\s*[：:]\s*([^/／|]+)" % (key, key), entry, re.I)
    return m.group(1).strip() if m else ""


def to_int(text, default):
    """宽松整数转换：从字段值中取数字部分，失败回退默认值。"""
    m = re.search(r"\d+", text or "")
    return int(m.group(0)) if m else default


def split_entries(text, header_re):
    """按 `## [ID] 标题` 切条目，返回 [(id, title, body)]。"""
    out, matches = [], list(header_re.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m.group(1), m.group(2).strip(), text[m.start():end]))
    return out


def section_of(text, startswith):
    """取标题小节正文（匹配 2~6 级标题，到下一个任意级标题为止）。"""
    m = re.search(r"^#{2,6}\s+%s.*$" % re.escape(startswith), text, re.M)
    if not m:
        return ""
    nxt = re.search(r"^#{2,6}\s+.*$", text[m.end():], re.M)
    return text[m.end():m.end() + nxt.start()] if nxt else text[m.end():]


def load_issues(root):
    entries = split_entries((root / "ISSUES.md").read_text(encoding="utf-8"), ISS_HEADER)
    out = []
    for iid, title, body in entries:
        meta = section_of(body, "Metadata") or body
        rule_sec = section_of(body, "规避规则")
        rule = next((ln.strip("- ").strip() for ln in rule_sec.splitlines()
                     if ln.strip() and not ln.strip().startswith("<")), "")
        # 先取组合键：避免 field 的同行兜底把 First-Seen 的日期当成 Last-Seen
        last_seen_raw = field(meta, "First-Seen / Last-Seen") or field(meta, "Last-Seen")
        last_seen_dates = DATE_RE.findall(last_seen_raw)
        out.append({
            "id": iid, "title": title, "body": body,
            "priority": field(body, "Priority").lower(),
            "status": field(body, "Status").lower(),
            "phase": field(body, "Phase").lower(),
            "recurrence": to_int(field(meta, "Recurrence-Count"), 1),
            "last_seen": parse_date(last_seen_dates[-1]) if last_seen_dates else None,
            "rule": rule,
        })
    return out


def load_rules(root):
    entries = split_entries((root / "PLAYBOOK.md").read_text(encoding="utf-8"), RUL_HEADER)
    out = []
    for rid, title, body in entries:
        out.append({
            "id": rid, "title": title, "body": body,
            "phase": field(body, "Phase").lower() or "any",
            "scope": field(body, "Scope"),
            "rule": field(body, "Rule"),
            "level": field(body, "Level").lower() or "active",
            "hits": to_int(field(body, "Hits"), 0),
            "last_hit": parse_date(field(body, "Last-Hit")) or parse_date(field(body, "Created")),
        })
    return out


def load_metrics(root):
    rows = []
    for line in (root / "METRICS.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("|") and not set(line) <= set("|- \t"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and cells[0] not in ("日期",) and parse_date(cells[0]):
                rows.append(cells)
    return rows


def load_preferences(root):
    sec = section_of((root / "USER_PROFILE.md").read_text(encoding="utf-8"), "偏好")
    lines = [ln.strip() for ln in sec.splitlines()
             if ln.strip().startswith("-") and not ln.strip().startswith("<!--")]
    return [re.sub(r"^-\s*", "", ln) for ln in lines]


def days_ago(d):
    return (date.today() - d).days if d else None


def ensure(root, verbose=True):
    """自愈初始化：确保 <项目根>/.evolution-mask/ 及数据文件存在（缺失从模板补齐）。

    返回数据目录 Path（调用方统一用它读写，保证目录契约唯一）。
    """
    data = root / ".evolution-mask"
    created = []
    data.mkdir(parents=True, exist_ok=True)
    for name in DATA_FILES:
        target = data / name
        if not target.exists():
            shutil.copyfile(TEMPLATE_DIR / name, target)
            created.append(name)
    if verbose:
        if created:
            print("已初始化 %s：%s" % (data, ", ".join(created)))
        else:
            print("数据目录完好：%s（%d 文件）" % (data, len(DATA_FILES)))
    return data


# ---------------------------------------------------------------- commands

def cmd_init(args):
    ensure(Path(args.root).resolve())


def cmd_inject(args):
    root = ensure(Path(args.root).resolve(), verbose=False)

    rules = [r for r in load_rules(root) if r["level"] == "active" and r["rule"]]
    rules.sort(key=lambda r: (-r["hits"], r["id"]))
    rules = rules[:args.max_rules]

    issues = [i for i in load_issues(root)
              if i["status"] in ("open", "mitigating", "")
              and i["priority"] in ("high", "critical")]
    issues.sort(key=lambda i: (-i["recurrence"], i["last_seen"] or date.min))
    issues = issues[:args.max_issues]

    prefs = load_preferences(root)[:15]

    rule_lines = ["- [%s]（%s｜Scope:%s）%s（Hits:%d）"
                  % (r["id"], r["phase"], r["scope"] or "全队", r["rule"], r["hits"])
                  for r in rules]
    issue_lines = ["- [%s]（%s/%s）%s（复发:%d）"
                   % (i["id"], i["phase"], i["title"],
                      i["rule"] or "暂无规避规则，优先补录", i["recurrence"])
                   for i in issues]
    pref_lines = ["- " + p for p in prefs]

    def build(dropped=0):
        parts = [
            "# 自我进化注入包（%s）" % date.today().isoformat(),
            "> 由 evolution_cli.py inject 生成｜预算：规则≤%d 条 / 全文≤%d 字符"
            % (args.max_rules, args.max_chars),
            "",
            "## 规避规则（PLAYBOOK active，按命中数排序，Scope 供主理人分发）",
            "\n".join(rule_lines) if rule_lines else "- （无，尚未晋升规则）",
            "",
            "## 高优未决问题（ISSUES open + high/critical）",
            "\n".join(issue_lines) if issue_lines else "- （无）",
            "",
            "## 用户偏好预填（访谈已知维度，只问增量）",
            "\n".join(pref_lines) if pref_lines else "- （画像为空，首次使用）",
        ]
        if dropped:
            parts += ["", "> 超预算已裁剪 %d 条（按 问题→规则尾部→偏好 顺序），完整数据见 .evolution-mask/" % dropped]
        return "\n".join(parts)

    # 字符预算按最终输出全文计算（含标题与包装）；超限从低价值端裁剪：
    # 问题 → 规则尾部（至少留 1 条）→ 偏好尾部
    total = len(rule_lines) + len(issue_lines) + len(pref_lines)
    while True:
        dropped = total - (len(rule_lines) + len(issue_lines) + len(pref_lines))
        if len(build(dropped)) <= args.max_chars:
            break
        if issue_lines:
            issue_lines.pop()
        elif len(rule_lines) > 1:
            rule_lines.pop()
        elif pref_lines:
            pref_lines.pop()
        elif rule_lines:
            rule_lines.pop()
        else:
            break  # 包装本身已超预算（--max-chars 过小），不再裁剪

    print(build(dropped))


def cmd_dedup(args):
    root = ensure(Path(args.root).resolve(), verbose=False)
    issues = [i for i in load_issues(root) if i["status"] not in ("resolved", "promoted")]
    groups = {}
    for i in issues:
        groups.setdefault((i["phase"], i["title"]), []).append(i)

    found = False
    for (phase, cat), items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if len(items) < 2:
            continue
        found = True
        newest = max(items, key=lambda i: i["last_seen"] or date.min)
        others = [i for i in items if i is not newest]
        print("合并候选｜%s / %s" % (phase or "未知Phase", cat))
        for i in items:
            mark = " ← 保留" if i is newest else ""
            print("  %s（复发:%d，Last-Seen:%s）%s"
                  % (i["id"], i["recurrence"], i["last_seen"] or "?", mark))
        print("  建议动作：%s 的 Recurrence-Count +%d、更新 Last-Seen，其余条目标 resolved 并 Related 关联\n"
              % (newest["id"], len(others)))
    if not found:
        print("无复发候选：所有未决条目的 Phase+分类 均唯一。")


def cmd_report(args):
    root = ensure(Path(args.root).resolve(), verbose=False)
    today = date.today()
    lines = ["# 进化报告（%s）" % today.isoformat()]

    rows = load_metrics(root)[-args.last:]
    lines.append("\n## 指标概览（最近 %d 次任务）" % len(rows))
    if rows:
        lines.append("| 日期 | 任务 | 访谈轮次 | 澄清返工 | 一次通过 | 存活率 | 规则命中 | 新增ISS |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for r in rows:
            cells = (r + [""] * 8)[:8]
            lines.append("| " + " | ".join(cells) + " |")
        rounds = [float(r[2]) for r in rows if len(r) > 2 and re.match(r"^\d+(\.\d+)?$", r[2])]
        if rounds:
            lines.append("\n- 访谈轮次均值：%.1f（目标 ↓）" % (sum(rounds) / len(rounds)))
    else:
        lines.append("- 暂无任务记录")

    issues = load_issues(root)
    by_cat, by_status, promo = {}, {}, []
    for i in issues:
        by_cat[i["title"]] = by_cat.get(i["title"], 0) + 1
        by_status[i["status"] or "open"] = by_status.get(i["status"] or "open", 0) + 1
        if i["recurrence"] >= 3 and i["status"] not in ("promoted", "resolved"):
            promo.append(i)
    lines.append("\n## 问题知识库（共 %d 条）" % len(issues))
    lines.append("- 分类分布：" + "，".join("%s %d" % kv for kv in sorted(by_cat.items())))
    lines.append("- 状态分布：" + "，".join("%s %d" % kv for kv in sorted(by_status.items())))
    top = sorted((i for i in issues if i["recurrence"] >= 2),
                 key=lambda i: -i["recurrence"])[:5]
    if top:
        lines.append("- 复发 Top：" + "；".join("%s（%d 次）" % (i["id"], i["recurrence"]) for i in top))

    lines.append("\n## 晋升候选（复发≥3，需人工确认跨≥2任务且30天内）")
    lines.append("\n".join("- %s（%s/%s，复发%d）%s" % (p["id"], p["phase"], p["title"], p["recurrence"], p["rule"])
                           for p in promo) if promo else "- （无）")

    rules = load_rules(root)
    by_level, stale = {}, []
    total_hits = 0
    for r in rules:
        by_level[r["level"]] = by_level.get(r["level"], 0) + 1
        total_hits += r["hits"]
        idle = days_ago(r["last_hit"])
        if r["level"] == "active" and idle is not None and idle > 90:
            stale.append((r, idle))
    lines.append("\n## PLAYBOOK 健康度（共 %d 条，累计命中 %d 次）" % (len(rules), total_hits))
    lines.append("- 级别分布：" + ("，".join("%s %d" % kv for kv in sorted(by_level.items())) or "空"))
    for r, idle in sorted(stale, key=lambda x: -x[1]):
        action = "建议归档（Level: archived）" if idle > 120 else "建议降级（Level: demoted）"
        lines.append("- %s 已 %d 天未命中，%s" % (r["id"], idle, action))
    if not stale:
        lines.append("- 无超期规则")

    prefs = section_of((root / "USER_PROFILE.md").read_text(encoding="utf-8"), "偏好")
    stale_prefs = [re.sub(r"^-\s*", "", ln.strip()) for ln in prefs.splitlines()
                   if ln.strip().startswith("-")
                   and days_ago(parse_date(ln)) is not None and days_ago(parse_date(ln)) > 30
                   and "用户原话" not in ln]
    lines.append("\n## 画像待复验（Updated>30 天且非显式偏好）")
    lines.append("\n".join("- " + s for s in stale_prefs) if stale_prefs else "- （无）")

    lines.append("\n## 建议动作")
    actions = []
    if promo:
        actions.append("对 %d 条晋升候选向用户展示 diff，批准后写入 PLAYBOOK.md" % len(promo))
    if stale:
        actions.append("更新 %d 条超期规则的 Level" % len(stale))
    if stale_prefs:
        actions.append("与用户复验 %d 条陈旧画像偏好" % len(stale_prefs))
    lines.append("\n".join("- " + a for a in actions) or "- 维持现状：继续记录，无待办动作")

    output = "\n".join(lines) + "\n"
    if args.save:
        target = root / ("REPORT-%s.md" % today.strftime("%Y%m%d"))
        target.write_text(output, encoding="utf-8")
        print("进化报告已写入：%s\n" % target)
    print(output)


def cmd_status(args):
    root = ensure(Path(args.root).resolve(), verbose=False)
    issues, rules, rows = load_issues(root), load_rules(root), load_metrics(root)
    open_hi = sum(1 for i in issues if i["status"] in ("open", "mitigating", "")
                  and i["priority"] in ("high", "critical"))
    active = sum(1 for r in rules if r["level"] == "active")
    last = max((i["last_seen"] for i in issues if i["last_seen"]), default=None)
    print(".evolution-mask 状态｜ISSUES %d 条（高优未决 %d）｜PLAYBOOK %d 条（active %d，累计命中 %d）"
          "｜METRICS %d 行｜最近记录 %s"
          % (len(issues), open_hi, len(rules), active, sum(r["hits"] for r in rules),
             len(rows), last or "无"))


def main():
    parser = argparse.ArgumentParser(description="self-evolution 运行时数据工具")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func in (("init", cmd_init), ("dedup", cmd_dedup), ("status", cmd_status)):
        p = sub.add_parser(name)
        p.add_argument("--root", default=".", help="用户项目根目录（默认当前目录）")
        p.set_defaults(func=func)
    p = sub.add_parser("inject")
    p.add_argument("--root", default=".", help="用户项目根目录（默认当前目录）")
    p.add_argument("--max-rules", type=int, default=15, help="注入规则条数上限")
    p.add_argument("--max-issues", type=int, default=5, help="注入高优问题条数上限")
    p.add_argument("--max-chars", type=int, default=4000, help="注入包字符预算")
    p.set_defaults(func=cmd_inject)
    p = sub.add_parser("report")
    p.add_argument("--root", default=".", help="用户项目根目录（默认当前目录）")
    p.add_argument("--last", type=int, default=5, help="纳入统计的最近任务数")
    p.add_argument("--save", action="store_true", help="另存为 .evolution-mask/REPORT-YYYYMMDD.md")
    p.set_defaults(func=cmd_report)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
