#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""manifest_cli.py 单元测试（零第三方依赖，pytest 与 unittest 均可运行）。

覆盖：init 幂等 / register 展开与哈希 / check 失效与级联 / refresh / exempt /
路径越界拦截 / 原子写 / 并发锁（进程内多线程近似验证）。

运行：python3 prd-workflow/scripts/tests/test_manifest_cli.py
或：  pytest prd-workflow/scripts/tests/test_manifest_cli.py -q
"""

import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import manifest_cli as mc  # noqa: E402


def run_cli(root, *args):
    """以子进程方式执行 CLI（stdin/stdout 隔离，校验退出码）。"""
    return subprocess.run(
        [Path(sys.executable).as_posix(),
         str(Path(__file__).resolve().parent.parent / "manifest_cli.py"),
         *args, "--root", str(root)],
        capture_output=True, text=True)


class ManifestCliTestBase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="mask_manifest_test_"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, rel, content):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return rel

    def register(self, path, phase=1, producer="tester", inputs=None):
        args = ["register", path, "--phase", str(phase), "--producer", producer]
        if inputs:
            args += ["--inputs", ",".join(inputs)]
        return run_cli(self.root, *args)


class TestInit(ManifestCliTestBase):
    def test_init_creates_and_is_idempotent(self):
        self.assertEqual(run_cli(self.root, "init").returncode, 0)
        data = mc.load(self.root)
        self.assertEqual(data["schema"], mc.SCHEMA)
        # 幂等：二次 init 不丢已有产物
        self.write("a.md", "A")
        self.register("a.md")
        run_cli(self.root, "init")
        data2 = mc.load(self.root)
        self.assertIn("a.md", data2["artifacts"])

    def test_check_empty_returns_0(self):
        self.assertEqual(run_cli(self.root, "check").returncode, 0)

    def test_status_on_empty(self):
        self.assertEqual(run_cli(self.root, "status").returncode, 0)


class TestRegister(ManifestCliTestBase):
    def test_register_file_and_inputs(self):
        self.write("input/upstream.md", "# 上游")
        self.write("prd/PRD.md", "# PRD")
        r = self.register("prd/PRD.md", inputs=["input/upstream.md"])
        self.assertEqual(r.returncode, 0)
        data = mc.load(self.root)
        e = data["artifacts"]["prd/PRD.md"]
        self.assertEqual(e["status"], "fresh")
        self.assertEqual(e["inputs"], ["input/upstream.md"])
        self.assertIn("input/upstream.md", e["input_hashes"])
        self.assertTrue(e["hash"].startswith("sha256:"))

    def test_register_directory_expands(self):
        self.write("design/a.mmd", "graph TD")
        self.write("design/b.mmd", "erDiagram")
        (self.root / "design/.hidden.mmd").write_text("x", encoding="utf-8")
        r = self.register("design")
        self.assertEqual(r.returncode, 0)
        data = mc.load(self.root)
        self.assertIn("design/a.mmd", data["artifacts"])
        self.assertIn("design/b.mmd", data["artifacts"])
        self.assertNotIn("design/.hidden.mmd", data["artifacts"])

    def test_register_rerecord_keeps_history(self):
        self.write("prd/PRD.md", "v1")
        self.register("prd/PRD.md")
        r = run_cli(self.root, "check")
        self.assertEqual(r.returncode, 0)
        data = mc.load(self.root)
        self.assertEqual(data["artifacts"]["prd/PRD.md"]["status"], "fresh")

    def test_register_missing_artifact_fails(self):
        r = self.register("nope.md")
        self.assertEqual(r.returncode, 2)

    def test_register_missing_input_fails(self):
        self.write("a.md", "x")
        r = self.register("a.md", inputs=["ghost.md"])
        self.assertEqual(r.returncode, 2)


class TestCheck(ManifestCliTestBase):
    def test_input_change_marks_stale(self):
        self.write("in.md", "v1")
        self.write("out.md", "o")
        self.register("out.md", inputs=["in.md"])
        self.assertEqual(run_cli(self.root, "check").returncode, 0)
        # 修改输入 → stale，退出码 1
        self.write("in.md", "v2")
        r = run_cli(self.root, "check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("in.md", json.loads(r.stdout)["stale"]["out.md"])
        # 输入恢复 → 自愈为 fresh，退出码 0
        self.write("in.md", "v1")
        self.assertEqual(run_cli(self.root, "check").returncode, 0)

    def test_cascade_stale(self):
        self.write("a.md", "A")
        self.write("b.md", "B")
        self.write("c.md", "C")
        self.register("b.md", inputs=["a.md"])
        self.register("c.md", inputs=["b.md"])
        self.write("a.md", "A2")
        r = run_cli(self.root, "check")
        report = json.loads(r.stdout)["stale"]
        self.assertIn("a.md", report["b.md"])       # 直接输入变化
        self.assertIn("b.md", report["c.md"])       # 级联：上游 stale
        self.assertEqual(r.returncode, 1)

    def test_input_missing_marks_stale(self):
        self.write("in.md", "v")
        self.write("out.md", "o")
        self.register("out.md", inputs=["in.md"])
        (self.root / "in.md").unlink()
        r = run_cli(self.root, "check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("input_missing", json.loads(r.stdout)["stale"]["out.md"])


class TestRefreshExempt(ManifestCliTestBase):
    def setUp(self):
        super().setUp()
        self.write("in.md", "v1")
        self.write("out.md", "o")
        self.register("out.md", inputs=["in.md"])
        self.write("in.md", "v2")
        run_cli(self.root, "check")

    def test_refresh_restores_fresh(self):
        self.assertEqual(run_cli(self.root, "check").returncode, 1)
        self.write("out.md", "o2")
        self.assertEqual(run_cli(self.root, "refresh", "out.md").returncode, 0)
        self.assertEqual(run_cli(self.root, "check").returncode, 0)
        data = mc.load(self.root)
        e = data["artifacts"]["out.md"]
        self.assertEqual(e["status"], "fresh")
        self.assertEqual(e["history"][0]["status"], "superseded")

    def test_refresh_unregistered_fails(self):
        self.assertEqual(run_cli(self.root, "refresh", "ghost.md").returncode, 2)

    def test_exempt_only_stale(self):
        r = run_cli(self.root, "exempt", "out.md", "--reason", "用户确认跳过")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(run_cli(self.root, "check").returncode, 0)
        # 非 stale 不可豁免
        self.assertEqual(
            run_cli(self.root, "exempt", "out.md", "--reason", "again").returncode, 2)


class TestPathSafety(ManifestCliTestBase):
    def test_absolute_path_rejected(self):
        outside = self.root.parent / "outside.md"
        outside.write_text("x", encoding="utf-8")
        try:
            self.assertEqual(run_cli(self.root, "refresh", str(outside)).returncode, 2)
        finally:
            outside.unlink(missing_ok=True)

    def test_traversal_rejected(self):
        self.assertEqual(run_cli(self.root, "refresh", "../evil.md").returncode, 2)

    def test_resolve_in_root_rejects_escape(self):
        with self.assertRaises(SystemExit):
            mc.resolve_in_root(self.root, "../evil.md")
        with self.assertRaises(SystemExit):
            mc.resolve_in_root(self.root, str(self.root.parent / "evil.md"))


class TestAtomicSaveAndLock(ManifestCliTestBase):
    def test_save_writes_valid_json(self):
        mc.save(self.root, {"schema": mc.SCHEMA, "artifacts": {}})
        data = mc.load(self.root)
        self.assertEqual(data["schema"], mc.SCHEMA)
        # 无残留 tmp 文件
        leftovers = list((self.root / ".mask").glob("manifest.json.tmp.*"))
        self.assertEqual(leftovers, [])

    def test_concurrent_registers_no_lost_update(self):
        self.write("a.md", "A")
        self.write("b.md", "B")
        errors = []

        def worker(path):
            r = self.register(path)
            if r.returncode != 0:
                errors.append((path, r.stderr))

        threads = [threading.Thread(target=worker, args=(p,))
                   for p in ("a.md", "b.md")]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        data = mc.load(self.root)
        self.assertIn("a.md", data["artifacts"])
        self.assertIn("b.md", data["artifacts"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
