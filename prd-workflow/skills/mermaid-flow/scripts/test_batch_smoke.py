#!/usr/bin/env python3
"""batch_render 冒烟测试。

回归测试：batch_render 曾引用 main() 的局部变量 `args`
（`getattr(args, 'puppeteer_config', None)`），导致 --batch 模式 100% 抛
NameError。修复后 puppeteer_config 以参数形式传入。

本测试用 monkeypatch 替换 render_mermaid，不依赖 mmdc / Chrome，
纯标准库可运行：

    python3 test_batch_smoke.py
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent


def _load_renderer():
    path = SCRIPTS_DIR / "mermaid_render.py"
    spec = importlib.util.spec_from_file_location("mermaid_render", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BatchRenderSmokeTest(unittest.TestCase):
    def setUp(self):
        self.mod = _load_renderer()
        self._orig_render = self.mod.render_mermaid
        self.calls = []

        def fake_render(input_path, output_path, width, background, scale,
                        puppeteer_config=None):
            self.calls.append({
                "input": Path(input_path).name,
                "output": Path(output_path).name,
                "puppeteer_config": puppeteer_config,
            })
            return True

        self.mod.render_mermaid = fake_render
        self.addCleanup(self._restore)

    def _restore(self):
        self.mod.render_mermaid = self._orig_render

    def _make_input_dir(self, tmp, names=("a.mmd", "b.mmd")):
        input_dir = Path(tmp) / "in"
        input_dir.mkdir()
        for name in names:
            (input_dir / name).write_text("graph TD\n  A-->B\n", encoding="utf-8")
        return input_dir

    def test_batch_render_no_nameerror(self):
        """batch_render 不再抛 NameError，且逐文件调用 render_mermaid。"""
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = self._make_input_dir(tmp)
            output_dir = Path(tmp) / "out"
            success, fail = self.mod.batch_render(input_dir, output_dir)
        self.assertEqual((success, fail), (2, 0))
        self.assertEqual(sorted(c["input"] for c in self.calls), ["a.mmd", "b.mmd"])
        self.assertEqual(sorted(c["output"] for c in self.calls), ["a.png", "b.png"])

    def test_batch_render_passes_puppeteer_config_through(self):
        """puppeteer_config 参数透传到每次 render_mermaid 调用。"""
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = self._make_input_dir(tmp)
            output_dir = Path(tmp) / "out"
            self.mod.batch_render(input_dir, output_dir,
                                  puppeteer_config="/tmp/pptr.json")
        self.assertTrue(self.calls)
        for call in self.calls:
            self.assertEqual(call["puppeteer_config"], "/tmp/pptr.json")

    def test_batch_render_missing_dir_returns_zero_tuple(self):
        """输入目录不存在时返回 (0, 0)，不抛异常。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = self.mod.batch_render(Path(tmp) / "nope", Path(tmp) / "out")
        self.assertEqual(result, (0, 0))


if __name__ == "__main__":
    unittest.main()
