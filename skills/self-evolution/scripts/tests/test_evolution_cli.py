#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""evolution_cli.py 单元测试（零第三方依赖，unittest 直接运行）。

覆盖：条目切分与字段解析（含宽松 to_int）/ init 自愈 / inject 预算裁剪 /
dedup 聚类 / report 统计 / status。模板来自插件真实 assets。

运行：python3 skills/self-evolution/scripts/tests/test_evolution_cli.py
或：  pytest skills/self-evolution/scripts/tests/test_evolution_cli.py -q
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import evolution_cli as ec  # noqa: E402

CLI = SCRIPT_DIR / "evolution_cli.py"


def run_cli(root, *args):
    return subprocess.run(
        [Path(sys.executable).as_posix(), str(CLI), *args, "--root", str(root)],
        capture_output=True, text=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="mask_evolution_test_"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)

    def write_data(self, issues="", playbook="", metrics="", profile=""):
        d = self.root / ".evolution-mask"
        d.mkdir(parents=True)
        for name, content in (("ISSUES.md", issues), ("PLAYBOOK.md", playbook),
                              ("METRICS.md", metrics), ("USER_PROFILE.md", profile)):
            (d / name).write_text(content, encoding="utf-8")


class TestParsing(unittest.TestCase):
    def test_parse_date_valid_and_invalid(self):
        self.assertEqual(str(ec.parse_date("2026-10-11 出现")), "2026-10-11")
        self.assertIsNone(ec.parse_date("没有日期"))
        self.assertIsNone(ec.parse_date("2026-13-99"))  # 非法日期回退 None
        self.assertIsNone(ec.parse_date(None))

    def test_field_line_and_fullwidth_colon(self):
        self.assertEqual(ec.field("**Priority**：high", "Priority"), "high")
        self.assertEqual(ec.field("- Status: open", "Status"), "open")
        self.assertEqual(ec.field("没有任何字段", "Priority"), "")

    def test_to_int_loose(self):
        self.assertEqual(ec.to_int("复发 3 次", 1), 3)
        self.assertEqual(ec.to_int("", 7), 7)
        self.assertEqual(ec.to_int(None, 1), 1)

    def test_split_entries(self):
        text = "## [ISS-20261010-001] A\nbody a\n## [ISS-20261010-002] B\nbody b"
        entries = ec.split_entries(text, ec.ISS_HEADER)
        self.assertEqual([e[0] for e in entries],
                         ["ISS-20261010-001", "ISS-20261010-002"])
        self.assertIn("body b", entries[1][2])

    def test_section_of(self):
        text = "## Metadata\n- K: v\n## 规避规则\n- 不要 X\n## 其他"
        self.assertIn("不要 X", ec.section_of(text, "规避规则"))
        self.assertIn("K: v", ec.section_of(text, "Metadata"))
        self.assertEqual(ec.section_of(text, "不存在"), "")


class TestLoaders(Base):
    def test_load_issues_fields(self):
        self.write_data(issues="""## [ISS-20261010-001] 访谈超长
### Metadata
- Phase: interview
- Priority: high
- Status: open
- Recurrence-Count: 3
- First-Seen / Last-Seen: 2026-10-01 / 2026-10-11
### 规避规则
- 批量提问，单次合并多题
""")
        issues = ec.load_issues(self.root / ".evolution-mask")
        self.assertEqual(len(issues), 1)
        i = issues[0]
        self.assertEqual(i["id"], "ISS-20261010-001")
        self.assertEqual(i["priority"], "high")
        self.assertEqual(i["status"], "open")
        self.assertEqual(i["recurrence"], 3)
        self.assertEqual(str(i["last_seen"]), "2026-10-11")
        self.assertIn("批量提问", i["rule"])

    def test_load_rules_defaults(self):
        self.write_data(playbook="""## [RUL-20261010-001] 规则一
- Phase: 3
- Scope: designer
- Rule: 先出信息架构再画图
- Level: active
- Hits: 5
- Last-Hit: 2026-10-11
""")
        r = ec.load_rules(self.root / ".evolution-mask")[0]
        self.assertEqual(r["hits"], 5)
        self.assertEqual(r["level"], "active")
        self.assertEqual(str(r["last_hit"]), "2026-10-11")

    def test_load_rules_missing_fields_fall_back(self):
        self.write_data(playbook="## [RUL-20261010-002] 无字段\n正文\n")
        r = ec.load_rules(self.root / ".evolution-mask")[0]
        self.assertEqual(r["level"], "active")   # 默认 active
        self.assertEqual(r["phase"], "any")      # 默认 any
        self.assertEqual(r["hits"], 0)           # to_int 回退

    def test_load_metrics_skips_header_and_separator(self):
        self.write_data(metrics="""| 日期 | 任务 |
|---|---|
| 2026-10-11 | demo |
""")
        rows = ec.load_metrics(self.root / ".evolution-mask")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "demo")

    def test_load_preferences(self):
        self.write_data(profile="# 画像\n## 偏好\n- 技术栈：Python\n- 输出中文\n")
        prefs = ec.load_preferences(self.root / ".evolution-mask")
        self.assertEqual(len(prefs), 2)
        self.assertIn("技术栈", prefs[0])


