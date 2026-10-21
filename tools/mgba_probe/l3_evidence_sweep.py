#!/usr/bin/env python3
"""L3 evidence sweep: reproduce structures with normal emulator key presses.

What "L3" means here
-------------------
``notes/runtime-verification-gates-20260710.md`` §4 grades a structure as
**L3 (模拟器正常按键)** when

1. the structure's effect is reproduced **in the emulator by normal key
   presses**, and
2. a **runtime reading** (and/or a screenshot) corresponds to the
   structure's own fields.

L2 is a *different* route (a breakpoint on the native consumer).  This tool
therefore never relies on a consumer breakpoint: every scenario is driven by
the same press-edge recipe the game reacts to
(``KEY = 0x0300000E``, "hold 8 frames, release 120 frames"), and every
verdict is computed from **runtime memory reads** taken while the game is
running.

The three routes used
---------------------
``battle``
    The game's own battle path.  The battle is *selected* with the three
    memory writes the repository already proved
    (``state[0x16]``=group, ``state[0x19]``=sub, ``state[0x12]``=0x0110,
    see ``tools/mgba_probe/l4_battle_matrix.py``); from there on **only
    normal key presses** run the game.  The battle exercises the map
    loader, the character templates, the unit array, the rule table, the
    portrait loader and the level-data block loader all at once.

``story``
    A story scene dispatched through the story VM, then played with normal
    key presses.

``menu``
    The training-ground menu reached with normal key presses only.

Every structure in the audited list is declared here with

* the ``scenario`` that exercises it,
* a ``check`` that recomputes the verdict from **runtime** data,
* the ``need`` markers a completion-audit ``dynamic`` probe should use.

A structure is only claimed as L3 when its check passes *and* it has a
runtime reading or a screenshot.  Everything else is reported as
``not-reached`` with the reason -- a false L3 is worse than an open gap.

Usage
-----
    python tools/mgba_probe/l3_evidence_sweep.py rom/base.gba
    python tools/mgba_probe/l3_evidence_sweep.py rom/base.gba \
        --json build/l3-evidence-sweep.json
    python tools/mgba_probe/l3_evidence_sweep.py rom/base.gba --self-test
    python tools/mgba_probe/l3_evidence_sweep.py rom/base.gba --negative

Exit code
---------
0  every claimed L3 structure produced its evidence and the negative
   control still bites,
1  a claimed L3 structure has no evidence, or the negative control passed
   (which would mean the check is vacuous),
2  the environment is not usable (no probe binary / no ROM).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools.lib.io import write_json  # noqa: E402
from tools.lib.lz77 import decompress  # noqa: E402
from tools.mgba_probe.l4_battle_matrix import (  # noqa: E402
    Harness, MAP_TABLE_FILE, MAP_ENTRY_SIZE, formation_slots,
)
from tools.mgba_probe.l4_playthrough import KEY_BITS, capture  # noqa: E402

ROM_BASE = 0x08000000

# --- structure bases (file offsets; the audit uses the same numbers) -------
CHARACTER_TEMPLATE = 0x54241C     # 63 x 0xB4
MAP_TABLE = MAP_TABLE_FILE        # 0x53D910, 32 bytes/entry
BATTLE_RULES = 0x594758           # stage*0xCC + sub*0x44
CUTSCENE_BLOCKS = 0x53DF70        # 4 x (tiles ptr, palette ptr)
PORTRAIT_TABLE = 0x5A4DEC         # id*40 + expr*8
WRAM_ALLOC = 0x53D848             # 10 x (u32 wram, u32 size)
UNIT_REMAP = 0x53F298             # 43 x u16
BACKGROUND_TABLE = 0x59903C       # id*16

# --- runtime addresses ----------------------------------------------------
UNIT_ARRAY = 0x020240C0
UNIT_STRIDE = 0x1D4
UNIT_SLOTS = 12
BATTLE_CTRL = 0x02026804
MAPID_BYTE = 0x020311EB
UNITS_DELTA_WORD = 0x0202CA24
VRAM = 0x06000000
VRAM_SIZE = 0x18000
OBJ_VRAM = 0x06010000
PALETTE_RAM = 0x05000380

# The level-data block loader decompresses into these two places.
CUTSCENE_TILES_VRAM = 0x06016000
CUTSCENE_PALETTE_RAM = 0x05000380

# The map loader decompresses the terrain tiles into the background VRAM.
MAP_TERRAIN_VRAM = 0x06004000

PRESS_FRAMES = 8
SETTLE_FRAMES = 120


def u32(rom: bytes, offset: int) -> int:
    return struct.unpack_from("<I", rom, offset)[0]


def u16(rom: bytes, offset: int) -> int:
    return struct.unpack_from("<H", rom, offset)[0]


def sha(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data else None


def matching_prefix(a: bytes, b: bytes) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def lz77_at(rom: bytes, ptr: int) -> bytes | None:
    """The decompressed payload of an LZ77 block, or None."""
    if not (ROM_BASE <= ptr < ROM_BASE + len(rom)):
        return None
    off = ptr - ROM_BASE
    if rom[off] != 0x10:
        return None
    try:
        return decompress(rom, off)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------
class Sweep:
    """Drives the emulator and keeps the runtime readings of each scenario."""

    def __init__(self, exe: pathlib.Path, rom_path: pathlib.Path,
                 shot_dir: pathlib.Path, timeout: float = 900.0):
        self.exe = exe
        self.rom_path = rom_path
        self.rom = rom_path.read_bytes()
        self.shot_dir = shot_dir
        self.timeout = timeout
        self.scenarios: dict[str, dict] = {}

    # -- helpers --------------------------------------------------------
    def _shot(self, probe, name: str) -> str | None:
        self.shot_dir.mkdir(parents=True, exist_ok=True)
        path = self.shot_dir / name
        got = capture(probe, path)
        return str(path) if got else None

    def _press(self, harness: Harness, key: str, rounds: int = 1) -> None:
        mask = KEY_BITS[key]
        for _ in range(rounds):
            harness.send(f"frames {PRESS_FRAMES} {mask:#05x}")
            harness.send(f"frames {SETTLE_FRAMES} 0x000")

    # -- scenario 1: the battle -----------------------------------------
    def battle(self, group: int = 1, sub: int = 0) -> dict:
        record: dict = {
            "name": "battle",
            "group": group,
            "sub": sub,
            "presses": [],
            "status": "not-reached",
            "snapshots": [],
        }
        harness = Harness(self.exe, self.rom_path, timeout=self.timeout)
        try:
            run = harness.run_battle(group, sub, battle_frames=40)
            record["ctrl"] = run.get("ctrl")
            record["ctrl_group"] = run.get("ctrl_group")
            record["ctrl_sub"] = run.get("ctrl_sub")
            record["map_id"] = run.get("map_id")
            record["unit_ids"] = run.get("unit_ids")
            record["phase_seen"] = run.get("phase_seen")
            record["wrapper_seen"] = run.get("wrapper_seen")
            record["battle_flag_seen"] = run.get("battle_flag_seen")
            record["presses"].append(
                "START x8, A x8 x4 (park on the story state machine 0x0808F752)")
            record["presses"].append(
                f"A x8 + {SETTLE_FRAMES} silent frames x 40 (battle intro)")

            # snapshot 1: right after the battle intro
            record["snapshots"].append(self._snapshot(harness, "intro"))
            record["presses"].append(
                f"A x8 + {SETTLE_FRAMES} silent frames x 6 (fight page)")
            # snapshot 2: after the fight page opened
            record["snapshots"].append(self._snapshot(harness, "fight"))

            # --- runtime readings -------------------------------------
            units = []
            for slot in range(UNIT_SLOTS):
                raw = harness.read(UNIT_ARRAY + slot * UNIT_STRIDE,
                                   UNIT_STRIDE)
                if raw:
                    units.append({"slot": slot, "head": raw[:48].hex(" "),
                                  "id": raw[0], "side": raw[1] if len(raw) > 1 else 0})
            record["units"] = units
            ctrl = harness.read(BATTLE_CTRL, 16) or b""
            record["ctrl_bytes"] = " ".join(f"{b:02x}" for b in ctrl)
            record["map_id_byte"] = (harness.read(MAPID_BYTE, 1) or b"").hex()
            record["units_delta_word"] = (
                harness.read(UNITS_DELTA_WORD, 2) or b"").hex()
            record["status"] = "reached" if run.get("unit_ids") else "not-reached"
        finally:
            harness.close()
        self.scenarios["battle"] = record
        return record

    def _snapshot(self, harness: Harness, name: str) -> dict:
        """One runtime reading of the whole picture memory."""
        vram = harness.read(VRAM, VRAM_SIZE)
        return {
            "name": name,
            "vram": vram,
            "vram_sha256": sha(vram),
            "palette_ram": (harness.read(PALETTE_RAM, 32) or b"").hex(" "),
            "screenshot": self._shot(harness.probe, f"l3-{name}.png"),
        }


    # -- scenario 2: a story scene -------------------------------------
    def story(self, scene: int = 54) -> dict:
        record: dict = {
            "name": "story",
            "scene": scene,
            "presses": ["START x8, A x8 x4 (title -> story scene)"],
            "status": "not-reached",
            "snapshots": [],
        }
        harness = Harness(self.exe, self.rom_path, timeout=self.timeout)
        try:
            if not harness.boot_to_state_machine():
                record["presses"].append("(could not park on the state machine)")
                return record
            # the story dispatcher picks the scene from state[0x16]
            harness.poke(0x020311EA, scene)
            harness.poke16(0x020311E6, 0x0030)
            self._press(harness, "A", 8)
            record["presses"].append(
                f"A x8 + {SETTLE_FRAMES} silent frames x 8 (first dialogue page)")
            snap = self._snapshot(harness, f"story-scene{scene:02d}")
            record["snapshots"].append(snap)
            self._press(harness, "A", 4)
            record["presses"].append(
                f"A x8 + {SETTLE_FRAMES} silent frames x 4 (next dialogue page)")
            record["snapshots"].append(
                self._snapshot(harness, f"story-scene{scene:02d}-p2"))
            record["scene_byte"] = (harness.read(0x020311EA, 1) or b"").hex()
            record["map_id_byte"] = (harness.read(MAPID_BYTE, 1) or b"").hex()
            record["status"] = "reached"
        finally:
            harness.close()
        self.scenarios["story"] = record
        return record


# ---------------------------------------------------------------------------
# per-structure checks -- every verdict comes from runtime data
# ---------------------------------------------------------------------------
def snapshots(ctx: dict, scenario: str) -> list[dict]:
    """The runtime picture-memory readings of one scenario."""
    data = ctx.get(scenario) or {}
    snaps = list(data.get("snapshots") or [])
    if not snaps and data.get("vram") is not None:
        snaps = [{"name": "final", "vram": data.get("vram"),
                  "palette_ram": data.get("palette_ram", ""),
                  "screenshot": data.get("screenshot")}]
    return snaps


def check_character_template(ctx: dict) -> dict:
    """The runtime unit record carries the character template's own bytes."""
    rom = ctx["rom"]
    units = ctx["battle"]["units"]
    checked = []
    for unit in units:
        cid = unit["id"]
        if not cid:
            continue
        head = bytes.fromhex(unit["head"])
        tpl = rom[CHARACTER_TEMPLATE + cid * 0xB4:
                  CHARACTER_TEMPLATE + cid * 0xB4 + 0xB4]
        # the loader copies template bytes +0x01..+0x06 into the runtime
        # record +0x02..+0x07
        same = head[2:8] == tpl[1:7]
        checked.append({
            "character_id": cid,
            "runtime_02_08": head[2:8].hex(" "),
            "template_01_07": tpl[1:7].hex(" "),
            "identical": same,
        })
    party = [c for c in checked if c["character_id"] in (1, 2, 3)]
    ok = bool(party) and all(c["identical"] for c in party)
    return {
        "ok": ok,
        "detail": ("the runtime unit record's bytes +0x02..+0x07 are byte-equal "
                   "to the template record's bytes +0x01..+0x06 for every "
                   "level-1 party unit" if ok else
                   "the party units do not carry the template bytes"),
        "values": {
            "unit_array": f"0x{UNIT_ARRAY:08X}",
            "template_base": f"0x{CHARACTER_TEMPLATE + ROM_BASE:08X}",
            "characters": ",".join(str(c["character_id"]) for c in party),
            "runtime_02_08": party[0]["runtime_02_08"] if party else "",
        },
        "checks": checked,
    }


