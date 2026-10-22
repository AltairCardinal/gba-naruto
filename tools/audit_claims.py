"""完成度宣称的机器核对（2026-10-22）

**为什么要有这个工具**
----------------------
2026-10-22 上一轮提交写「所有 L2 / L3 / 文档 / 语义 / 证据类缺口已清零」，
而同一时刻内容包里忍具记录表那 16 格**全是**「未解字节 +0xNN」。
用户在编辑器里一眼就看出来了 —— 文档的宣称和**机器事实**对不上。

这个工具把那条链补上：

1. **机器事实**：内容包里还标着「未解字节/未知/字节NN」的字段有多少、在哪；
   审计（`tools/completion_audit.py`）算出来的缺口条数。
2. **宣称清单**：扫 `docs/`、`notes/`、`README.md`，
   找出「**语义/字段类缺口已清零**」这类**断言语义面已闭合**的句子。
3. **对照**：宣称存在时，机器事实必须也支持它 —— 否则**退出码非 0**。

用法::

    python tools/audit_claims.py
    python tools/audit_claims.py --json build/claims-audit.json

退出码：0 = 宣称与事实一致；1 = 有宣称与事实冲突（并打印冲突清单）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
PACK = REPO / "rom-editor" / "content" / "pack.json"
AUDIT_JSON = REPO / "build" / "completion-audit.json"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

# 「这个字段是什么我不知道」的标签写法
UNKNOWN_LABEL = re.compile(r"^(未解字节|未知\w*|字节\d)")

# 断言「语义/字段这一面已经闭合」的句子。
# 注意只收**明确断言语义面**的句子；「结构已证明」「格式已证明」不在此列。
SEMANTIC_CLOSED = re.compile(
    r"(语义|字段)[^。\n]{0,12}缺口[^。\n]{0,12}清零|"
    r"缺口[^。\n]{0,20}语义[^。\n]{0,20}清零|"
    r"(语义|字段)类缺口已清零|"
    r"所有[^。\n]{0,20}语义[^。\n]{0,20}清零"
)
# 明确是「更正 / 历史 / 否定」语境的句子不算断言。
NEGATION = re.compile(
    r"(作废|不再|更正|误|错|没有|不是|并非|未达成|⚠|已取代|被取代|"
    r"上一轮|上一版|之前|曾经|≠|不得|不能|不成立|不采信|不可|不要|不应|"
    r"欠|缺$|以本文|见第|本节|本文)"
)
# **元叙述**：这些行是在**谈论**那个说法（写门禁、写口径、列清单），
# 不是在断言它。把它们当成断言会让门禁自己咬自己。
META = re.compile(
    r"(门禁|口径|工具|检查|核对|清单|宣称|断言|不能再|不许|"
    r"不成立|不采信|若|如果|例如|比如|即|以及|写进|写清|盯着)"
)
# 说法被引号包起来 ⇒ 也是在谈论它。
QUOTED = re.compile(r"[「『\"“][^」』\"”]{0,40}语义[^」』\"”]{0,40}清零")


def pack_unresolved() -> list[dict]:
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    out = []
    for s in pack.get("structures") or []:
        for f in s.get("fields") or []:
            label = str(f.get("label") or "")
            if UNKNOWN_LABEL.match(label):
                out.append({
                    "structure": s.get("id"),
                    "label": s.get("label"),
                    "rom": s.get("rom_offset"),
                    "field": f.get("key"),
                    "offset": f.get("offset"),
                    "size": f.get("size"),
                    "field_label": label,
                })
    return out


def claims() -> list[dict]:
    files = [REPO / "README.md", REPO / "AGENTS.md"]
    for root in (REPO / "docs", REPO / "notes"):
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
            if not SEMANTIC_CLOSED.search(line):
                continue
            if NEGATION.search(line) or META.search(line) or QUOTED.search(line):
                continue
            out.append({
                "file": str(path.relative_to(REPO)).replace("\\", "/"),
                "line": lineno,
                "text": line.strip()[:240],
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args()

    unresolved = pack_unresolved()
    claim_rows = claims()

    print(f"机器事实：内容包里还标着「未解字节/未知/字节NN」的字段 {len(unresolved)} 处")
    for u in unresolved:
        print(f"  {u['structure']:<22} {u['field_label']}（{u['size']} 字节）")
    print()
    print(f"文档里的「语义/字段类缺口已清零」断言：{len(claim_rows)} 句")
    for c in claim_rows:
        print(f"  {c['file']}:{c['line']}")
        print(f"      {c['text']}")
    print()

    problems: list[str] = []
    if claim_rows and unresolved:
        for c in claim_rows:
            problems.append(
                f"{c['file']}:{c['line']} 断言「语义/字段类缺口已清零」，"
                f"但内容包里还有 {len(unresolved)} 处未解字段")

    if problems:
        print("宣称与事实冲突：")
        for p in problems:
            print(f"  FAIL {p}")
        print()
        print("处理办法二选一：")
        print("  a) 把这些字段定案（读者普查 → 给名字或证明原生不读）")
        print("  b) 把这句宣称改成**如实**的写法（写清还剩几处、卡在哪）")
        if args.json_out:
            pathlib.Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
            pathlib.Path(args.json_out).write_text(json.dumps({
                "unresolved": unresolved, "claims": claim_rows, "problems": problems,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"写出 {args.json_out}")
        return 1

    print("宣称与事实一致：没有「语义面已闭合」的说法压着未解字段。")
    if args.json_out:
        pathlib.Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.json_out).write_text(json.dumps({
            "unresolved": unresolved, "claims": claim_rows, "problems": [],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"写出 {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
