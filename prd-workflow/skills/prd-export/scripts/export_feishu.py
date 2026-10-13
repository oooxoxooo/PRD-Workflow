#!/usr/bin/env python3
"""
export_feishu.py — 飞书在线文档导出模块 v1.0
将 Markdown PRD 导出为飞书在线文档（docx），自动打开文档链接。

链路：auth check → markdown 预处理 → lark-cli docs +create → URL 返回
依赖：lark-cli >= 1.0.97（feishu connector 提供）

错误分类（--retry 支持）：
  AUTH     未登录 / 授权过期 / scope 缺失   → 提示重新授权（auth login）
  NETWORK  网络异常 / 超时                   → 自动重试 + 提示
  PERM     权限不足（无 docx:create 等）     → 提示补充授权
  FAIL     其他导出失败                      → 展示服务端信息 + 可重试
"""

import os
import re
import sys
import json
import time
import shutil
import tempfile
import argparse
import subprocess
import webbrowser

RETRYABLE = {'NETWORK', 'FAIL'}   # 可自动重试的错误类别
MAX_RETRIES = 2                    # 自动重试次数（不含首次）


# ==================== 错误分类 ====================

class ExportError(Exception):
    """带类别的导出错误：category ∈ {AUTH, NETWORK, PERM, FAIL}"""

    def __init__(self, category, message, hint=''):
        super().__init__(message)
        self.category = category
        self.hint = hint


def classify_error(stderr_text, returncode, output_json):
    """把 lark-cli 输出归类为四类错误之一"""
    text = (stderr_text or '') + json.dumps(output_json or {}, ensure_ascii=False)

    # 授权类：未登录 / token 过期 / 需要重新授权
    if any(k in text for k in (
            'not logged in', 'unauthorized', 'token expired',
            'invalid_token', 'access_token', 're-auth', '重新授权',
            '未登录', '授权过期', 'login required', 'auth status')):
        return ExportError('AUTH',
                           '飞书授权已失效或未登录',
                           '请运行 lark-cli auth login 重新授权后重试；授权 URL 会附带二维码，手机扫码确认即可')

    # 权限类：scope 缺失 / permission denied
    if any(k in text for k in (
            'permission', 'forbidden', 'scope', '403', '99991672',
            '权限不足', 'AccessDenied', 'permission_denied')):
        return ExportError('PERM',
                           '飞书应用权限不足，无法创建云文档',
                           '请在飞书开放平台为应用补充 docx:document:create 等文档权限，或运行 lark-cli auth login --force 重新授权勾选新 scope')

    # 网络类：超时 / 连接失败 / DNS
    if any(k in text for k in (
            'timeout', 'timed out', 'network', 'ENOTFOUND', 'ECONNREFUSED',
            'ECONNRESET', 'ETIMEDOUT', 'fetch failed', 'socket', '网络')):
        return ExportError('NETWORK',
                           '网络异常，无法连接飞书服务',
                           '请检查网络连接后重试；已连续失败时可能是飞书服务波动，建议稍后再试')

    return ExportError('FAIL',
                       f'导出失败（exit={returncode}）',
                       (stderr_text or '').strip()[:500] or '请查看上方服务端返回信息')


# ==================== 授权检查 ====================

def check_auth():
    """检查 user 身份授权状态；返回 (ok, message)"""
    try:
        r = subprocess.run(['lark-cli', 'auth', 'status'],
                           capture_output=True, text=True, timeout=15)
    except FileNotFoundError:
        return False, '未找到 lark-cli，请先在 WorkBuddy 中连接飞书（feishu）connector'
    except subprocess.TimeoutExpired:
        return False, '授权状态检查超时，请稍后重试'

    out = r.stdout + r.stderr
    try:
        d = json.loads(out)
    except json.JSONDecodeError:
        return False, '无法解析授权状态，请运行 lark-cli auth status 排查'

    user = (d.get('identities') or {}).get('user') or {}
    if d.get('defaultAs') == 'user' and user.get('status') == 'ready':
        return True, f"已授权：{user.get('userName', 'user')}（token 状态 {user.get('tokenStatus')}）"

    if user.get('status') == 'ready' and user.get('tokenStatus') == 'valid':
        return True, f"已授权：{user.get('userName', 'user')}"

    if user.get('tokenStatus') in ('expired', 'invalid', 'refresh_failed'):
        return False, '飞书授权已过期，需要重新授权'

    return False, '飞书尚未登录或授权未完成'


