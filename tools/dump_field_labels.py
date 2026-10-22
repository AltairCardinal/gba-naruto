"""列出内容包里所有结构表的字段标签（按表分组），用来人工过一遍。"""
import json
import sys

pack = json.load(open("rom-editor/content/pack.json", encoding="utf-8"))
want = sys.argv[1] if len(sys.argv) > 1 else None

for s in pack["structures"]:
    if want and want not in s["id"]:
        continue
    fields = []
    for f in s["fields"]:
        desc = (f.get("desc") or "").replace("\n", " ")
        fields.append("%s|%s|%s" % (f["key"], f.get("label", ""), desc[:60]))
    print("### %s（%s）%d 条" % (s["id"], s["label"], len(fields)))
    for line in fields:
        print("   " + line)
    print()
