"""审计：内容包里的字段标签，哪些是占位符而不是游戏语义。

「属性A~F」「stat_a」「raw_05」「unused_01」这类标签，作者在界面上看不出
它是什么 —— 这跟「没有关联」是同一类毛病：界面替作者做了判断，
但断得没道理。

判据（保守，不猜）：
  * 标签里出现 stat_a / 属性A / raw_XX / unused / pad 之类占位；
  * 字段的 desc 为空或只说了「未解码」；
  * 同族字段（stat_x / stat_x_gain）没有一句说清它是什么。

**只看标签**（作者看到的那个词）：key 是内部标识符，写回路径按它找字段。

用法：python tools/audit_field_labels.py
"""
import collections
import json
import re
import sys

PACK = "rom-editor/content/pack.json"

# 明显是占位符的写法（**诚实的说法不算**：未解字节 / 未使用 / 填充 / 保留 / 标志）
PLACEHOLDER = re.compile(
    r"(stat_[a-f]\b|stat_[a-f]_gain|属性[A-F]|raw_[0-9a-f]+|unused|unknown|"
    r"padding|^pad$|^fill$|reserved|字节[0-9]|field[0-9])",
    re.IGNORECASE,
)
HONEST = re.compile(r"^(未解|未使用|填充|保留|标志|原始字节)")


def main() -> int:
    pack = json.load(open(PACK, encoding="utf-8"))
    structures = pack["structures"]

    print("=== 字段标签里带占位符的 ===")
    hits = []
    for s in structures:
        for f in s["fields"]:
            key = f.get("key", "")
            label = f.get("label", "")
            desc = f.get("desc", "") or ""
            # 只看**标签**（作者看到的那个词）。
            # key 是内部标识符（写回路径按它找字段），改不了也不该改。
            if not PLACEHOLDER.search(label):
                continue
            if HONEST.match(label):
                continue
            hits.append((s["id"], s["label"], key, label, desc))
    by_table = collections.defaultdict(list)
    for sid, slabel, key, label, desc in hits:
        by_table[sid].append((key, label, desc))
    for sid in sorted(by_table):
        s = next(x for x in structures if x["id"] == sid)
        print()
        print("  %s（%s）  %d 条" % (sid, s["label"], len(by_table[sid])))
        for key, label, desc in by_table[sid][:12]:
            print("     %-18s %-22s %s" % (key, label, (desc or "（没有说明）")[:46]))
        if len(by_table[sid]) > 12:
            print("     …还有 %d 个" % (len(by_table[sid]) - 12))

    print()
    print("=== 完全没有 desc 的字段（按表统计）===")
    no_desc = collections.Counter()
    for s in structures:
        n = sum(1 for f in s["fields"] if not (f.get("desc") or "").strip())
        if n:
            no_desc[s["id"]] = n
    for sid, n in no_desc.most_common(18):
        s = next(x for x in structures if x["id"] == sid)
        print("  %-26s %3d / %3d 个字段没有说明" % (sid, n, len(s["fields"])))
    print()
    print("共 %d 张结构表的字段带占位符标签" % len(by_table))
    return 0


if __name__ == "__main__":
    sys.exit(main())