def ensure_auth(interactive=True):
    """确保授权可用；interactive=True 时打印引导信息。抛出 ExportError(AUTH) 表示无法继续"""
    ok, msg = check_auth()
    if ok:
        if interactive:
            print(f'🔑 {msg}')
        return

    print(f'⚠️  {msg}')
    if not interactive:
        raise ExportError('AUTH', msg, '请运行 lark-cli auth login 完成授权')

    print('   即将发起重新授权（lark-cli auth login）...')
    print('   授权页会输出 URL 与二维码，请在浏览器/手机端完成确认。')
    try:
        r = subprocess.run(['lark-cli', 'auth', 'login'], timeout=180)
        ok2, msg2 = check_auth()
        if ok2:
            print(f'✅ 授权成功：{msg2}')
            return
        raise ExportError('AUTH',
                          '重新授权后仍未通过检查',
                          msg2)
    except subprocess.TimeoutExpired:
        raise ExportError('AUTH', '授权流程超时（180s）', '请重新运行导出命令完成扫码')
    except FileNotFoundError:
        raise ExportError('AUTH', '未找到 lark-cli', '请先连接飞书 connector')


# ==================== Markdown 预处理 ====================

def extract_title(md_text):
    """取第一个 H1 作为文档标题；无则用默认名"""
    m = re.search(r'^#\s+(.+?)\s*$', md_text, re.M)
    return m.group(1).strip() if m else 'PRD 导出文档'


def preprocess_markdown(md_text, base_dir):
    """飞书 Markdown 写入前的格式预处理，尽量保留原文格式。

    规则（依据 lark-doc-md.md 转义规范）：
    1. 本地图片路径 → 相对路径（lark-cli 只接受 cwd 内相对 @路径）
    2. 代码块内的内容不动（ fenced block 原样保留）
    3. 行首字面量符号无需额外转义 —— PRD 正文按 Markdown 语义写入，
       标题/列表/表格/加粗等由 --doc-format markdown 原生保留
    """
    lines = md_text.split('\n')
    out = []
    in_fence = False
    fence_re = re.compile(r'^(\s*)```')

    for ln in lines:
        if fence_re.match(ln):
            in_fence = not in_fence
            out.append(ln)
            continue
        if in_fence:
            out.append(ln)
            continue

        # 本地图片：![alt](images/xx.png) → ![alt](@images/xx.png)
        def _img(m):
            alt, p = m.group(1), m.group(2)
            if p.startswith(('http://', 'https://', '@', 'data:')):
                return m.group(0)
            # 绝对路径或相对路径 → 统一转成相对 cwd 的路径并加 @ 前缀
            ap = p if os.path.isabs(p) else os.path.join(base_dir or '.', p)
            rp = os.path.relpath(ap, os.getcwd())
            return f'![{alt}](@{rp})'
        out.append(re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _img, ln))

    return '\n'.join(out)


# ==================== 导出核心 ====================