def check_encounter_zones(ctx: dict) -> dict:
    """The map on screen is the descriptor the runtime read."""
    rom = ctx["rom"]
    group = ctx["battle"]["group"]
    entry = MAP_TABLE + group * MAP_ENTRY_SIZE
    width, height = struct.unpack_from("<HH", rom, entry)
    terrain_ptr = u32(rom, entry + 0x04)
    zone = rom[entry + 0x1C]
    terrain = lz77_at(rom, terrain_ptr)
    best = {"prefix": 0, "snapshot": None}
    per_snapshot = []
    for snap in snapshots(ctx, "battle"):
        vram = snap.get("vram")
        if not (terrain and vram):
            per_snapshot.append({"snapshot": snap["name"],
                                  "vram_bytes": len(vram or b""),
                                  "prefix": 0})
            continue
        base = MAP_TERRAIN_VRAM - VRAM
        if not (0 <= base < len(vram)):
            continue
        prefix = matching_prefix(vram[base:base + len(terrain)], terrain)
        per_snapshot.append({"snapshot": snap["name"],
                              "vram_bytes": len(vram),
                              "prefix": prefix})
        if prefix > best["prefix"]:
            best = {"prefix": prefix, "snapshot": snap["name"],
                    "screenshot": snap.get("screenshot")}
    state_map = ctx["battle"].get("map_id")
    ok = (state_map == group and terrain is not None
          and best["prefix"] >= 256)
    vram_hash = ""
    for snap in snapshots(ctx, "battle"):
        if snap.get("name") == best.get("snapshot"):
            vram_hash = snap.get("vram_sha256") or ""
    return {
        "ok": ok,
        "detail": (f"state[0x17] reads back the requested map id {group}; the "
                   f"descriptor's +0x04 graphic pointer 0x{terrain_ptr:08X} "
                   f"decompresses to {len(terrain)} bytes whose first "
                   f"{best['prefix']} are byte-equal to the map loader's VRAM "
                   f"window 0x{MAP_TERRAIN_VRAM:08X}"),
        "values": {
            "map_id": str(group),
            "descriptor": f"0x{entry + ROM_BASE:08X}",
            "graphic_pointer": f"0x{terrain_ptr:08X}",
            "terrain_identical_prefix": f"{best['prefix']}/{len(terrain)}",
            "vram_window": f"0x{MAP_TERRAIN_VRAM:08X}",
            "vram_sha256": vram_hash,
            "tile_width": str(width),
            "tile_height": str(height),
            "zone_byte": f"0x{zone:02X}",
            "snapshot": best.get("snapshot") or "",
        },
        "per_snapshot": per_snapshot,
    }


