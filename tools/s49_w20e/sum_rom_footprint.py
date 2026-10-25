#!/usr/bin/env python3
"""E4: sum the linked ROM footprint of the unreferenced dialogue assets.

Reads the Butano/ld linker map of the E4 lane build and adds up the
`.rodata` size of every `scenario_41_postbattle_dialogue_*_bn_gfx.o` object.
The map lists discarded-but-linked objects with their real section sizes, so
this is the exact ROM byte count the cleanup would reclaim.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

MAP = pathlib.Path(
    r"D:\Github\gba-naruto\build\w20-e4\butano-sequel\build\butano-sequel.map"
)
UNUSED = pathlib.Path(
    r"D:\Github\gba-naruto\build\w20-e4\unused-dialogue-assets.json"
)
OUT = pathlib.Path(
    r"D:\Github\gba-naruto\build\w20-e4\dialogue-asset-rom-footprint.json"
)

LINE_RE = re.compile(
    r"^\s*\.(?P<section>rodata|data|bss|text)\s+0x(?P<addr>[0-9a-f]+)\s+"
    r"0x(?P<size>[0-9a-f]+)\s+(?P<object>\S+)"
)


def main() -> int:
    unused = json.loads(UNUSED.read_text(encoding="utf-8"))
    unused_stems = set(unused["unreferenced_stems"])
    referenced_stems = set(unused["referenced_stems"])

    totals = {}
    for line in MAP.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = LINE_RE.match(line)
        if not match:
            continue
        obj = match.group("object")
        if "postbattle_dialogue" not in obj:
            continue
        stem = obj.split("_bn_gfx.o")[0]
        totals.setdefault(stem, {})[match.group("section")] = int(
            match.group("size"), 16
        )

    def bucket(stems):
        rows = []
        for stem in sorted(stems):
            sections = totals.get(stem)
            if sections is None:
                rows.append({"stem": stem, "linked": False, "bytes": 0})
                continue
            rodata = sections.get("rodata", 0)
            rows.append(
                {
                    "stem": stem,
                    "linked": True,
                    "rodata_bytes": rodata,
                    "data_bytes": sections.get("data", 0),
                    "bss_bytes": sections.get("bss", 0),
                    "bytes": rodata + sections.get("data", 0),
                }
            )
        return rows

    unused_rows = bucket(unused_stems)
    referenced_rows = bucket(referenced_stems)
    unused_total = sum(row["bytes"] for row in unused_rows)
    referenced_total = sum(row["bytes"] for row in referenced_rows)

    payload = {
        "schema": "konoha.s49-dialogue-asset-rom-footprint.v1",
        "linker_map": str(MAP),
        "rom": str(
            pathlib.Path(
                r"D:\Github\gba-naruto\build\w20-e4\butano-sequel\butano-sequel.gba"
            )
        ),
        "rom_bytes": pathlib.Path(
            r"D:\Github\gba-naruto\build\w20-e4\butano-sequel\butano-sequel.gba"
        ).stat().st_size,
        "unreferenced_assets_linked": sum(1 for r in unused_rows if r["linked"]),
        "unreferenced_rom_bytes": unused_total,
        "referenced_rom_bytes": referenced_total,
        "unreferenced": unused_rows,
        "referenced": referenced_rows,
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"unreferenced assets present in the link : "
          f"{payload['unreferenced_assets_linked']}/33")
    print(f"unreferenced .rodata+.data bytes       : {unused_total}")
    print(f"referenced  (page_1..7) bytes          : {referenced_total}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
