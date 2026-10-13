#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
voc_pipeline.py —— VoC 反馈材料确定性预处理脚本
（allan-team / skills/user-research，增强 B 的落地实现）

定位：本脚本只做**确定性预处理，语义洞察归 LLM**。
    脚本负责：清洗、去重、脱敏（隐私红线的技术兜底，不可逆）、
              主题词频聚类草稿、情感粗标、候选原声排序。
    脚本不做：语义聚类（无 embedding 依赖）、主题命名、洞察结论、联网抓取。
    themes.json / quotes.md 是**工作底稿**，不直接进最终报告；
    主题归并、money quotes 挑选、事实/解读分层均由 LLM 在草稿之上完成。

输入契约（三种格式按扩展名自动嗅探，无法识别时按内容兜底嗅探）：
    .csv    —— 需 --text-col 指定文本列（csv.DictReader 读取）
    .jsonl  —— 每行一个 JSON 对象，取 --text-col 字段（默认 "text"）
    .txt    —— 一行一条反馈

输出契约（写入 --out 目录，自动创建）：
    cleaned.jsonl —— 每行 {"id": int, "text": str, "redacted": [类别, ...]}
    themes.json   —— {"themes": {主题: {"count": n, "item_ids": [...],
                      "co_occurs_with": {主题: n}}},
                      "unmatched_ids": [...], "total": n}
    quotes.md     —— 候选原声库，按「负面强烈 / 正面强烈 / 中性高信息」三组，
                      每条带 id、情感分、逐字原文（已脱敏）

脱敏的取舍说明（重要）：
    手机号 / 身份证 / 邮箱 / 银行卡 / QQ 号用正则掩码，替换为占位符，不可逆。
    匹配顺序经过设计：邮箱 → 身份证（18 位）→ 银行卡（16-19 位）→ 手机号（11 位），
    避免长数字串被短规则抢先切碎；QQ 号要求上下文 ±12 字符内出现 QQ/qq 字样才掩码，
    避免误伤普通数字。
    **中文姓名不做正则猜测**（"王伟""李娜"与正常文本无法可靠区分，误报率太高），
    改为可选 --names names.txt（一行一个姓名，精确替换为 [姓名]）。
    脚本脱敏是兜底而非免责：LLM 在报告中仍须人工复查无个人信息残留。

词表加载优先级：
    主题词表：--themes 指定 > 内置通用词表（10 个通用主题）。
    情感词表：--lexicon 指定 > 当前工作目录 research/lexicon-zh.txt（项目级覆盖）
              > 包内 assets/sentiment-lexicon-zh.txt。
    主题词表格式：「主题: 词1, 词2, 词3」（支持中文冒号与顿号）；
    情感词表格式：「词<TAB>分数」，分数 -3 到 +3。