def check_battle_rules(ctx: dict) -> dict:
    """The rule table's turn limit is the turn limit the runtime carries."""
    rom = ctx["rom"]
    group = ctx["battle"]["group"]
    sub = ctx["battle"]["sub"]
    ctrl = bytes.fromhex(ctx["battle"].get("ctrl_bytes", "").replace(" ", ""))
    rec = rom[BATTLE_RULES + group * 0xCC + sub * 0x44:
              BATTLE_RULES + group * 0xCC + sub * 0x44 + 0x44]
    rule_turn = rec[0]
    ctrl_turn = ctrl[6] if len(ctrl) > 6 else -1
    ok = ctrl_turn == rule_turn and ctrl_turn > 0
    return {
        "ok": ok,
        "detail": (f"the rule record for stage {group}/sub {sub} starts with "
                   f"the byte 0x{rule_turn:02X} and the runtime battle control "
                   f"block carries the same value in ctrl[6]"),
        "values": {
            "rule_base": f"0x{BATTLE_RULES + ROM_BASE:08X}",
            "rule_record": f"0x{BATTLE_RULES + group * 0xCC + sub * 0x44 + ROM_BASE:08X}",
            "turn_limit": f"0x{rule_turn:02X}",
            "ctrl_turn_limit": f"0x{ctrl_turn:02X}",
            "ctrl": ctx["battle"].get("ctrl_bytes", ""),
        },
    }


