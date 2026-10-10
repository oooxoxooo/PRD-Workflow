#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""产物依赖与失效台账工具（零第三方依赖，Python 3.8+）。

在用户项目根目录下维护 .mask/manifest.json，记录每个产物的
{phase, producer, inputs, input_hashes, hash, status}，
为专家团主理人提供确定性操作；LLM 只负责语义裁决（重跑 / 豁免）：

  init      自愈初始化：确保 .mask/manifest.json 存在（幂等）
  register  登记产物：计算自身哈希与输入哈希快照（目录型产物按文件逐个展开）
  check     失效检查：重算输入哈希比对快照，不一致标 stale（级联）；退出码 0=全 fresh，1=有 stale
  refresh   重跑后重新登记：旧状态入 history（superseded），哈希刷新归 fresh
  exempt    人工裁决豁免：status 置 exempted，理由强制必填
  status    一行概览

用法：
  python3 manifest_cli.py <command> [--root DIR] [其他参数]

设计文档：《2026-10-10 mask-team 产物依赖与失效机制设计文档》（mask-team v2.3.0 引入）。
仅在团队编排（TeamCreate 后）启用；单点直调场景无并行下游，不使用本机制。
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

SCHEMA = "mask-manifest/1"
STATUSES = ("fresh", "stale", "exempted", "superseded")


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def file_hash(path):
    """sha256 前 12 位，带前缀；与 `shasum -a 256` 可复算口径一致。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()[:12]


def manifest_path(root):
    return root / ".mask" / "manifest.json"


def load(root):
    p = manifest_path(root)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        print("manifest.json 解析失败：%s" % e, file=sys.stderr)
        sys.exit(2)


def save(root, data):
    p = manifest_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure(root, slug=None):
    """自愈初始化：缺失则按空 schema 重建，返回 manifest 数据。"""
    data = load(root)
    if data is None:
        data = {
            "schema": SCHEMA,
            "slug": slug or root.resolve().name,
            "created_at": now_iso(),
            "artifacts": {},
        }
        save(root, data)
    return data


def expand_paths(root, rel):
    """目录型产物按文件逐个展开（排序、跳过隐藏文件与 .versions）；返回相对路径列表。"""
    target = root / rel
    if not target.exists():
        print("产物不存在：%s" % rel, file=sys.stderr)
        sys.exit(2)
    if target.is_file():
        return [rel]
    files = []
    for f in sorted(target.rglob("*")):
        if not f.is_file():
            continue
        r = f.relative_to(root).as_posix()
        parts = r.split("/")
        if any(p.startswith(".") for p in parts):
            continue
        files.append(r)
    if not files:
        print("目录产物为空（无可见文件）：%s" % rel, file=sys.stderr)
        sys.exit(2)
    return files


def snapshot_inputs(root, inputs):
    """对输入列表取当前哈希快照；输入文件不存在时报错退出（登记时上游必须已在盘上）。"""
    snaps = {}
    for rel in inputs:
        p = root / rel
        if not p.is_file():
            print("输入文件不存在，无法登记：%s" % rel, file=sys.stderr)
            sys.exit(2)
        snaps[rel] = file_hash(p)
    return snaps


def detect_prd_version(root, rel):
    """产物旁存在 .versions/vN/ 时取最大 N 作为版本标签；否则返回 None。"""
    versions_dir = (root / rel).parent / ".versions"
    if not versions_dir.is_dir():
        return None
    best = None
    for d in versions_dir.iterdir():
        if d.is_dir() and d.name.startswith("v") and d.name[1:].isdigit():
            n = int(d.name[1:])
            if best is None or n > best:
                best = n
    return "v%d" % best if best is not None else None


def cmd_init(args):
    data = ensure(args.root, args.slug)
    print("init: .mask/manifest.json 就绪（slug=%s，产物 %d 个）"
          % (data["slug"], len(data["artifacts"])))
    return 0


def cmd_register(args):
    data = ensure(args.root)
    inputs = [s.strip() for s in (args.inputs or "").split(",") if s.strip()]
    snaps = snapshot_inputs(args.root, inputs)
    count = 0
    for rel in expand_paths(args.root, args.path):
        entry = {
            "phase": args.phase,
            "producer": args.producer,
            "inputs": inputs,
            "input_hashes": dict(snaps),
            "hash": file_hash(args.root / rel),
            "status": "fresh",
            "registered_at": now_iso(),
        }
        ver = detect_prd_version(args.root, rel)
        if ver:
            entry["prd_version"] = ver
        old = data["artifacts"].get(rel)
        if old:  # 重复登记等价于 refresh：旧状态留痕
            entry.setdefault("history", []).append(
                dict(old, superseded_at=now_iso(), status="superseded"))
        data["artifacts"][rel] = entry
        count += 1
    save(args.root, data)
    print("register: %s → %d 个节点（phase=%s producer=%s inputs=%d）"
          % (args.path, count, args.phase, args.producer, len(inputs)))
    return 0


def compute_stale(root, data):
    """重算全部输入哈希并级联标记，返回 (stale_map, missing_map)。只读计算，不落盘。"""
    arts = data["artifacts"]
    stale = {}
    missing = {}
    for rel, e in arts.items():
        if e["status"] in ("superseded",):
            continue
        if not (root / rel).is_file():
            missing[rel] = "artifact_missing"
    # 级联至不动点：输入哈希变化或输入节点本身 stale 均导致 stale
    for _ in range(len(arts) + 1):
        changed = False
        for rel, e in arts.items():
            if rel in stale or rel in missing or e["status"] in ("superseded", "exempted"):
                continue
            for inp, old_hash in e.get("input_hashes", {}).items():
                p = root / inp
                if not p.is_file():
                    stale[rel] = "input_missing: %s" % inp
                    changed = True
                    break
                cur = file_hash(p)
                if cur != old_hash:
                    stale[rel] = "input_changed: %s (%s → %s)" % (inp, old_hash, cur)
                    changed = True
                    break
                if (inp in arts and arts[inp].get("status") == "stale") or inp in stale:
                    stale[rel] = "input_stale: %s" % inp
                    changed = True
                    break
        if not changed:
            break
    return stale, missing


def cmd_check(args):
    data = ensure(args.root)
    stale, missing = compute_stale(args.root, data)
    arts = data["artifacts"]
    for rel, reason in list(stale.items()) + list(missing.items()):
        e = arts[rel]
        if e["status"] != "stale" or e.get("stale_reason") != reason:
            e["status"] = "stale"
            e["stale_reason"] = reason
            e["stale_at"] = now_iso()
    if stale or missing:
        save(args.root, data)
    report = {rel: reason for rel, reason in
              list(stale.items()) + list(missing.items())}
    print(json.dumps({"stale": report, "count": len(report)},
                     ensure_ascii=False, indent=2))
    return 1 if report else 0


def cmd_refresh(args):
    data = ensure(args.root)
    e = data["artifacts"].get(args.path)
    if not e:
        print("未登记的产物：%s（请先 register）" % args.path, file=sys.stderr)
        return 2
    if not (args.root / args.path).is_file():
        print("产物不存在：%s" % args.path, file=sys.stderr)
        return 2
    old_snapshot = {k: v for k, v in e.items() if k != "history"}
    old_snapshot["status"] = "superseded"
    old_snapshot["superseded_at"] = now_iso()
    e.setdefault("history", []).append(old_snapshot)
    e["input_hashes"] = snapshot_inputs(args.root, e.get("inputs", []))
    e["hash"] = file_hash(args.root / args.path)
    e["status"] = "fresh"
    e.pop("stale_reason", None)
    e.pop("stale_at", None)
    e["registered_at"] = now_iso()
    ver = detect_prd_version(args.root, args.path)
    if ver:
        e["prd_version"] = ver
    save(args.root, data)
    print("refresh: %s → fresh（旧状态已入 history）" % args.path)
    return 0


def cmd_exempt(args):
    data = ensure(args.root)
    e = data["artifacts"].get(args.path)
    if not e:
        print("未登记的产物：%s" % args.path, file=sys.stderr)
        return 2
    if e["status"] != "stale":
        print("仅 stale 产物可豁免（当前 status=%s）" % e["status"], file=sys.stderr)
        return 2
    e["status"] = "exempted"
    e["exempt_reason"] = args.reason
    e["exempted_at"] = now_iso()
    save(args.root, data)
    print("exempt: %s → exempted（理由：%s）" % (args.path, args.reason))
    return 0


def cmd_status(args):
    data = ensure(args.root)
    counts = {s: 0 for s in STATUSES}
    for e in data["artifacts"].values():
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    print(" ".join("%s %d" % (s, counts[s]) for s in STATUSES if counts[s])
          or "（无产物）")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="mask-team 产物依赖与失效台账",
        usage="%(prog)s <command> [--root DIR] [参数]")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", type=Path, default=Path.cwd(), help="项目根目录（默认 cwd）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", parents=[common], help="自愈初始化")
    p.add_argument("--slug", default=None)
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("register", parents=[common], help="登记产物（目录按文件展开）")
    p.add_argument("path")
    p.add_argument("--phase", type=int, required=True)
    p.add_argument("--producer", required=True)
    p.add_argument("--inputs", default="", help="逗号分隔的上游相对路径")
    p.set_defaults(fn=cmd_register)

    p = sub.add_parser("check", parents=[common], help="失效检查（退出码 0=全 fresh，1=有 stale）")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("refresh", parents=[common], help="重跑后重新登记")
    p.add_argument("path")
    p.set_defaults(fn=cmd_refresh)

    p = sub.add_parser("exempt", parents=[common], help="人工裁决豁免（理由必填）")
    p.add_argument("path")
    p.add_argument("--reason", required=True)
    p.set_defaults(fn=cmd_exempt)

    p = sub.add_parser("status", parents=[common], help="一行概览")
    p.set_defaults(fn=cmd_status)

    args = ap.parse_args()
    args.root = args.root.resolve()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
