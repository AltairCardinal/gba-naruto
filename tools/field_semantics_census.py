"""仓库里所有「完成度宣称」的清单 + 与机器事实的对照（2026-10-22）

这个工具回答一个问题：**仓库里的文档/笔记/提交信息有没有在宣称
「全部闭合」，而内容包里其实还有未解字段**。

它做三件事：

1. **机器事实**：读内容包，按「标签口径」与「说明口径」把**仍未解语义**的字段列出来
   （并按字段定义去重 —— 90 张音频表共用同两个字段，不该算成 180 条）；
2. **宣称清单**：扫 `docs/`、`notes/`、`README.md`、`AGENTS.md`，
   找出带完成度口吻的句子（清零 / 全部闭合 / 100% / 无未完成 / 缺口 0 …）；
3. **对照**：把两者并排打出来，供人逐条核对。

用法::

    python tools/field_semantics_census.py
    python tools/field_semantics_census.py --json build/field-census.json
    python tools/field_semantics_census.py --claims-only
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
PACK = REPO / "rom-editor" / "content" / "pack.json"

# Windows 控制台默认 GBK，印不出「−」「✓」这类字符 —— 换成 UTF-8 并兜底。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

# 标签口径：标签本身就承认「这格还没解」。
LABEL_PATTERNS = (
    re.compile(r"^未解字节"),
    re.compile(r"^未知"),
    re.compile(r"^字节\d"),
    re.compile(r"^未解"),
)
# 说明口径：标签有名字，但说明里承认语义没定。
DESC_PATTERNS = (
    re.compile(r"语义未解"),
    re.compile(r"语义未定"),
    re.compile(r"语义不明"),
    re.compile(r"尚未解码"),
    re.compile(r"未证实"),
    re.compile(r"未解"),
    re.compile(r"没���证明"),
    re.compile(r"没有一处证明"),
)

# 完成度宣称：这些句子是最容易「说过头」的地方。
CLAIM_PATTERNS = (
    re.compile(r"全部闭合"),
    re.compile(r"已清零"),
    re.compile(r"清零"),
    re.compile(r"没有未完成"),
    re.compile(r"无未完成"),
    re.compile(r"100\s*%"),
    re.compile(r"全部.*(完成|定案|证明)"),
    re.compile(r"缺口\s*0"),
    re.compile(r"零缺口"),
    re.compile(r"全部定案"),
    re.compile(r"已全部"),
    re.compile(r"全部达成"),
)
# 明确是「历史/更正/否定」语境的句子，不算宣称。
NEGATION = re.compile(
    r"(作废|不再|旧|曾|曾经|曾经说|更正|误|错|没有|不是|并非|未达成|没达成|"
    r"⚠|已取代|被取代|之前|上一轮|上一版|曾经是|≠|避免|防止|不得|不能|"
    r"不成立|不采信|不可|不要|不应|不够|欠缺)"
)


def load_pack() -> dict:
    return json.loads(PACK.read_text(encoding="utf-8"))


def census(pack: dict) -> dict:
    """内容包里仍未解语义的字段（按字段定义去重）。"""
    defs: dict[tuple, dict] = {}
    for s in pack.get("structures") or []:
        for f in s.get("fields") or []:
            label = str(f.get("label") or "")
            desc = str(f.get("desc") or "")
            why = []
            if any(p.search(label) for p in LABEL_PATTERNS):
                why.append("标签")
            if any(p.search(desc) for p in DESC_PATTERNS):
                why.append("说明")
            if not why:
                continue
            key = (label, desc)
            entry = defs.setdefault(key, {
                "label": label,
                "offset": f.get("offset"),
                "size": f.get("size"),
                "why": why,
                "structures": [],
            })
            entry["structures"].append(s.get("id"))
    return defs


def claims() -> list[dict]:
    """扫文档与笔记里的完成度宣称。"""
    roots = [REPO / "docs", REPO / "notes"]
    files = [REPO / "README.md", REPO / "AGENTS.md"]
    for root in roots:
        if root.is_dir():
            files += sorted(root.rglob("*.md"))
    out = []
    for path in files:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if not any(p.search(line) for p in CLAIM_PATTERNS):
                continue
            out.append({
                "file": str(path.relative_to(REPO)).replace("\\", "/"),
                "line": lineno,
                "text": line.strip()[:200],
                "negated": bool(NEGATION.search(line)),
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--claims-only", action="store_true")
    args = ap.parse_args()

    pack = load_pack()
    defs = census(pack)

    if not args.claims_only:
        print(f"内容包里仍未解语义的字段定义：{len(defs)} 个"
              f"（分布在 {len({s for d in defs.values() for s in d['structures']})} 张表）")
        print()
        for d in sorted(defs.values(), key=lambda x: (x["structures"][0], x["offset"] or 0)):
            owner = d["structures"][0]
            print(f"  [{'/'.join(d['why'])}] {owner} +0x{(d['offset'] or 0):02X} "
                  f"「{d['label']}」 —— 同样定义出现在 {len(d['structures'])} 张表")
        print()

    claim_rows = claims()
    active = [c for c in claim_rows if not c["negated"]]
    print(f"文档/笔记里的完成度宣称：{len(claim_rows)} 句"
          f"（其中 {len(active)} 句**没有**否定/更正语境，需要逐条核对）")
    print()
    for c in active:
        print(f"  {c['file']}:{c['line']}")
        print(f"      {c['text']}")
    print()
    print("（带 ⚠ 的那些是历史/更正语境 —— 见每行前的标记）")

    if args.json_out:
        pathlib.Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.json_out).write_text(json.dumps({
            "unresolved_field_defs": list(defs.values()),
            "claims": claim_rows,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"写出 {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