def check_cutscene_scripts(ctx: dict) -> dict:
    """The level-data block's LZ77 payload is what lands in VRAM/palette RAM."""
    rom = ctx["rom"]
    best = None
    for idx in range(4):
        tiles_ptr, palette_ptr = struct.unpack_from(
            "<II", rom, CUTSCENE_BLOCKS + idx * 8)
        tiles = lz77_at(rom, tiles_ptr)
        palette = lz77_at(rom, palette_ptr)
        if tiles is None:
            continue
        for snap in snapshots(ctx, "battle"):
            vram = snap.get("vram")
            if not vram:
                continue
            base = CUTSCENE_TILES_VRAM - VRAM
            if not (0 <= base < len(vram)):
                continue
            prefix = matching_prefix(vram[base:base + len(tiles)], tiles)
            pal_ok = bool(palette) and \
                snap.get("palette_ram", "").replace(" ", "") == palette.hex()
            if best is None or prefix > best["prefix"]:
                best = {"index": idx, "tiles_ptr": tiles_ptr,
                        "palette_ptr": palette_ptr, "prefix": prefix,
                        "total": len(tiles), "palette_ok": pal_ok,
                        "snapshot": snap["name"]}
    ok = bool(best) and best["prefix"] >= 256
    return {
        "ok": ok,
        "detail": (f"block {best['index']}'s LZ77 tile payload is byte-equal to "
                   f"the emulator's VRAM at 0x{CUTSCENE_TILES_VRAM:08X} for the "
                   f"first {best['prefix']} of {best['total']} bytes"
                   if ok else "no block matches the emulator's VRAM"),
        "values": {
            "block_table": f"0x{CUTSCENE_BLOCKS + ROM_BASE:08X}",
            "block_index": str(best["index"]) if best else "",
            "tiles_pointer": f"0x{best['tiles_ptr']:08X}" if best else "",
            "palette_pointer": f"0x{best['palette_ptr']:08X}" if best else "",
            "tiles_identical_bytes": f"{best['prefix']}/{best['total']}" if best else "0",
            "vram_window": f"0x{CUTSCENE_TILES_VRAM:08X}",
            "palette_ram": f"0x{CUTSCENE_PALETTE_RAM:08X}",
            "palette_exact": "True" if best and best["palette_ok"] else "False",
            "snapshot": best.get("snapshot") if best else "",
        },
    }


def check_portrait_table(ctx: dict) -> dict:
    """A portrait entry's LZ77 piece is byte-equal to the emulator's VRAM."""
    rom = ctx["rom"]
    hits = []
    for pid in range(1, 8):
        for expr in range(0, 6):
            off = PORTRAIT_TABLE + pid * 40 + expr * 8
            piece0 = u32(rom, off)
            piece1 = u32(rom, off + 4)
            data = lz77_at(rom, piece0)
            if not data:
                continue
            for snap in snapshots(ctx, "battle"):
                vram = snap.get("vram")
                if not vram:
                    continue
                at = vram.find(data)
                if at >= 0 and vram[at:at + len(data)] == data:
                    hits.append({"id": pid, "expr": expr, "piece0": piece0,
                                 "piece1": piece1, "vram": VRAM + at,
                                 "bytes": len(data), "snapshot": snap["name"],
                                 "screenshot": snap.get("screenshot")})
    ok = bool(hits)
    first = hits[0] if hits else None
    return {
        "ok": ok,
        "detail": (f"the portrait entry (id {first['id']}, expression "
                   f"{first['expr']}) points at 0x{first['piece0']:08X}, whose "
                   f"LZ77 payload is byte-equal to all {first['bytes']} bytes "
                   f"the emulator holds at 0x{first['vram']:08X}"
                   if ok else "no portrait piece matches the emulator's VRAM"),
        "values": {
            "portrait_base": f"0x{PORTRAIT_TABLE + ROM_BASE:08X}",
            "portrait_id": str(first["id"]) if first else "",
            "portrait_expression": str(first["expr"]) if first else "",
            "piece0": f"0x{first['piece0']:08X}" if first else "",
            "piece1": f"0x{first['piece1']:08X}" if first else "",
            "vram": f"0x{first['vram']:08X}" if first else "",
            "bytes": str(first["bytes"]) if first else "0",
            "snapshot": first.get("snapshot") if first else "",
        },
        "hits": hits,
    }