运行环境：纯标准库，Python 3.8+，跨平台；所有文件读写显式 utf-8 / errors=replace。
"""

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 内置通用主题词表（--themes 未指定时使用；草稿级，LLM 在其上做语义归并）
# ---------------------------------------------------------------------------
BUILTIN_THEMES = {
    "价格": ["价格", "收费", "贵", "便宜", "免费", "付费", "会员费", "性价比"],
    "质量": ["质量", "做工", "bug", "漏洞", "错误", "准确"],
    "物流交付": ["物流", "发货", "快递", "交付", "到货", "延迟"],
    "客服": ["客服", "回复", "态度", "人工客服", "投诉"],
    "界面体验": ["界面", "UI", "排版", "美观", "颜值", "设计"],
    "功能": ["功能", "支持", "缺少", "新增", "导出", "需求"],
    "性能稳定性": ["卡顿", "闪退", "崩溃", "加载", "速度", "稳定", "卡死"],
    "售后": ["售后", "退款", "退货", "维修", "保修"],
    "隐私安全": ["隐私", "安全", "泄露", "权限", "个人信息", "被盗"],
    "易用性": ["上手", "易用", "难用", "操作", "步骤", "复杂", "简单", "方便"],
}

# ---------------------------------------------------------------------------
# 脱敏正则（顺序即优先级：先长后短，先特殊后一般）
# ---------------------------------------------------------------------------
RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RE_IDCARD = re.compile(r"\d{17}[\dXx]")          # 18 位身份证，末位可为 X/x
RE_BANKCARD = re.compile(r"\d{16,19}")           # 16-19 位连续数字（须在身份证之后匹配）
RE_PHONE = re.compile(r"1[3-9]\d{9}")            # 手机号
RE_QQ_DIGITS = re.compile(r"\d{5,11}")           # QQ 候选，需上下文确认
RE_QQ_CONTEXT = re.compile(r"QQ|qq|Qq|qQ|ＱＱ")   # QQ 上下文关键词

# 信息密度启发用信号词
DENSITY_SIGNAL_WORDS = ("因为", "但是", "希望", "建议", "其实", "每次")


# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------
def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="VoC 反馈材料确定性预处理：清洗 → 脱敏 → 主题聚类草稿 → 候选原声。"
                    "本脚本只做确定性预处理，语义洞察归 LLM。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python3 voc_pipeline.py --input feedback.csv --text-col content --out voc/\n"
            "  python3 voc_pipeline.py --input feedback.jsonl --out voc/ --themes themes.txt\n"
            "\n"
            "脱敏说明：手机号/身份证/邮箱/银行卡/QQ 号走正则掩码；中文姓名不做正则猜测\n"
            "（误报太高），请用 --names names.txt（一行一个姓名）做精确替换。"
        ),
    )
    parser.add_argument("--input", required=True,
                        help="输入文件路径，支持 .csv / .jsonl / .txt（自动嗅探）")
    parser.add_argument("--text-col", default=None,
                        help="文本列名：.csv 必填；.jsonl 默认为 \"text\"；.txt 忽略此参数")
    parser.add_argument("--out", required=True,
                        help="输出目录（自动创建），产出 cleaned.jsonl / themes.json / quotes.md")
    parser.add_argument("--themes", default=None,
                        help="主题词表文件，格式「主题: 词1, 词2」；缺省用内置通用词表")
    parser.add_argument("--lexicon", default=None,
                        help="情感词表文件，格式「词<TAB>分数(-3~+3)」；"
                             "缺省依次尝试 ./research/lexicon-zh.txt 与包内 assets 词表")
    parser.add_argument("--names", default=None,
                        help="可选：姓名清单（一行一个），精确替换为 [姓名]；"
                             "中文姓名不做正则猜测以避免误报")
    parser.add_argument("--top-quotes", type=int, default=20,
                        help="quotes.md 候选原声总条数上限（默认 20）")
    parser.add_argument("--min-len", type=int, default=5,
                        help="短于该字符数的条目视为无信息量丢弃（默认 5）")
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# 输入读取：按扩展名嗅探，未知扩展名按内容兜底
# ---------------------------------------------------------------------------
def sniff_format(path, first_line):
    """返回 'csv' / 'jsonl' / 'txt'。"""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix in (".jsonl", ".ndjson"):
        return "jsonl"
    if suffix == ".txt":
        return "txt"
    # 兜底：按首行内容猜测
    stripped = first_line.strip()
    if stripped.startswith("{"):
        return "jsonl"
    if "," in stripped or "\t" in stripped:
        return "csv"
    return "txt"


def load_input(args):
    """读取输入文件，返回原始文本条目列表（未清洗）。"""
    path = Path(args.input)
    if not path.is_file():
        sys.stderr.write("错误：输入文件不存在：%s\n" % path)
        sys.exit(1)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    lines = content.splitlines()
    first_line = next((ln for ln in lines if ln.strip()), "")
    fmt = sniff_format(path, first_line)

    texts = []
    if fmt == "csv":
        text_col = args.text_col
        if not text_col:
            sys.stderr.write("错误：.csv 输入必须用 --text-col 指定文本列名\n")
            sys.exit(2)
        reader = csv.DictReader(lines)
        if reader.fieldnames is None or text_col not in reader.fieldnames:
            sys.stderr.write("错误：CSV 中不存在列 \"%s\"，实际列：%s\n"
                             % (text_col, reader.fieldnames))
            sys.exit(2)
        for row in reader:
            texts.append(row.get(text_col) or "")
    elif fmt == "jsonl":
        text_col = args.text_col or "text"
        for i, ln in enumerate(lines, 1):
            if not ln.strip():
                continue
            try:
                obj = json.loads(ln)
            except json.JSONDecodeError:
                sys.stderr.write("警告：第 %d 行不是合法 JSON，已跳过\n" % i)
                continue
            texts.append(str(obj.get(text_col) or ""))
    else:  # txt：一行一条
        texts.extend(lines)
    return texts


# ---------------------------------------------------------------------------
# 清洗：strip、去空、长度过滤、归一化哈希去重
# ---------------------------------------------------------------------------
def normalize_for_hash(text):
    """去标点空白转小写后的归一化串，用于去重哈希。"""
    return "".join(ch for ch in text.lower() if ch.isalnum())


def clean_items(raw_texts, min_len):
    """返回 (清洗后条目列表, 空条目数, 过短丢弃数, 重复丢弃数)。"""
    items = []
    seen = set()
    n_empty = n_short = n_dup = 0
    for raw in raw_texts:
        text = raw.strip()
        if not text:
            n_empty += 1
            continue
        if len(text) < min_len:
            n_short += 1
            continue
        digest = hashlib.sha1(
            normalize_for_hash(text).encode("utf-8", errors="replace")
        ).hexdigest()[:16]
        if digest in seen:
            n_dup += 1
            continue
        seen.add(digest)
        items.append(text)
    return items, n_empty, n_short, n_dup


# ---------------------------------------------------------------------------
# 脱敏：正则掩码，不可逆。顺序：邮箱 → 身份证 → 银行卡 → 手机号 → QQ → 姓名
# ---------------------------------------------------------------------------
def _sub_count(pattern, repl, text):
    """替换并返回 (新文本, 命中次数)。"""
    new_text, n = pattern.subn(repl, text)
    return new_text, n


def redact_text(text, names):
    """返回 (脱敏后文本, 命中的脱敏类别列表)。"""
    hits = []

    # 1. 邮箱（最先，避免其中数字段被后续规则切碎）
    text, n = _sub_count(RE_EMAIL, "[邮箱]", text)
    if n:
        hits.append("邮箱")

    # 2. 身份证（18 位，必须先于银行卡匹配，否则会被 16-19 位规则吃掉）
    text, n = _sub_count(RE_IDCARD, "[证件号]", text)
    if n:
        hits.append("证件号")

    # 3. 银行卡（16-19 位连续数字）
    text, n = _sub_count(RE_BANKCARD, "[卡号]", text)
    if n:
        hits.append("卡号")

    # 4. 手机号（11 位）
    text, n = _sub_count(RE_PHONE, "[手机号]", text)
    if n:
        hits.append("手机号")

    # 5. QQ 号（5-11 位，仅当上下文 ±12 字符内出现 QQ/qq 字样才掩码）
    qq_hit = [False]

    def _qq_repl(match):
        start, end = match.start(), match.end()
        window = text[max(0, start - 12):min(len(text), end + 12)]
        if RE_QQ_CONTEXT.search(window):
            qq_hit[0] = True
            return "[QQ号]"
        return match.group(0)

    text = RE_QQ_DIGITS.sub(_qq_repl, text)
    if qq_hit[0]:
        hits.append("QQ号")

    # 6. 姓名（可选清单精确替换，长名优先避免部分覆盖；不做正则猜测）
    if names:
        name_hit = False
        for name in sorted(names, key=len, reverse=True):
            if name and name in text:
                text = text.replace(name, "[姓名]")
                name_hit = True
        if name_hit:
            hits.append("姓名")

    return text, hits


# ---------------------------------------------------------------------------
# 主题词表加载与命中统计
# ---------------------------------------------------------------------------
def load_themes(themes_path):
    """加载主题词表；文件格式「主题: 词1, 词2, 词3」，# 开头为注释。"""
    if not themes_path:
        return dict(BUILTIN_THEMES)
    path = Path(themes_path)
    if not path.is_file():
        sys.stderr.write("错误：主题词表文件不存在：%s\n" % path)
        sys.exit(1)
    themes = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, ln in enumerate(f, 1):
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            # 支持中英文冒号
            m = re.split(r"[:：]", ln, maxsplit=1)
            if len(m) != 2:
                sys.stderr.write("警告：主题词表第 %d 行缺少冒号，已跳过：%s\n" % (i, ln))
                continue
            theme = m[0].strip()
            words = [w.strip() for w in re.split(r"[,，、]", m[1]) if w.strip()]
            if theme and words:
                themes.setdefault(theme, []).extend(words)
    if not themes:
        sys.stderr.write("警告：主题词表为空，回退到内置通用词表\n")
        return dict(BUILTIN_THEMES)
    return themes


