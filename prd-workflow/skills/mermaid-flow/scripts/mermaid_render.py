#!/usr/bin/env python3
"""
Mermaid Render - Mermaid 图表渲染脚本
封装 mermaid-cli 调用，支持批量导出 PNG/SVG
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path

# 默认配置
DEFAULT_WIDTH = 1600
DEFAULT_BACKGROUND = "white"  # 白色背景更适合 Word 文档
DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def check_mermaid_cli():
    """检查 mermaid-cli 是否安装"""
    try:
        result = subprocess.run(
            ["mmdc", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print(f"✅ mermaid-cli 已安装：{result.stdout.strip()}")
            return True
        else:
            print("❌ 错误：mermaid-cli 未正确安装")
            return False
    except FileNotFoundError:
        print("❌ 错误：未找到 mmdc 命令")
        print("解决方案：npm install -g @mermaid-js/mermaid-cli")
        return False


def check_puppeteer():
    """检查 Puppeteer 是否可用"""
    chrome_path = os.environ.get(
        "PUPPETEER_EXECUTABLE_PATH",
        DEFAULT_CHROME_PATH
    )
    
    if os.path.exists(chrome_path):
        print(f"✅ Chrome 可用：{chrome_path}")
        return True
    else:
        print(f"⚠️ 警告：未找到 Chrome ({chrome_path})")
        print("请设置 PUPPETEER_EXECUTABLE_PATH 环境变量")
        return False


def detect_chrome():
    """检测可用的 Chrome 路径（优先 chrome-headless-shell，与 GUI Chrome 隔离）"""
    import glob
    candidates = []
    env_path = os.environ.get("PUPPETEER_EXECUTABLE_PATH")
    if env_path and os.path.exists(env_path):
        candidates.append(env_path)
    # puppeteer 缓存的 chrome-headless-shell（优先）
    home = os.path.expanduser("~")
    for pattern in [
        os.path.join(home, ".cache/puppeteer/chrome-headless-shell", "*", "*", "chrome-headless-shell"),
        os.path.join(home, ".cache/puppeteer/chrome-headless-shell", "*", "chrome-headless-shell"),
        os.path.join(home, "Library/Caches/puppeteer/chrome-headless-shell", "*", "*", "chrome-headless-shell"),
    ]:
        candidates += sorted(glob.glob(pattern), reverse=True)
    if sys.platform == "darwin":
        candidates += [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    elif sys.platform == "win32":
        candidates += [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
    else:
        candidates += ["/usr/bin/google-chrome", "/usr/bin/chromium-browser", "/usr/bin/chromium"]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def ensure_puppeteer_config(explicit_path=None):
    """
    确保 mmdc 有可用的 puppeteer 配置（headless:true + executablePath）。
    优先级：显式 -p 参数 > 自动生成临时配置。
    返回配置文件路径；完全找不到 Chrome 时返回 None（交由 mmdc 自行处理）。
    """
    if explicit_path:
        return explicit_path if os.path.exists(explicit_path) else None
    chrome = detect_chrome()
    if not chrome:
        return None
    import tempfile
    cfg = {"executablePath": chrome, "headless": True}
    fd, cfg_path = tempfile.mkstemp(prefix="mflow_pptr_", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(cfg, f)
    return cfg_path


def render_mermaid(input_path, output_path, width=DEFAULT_WIDTH,
                   background=DEFAULT_BACKGROUND, scale=1,
                   puppeteer_config=None):
    """
    渲染单个 mermaid 文件
    
    Args:
        input_path: 输入 .mmd 文件路径
        output_path: 输出文件路径 (.png/.svg/.pdf)
        width: 图像宽度 (像素)
        background: 背景色 (transparent/white/#F0F0F0)
        scale: 缩放比例 (1=标准，2=高清)
    
    Returns:
        bool: 是否成功
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    
    if not input_path.exists():
        print(f"❌ 错误：输入文件不存在：{input_path}")
        return False
    
    # 构建命令
    cmd = [
        "mmdc",
        "-i", str(input_path),
        "-o", str(output_path),
        "-w", str(width),
        "-b", background,
        "-s", str(scale)
    ]

    # 自动附加 puppeteer 配置（修复裸调 mmdc 时 Chrome ConnectionClosed 崩溃）
    pp_cfg = ensure_puppeteer_config(puppeteer_config)
    if pp_cfg:
        cmd += ["-p", pp_cfg]

    # 设置 Puppeteer 环境变量（确保 mermaid-cli 能继承）
    env = os.environ.copy()
    env["PUPPETEER_EXECUTABLE_PATH"] = detect_chrome() or DEFAULT_CHROME_PATH
    env["FORCE_COLOR"] = "0"
    
    print(f"🎨 渲染：{input_path.name} → {output_path.name}")
    print(f"   命令：{' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=300  # 5 分钟超时
        )
        
        # 检查结果
        if result.returncode == 0:
            if output_path.exists():
                file_size = output_path.stat().st_size / 1024  # KB
                print(f"✅ 成功：{output_path.name} ({file_size:.1f}KB)")
                return True
            else:
                print(f"❌ 错误：输出文件未生成")
                if result.stderr:
                    print(f"   错误：{result.stderr}")
                return False
        else:
            print(f"❌ 渲染失败 (返回码：{result.returncode})")
            if result.stderr:
                print(f"   错误：{result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"❌ 超时：渲染超过 5 分钟")
        return False
    except Exception as e:
        print(f"❌ 异常：{e}")
        return False


def batch_render(input_dir, output_dir, width=DEFAULT_WIDTH,
                 background=DEFAULT_BACKGROUND, scale=1):
    """
    批量渲染目录中的所有 .mmd 文件
    
    Args:
        input_dir: 输入目录路径
        output_dir: 输出目录路径
        width: 图像宽度
        background: 背景色
        scale: 缩放比例
    
    Returns:
        tuple: (成功数，失败数)
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    
    if not input_dir.exists():
        print(f"❌ 错误：输入目录不存在：{input_dir}")
        return (0, 0)
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 查找所有 .mmd 文件
    mmd_files = list(input_dir.glob("*.mmd"))
    
    if not mmd_files:
        print(f"⚠️ 警告：未找到 .mmd 文件：{input_dir}")
        return (0, 0)
    
    print(f"📊 批量渲染：找到 {len(mmd_files)} 个 .mmd 文件")
    print(f"   输入：{input_dir}")
    print(f"   输出：{output_dir}")
    print()
    
    success_count = 0
    fail_count = 0
    
    for mmd_file in mmd_files:
        # 生成输出文件名
        output_file = output_dir / f"{mmd_file.stem}.png"
        
        if render_mermaid(mmd_file, output_file, width, background, scale,
                          puppeteer_config=getattr(args, 'puppeteer_config', None)):
            success_count += 1
        else:
            fail_count += 1
        
        print()
    
    return (success_count, fail_count)


def main():
    parser = argparse.ArgumentParser(
        description="Mermaid 图表渲染工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 渲染单个文件
  python mermaid_render.py -i flowchart.mmd -o flowchart.png
  
  # 批量渲染目录
  python mermaid_render.py -i ./diagrams/ -o ./output/ --batch
  
  # 指定宽度和质量
  python mermaid_render.py -i flow.mmd -o flow.png -w 1600 -b transparent
        """
    )
    
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="输入 .mmd 文件或目录"
    )
    
    parser.add_argument(
        "-o", "--output",
        required=True,
        help="输出 .png 文件或目录"
    )
    
    parser.add_argument(
        "-w", "--width",
        type=int,
        default=DEFAULT_WIDTH,
        help=f"图像宽度 (默认：{DEFAULT_WIDTH})"
    )
    
    parser.add_argument(
        "-b", "--background",
        default=DEFAULT_BACKGROUND,
        help=f"背景色 (默认：{DEFAULT_BACKGROUND})"
    )
    
    parser.add_argument(
        "-s", "--scale",
        type=int,
        default=1,
        help="缩放比例 (默认：1, 2=高清)"
    )
    
    parser.add_argument(
        "--batch",
        action="store_true",
        help="批量模式 (输入输出都是目录)"
    )
    
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查依赖，不渲染"
    )

    parser.add_argument(
        "-p", "--puppeteer-config",
        default=None,
        help="puppeteer 配置文件路径（缺省时自动检测 Chrome 并生成临时配置）"
    )
    
    args = parser.parse_args()
    
    print("🎨 Mermaid Render Tool")
    print("=" * 50)
    
    # 检查依赖
    if args.check or True:  # 总是检查
        if not check_mermaid_cli():
            sys.exit(1)
        check_puppeteer()
        print()
        
        if args.check:
            print("✅ 依赖检查完成")
            sys.exit(0)
    
    # 渲染
    if args.batch:
        # 批量模式
        success, fail = batch_render(
            args.input,
            args.output,
            args.width,
            args.background,
            args.scale
        )
        print()
        print("=" * 50)
        print(f"📊 渲染完成：成功 {success} 个，失败 {fail} 个")
        sys.exit(0 if fail == 0 else 1)
    else:
        # 单文件模式
        if render_mermaid(
            args.input,
            args.output,
            args.width,
            args.background,
            args.scale,
            puppeteer_config=getattr(args, 'puppeteer_config', None)
        ):
            print()
            print("✅ 渲染成功")
            sys.exit(0)
        else:
            print()
            print("❌ 渲染失败")
            sys.exit(1)


if __name__ == "__main__":
    main()