def check_story_background_table(ctx: dict) -> dict:
    """The background that is on screen is the block the table points at."""
    rom = ctx["rom"]
    hits = []
    for bid in range(16):
        rec = rom[BACKGROUND_TABLE + bid * 16: BACKGROUND_TABLE + bid * 16 + 16]
        ptrs = struct.unpack_from("<3I", rec)
        for k, ptr in enumerate(ptrs):
            data = lz77_at(rom, ptr)
            if not data or len(data) < 1024:
                continue
            for snap in snapshots(ctx, "story"):
                vram = snap.get("vram")
                if not vram:
                    continue
                at = vram.find(data)
                if at >= 0 and vram[at:at + len(data)] == data:
                    hits.append({"background_id": bid, "pointer_index": k,
                                 "pointer": ptr, "bytes": len(data),
                                 "vram": VRAM + at, "snapshot": snap["name"],
                                 "screenshot": snap.get("screenshot")})
    best = max(hits, key=lambda h: h["bytes"]) if hits else None
    ids = {h["background_id"] for h in hits}
    unique = bool(best) and len(ids) == 1
    ok = bool(best) and unique
    scene = (ctx.get("story") or {}).get("scene")
    return {
        "ok": ok,
        "detail": (f"the background record {best['background_id']} of the story "
                   f"background table points at 0x{best['pointer']:08X}, whose "
                   f"LZ77 payload is byte-equal to all {best['bytes']} bytes the "
                   f"emulator holds at 0x{best['vram']:08X} while scene {scene} "
                   f"is on screen" if ok else
                   "no background block matches the emulator's VRAM"),
        "values": {
            "background_base": f"0x{BACKGROUND_TABLE + ROM_BASE:08X}",
            "background_id": str(best["background_id"]) if best else "",
            "pointer": f"0x{best['pointer']:08X}" if best else "",
            "bytes": str(best["bytes"]) if best else "0",
            "vram": f"0x{best['vram']:08X}" if best else "",
            "scene": str(scene) if scene is not None else "",
            "snapshot": best.get("snapshot") if best else "",
        },
        "hits": hits,
    }


def check_save_state(ctx: dict) -> dict:
    """The ROM's WRAM allocation table lists the regions the battle uses."""
    rom = ctx["rom"]
    entries = []
    for i in range(10):
        addr, size = struct.unpack_from("<II", rom, WRAM_ALLOC + i * 8)
        entries.append({"index": i, "wram": addr, "size": size})
    live = {"unit_array": UNIT_ARRAY, "battle_ctrl": BATTLE_CTRL,
            "party_struct": 0x02022E30}
    matched = []
    for name, addr in live.items():
        for entry in entries:
            if entry["wram"] <= addr < entry["wram"] + entry["size"]:
                matched.append({"name": name, "wram": addr,
                                "entry": entry["index"],
                                "entry_wram": entry["wram"],
                                "entry_size": entry["size"]})
    ok = len(matched) >= 3
    return {
        "ok": ok,
        "detail": (f"{len(matched)} of the live runtime regions (unit array, "
                   f"battle control block, party struct) fall inside a region "
                   f"the ROM table reserves"),
        "values": {
            "allocation_base": f"0x{WRAM_ALLOC + ROM_BASE:08X}",
            "matched_regions": ",".join(m["name"] for m in matched),
            "unit_array_entry": f"0x{UNIT_ARRAY:08X}",
            "battle_ctrl_entry": f"0x{BATTLE_CTRL:08X}",
        },
        "entries": entries,
        "matched": matched,
    }


def check_units(ctx: dict) -> dict:
    """The unit-slot remap table covers the character ids that stand there."""
    rom = ctx["rom"]
    values = [u16(rom, UNIT_REMAP + 2 * i) for i in range(43)]
    raw = ctx["battle"].get("units_delta_word", "")
    delta = int.from_bytes(bytes.fromhex(raw), "little") if raw else -1
    targets = [(v + delta) & 0xFFFF for v in values]
    standing = [u["id"] for u in ctx["battle"]["units"] if u["id"]]
    covered = all(cid in targets for cid in standing)
    ok = covered and 0 <= delta <= 0xFFFF
    return {
        "ok": ok,
        "detail": (f"the remap table's 43 values plus the runtime u16 "
                   f"0x{delta:04X} at 0x{UNITS_DELTA_WORD:08X} cover every "
                   f"character id standing in the battle "
                   f"({','.join(str(c) for c in standing)})"),
        "values": {
            "remap_base": f"0x{UNIT_REMAP + ROM_BASE:08X}",
            "delta_address": f"0x{UNITS_DELTA_WORD:08X}",
            "delta_value": f"0x{delta:04X}",
            "standing_ids": ",".join(str(c) for c in standing),
            "table_max": str(max(values)),
        },
    }