def analyze_themes(items, themes):
    """子串匹配统计主题命中与共现，返回 themes.json 的数据结构。"""
    result = {
        theme: {"count": 0, "item_ids": [], "co_occurs_with": {}}
        for theme in themes
    }
    unmatched = []
    for item in items:
        text = item["text"]
        hit_themes = [theme for theme, words in themes.items()
                      if any(w in text for w in words)]
        if not hit_themes:
            unmatched.append(item["id"])
            continue
        for theme in hit_themes:
            entry = result[theme]
            entry["count"] += 1
            entry["item_ids"].append(item["id"])
        # 两两共现（同一条目内同时命中计 1 次，不含自身）
        for a in hit_themes:
            for b in hit_themes:
                if a != b:
                    co = result[a]["co_occurs_with"]
                    co[b] = co.get(b, 0) + 1
    # 删除零命中主题，保持输出紧凑
    result = {t: v for t, v in result.items() if v["count"] > 0}
    return {
        "themes": result,
        "unmatched_ids": unmatched,
        "total": len(items),
    }


# ---------------------------------------------------------------------------
# 情感词表加载与粗标
# ---------------------------------------------------------------------------
def load_lexicon(args):
    """按优先级加载情感词表：--lexicon > ./research/lexicon-zh.txt > 包内 assets。"""
    candidates = []
    if args.lexicon:
        candidates.append(Path(args.lexicon))
    else:
        candidates.append(Path.cwd() / "research" / "lexicon-zh.txt")
        # 包内词表：scripts/ 的上一级 assets/
        candidates.append(
            Path(__file__).resolve().parent.parent
            / "assets" / "sentiment-lexicon-zh.txt"
        )
    for path in candidates:
        if path.is_file():
            lexicon = {}
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln or ln.startswith("#"):
                        continue
                    parts = ln.split("\t") if "\t" in ln else ln.split()
                    if len(parts) < 2:
                        continue
                    try:
                        lexicon[parts[0].strip()] = int(parts[1].strip())
                    except ValueError:
                        continue
            sys.stderr.write("情感词表：%s（%d 词）\n" % (path, len(lexicon)))
            return lexicon
    sys.stderr.write("警告：未找到情感词表，情感分全部记 0\n")
    return {}