def export_to_feishu(md_path, title=None, open_url=True, interactive=True):
    """将 md_path 导出为飞书在线文档，返回 dict(url, document_id, title)"""
    # 0) 授权前置检查
    ensure_auth(interactive=interactive)

    # 1) 读入 markdown
    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()
    if not md_text.strip():
        raise ExportError('FAIL', '源 Markdown 文件为空，无法导出')

    doc_title = title or extract_title(md_text)
    base_dir = os.path.dirname(os.path.abspath(md_path))

    # 2) 预处理（本地图片路径）
    content = preprocess_markdown(md_text, base_dir)
    if doc_title and not content.lstrip().startswith('# '):
        content = f'# {doc_title}\n\n' + content

    # 3) 落盘到临时文件（lark-cli @file 只接受 cwd 相对路径）
    tmp_name = '._feishu_export_tmp.md'
    with open(tmp_name, 'w', encoding='utf-8') as f:
        f.write(content)

    try:
        # 4) 调用 lark-cli docs +create
        cmd = ['lark-cli', 'docs', '+create',
               '--as', 'user',
               '--doc-format', 'markdown',
               '--content', f'@{tmp_name}',
               '--title', doc_title]
        print('⏳ 正在导出到飞书在线文档...')
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            raise ExportError('NETWORK', '飞书创建文档请求超时（120s）', '请检查网络后重试')

        out_json = {}
        try:
            out_json = json.loads(r.stdout)
        except (json.JSONDecodeError, TypeError):
            pass

        # 成功判定：ok == true（JSON 契约），或退出码 0 且拿到 document.url
        doc = ((out_json.get('data') or {}).get('document') or {})
        url = doc.get('url', '')
        if r.returncode == 0 and out_json.get('ok') and url:
            print(f'✅ 导出成功')
            print(f'📄 文档：{doc_title}')
            print(f'🔗 链接：{url}')
            for w in (out_json.get('data') or {}).get('warnings') or []:
                print(f'⚠️  服务端警告：{w}')

            if open_url:
                try:
                    webbrowser.open(url)
                    print('🌐 已自动打开文档链接')
                except (OSError, webbrowser.Error):
                    print('（自动打开失败，请手动点击上方链接）')
            return {'ok': True, 'url': url, 'document_id': doc.get('document_id'), 'title': doc_title}

        # 高风险确认门禁（退出码 10）不在此列；正常失败 → 分类抛错
        raise classify_error(r.stderr, r.returncode, out_json)

    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)


def export_with_retry(md_path, title=None, open_url=True, max_retries=MAX_RETRIES):
    """带自动重试的导出（NETWORK/FAIL 自动重试；AUTH/PERM 直接抛出引导）"""
    attempt = 0
    while True:
        try:
            return export_to_feishu(md_path, title=title, open_url=open_url)
        except ExportError as e:
            attempt += 1
            if e.category in RETRYABLE and attempt <= max_retries:
                wait = attempt * 2
                print(f'❌ {e.category} {e}——{wait}s 后第 {attempt}/{max_retries} 次重试...')
                print(f'   提示：{e.hint}') if e.hint else None
                time.sleep(wait)
                continue
            # 不可重试 / 重试耗尽 → 终态输出
            print()
            print(f'❌ 导出失败 [{e.category}]')
            print(f'   原因：{e}')
            if e.hint:
                print(f'   处理：{e.hint}')
            print('   重试：修正后重新运行本命令即可（已导出的内容不会重复创建失败文档）')
            sys.exit(2)


# ==================== Main ====================

def main():
    ap = argparse.ArgumentParser(description='导出 Markdown 为飞书在线文档')
    ap.add_argument('input', help='输入 Markdown 文件')
    ap.add_argument('--title', help='文档标题（默认取第一个 H1）')
    ap.add_argument('--no-open', action='store_true', help='导出成功后不自动打开链接')
    ap.add_argument('--no-retry', action='store_true', help='禁用自动重试')
    ap.add_argument('--quiet-auth', action='store_true', help='授权失败时不进入交互式登录流程')
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print(f'❌ 文件不存在：{args.input}')
        sys.exit(1)

    export_with_retry(args.input,
                      title=args.title,
                      open_url=not args.no_open,
                      max_retries=0 if args.no_retry else MAX_RETRIES)


if __name__ == '__main__':
    main()