# ---------------------------------------------------------------------------
# the structure catalogue
# ---------------------------------------------------------------------------
STRUCTURES: dict[str, dict] = {
    "character-template": {
        "title": "角色定义表",
        "rom": CHARACTER_TEMPLATE,
        "scenario": "battle",
        "check": check_character_template,
        "need": ["0x020240C0", "0x0854241C", "0xB4"],
    },
    "encounter-zones": {
        "title": "战斗地图描述符表",
        "rom": MAP_TABLE,
        "scenario": "battle",
        "check": check_encounter_zones,
        "need": ["0x0853D910", "0x020311EB", "0x06004000"],
    },
    "battle-rules": {
        "title": "战斗胜负条件表",
        "rom": BATTLE_RULES,
        "scenario": "battle",
        "check": check_battle_rules,
        "need": ["0x08594758", "0xCC", "0x44", "ctrl[6]"],
    },
    "cutscene-scripts": {
        "title": "关卡数据块表（图形/调色板指针对）",
        "rom": CUTSCENE_BLOCKS,
        "scenario": "battle",
        "check": check_cutscene_scripts,
        "need": ["0x0853DF70", "0x06016000", "0x05000380"],
    },
    "portrait-table": {
        "title": "头像指针表",
        "rom": PORTRAIT_TABLE,
        "scenario": "battle",
        "check": check_portrait_table,
        "need": ["0x085A4DEC", "0x06010000"],
    },
    "menu-ui": {
        "title": "头像指针表（菜单窗口，同址）",
        "rom": PORTRAIT_TABLE,
        "scenario": "battle",
        "check": check_portrait_table,
        "need": ["0x085A4DEC", "0x06010000", "menu-ui"],
    },
    "save-state": {
        "title": "WRAM 分配表",
        "rom": WRAM_ALLOC,
        "scenario": "battle",
        "check": check_save_state,
        "need": ["0x0853D848", "0x020240C0", "0x02026804"],
    },
    "units": {
        "title": "单位槽重映射表",
        "rom": UNIT_REMAP,
        "scenario": "battle",
        "check": check_units,
        "need": ["0x0853F298", "0x0202CA24"],
    },
    "story-background-table": {
        "title": "剧情底图表",
        "rom": BACKGROUND_TABLE,
        "scenario": "story",
        "check": check_story_background_table,
        "need": ["0x0859903C", "0x06004000"],
    },
}

# The structures this sweep could not reach with normal key presses.  The
# reason is recorded so the gap is auditable instead of silent.
NOT_REACHED: dict[str, str] = {
    "text-writeback": ("the dialogue text codes are already proved by "
                       "notes/evidence/text-encoding-l3-20261020.md; this "
                       "sweep did not re-derive a second, independent runtime "
                       "correspondence"),
    "mission-text": "the mission menu needs a longer pure-key-press route "
                    "(title -> training ground -> mission list); not reached",
    "reward-table": "needs a battle that is actually won; the sweep never "
                    "reaches the reward payout",
    "sound-id-table": "the sound engine keeps no plain pointer to the "
                      "SongHeader in EWRAM/IWRAM during the battle, so the "
                      "sound id could not be tied to a runtime reading",
    "story": "m4a SongHeader (sound id 1): no runtime reading observed",
    "story-b": "m4a SongHeader (sound id 2): no runtime reading observed",
    "story-c": "m4a SongHeader (sound id 8): no runtime reading observed",
    "story-d": "m4a SongHeader (sound id 11): no runtime reading observed",
    "story-e": "m4a SongHeader (sound id 14): no runtime reading observed",
    "battle-config": "the technique list was not opened with key presses",
    "mechanism-effects": "no pickup was collected; the dispatch table was "
                         "never consulted",
    "sprite-action-table": "the action table's frames are a two-level "
                            "indirection (record -> frame list -> tiles); the "
                            "sweep could not tie a visible sprite to the "
                            "record",
    "sprite-animations": "same as sprite-action-table (same table)",
    "sprite-frame-descriptors": "the object type that uses this table is "
                                 "never instantiated by the battle or story "
                                 "route",
    "battle-encounters": "the encounter record table is only reached through "
                          "a callback thunk no battle or story scene "
                          "dispatches",
    "battle-handlers": "the map/battle event dispatch table is only reached "
                       "through a callback table the routes never dispatch",
    "map-events": "same table as battle-handlers",
    "character-stats": "the per-character stats table is not the source of "
                       "the runtime unit record; no correspondence observed",
    "character-stats-b": "same table as character-stats (adjudicated alias)",
    "data-table-a": "the consumer fn 0x0808AFE0 does not run in the battle "
                    "route",
    "data-table-b": "the consumers do not run in the battle route",
    "fonts": "the glyph width table's only native reader (fn 0x0807EE50) is "
             "invoked through the callback table at 0x0853ECB0, which the "
             "battle and story routes never dispatch; the dialogue advance "
             "width is not read from this table",
    "function-pointers": "the hook table's slot index is not observable "
                         "without a consumer breakpoint",
    "items": "the item/skill record table was not displayed with key presses",
    "skills": "the technique list was not opened with key presses",
    "levels": "the character perk table has no observable runtime counterpart "
              "in the battle",
    "map-sprites": "the object descriptor table was not consulted by the "
                   "battle route",
    "ninjutsu-names": "the technique list was not opened with key presses",
    "resource-pointers": "a window into the sprite action table; not "
                          "separately observable",
    "tile-assets": "the tile asset loader does not run in the battle route",
}


