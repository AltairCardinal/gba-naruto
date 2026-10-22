"""审计：内容包里的跨表关联现状。

界面上的「来源 / 被谁引用」完全由内容包驱动，所以这里查的是**内容包侧**
还差什么：

  * 哪些字段声明了跨表关系（relation），分别是哪种关系；
  * 哪些表之间共享同一个 id 空间（`id_relation`）；
  * 哪些表之间是「同一件事的两份记录」（`peers`）；
  * 哪些表有原生读者（`consumers`）。

界面上每条记录能不能溯源，由 `rom-editor/tools/verify_sources.mjs` 断言
（它跑的是真正的前端引擎）。

用法：python tools/audit_crossrefs.py
"""
import collections
import json
import sys

PATH = "rom-editor/content/pack.json"


def main() -> int:
    pack = json.load(open(PATH, encoding="utf-8"))
    structures = pack["structures"]
    texts = pack["texts"]

    # --- 1. 字段声明的关系 ------------------------------------------------
    kinds = collections.Counter()
    targets = collections.defaultdict(list)
    for s in structures:
        for f in s["fields"]:
            rel = f.get("relation")
            if not rel:
                continue
            kinds[rel.get("kind", "?")] += 1
            table = rel.get("table")
            if table:
                targets[table].append("%s.%s" % (s["id"], f["key"]))
            for extra in rel.get("tables", []) or []:
                targets[extra].append("%s.%s" % (s["id"], f["key"]))

    print("=== 字段关系（界面据此渲染下拉与跳转）===")
    for kind, n in sorted(kinds.items()):
        print("  %-14s %4d 个字段" % (kind, n))
    print()
    print("=== 被指向的表 ===")
    for table in sorted(targets):
        print("  %-26s <- %3d 处  例：%s" % (table, len(targets[table]), targets[table][0]))

    # --- 2. id 空间 ------------------------------------------------------
    print()
    print("=== 共享同一个 id 的表 ===")
    groups = collections.defaultdict(set)
    for s in structures:
        rel = s.get("id_relation")
        if not rel or not rel.get("table"):
            continue
        groups[rel["table"]].add(s["id"])
        groups[rel["table"]].add(rel["table"])
    for table in sorted(groups):
        members = sorted(groups[table])
        if len(members) > 1:
            print("  %-26s %s" % (table, "、".join(members)))

    # --- 3. 同键对应 -----------------------------------------------------
    print()
    print("=== 同一件事在另一张表里的对应记录 ===")
    for s in structures:
        for peer in s.get("peers", []) or []:
            print("  %-24s <-> %-22s by %s" % (s["id"], peer.get("table"), peer.get("by")))

    # --- 4. 原生读者 -----------------------------------------------------
    print()
    print("=== 有原生读者的表 ===")
    with_consumers = [s for s in structures if s.get("consumers")]
    for t in texts:
        if t.get("consumers"):
            with_consumers.append(t)
    print("  %d 张表写出了原生读者地址" % len(with_consumers))
    missing = [s["id"] for s in structures if not s.get("consumers")]
    if missing:
        print("  没有原生读者的结构表：%s" % "、".join(missing))

    print()
    print("=== 总量 ===")
    print("  %d 张结构表 / %d 条记录" % (len(structures), sum(len(s["records"]) for s in structures)))
    print("  %d 张文本表 / %d 条文本" % (len(texts), sum(t["count"] for t in texts)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
