#!/usr/bin/env python3
"""Hook points in the base ROM, with verified original-byte preimages.

These are the runtime hook sites the third-party "Konoha Workshop" package
used to extend the game (new game init, character setup, story join, level up,
item ownership, arrival rules, damage gate, unit removal, ...).

The package asserted the original bytes at each site so its build would fail
loudly on a mismatched ROM.  That is the same discipline our patch pipeline
uses (`before_hex` in `tools/patch_safety.py`), so the table is directly
usable here: every preimage below is checked against our base ROM by
`verify_hook_preimages()`.

Provenance: the preimage bytes come from the vendored third-party sources
(`third_party/konoha-workshop/源码/tools/build.py` and
`.../源码/continuation/tools/build_campaign.js`).  The *addresses* are ROM file
offsets; add 0x08000000 for the runtime address.

Verification on our base ROM: 16/16 preimages match byte for byte.

Usage:
    python tools/hook_points.py                # table + verification
    python tools/hook_points.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools import text_codec  # noqa: E402

BASE = 0x08000000

# (file offset, runtime name, what the site is for, original-byte preimage)
HOOKS: list[tuple[int, str, str, str]] = [
    (0x68DFC, "new_game_init", "新游戏初始化", "10b581b000200090"),
    (0x6D4A0, "character_setup", "角色建立 / 初始独有能力等级", "f0b557464e464546"),
    (0x97614, "story_join_leave", "剧情中我方加入 / 退出", "f0b557464e464546"),
    (0x972F8, "ability_reward", "独有能力剧情奖励", "f0b54f464646c0b4"),
    (0x6E898, "ability_scroll", "独有能力卷轴对象", "6078fef7ddfe751c"),
    (0x6E2F4, "fixed_ally_lookup", "固定我方出场人物查找", "bc20604340440079"),
    (0x8927C, "level_up_popup", "升级提示", "071c0df057ff0028"),
    (0x89984, "level_up_flow", "升级流程", "0df0d4fb002802d1"),
    (0x93A78, "exp_threshold", "经验门槛显示", "03d0534618780328"),
    (0x899EC, "ninja_learn", "忍术学习（需保留以防绕过锁定）", "f0b5474680b4061c"),
    (0x958D8, "equipment_permission", "装备操作权限", "07d101f029fc0028"),
    (0x95C90, "equipment_owner", "物品归属 / 转移", "03d901f04dfa0028"),
    (0x8FC20, "item_eligibility", "忍具资格", "10b50006040e0906"),
    (0x77856, "arrival_rule_dispatch", "到达规则派发", "28780138082800d96ce1"),
    (0x76B70, "damage_settlement", "伤害结算", "41468889059a9042"),
    (0x6B1A8, "unit_removal", "单位退场", "f0b557464e464546"),
]

# Original function entry addresses, for tail-call forwarding.
FUNCTION_ENTRIES = {
    0x080688C1: "load_save",
    0x08068685: "load_immediate",
    0x08068AFB: "load_immediate_2",
    0x0806868D: "save_io",
    0x08068E00: "new_game",
    0x0806A99D: "battle_init",
    0x0807518D: "battle_init_2",
    0x0806D96D: "stat_calc",
    0x0806D965: "stat_recalc",
    0x0806B1B1: "unit_remove",
    0x0808F515: "background_dispatch",
    0x0808F545: "scene_start",
    0x0808F67D: "scene_call",
    0x0808A549: "event_gate",
    0x0808A55D: "event_gate_2",
    0x0808A5D1: "event_table_gate",
    0x0808A5E9: "event_table_gate_2",
    0x080970A1: "clear_check",
    0x08097131: "clear_check_2",
    0x08097579: "enqueue",
    0x08097618: "story",
    0x08077B29: "arrival_rule",
    0x08077861: "arrival_rule_2",
    0x08077B3B: "arrival_rule_3",
    0x08076B79: "hp_deduct",
}


def verify_hook_preimages(rom: bytes | None = None) -> list[dict]:
    """Check every hook's preimage against the base ROM."""
    if rom is None:
        rom = text_codec.resolve_rom().read_bytes()
    rows = []
    for offset, name, purpose, preimage in HOOKS:
        want = bytes.fromhex(preimage)
        got = rom[offset:offset + len(want)]
        rows.append({
            "offset": offset,
            "offset_hex": hex(offset),
            "runtime_address": hex(BASE + offset),
            "name": name,
            "purpose": purpose,
            "preimage": preimage,
            "rom_actual": got.hex(),
            "match": got == want,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", default=None)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    rom_path = text_codec.resolve_rom(args.rom)
    rom = rom_path.read_bytes()
    rows = verify_hook_preimages(rom)
    verified = sum(1 for r in rows if r["match"])

    report = {
        "rom": str(rom_path),
        "hooks": len(rows),
        "preimages_verified": verified,
        "rows": rows,
        "function_entries": {hex(k): v for k, v in FUNCTION_ENTRIES.items()},
    }
    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"ROM: {rom_path.name}")
    print(f"hook preimages verified: {verified}/{len(rows)}")
    print()
    for r in rows:
        flag = "OK  " if r["match"] else "DIFF"
        print(f"[{flag}] {r['offset_hex']} ({r['runtime_address']})  {r['name']}")
        print(f"        {r['purpose']}")
    return 0 if verified == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