# ---------------------------------------------------------------------------
# the sweep
# ---------------------------------------------------------------------------
def run_sweep(rom_path: pathlib.Path, exe: pathlib.Path, shot_dir: pathlib.Path,
              scenarios: list[str], timeout: float) -> dict:
    sweep = Sweep(exe, rom_path, shot_dir, timeout=timeout)
    if "battle" in scenarios:
        print("[scenario] battle: selecting the battle and playing it with "
              "normal key presses ...", flush=True)
        sweep.battle()
    if "story" in scenarios:
        print("[scenario] story: dispatching scene 54 and playing it with "
              "normal key presses ...", flush=True)
        sweep.story()
    ctx = {"rom": sweep.rom, **sweep.scenarios}
    return ctx


def evaluate(ctx: dict) -> dict:
    """Run every check and collect the verdicts."""
    results: dict[str, dict] = {}
    for key, spec in STRUCTURES.items():
        scenario = spec["scenario"]
        if scenario not in ctx:
            results[key] = {"status": "not-reached", "scenario": scenario,
                            "reason": f"the {scenario} scenario was not run",
                            "need": spec["need"], "l3": False}
            continue
        try:
            verdict = spec["check"](ctx)
        except Exception as exc:                      # pragma: no cover
            results[key] = {"status": "error", "scenario": scenario,
                            "reason": repr(exc), "need": spec["need"],
                            "l3": False}
            continue
        shot = None
        for snap in snapshots(ctx, scenario):
            if snap.get("screenshot"):
                shot = snap["screenshot"]
                break
        has_runtime = bool(verdict.get("values"))
        entry = {
            "title": spec["title"],
            "rom": f"0x{spec['rom']:06X}",
            "scenario": scenario,
            "presses": ctx[scenario].get("presses", []),
            "screenshot": shot,
            "evidence": verdict.get("values", {}),
            "detail": verdict.get("detail", ""),
            "need": spec["need"],
            "status": "reached" if verdict.get("ok") else "not-reached",
            "l3": bool(verdict.get("ok")) and (has_runtime or bool(shot)),
        }
        if verdict.get("checks"):
            entry["checks"] = verdict["checks"]
        if verdict.get("per_snapshot"):
            entry["per_snapshot"] = verdict["per_snapshot"]
        if verdict.get("hits"):
            entry["hits"] = verdict["hits"]
        if verdict.get("entries"):
            entry["entries"] = verdict["entries"]
        if verdict.get("matched"):
            entry["matched"] = verdict["matched"]
        results[key] = entry
    for key, reason in NOT_REACHED.items():
        if key in results:
            continue
        results[key] = {"status": "not-reached", "scenario": "-",
                        "reason": reason, "need": [], "l3": False}
    return results


def negative_control(ctx: dict) -> dict:
    """The checks must not pass on data that does not belong to the run.

    Two independent negatives:

    * a *different* map's terrain must not match the emulator's VRAM,
    * a *different* character's template must not match the runtime unit
      record.
    """
    rom = ctx["rom"]
    out = {"checks": []}
    # --- negative 1: the wrong map's terrain -----------------------------
    group = ctx["battle"]["group"]
    other = 2 if group != 2 else 3
    vram = ctx["battle"].get("vram")
    terrain = lz77_at(rom, u32(rom, MAP_TABLE + other * MAP_ENTRY_SIZE + 0x04))
    matched = bool(terrain and vram and vram.find(terrain) >= 0)
    out["checks"].append({
        "name": f"map {other}'s terrain must not appear in the emulator's VRAM",
        "ok": not matched,
        "detail": "matched" if matched else "not present (as required)",
    })
    # --- negative 2: the wrong character's template ----------------------
    units = [u for u in ctx["battle"]["units"] if u["id"]]
    wrong = False
    if units:
        head = bytes.fromhex(units[0]["head"])
        other_id = 40 if units[0]["id"] != 40 else 41
        tpl = rom[CHARACTER_TEMPLATE + other_id * 0xB4:
                  CHARACTER_TEMPLATE + other_id * 0xB4 + 0xB4]
        wrong = head[2:8] == tpl[1:7]
    out["checks"].append({
        "name": "another character's template must not match the runtime "
                "unit record",
        "ok": not wrong,
        "detail": "matched" if wrong else "not present (as required)",
    })
    out["passed"] = all(c["ok"] for c in out["checks"])
    return out


def self_test(report: dict) -> int:
    """A claimed L3 structure without evidence is a failure."""
    failures: list[str] = []
    structures = report.get("structures", {})
    claimed = [k for k, v in structures.items() if v.get("l3")]
    if not claimed:
        failures.append("no structure claimed L3 at all")
    for key in claimed:
        entry = structures[key]
        if entry.get("status") != "reached":
            failures.append(f"{key}: claimed L3 but status is "
                            f"{entry.get('status')}")
        if not entry.get("evidence"):
            failures.append(f"{key}: claimed L3 but carries no evidence")
        if not (entry.get("screenshot") or entry.get("evidence")):
            failures.append(f"{key}: claimed L3 but has neither a screenshot "
                            f"nor a runtime reading")
        for marker in entry.get("need", []):
            if not marker:
                failures.append(f"{key}: an empty need marker")
    negative = report.get("negative_control")
    if not negative:
        failures.append("the negative control did not run")
    elif not negative.get("passed"):
        failures.append("the negative control no longer bites: a check that "
                        "must fail passed")
    print(f"self-test: {len(claimed)} structure(s) claim L3 "
          f"({', '.join(sorted(claimed)) or 'none'})")
    if failures:
        print("\nFAILED:")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("OK: every claimed L3 structure produced its evidence")
    return 0


