#!/usr/bin/env python3
"""Disassemble the battle-effect dispatcher chain for a given sequence.

The battle-effect dispatchers are a multi-layer switch/case stack that selects
sequence 6/8/9/11/13/16/18/19 (inlined) plus case 8 -> 0x0807CCA8 and case
14 -> 0x0807CD3C (per-handler implementations). This tool exposes the full
chain so a future mGBA session can find the dynamic callback that triggers
the upper layer.

Reverse-engineered dispatcher chain (2026-08-06):
    dynamic callback / BLX
        -> 0x0807B8B8 mid-layer (21-case switch table at 0x0807B966)
            -> 0x0807B9C0 case-10 handler (side effect + phase anchor + spawn obj)
                -> 0x0807C93C inner-layer dispatcher
                    -> 0x0807CCA8 case 8 (Group 6)
                    -> 0x0807CD3C case 14 (Group 12)
                    -> 0x0807CE1C case 15 (Group 13)
                    -> 0x0807CEE0 case 18 (Group 18)
                    -> 0x0807D2F4 case 19 (Group 16)
                    -> 0x0807C998 inline case 11 (Group 11)
                    -> 0x0807CA00 inline case 9 (Group 7)
                    -> 0x0807D078 case 6 (Group 5)
                    -> 0x0807DCA4 fallback

Output: a JSON document with the full dispatcher hierarchy plus the dispatcher
caller chain from tools/find_thumb_calls.py.

This is a debug-only static analyzer; it does not start mGBA, does not modify
manifests, and never touches artifacts/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    import capstone
except ImportError:
    print("capstone not in path; tools/_vendor must be on PYTHONPATH", file=sys.stderr)
    raise

try:
    from tools.thumb_branch import find_thumb_branches
except ImportError:
    from thumb_branch import find_thumb_branches


ROM_BASE = 0x08000000
MD = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

DISPATCHERS = {
    "mid_layer": {
        "entry": 0x0807B8B8,
        "switch_table": 0x0807B966,
        "case_handler_offsets": {
            0: 0x0807BB08, 1: 0x0807BEB0, 2: 0x0807BEB0, 3: 0x0807BEB0,
            4: 0x0807BEB0, 5: 0x0807BEB0, 6: 0x0807B9C0, 7: 0x0807BEB0,
            8: 0x0807BEB0, 9: 0x0807BEB0, 10: 0x0807BEB0, 11: 0x0807BEB0,
            12: 0x0807BC6C, 13: 0x0807BEB0, 14: 0x0807BEB0, 15: 0x0807BEB0,
            16: 0x0807BEB0, 17: 0x0807BEB0, 18: 0x0807BCE8, 19: 0x0807BEB0,
            20: 0x0807BEB0, 21: 0x0807BCE8,
        },
    },
    "mid_fallback": {
        "entry": 0x0807BEB0,
        "switch_table": 0x0807BECE,
    },
    "inner_layer": {
        "entry": 0x0807C93C,
        "switch_table": 0x0807CABA,
        "case_handler_offsets": {
            5: 0x0807D078,
            7: 0x0807CCA8,
            13: 0x0807CD3C,
            14: 0x0807CE1C,
            16: 0x0807CEE0,
            17: 0x0807D2F4,
        },
    },
    "group_6_case_8_handler": 0x0807CCA8,
    "group_12_case_14_handler": 0x0807CD3C,
    "group_13_case_15_handler": 0x0807CE1C,
    "group_18_case_18_handler": 0x0807CEE0,
    "group_16_case_19_handler": 0x0807D2F4,
    "generic_binder": 0x0807FE2C,
}


def _read_dispatch_table(rom: bytes, table_addr: int, count: int) -> list[int]:
    off = table_addr - ROM_BASE
    out: list[int] = []
    for i in range(count):
        val = rom[off + i * 4] | (rom[off + i * 4 + 1] << 8) | (rom[off + i * 4 + 2] << 16) | (rom[off + i * 4 + 3] << 24)
        out.append(val)
    return out


def _disasm(rom: bytes, addr: int, count: int = 24) -> list[dict[str, Any]]:
    off = addr - ROM_BASE
    out: list[dict[str, Any]] = []
    for ins in MD.disasm(rom[off:off + count * 4], addr):
        out.append({
            "address": f"0x{ins.address:08X}",
            "mnemonic": ins.mnemonic,
            "op_str": ins.op_str,
        })
        if len(out) >= count:
            break
    return out


def _caller_chain(rom: bytes, target: int) -> list[str]:
    return [
        f"0x{branch.address:08X}"
        for branch in find_thumb_branches(rom, target, rom_base=ROM_BASE)
    ]


def build_dispatcher_inventory(rom_path: Path) -> dict[str, Any]:
    rom = rom_path.read_bytes()

    inner_switch = _read_dispatch_table(rom, 0x0807CABA, 13)
    mid_switch = _read_dispatch_table(rom, 0x0807B966, 22)

    group_6_handler = _disasm(rom, 0x0807CCA8, 20)
    group_12_handler = _disasm(rom, 0x0807CD3C, 24)
    generic_binder = _disasm(rom, 0x0807FE2C, 24)

    return {
        "schema": "battle-effect-dispatcher-inventory-v1",
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "rom_path": str(rom_path),
        "rom_size": len(rom),
        "direct_callers": {
            "0x0807C93C": _caller_chain(rom, 0x0807C93C),
            "0x0807B8B8": _caller_chain(rom, 0x0807B8B8),
        },
        "dispatchers": DISPATCHERS,
        "inner_layer_switch_table": {
            "table_addr": "0x0807CABA",
            "entries": [f"0x{v:08X}" for v in inner_switch],
        },
        "mid_layer_switch_table": {
            "table_addr": "0x0807B966",
            "entries": [f"0x{v:08X}" for v in mid_switch],
        },
        "group_6_case_8_handler_disasm": group_6_handler,
        "group_12_case_14_handler_disasm": group_12_handler,
        "generic_binder_disasm": generic_binder,
        "scope": {
            "outer_entry_boundary": (
                "No direct Thumb branch to 0x0807B8B8 was found; a dynamic "
                "callback remains the working boundary and requires runtime tracing."
            ),
            "direct_callers_are_static_only": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    inventory = build_dispatcher_inventory(args.rom)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(f"dispatcher inventory written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
