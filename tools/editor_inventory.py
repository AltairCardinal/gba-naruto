#!/usr/bin/env python3
"""Inventory of everything the ROM editor can edit.

One line per editable table: where it lives, how big it is, which fields the
author actually fills in, and — importantly — which of those fields are
"unknown byte" filler that the generic editor currently presents exactly like
a meaningful field.

This is the reference the interaction redesign works from: it is the list of
*editing functions* the editor exposes.

Usage:
    python tools/editor_inventory.py            # human-readable
    python tools/editor_inventory.py --json     # machine-readable
    python tools/editor_inventory.py --domain battle
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / "rom-editor" / "content" / "pack.json"

# Which module a table belongs to, and what a user would call that kind of
# editing.  Kept here so the inventory reads like a task list, not a dump.
DOMAIN_LABELS = {
    "story": "剧情与对白",
    "items": "道具",
    "characters": "角色属性与技能",
    "ninjutsu": "忍术",
    "battle": "战斗",
    "route": "剧情路线",
    "audio": "音频",
    "assets": "素材与资源",
}


def load_pack() -> dict:
    if not PACK.exists():
        print(f"找不到内容包：{PACK}\n先跑 python tools/export_content_pack.py", file=sys.stderr)
        raise SystemExit(2)
    return json.loads(PACK.read_text(encoding="utf-8"))


def describe(pack: dict) -> dict:
    structures = []
    for s in pack["structures"]:
        fields = s["fields"]
        known = [f for f in fields if f["type"] != "hex"]
        filler = [f for f in fields if f["type"] == "hex"]
        groups: dict[str, list[str]] = {}
        for f in known:
            groups.setdefault(f.get("group") or "未分组", []).append(f["key"])
        structures.append({
            "id": s["id"],
            "label": s["label"],
            "module": s["module"],
            "module_label": DOMAIN_LABELS.get(s["module"], s["module"]),
            "rom_offset": s["rom_offset"],
            "entry_size": s["entry_size"],
            "entry_count": s["entry_count"],
            "fields_known": len(known),
            "fields_filler": len(filler),
            "groups": {k: len(v) for k, v in groups.items()},
            "group_keys": groups,
            "field_types": sorted({f["type"] for f in known}),
            "note": s.get("note", ""),
            "primary_columns": s.get("primary_columns", []),
            "verification": s.get("verification", ""),
        })
    texts = []
    for t in pack["texts"]:
        texts.append({
            "id": t["id"],
            "label": t["label"],
            "module": t["module"],
            "module_label": DOMAIN_LABELS.get(t["module"], t["module"]),
            "count": t["count"],
            "relocatable": bool(t.get("relocatable")),
            "pointer_table_offset": t.get("pointer_table_offset"),
            "has_bindings": bool(t.get("bindings")),
            "note": t.get("note", ""),
        })
    return {
        "rom": pack["rom"],
        "structures": structures,
        "texts": texts,
        "totals": {
            "structures": len(structures),
            "records": sum(s["entry_count"] for s in structures),
            "texts": len(texts),
            "text_records": sum(t["count"] for t in texts),
        },
    }


def print_human(data: dict, domain: str | None) -> None:
    totals = data["totals"]
    print(f"内容包：{totals['structures']} 张结构表 / {totals['records']} 条记录 / "
          f"{totals['texts']} 张文本表 / {totals['text_records']} 条文本")
    print(f"ROM：{data['rom']['name']}  {data['rom']['size']} 字节  sha256 {data['rom']['sha256'][:16]}…")
    print()

    if domain:
        picked = [s for s in data["structures"] if s["module"] == domain]
        picked_t = [t for t in data["texts"] if t["module"] == domain]
    else:
        picked = data["structures"]
        picked_t = data["texts"]

    for module in DOMAIN_LABELS:
        rows = [s for s in picked if s["module"] == module]
        trows = [t for t in picked_t if t["module"] == module]
        if not rows and not trows:
            continue
        print(f"== {DOMAIN_LABELS[module]} ==")
        for s in rows:
            groups = "、".join(f"{k}×{v}" for k, v in s["groups"].items()) or "无分组"
            print(f"  [结构] {s['label']}（{s['id']}）")
            print(f"         ROM 0x{s['rom_offset']:06X}  {s['entry_size']}B/条  {s['entry_count']} 条")
            print(f"         字段 {s['fields_known']} 已知 + {s['fields_filler']} 原始字节  分组：{groups}")
            if s["field_types"]:
                print(f"         类型：{', '.join(s['field_types'])}")
            if s["note"]:
                print(f"         说明：{s['note']}")
        for t in trows:
            mode = "可重定位（可变长）" if t["relocatable"] else "等长改写"
            print(f"  [文本] {t['label']}（{t['id']}）  {t['count']} 条  {mode}")
            if t["note"]:
                print(f"         说明：{t['note']}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--domain", help="只看某个域：story/items/characters/ninjutsu/battle/route/audio/assets")
    args = parser.parse_args()

    data = describe(load_pack())
    if args.json:
        if args.domain:
            data["structures"] = [s for s in data["structures"] if s["module"] == args.domain]
            data["texts"] = [t for t in data["texts"] if t["module"] == args.domain]
        print(json.dumps(data, ensure_ascii=False, indent=1))
    else:
        print_human(data, args.domain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