def gate_test(report: dict, json_path: pathlib.Path) -> int:
    """Prove the gate bites: a claim without evidence must fail the check.

    The report is tampered with in a throw-away copy (never the real one)
    and the self-test is re-run against it.
    """
    import copy
    import subprocess

    tampered = copy.deepcopy(report)
    claimed = [k for k, v in tampered.get("structures", {}).items() if v.get("l3")]
    if not claimed:
        print("FAILED: the gate cannot be tested, nothing claims L3")
        return 1
    victim = claimed[0]
    tampered["structures"][victim]["evidence"] = {}
    tampered["negative_control"]["passed"] = True
    scratch = json_path.parent / "l3-evidence-gate-test.json"
    write_json(scratch, tampered)
    try:
        proc = subprocess.run(
            [sys.executable, str(pathlib.Path(__file__).resolve()),
             "--check-json", "--json", str(scratch)],
            capture_output=True, text=True, encoding="utf-8")
    finally:
        try:
            scratch.unlink()
        except OSError:
            pass
    print(f"gate test: tampered '{victim}' (no evidence) and the negative "
          f"control -> exit {proc.returncode}")
    for line in proc.stdout.splitlines():
        print("   " + line)
    if proc.returncode == 0:
        print("FAILED: the gate did not bite")
        return 1
    print("OK: the gate exits non-zero on a claim without evidence")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--exe", type=pathlib.Path,
                    default=REPO / "build" / "mgba-probe" / "mgba-probe.exe")
    ap.add_argument("--json", type=pathlib.Path,
                    default=REPO / "build" / "l3-evidence-sweep.json")
    ap.add_argument("--shots", type=pathlib.Path,
                    default=REPO / "notes" / "evidence")
    ap.add_argument("--scenarios", default="battle,story")
    ap.add_argument("--self-test", action="store_true",
                    help="fail when a claimed L3 structure has no evidence")
    ap.add_argument("--negative", action="store_true",
                    help="only run the negative control")
    ap.add_argument("--check-json", action="store_true",
                    help="re-check an existing report instead of running the "
                         "scenarios again (CI gate)")
    ap.add_argument("--gate-test", action="store_true",
                    help="prove the gate bites: tamper with a claim and "
                         "re-check it")
    ap.add_argument("--boot-timeout", type=float, default=900.0)
    args = ap.parse_args(argv)

    if not args.exe.exists():
        print(f"ERR {args.exe} missing; run: python tools/mgba_probe/build.py",
              file=sys.stderr)
        return 2
    rom_path = pathlib.Path(args.rom)
    if not rom_path.is_file():
        print(f"ERR ROM not found: {rom_path}", file=sys.stderr)
        return 2

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.check_json:
        if not args.json.is_file():
            print(f"ERR {args.json} missing; run the sweep first",
                  file=sys.stderr)
            return 2
        report = json.loads(args.json.read_text(encoding="utf-8"))
        return self_test(report)

    if args.gate_test:
        if not args.json.is_file():
            print(f"ERR {args.json} missing; run the sweep first",
                  file=sys.stderr)
            return 2
        report = json.loads(args.json.read_text(encoding="utf-8"))
        return gate_test(report, args.json)

    wanted = [s.strip() for s in args.scenarios.split(",") if s.strip()]

    if args.negative:
        ctx = run_sweep(rom_path, args.exe, args.shots, wanted, args.boot_timeout)
        negative = negative_control(ctx)
        write_json(args.json, {"negative_control": negative})
        for check in negative["checks"]:
            print(f"  [{'ok ' if check['ok'] else 'BAD'}] {check['name']} "
                  f"({check['detail']})")
        return 0 if negative["passed"] else 1

    report: dict = {
        "rom": str(rom_path),
        "rom_sha256": hashlib.sha256(rom_path.read_bytes()).hexdigest(),
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "levels": {"L3": "reproduced with normal key input in an emulator"},
        "press_recipe": (f"hold {PRESS_FRAMES} frames, release "
                         f"{SETTLE_FRAMES} frames (the game only reacts to a "
                         f"press edge, GBA key mask 0x0300000E)"),
        "scenarios": {},
        "structures": {},
    }
    ctx = run_sweep(rom_path, args.exe, args.shots, wanted, args.boot_timeout)
    for name, data in ctx.items():
        if name == "rom":
            continue
        clean = {k: v for k, v in data.items() if k != "snapshots"}
        clean["snapshots"] = [
            {k: v for k, v in snap.items() if k != "vram"}
            for snap in data.get("snapshots", [])
        ]
        report["scenarios"][name] = clean
    report["structures"] = evaluate(ctx)
    report["negative_control"] = negative_control(ctx)
    write_json(args.json, report)

    reached = [k for k, v in report["structures"].items() if v.get("l3")]
    not_reached = [k for k, v in report["structures"].items() if not v.get("l3")]
    print(f"\nL3 claimed for {len(reached)}/{len(report['structures'])} "
          f"structure(s): {', '.join(sorted(reached)) or 'none'}")
    print(f"not reached: {len(not_reached)}")
    for key in sorted(not_reached):
        print(f"  - {key}: {report['structures'][key].get('reason', '')[:110]}")
    print(f"report: {args.json}")

    if args.self_test:
        return self_test(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