class TestCliCommands(Base):
    def test_init_idempotent_keeps_content(self):
        self.assertEqual(run_cli(self.root, "init").returncode, 0)
        f = self.root / ".evolution-mask/ISSUES.md"
        f.write_text("## [ISS-20261010-001] keep\n", encoding="utf-8")
        run_cli(self.root, "init")
        self.assertIn("ISS-20261010-001", f.read_text(encoding="utf-8"))

    def test_status_runs_on_empty(self):
        r = run_cli(self.root, "status")
        self.assertEqual(r.returncode, 0)
        self.assertIn(".evolution-mask 状态", r.stdout)

    def test_inject_outputs_structure(self):
        r = run_cli(self.root, "inject", "--max-chars", "4000")
        self.assertEqual(r.returncode, 0)
        for heading in ("规避规则", "高优未决问题", "用户偏好预填"):
            self.assertIn(heading, r.stdout)
        self.assertLessEqual(len(r.stdout), 4200)  # ≤ 预算（含包装）

    def test_inject_budget_trim(self):
        r = run_cli(self.root, "inject", "--max-chars", "600")
        self.assertEqual(r.returncode, 0)
        self.assertLessEqual(len(r.stdout), 4000)

    def test_inject_prioritizes_high_open_issues(self):
        self.write_data(issues="""## [ISS-20261010-001] 低优
- Priority: low
- Status: open

## [ISS-20261010-002] 高优复发
- Priority: high
- Status: open
""")
        r = run_cli(self.root, "inject")
        self.assertEqual(r.returncode, 0)
        self.assertIn("ISS-20261010-002", r.stdout)
        self.assertNotIn("ISS-20261010-001", r.stdout)

    def test_dedup_clusters_and_marks_newest(self):
        self.write_data(issues="""## [ISS-20261010-001] 访谈超长
- Phase: interview
- Status: open
- Recurrence-Count: 1
- First-Seen / Last-Seen: 2026-10-01 / 2026-10-05

## [ISS-20261010-002] 访谈超长
- Phase: interview
- Status: open
- Recurrence-Count: 2
- First-Seen / Last-Seen: 2026-10-02 / 2026-10-11
""")
        r = run_cli(self.root, "dedup")
        self.assertEqual(r.returncode, 0)
        self.assertIn("合并候选", r.stdout)
        self.assertIn("ISS-20261010-002", r.stdout)      # 保留最新
        self.assertIn("Recurrence-Count +1", r.stdout)   # 建议合并计数

    def test_dedup_no_candidates(self):
        r = run_cli(self.root, "dedup")
        self.assertEqual(r.returncode, 0)
        self.assertIn("无复发候选", r.stdout)

    def test_report_runs_and_saves(self):
        self.write_data(
            issues="## [ISS-20261010-001] X\n- Priority: high\n- Status: open\n"
                   "- Recurrence-Count: 3\n",
            metrics="| 2026-10-11 | demo | 18 | 0 | 1 | 1.0 | 0 | 1 |\n")
        r = run_cli(self.root, "report", "--save")
        self.assertEqual(r.returncode, 0)
        self.assertIn("晋升候选", r.stdout)
        self.assertIn("ISS-20261010-001", r.stdout)      # 复发≥3 晋升候选
        saved = list((self.root / ".evolution-mask").glob("REPORT-*.md"))
        self.assertEqual(len(saved), 1)

    def test_report_empty_state(self):
        r = run_cli(self.root, "report")
        self.assertEqual(r.returncode, 0)
        self.assertIn("暂无任务记录", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