def sentiment_score(text, lexicon):
    """情感分 = 命中词分数按出现次数求和。"""
    score = 0
    for word, val in lexicon.items():
        if word and word in text:
            score += val * text.count(word)
    return score


def info_density(text):
    """信息密度启发分：长度适中、含数字、含因果/转折/建议类信号词加分。"""
    score = 1
    if 20 <= len(text) <= 200:
        score += 2
    if any(ch.isdigit() for ch in text):
        score += 1
    if any(w in text for w in DENSITY_SIGNAL_WORDS):
        score += 1
    return score


def pick_quotes(items, lexicon, top_n):
    """按 强度×密度 排序，分三组挑选候选原声，返回 {组名: [(item, score, rank), ...]}。"""
    scored = []
    for item in items:
        s = sentiment_score(item["text"], lexicon)
        density = info_density(item["text"])
        rank = abs(s) * density
        scored.append((item, s, density, rank))

    neg = sorted((x for x in scored if x[1] < 0), key=lambda x: x[3], reverse=True)
    pos = sorted((x for x in scored if x[1] > 0), key=lambda x: x[3], reverse=True)
    # 中性组按信息密度排序（强度为 0，密度即区分度）
    neu = sorted((x for x in scored if x[1] == 0), key=lambda x: x[2], reverse=True)

    # 名额分配：负/正各约 40%，其余给中性，保证三组都有机会出镜
    neg_q = max(1, top_n * 2 // 5)
    pos_q = max(1, top_n * 2 // 5)
    neu_q = max(1, top_n - neg_q - pos_q)
    return {
        "负面强烈": neg[:neg_q],
        "正面强烈": pos[:pos_q],
        "中性高信息": neu[:neu_q],
    }


def render_quotes_md(groups):
    lines = [
        "# 候选原声库（voc_pipeline 自动生成）",
        "",
        "> 本文件是**工作底稿**：已脱敏、已按「情感强度 × 信息密度」粗排。",
        "> money quotes 的最终挑选与逐字核对由 LLM 完成；引用时保留原样，禁止润色改写。",
        "",
    ]
    for group_name, entries in groups.items():
        lines.append("## %s" % group_name)
        lines.append("")
        if not entries:
            lines.append("（本组无候选）")
        for item, score, density, rank in entries:
            lines.append("- id=%d | 情感分=%+d | 信息密度=%d | 排序分=%d"
                         % (item["id"], score, density, rank))
            lines.append("  > %s" % item["text"])
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main(argv=None):
    args = parse_args(argv)

    # 1. 读取输入
    raw_texts = load_input(args)
    n_input = len(raw_texts)

    # 2. 清洗（去空 / 长度过滤 / 去重）
    cleaned, n_empty, n_short, n_dup = clean_items(raw_texts, args.min_len)

    # 3. 脱敏（一票否决环节，不可跳过）
    names = []
    if args.names:
        names_path = Path(args.names)
        if not names_path.is_file():
            sys.stderr.write("错误：姓名清单不存在：%s\n" % names_path)
            sys.exit(1)
        with open(names_path, "r", encoding="utf-8", errors="replace") as f:
            names = [ln.strip() for ln in f if ln.strip()]
    items = []
    n_redacted = 0
    for i, text in enumerate(cleaned, 1):
        redacted_text, hits = redact_text(text, names)
        if hits:
            n_redacted += 1
        items.append({"id": i, "text": redacted_text, "redacted": hits})

    # 4. 主题聚类草稿
    themes = load_themes(args.themes)
    themes_data = analyze_themes(items, themes)

    # 5. 情感粗标 + 候选原声
    lexicon = load_lexicon(args)
    groups = pick_quotes(items, lexicon, args.top_quotes)

    # 6. 落盘三个产物
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    cleaned_path = out_dir / "cleaned.jsonl"
    with open(cleaned_path, "w", encoding="utf-8", errors="replace") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    themes_path = out_dir / "themes.json"
    with open(themes_path, "w", encoding="utf-8", errors="replace") as f:
        json.dump(themes_data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    quotes_path = out_dir / "quotes.md"
    with open(quotes_path, "w", encoding="utf-8", errors="replace") as f:
        f.write(render_quotes_md(groups))

    # 7. stderr 汇总
    theme_counts = " ".join(
        "%s=%d" % (t, v["count"]) for t, v in themes_data["themes"].items()
    ) or "（无命中）"
    sys.stderr.write(
        "汇总：输入 %d 条 | 空条目丢弃 %d | 过短丢弃 %d | 去重丢弃 %d | "
        "脱敏命中 %d 条 | 主题命中: %s | 未匹配 %d 条\n"
        % (n_input, n_empty, n_short, n_dup, n_redacted,
           theme_counts, len(themes_data["unmatched_ids"]))
    )
    sys.stderr.write("产物：%s | %s | %s\n" % (cleaned_path, themes_path, quotes_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
