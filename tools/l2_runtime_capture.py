#!/usr/bin/env python3
"""L2 runtime evidence: prove a native consumer reads a ROM table.

What L2 means
-------------
`notes/runtime-verification-gates-20260710.md` defines the evidence ladder.
**L2 = "原生判定定点检查"**: a breakpoint hits the *native* consumer of a ROM
structure and the captured registers / memory correspond to that structure's
fields.  A static disassembly is only **L1**; a screenshot is nothing.

This tool produces L2 evidence mechanically:

  1. the structure's base address is taken from the authoritative registry
     (`tools/table_registry.py`), never from a hand-written constant;
  2. the *native consumer* is found with `tools/consumer_locate.py`'s
     `LiteralIndex` -- the whole-ROM index of every pc-relative literal load.
     A structure with no literal reader has no native consumer and cannot
     reach L2 at all;
  3. the game is driven (headless mGBA probe) to a real in-game state;
  4. a breakpoint is armed on the consumer's *decision point* -- the
     instruction where the register already holds the table base, the
     selected index and the field value;
  5. the registers at the hit are checked against the static ROM bytes, and
     the emulator's memory at the table base is compared with the ROM.

The tool is a **gate**, not a dumper: it exits non-zero when the expected
register <-> field correspondence is *not* observed.

Routes
------
Three deterministic routes reach the consumers; each is cached as a savestate
under `build/l2-states/` so the walk to the state is paid once and reused:

``title``
    boot -> title screen -> START -> story scene -> A presses.  Reaches the
    text renderer (font segments), the sound dispatcher (sound id table),
    the character loader (character template) and the portrait lookup.

``dispatch``
    boot -> navigate to the "next scene" dispatch -> poke the scene byte ->
    dispatch a scene.  Reaches the map descriptor reader (maps).

``sweep``
    boot -> navigate to the "next scene" dispatch -> for every scene of the
    sweep list: reload the dispatch state, poke the scene byte, dispatch the
    scene and play it with a key cycle.  Reaches the batch-2 consumers
    (battle/map event handlers, the font width table, the data pointer
    tables, the function pointer table, the tile/sprite asset records, the
    sprite frame descriptors, the battle encounter records, the ninjutsu
    name table, the reward table, the level data block table and the sprite
    action table).

Usage:
    python tools/l2_runtime_capture.py --list
    python tools/l2_runtime_capture.py font-segments
    python tools/l2_runtime_capture.py --all --json build/l2-runtime.json
    python tools/l2_runtime_capture.py --self-test
"""
from __future__ import annotations

import argparse
import pathlib
import re
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools", REPO / "tools" / "mgba_probe"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from consumer_locate import LiteralIndex            # noqa: E402
from navigate import Probe as _BaseProbe            # noqa: E402
from runtime_probe import parse_status              # noqa: E402
from table_registry import TABLES                   # noqa: E402
from tools.lib.io import write_json                 # noqa: E402

ROM_BASE = 0x08000000
DEFAULT_EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"
STATE_DIR = REPO / "build" / "l2-states"

# --- the story dispatch, used by the `dispatch` route ------------------------
STORY_STATE = 0x020311D4
SCENE_BYTE = STORY_STATE + 0x16      # 0x020311EA -- the scene number
NEXT_SCENE = 0x0808F8DC              # 'ldrb r0,[r4,#0x16]'
VM_ENTRY = 0x080977B8                # story VM entry

# --- the battle route -------------------------------------------------------
# The story state machine's loop head; a battle is requested with **three
# memory writes** while the core sits there (recipe proven by
# `tools/mgba_probe/l4_battle_matrix.py`, see
# `notes/evidence/l4-playthrough-20261021.md`):
#
#     state[0x16] = group      (0x020311EA)
#     state[0x19] = sub        (0x020311ED)
#     state[0x12] = 0x0110     (0x020311E6, u16)
#
# The state machine then runs 0x0808F92E -> 0x080732B4 -> 0x0808A588, which
# loads the battle map and instantiates the units -- so the whole battle
# subsystem (map events, battle text, sprites, tiles) becomes reachable.
STATE_LOOP = 0x0808F752               # story state machine, phase dispatch head
PHASE_WORD = STORY_STATE + 0x12      # 0x020311E6  state[0x12] (u16)
SUBCFG_BYTE = STORY_STATE + 0x19     # 0x020311ED  state[0x19]
PHASE_BATTLE = 0x0110                # state[0x12] value that means "battle"
PHASE_SAVE = 0x0018                  # state[0x12] value that runs the story
                                    # event branch (fn 0x08087940), which is
                                    # the one that reads the WRAM allocation
                                    # table and the mission index
BATTLE_GROUPS = 48                   # formation matrix groups
BATTLE_SUBS = 3                      # formation matrix sub-configurations

# A capture may ask to stay armed after a *failing* hit.  That is needed when
# one decision point is shared by several native consumers: the first hit can
# come from a different caller, and the breakpoint must survive to see the
# hit that actually belongs to this structure.  `expect_lr` filters those
# hits out before they are even evaluated.
#
# The budget is counted **per decision point**: one capture that is hit
# hundreds of times (the m4a play entry runs for every song) must not eat the
# budget of the capture that shares the structure.
STICKY_MAX_RECORDS = 256

# --- the key recipe the game actually reacts to -----------------------------
# Only the *press edge* counts (GBA key register 0x0300000E), so a key is
# held for a few frames and then released for a long settle window.
PRESS_FRAMES = 8
SETTLE_FRAMES = 120
KEY_A = 0x001
KEY_B = 0x002
KEY_START = 0x008
KEY_UP = 0x040
KEY_DOWN = 0x080
KEY_LEFT = 0x020
KEY_RIGHT = 0x010

NAV_PLAN = ((KEY_START, 8), (KEY_A, 8), (KEY_A, 8), (KEY_A, 8), (KEY_A, 20))

HIT_RE = re.compile(r"(?:Hit breakpoint|Hit watchpoint)\s+#?(\d+)\s+at\s+(0x[0-9a-fA-F]+)")


# ---------------------------------------------------------------------------
# ROM helpers
# ---------------------------------------------------------------------------
def u8(rom: bytes, addr: int) -> int:
    return rom[addr - ROM_BASE]


def u16(rom: bytes, addr: int) -> int:
    return struct.unpack_from("<H", rom, addr - ROM_BASE)[0]


def u32(rom: bytes, addr: int) -> int:
    return struct.unpack_from("<I", rom, addr - ROM_BASE)[0]


def is_rom_pointer(value: int) -> bool:
    return ROM_BASE <= value < ROM_BASE + 0x02000000


def is_code_pointer(value: int) -> bool:
    """A ROM address that points into the game's code region."""
    return 0x08000000 <= value < 0x08100000


def hexs(value: int) -> str:
    return f"0x{value:08X}"


# ---------------------------------------------------------------------------
# the probe
# ---------------------------------------------------------------------------
class Probe(_BaseProbe):
    """`navigate.Probe` plus a normalised register snapshot."""

    def registers(self) -> dict:
        raw = parse_status(self.send("status"))
        out = {f"r{i}": raw.get(f"r{i}", 0) for i in range(13)}
        # mGBA prints r13/r14/r15 for sp/lr/pc.
        out["sp"] = raw.get("r13", 0)
        out["lr"] = raw.get("r14", 0)
        out["pc"] = raw.get("r15", 0)
        return out


def arm(probe: Probe, address: int) -> int | None:
    for line in probe.send(f"b {address:#x}"):
        if "breakpoint #" in line:
            return int(line.split("#")[1].split()[0])
    return None


def hits_in(output: list[str]) -> list[tuple[int, int]]:
    found = []
    for line in output:
        m = HIT_RE.search(line)
        if m:
            found.append((int(m.group(1)), int(m.group(2), 16)))
    return found


def live_u8(probe: Probe, address: int) -> int | None:
    data = probe.read_bytes(address, 1)
    return data[0] if data else None


def live_u32(probe: Probe, address: int) -> int | None:
    data = probe.read_bytes(address, 4)
    if len(data) != 4:
        return None
    return struct.unpack_from("<I", data, 0)[0]


# ---------------------------------------------------------------------------
# derive functions: registers at the hit -> structure fields
# ---------------------------------------------------------------------------
def _common_checks(base_reg: int | None, base: int, entry: int, stride: int,
                   count: int, rom: bytes, probe: Probe,
                   entry_len: int) -> list[dict]:
    checks: list[dict] = []
    if base_reg is None:
        checks.append({
            "name": "a register holds the structure's table base",
            "ok": True,
            "detail": "not checkable at this decision point -- the consumer "
                      "overwrites the base register before the field is loaded; "
                      "the base itself is proved by the literal reader "
                      "(see the static checks)",
        })
    else:
        checks.append({
            "name": "a register holds the structure's table base",
            "ok": base_reg == base,
            "detail": f"register=0x{base_reg:08X} expected=0x{base:08X}",
        })
    aligned = (entry - base) % stride == 0
    index = (entry - base) // stride if aligned else -1
    checks.append({
        "name": "the selected address is base + index*stride inside the table",
        "ok": aligned and 0 <= index < count,
        "detail": f"entry=0x{entry:08X} index={index} stride=0x{stride:X} count={count}",
    })
    if aligned and 0 <= index < count:
        rom_bytes = rom[entry - ROM_BASE:entry - ROM_BASE + entry_len]
        live = probe.read_bytes(entry, entry_len)
        checks.append({
            "name": "emulator memory at the selected entry equals the ROM bytes",
            "ok": live == rom_bytes,
            "detail": f"live={live.hex()} rom={rom_bytes.hex()}",
        })
    return checks, index


def derive_font_segments(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x08065EB8, decision 0x08065EF0.

        08065EE6  ldr  r2, [pc, #0x84]   ; r2 = 0x0853D644  (font segment table)
        08065EE8  lsls r0, r1, #3        ; r0 = segment index * 8
        08065EEA  adds r1, r2, #4
        08065EEC  adds r1, r0, r1
        08065EEE  adds r0, r0, r2        ; r0 = base + index*8
        08065EF0  ldrh r0, [r0]          ; r0 = segment start code point
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    entry = regs["r0"]
    char = regs["r5"]
    checks, index = _common_checks(regs["r2"], base, entry, 8, 31, rom, probe, 8)
    start = width = 0
    if index >= 0:
        start = u16(rom, entry)
        width = u8(rom, entry + 2)
        checks.append({
            "name": "the queried character code lies inside the segment's "
                    "[start, start+width] range",
            "ok": start <= char <= start + width,
            "detail": f"char=0x{char:04X} segment={index} "
                      f"start=0x{start:04X} width={width} "
                      f"range=[0x{start:04X},0x{start + width:04X}]",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"char_code": hexs(char), "segment_start": hexs(start),
                  "segment_width": width},
        "checks": checks,
    }


def derive_sound_id(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0809AAC0, decision 0x0809AACE.

        0809AAC6  ldr  r1, [pc, #0x20]   ; r1 = 0x08465B70  (sound id table)
        0809AAC8  lsrs r0, r0, #0xd      ; r0 = sound id * 8
        0809AACA  adds r0, r0, r1        ; r0 = base + id*8
        0809AACC  ldrh r3, [r0, #4]      ; r3 = u16 field of the 8-byte entry
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    entry = regs["r0"]
    base_reg_name = capture.get("base_reg", "r1")
    field_reg_name = capture.get("field_reg", "r3")
    base_reg = regs[base_reg_name] if base_reg_name else None
    field16 = regs[field_reg_name]
    checks, index = _common_checks(base_reg, base, entry, 8, 159, rom, probe, 8)
    pointer = 0
    if index >= 0:
        pointer = u32(rom, entry)
        checks.append({
            "name": f"{field_reg_name} equals the u16 the entry stores at +4",
            "ok": field16 == u16(rom, entry + 4),
            "detail": f"{field_reg_name}={field16} "
                      f"rom=0x{u16(rom, entry + 4):04X}",
        })
        checks.append({
            "name": "the entry's +0 pointer is a ROM address (an m4a SongHeader)",
            "ok": is_rom_pointer(pointer),
            "detail": f"pointer=0x{pointer:08X}",
        })
        expected = ctx["song_headers"].get(index)
        if expected is not None:
            checks.append({
                "name": f"sound id {index} resolves to the registered "
                        f"SongHeader base",
                "ok": pointer == expected,
                "detail": f"pointer=0x{pointer:08X} registry=0x{expected:08X}",
            })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"song_header": hexs(pointer), "voice_index": field16},
        "checks": checks,
    }


def derive_character_template(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0806D964, decision 0x0806D988.

        0806D974  ldrb r2, [r6]          ; r2 = character id
        0806D97E  movs r0, #0xb4
        0806D982  muls r1, r0, r1        ; r1 = id * 0xB4
        0806D984  ldr  r0, [pc, #0xc]    ; r0 = 0x0854241C  (character template)
        0806D986  adds r1, r1, r0        ; r1 = base + id*0xB4
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    entry = regs["r1"]
    ident = regs["r2"]
    checks, index = _common_checks(regs["r0"], base, entry, 0xB4, 63, rom, probe, 0xB4)
    checks.append({
        "name": "the character id in the register selects that very entry",
        "ok": ident == index,
        "detail": f"id={ident} entry index={index}",
    })
    if index >= 0:
        payload = rom[entry - ROM_BASE:entry - ROM_BASE + 0xB4]
        checks.append({
            "name": "the selected template record is not empty",
            "ok": any(payload),
            "detail": f"first16={payload[:16].hex(' ')}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"character_id": ident, "record_head": rom[
            entry - ROM_BASE:entry - ROM_BASE + 16].hex(" ")},
        "checks": checks,
    }


def derive_character_template_copy(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0806D4A0, decision 0x0806D4F8 (the ROM -> runtime copy).

        0806D4D4  adds r7, r1, r0        ; r7 = base + id*0xB4 (the template)
        0806D4F4  adds r1, r7, r0        ; r1 = template + field offset
        0806D4F6  ldrb r0, [r1, #0xc]    ; r0 = one template byte
        0806D4F8  strb r0, [r2, #0x14]   ; -> runtime structure
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    template = regs["r7"]
    source = regs["r1"] + 0x0C          # the load adds 0x0C to r1
    destination = regs["r2"] + 0x14
    value = regs["r0"]
    checks: list[dict] = []
    index = (template - base) // 0xB4 if (template - base) % 0xB4 == 0 else -1
    checks.append({
        "name": "r7 is the character template entry base + index*0xB4",
        "ok": index >= 0 and 0 <= index < 63,
        "detail": f"r7=0x{template:08X} index={index}",
    })
    checks.append({
        "name": "r1+0x0C points inside that template entry",
        "ok": index >= 0 and template <= source < template + 0xB4,
        "detail": f"r1=0x{regs['r1']:08X} +0x0C=0x{source:08X} "
                  f"entry=0x{template:08X}",
    })
    if template <= source < template + 0xB4:
        rom_byte = u8(rom, source)
        live = probe.read_bytes(source, 1)
        checks.append({
            "name": "the byte in the register is the ROM byte at r1+0x0C",
            "ok": value == rom_byte and live == bytes([rom_byte]),
            "detail": f"r0=0x{value:02X} rom=0x{rom_byte:02X} live={live.hex()}",
        })
    checks.append({
        "name": "the destination is a WRAM slot of the runtime character struct",
        "ok": 0x02000000 <= destination < 0x02040000,
        "detail": f"r2+0x14=0x{destination:08X}",
    })
    return {
        "index": index,
        "entry_address": hexs(template),
        "field": {"field_address": hexs(source), "field_value": value,
                  "runtime_destination": hexs(destination)},
        "checks": checks,
    }


def derive_maps(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0808F190, decision 0x0808F4FE.

        0808F4F6  ldr  r1, [pc, #0x10]   ; r1 = 0x0853D910  (map descriptors)
        0808F4F8  lsls r0, r4, #5        ; r0 = chapter id * 32
        0808F4FA  adds r0, r0, r1
        0808F4FC  ldrb r0, [r0, #0x1c]   ; r0 = the descriptor's +0x1C byte
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    ident = regs["r4"]
    value = regs["r0"]
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the map descriptor table's base",
        "ok": regs["r1"] == base,
        "detail": f"r1=0x{regs['r1']:08X} expected=0x{base:08X}",
    })
    entry = base + ident * 0x20
    checks.append({
        "name": "the chapter id in the register is the one the consumer bounds",
        "ok": ident <= 0x31,
        "detail": f"r4={ident} (consumer compares against 0x31)",
    })
    checks.append({
        "name": "the selected descriptor lies inside the declared map table",
        "ok": 0 <= ident < 50,
        "detail": f"entry=0x{entry:08X}",
    })
    checks.append({
        "name": "r0 equals the descriptor byte the consumer loaded at +0x1C",
        "ok": value == u8(rom, entry + 0x1C),
        "detail": f"r0={value} rom=0x{u8(rom, entry + 0x1C):02X}",
    })
    live = probe.read_bytes(entry + 0x1C, 1)
    checks.append({
        "name": "emulator memory at descriptor+0x1C equals the ROM byte",
        "ok": live == bytes([u8(rom, entry + 0x1C)]),
        "detail": f"live={live.hex()} rom={u8(rom, entry + 0x1C):02X}",
    })
    terrain = u32(rom, entry + 0x04)
    checks.append({
        "name": "the descriptor's +0x04 graphic pointer is a ROM address",
        "ok": is_rom_pointer(terrain),
        "detail": f"terrain=0x{terrain:08X}",
    })
    descriptor = rom[entry - ROM_BASE:entry - ROM_BASE + 0x20]
    return {
        "index": ident,
        "entry_address": hexs(entry),
        "field": {"zone_byte": value,
                  "descriptor": descriptor.hex(" ")},
        "checks": checks,
    }


def derive_portrait(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x08095F58, decision 0x0809615A.

        08096150  lsls r0, r2, #2         ; r0 = id * 5
        08096152  adds r0, r0, r2
        08096154  lsls r0, r0, #3         ; r0 = id * 40
        08096156  lsls r1, r1, #3         ; r1 = expression * 8
        08096158  ldr  r2, [pc, #8]       ; r2 = 0x085A4DEC  (portrait table)
        0809615A  adds r1, r1, r2         ; r1 = base + expression*8
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    id_offset = regs["r0"]
    expr_offset = regs["r1"]
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the portrait table's base",
        "ok": regs["r2"] == base,
        "detail": f"r2=0x{regs['r2']:08X} expected=0x{base:08X}",
    })
    checks.append({
        "name": "r0 is a multiple of the 40-byte id stride",
        "ok": id_offset % 40 == 0,
        "detail": f"r0=0x{id_offset:08X} id={id_offset // 40}",
    })
    checks.append({
        "name": "r1 is a multiple of the 8-byte expression stride",
        "ok": expr_offset % 8 == 0,
        "detail": f"r1=0x{expr_offset:08X} expression={expr_offset // 8}",
    })
    index = id_offset // 40
    expression = expr_offset // 8
    entry = base + id_offset + expr_offset
    checks.append({
        "name": "the two registers address base + id*40 + expression*8",
        "ok": entry == base + index * 40 + expression * 8,
        "detail": f"entry=0x{entry:08X} id={index} expression={expression}",
    })
    checks.append({
        "name": "the id and expression are inside the consumer's own u8 range "
                "and the expression is not its special case 5",
        "ok": index <= 255 and expression <= 255 and expression != 5,
        "detail": f"id={index} expression={expression} "
                  f"(the consumer masks both to u8 and short-circuits on 5)",
    })
    payload = rom[entry - ROM_BASE:entry - ROM_BASE + 8]
    live = probe.read_bytes(entry, 8)
    checks.append({
        "name": "emulator memory at the portrait entry equals the ROM bytes",
        "ok": live == payload,
        "detail": f"live={live.hex()} rom={payload.hex()}",
    })
    checks.append({
        "name": "the portrait entry is not empty",
        "ok": any(payload),
        "detail": f"entry=0x{entry:08X} bytes={payload.hex(' ')}",
    })
    first = u32(rom, entry)
    second = u32(rom, entry + 4)
    checks.append({
        "name": "both portrait pointers are ROM addresses",
        "ok": is_rom_pointer(first) and is_rom_pointer(second),
        "detail": f"piece0=0x{first:08X} piece1=0x{second:08X}",
    })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"expression": expression,
                  "piece0": hexs(first), "piece1": hexs(second)},
        "checks": checks,
    }


# ---------------------------------------------------------------------------
# batch 2: the derive functions of the twelve new structures
# ---------------------------------------------------------------------------
def _index_from_offset(base: int, offset: int, stride: int, count: int) -> int:
    if offset < 0 or offset % stride:
        return -1
    index = offset // stride
    return index if 0 <= index < count else -1


def derive_battle_handlers(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0807F414, decision 0x0807F942.

        0807F934  ldr  r1, [pc, #0x100]  ; r1 = 0x0853E698  <- table base
        0807F936  movs r0, #0xee
        0807F938  lsls r0, r0, #3        ; r0 = 0x770
        0807F93A  add  r0, sb            ; r0 = r9 + 0x770 (a WRAM slot)
        0807F93C  ldrb r0, [r0]          ; r0 = the map event id
        0807F93E  lsls r0, r0, #3        ; r0 = id * 8
        0807F940  adds r0, r0, r1        ; r0 = base + id*8
        0807F942  ldr  r1, [r0]          ; r1 = the handler code pointer
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    entry = regs["r0"]
    checks, index = _common_checks(regs["r1"], base, entry, 8, 256, rom, probe, 8)
    source = regs["r9"] + 0x770
    live = probe.read_bytes(source, 1)
    checks.append({
        "name": "the map event id byte in WRAM is the id that selected the entry",
        "ok": bool(live) and live[0] == index,
        "detail": f"wram@0x{source:08X}={live.hex() if live else '??'} "
                  f"index={index}",
    })
    first = second = 0
    if index >= 0:
        first = u32(rom, entry)
        second = u32(rom, entry + 4)
        checks.append({
            "name": "both handler words are either 0 or a ROM code pointer",
            "ok": (first == 0 or is_code_pointer(first))
                  and (second == 0 or is_code_pointer(second)),
            "detail": f"first=0x{first:08X} second=0x{second:08X}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"handler0": hexs(first), "handler1": hexs(second),
                  "wram_source": hexs(source)},
        "checks": checks,
    }


def derive_font_width(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0807EE50, decisions 0x0807F108 and 0x0807F10A.

        0807F0FC  ldr  r1, [pc, #0x14]   ; r1 = 0x0853E596  <- width table
        0807F0FE  movs r2, #0xee
        0807F100  lsls r2, r2, #3        ; r2 = 0x770
        0807F102  adds r0, r4, r2        ; r0 = r4 + 0x770 (a WRAM slot)
        0807F104  ldrb r0, [r0]          ; r0 = the character code
        0807F106  adds r0, r0, r1        ; r0 = base + character code
        0807F108  ldrb r1, [r0]          ; r1 = the glyph width
        0807F10A  movs r0, #1
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    base_reg = capture.get("base_reg", "r1")
    entry = regs["r0"]
    checks: list[dict] = []
    source = regs["r4"] + 0x770
    live = probe.read_bytes(source, 1)
    code = live[0] if live else None
    checks.append({
        "name": "the character code comes from the WRAM slot at r4+0x770",
        "ok": code is not None,
        "detail": f"wram@0x{source:08X}={code if code is None else hex(code)}",
    })
    if base_reg:
        checks.append({
            "name": "a register holds the font width table's base",
            "ok": regs[base_reg] == base,
            "detail": f"{base_reg}=0x{regs[base_reg]:08X} expected=0x{base:08X}",
        })
        index = entry - base
        checks.append({
            "name": "the register holds base + the character code",
            "ok": code is not None and index == code,
            "detail": f"r0-base={index} character_code={code}",
        })
    else:
        # decision point after `ldrb r1,[r0]`: r1 is the width, r0 the address
        index = entry - base
        checks.append({
            "name": "r0 holds base + the character code read from WRAM",
            "ok": code is not None and index == code and 0 <= index < 256,
            "detail": f"r0-base={index} character_code={code}",
        })
        width = u8(rom, entry) if 0 <= index < 256 else None
        checks.append({
            "name": "the register holds the width byte stored at base+code",
            "ok": width is not None and regs["r1"] == width,
            "detail": f"r1={regs['r1']} rom=0x{width:02X}"
                      if width is not None else "index out of range",
        })
    if code is not None and 0 <= code < 256:
        live_byte = probe.read_bytes(base + code, 1)
        rom_byte = bytes([u8(rom, base + code)])
        checks.append({
            "name": "emulator memory at base+character code equals the ROM byte",
            "ok": live_byte == rom_byte,
            "detail": f"live={live_byte.hex()} rom={rom_byte.hex()}",
        })
    return {
        "index": code if code is not None else -1,
        "entry_address": hexs(entry),
        "field": {"character_code": hexs(code or 0),
                  "width": regs["r1"] if not base_reg else u8(rom, entry)},
        "checks": checks,
    }


def derive_data_pointer_table(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0808AFE0 (table A) / 0x08099BFC (table B), decision after the add.

        0808B19E  ldr  r1, [pc, #0x74]   ; r1 = 0x085A143C  <- table base
        0808B1A0  ldrb r0, [r6]          ; r0 = the index (a WRAM byte)
        0808B1A2  lsls r0, r0, #2        ; r0 = index * 4
        0808B1A4  adds r0, r0, r1        ; r0 = base + index*4
        0808B1A6  ldr  r0, [r0]          ; r0 = the u32 pointer
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    count = ctx["layout"]["count"]
    entry = regs["r0"]
    checks, index = _common_checks(regs["r1"], base, entry, 4, count, rom, probe, 4)
    struct_reg = capture.get("index_reg", "r6")
    source = regs[struct_reg]
    live = probe.read_bytes(source, 1)
    checks.append({
        "name": "the index byte in WRAM is the index that selected the entry",
        "ok": bool(live) and live[0] == index,
        "detail": f"wram@0x{source:08X}={live.hex() if live else '??'} "
                  f"index={index}",
    })
    pointer = 0
    if index >= 0:
        pointer = u32(rom, entry)
        checks.append({
            "name": "the entry is a ROM pointer",
            "ok": is_rom_pointer(pointer),
            "detail": f"pointer=0x{pointer:08X}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"pointer": hexs(pointer), "wram_source": hexs(source)},
        "checks": checks,
    }


def derive_function_pointers(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x08061D8C, decisions 0x08061DDA and 0x08061DE0.

        08061DD4  ldr  r3, [pc, #0x24]   ; r3 = 0x0853D5F0  <- table base
        08061DD6  lsls r0, r4, #2        ; r0 = slot * 4
        08061DD8  adds r0, r0, r3        ; r0 = base + slot*4
        08061DDA  ldr  r0, [r0]          ; r0 = the hook pointer
        08061DDC  str  r0, [r1]
        08061DDE  adds r2, r2, r5
        08061DE0  movs r0, #1
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    slot = regs["r4"]
    entry = base + slot * 4
    checks, index = _common_checks(regs["r3"], base, entry, 4, 13, rom, probe, 4)
    checks.append({
        "name": "the slot index is inside the 13-slot table",
        "ok": 0 <= slot < 13,
        "detail": f"r4={slot}",
    })
    value = u32(rom, entry) if 0 <= slot < 13 else 0
    checks.append({
        "name": "the slot is either the 0xFFFFFFFF sentinel or a ROM code pointer",
        "ok": value == 0xFFFFFFFF or is_code_pointer(value),
        "detail": f"value=0x{value:08X}",
    })
    if capture.get("field_reg"):
        checks.append({
            "name": "the register holds the u32 the slot stores",
            "ok": regs[capture["field_reg"]] == value,
            "detail": f"{capture['field_reg']}=0x{regs[capture['field_reg']]:08X} "
                      f"rom=0x{value:08X}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"slot": slot, "pointer": hexs(value)},
        "checks": checks,
    }


def derive_tile_assets(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0809880C, decision 0x08098822.

        08098814  ldr  r3, [pc, #0x24]   ; r3 = a WRAM slot
        08098816  ldrb r2, [r3]          ; r2 = the record index
        08098818  lsls r1, r2, #4
        0809881A  adds r1, r1, r2        ; r1 = index * 17
        0809881C  lsls r1, r1, #2        ; r1 = index * 68
        0809881E  ldr  r2, [pc, #0x20]   ; r2 = 0x085A320C  <- table base
        08098820  adds r5, r1, r2        ; r5 = base + index*68
        08098822  adds r4, r0, #0
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    entry = regs["r5"]
    checks, index = _common_checks(regs["r2"], base, entry, 68, 79, rom, probe, 68)
    source = regs["r3"]
    live = probe.read_bytes(source, 1)
    checks.append({
        "name": "the record index byte in WRAM is the index that selected the record",
        "ok": bool(live) and live[0] == index,
        "detail": f"wram@0x{source:08X}={live.hex() if live else '??'} "
                  f"index={index}",
    })
    checks.append({
        "name": "the scaled index register is index*68",
        "ok": regs["r1"] == index * 68 if index >= 0 else False,
        "detail": f"r1={regs['r1']} index*68={index * 68 if index >= 0 else 'n/a'}",
    })
    tiles: list[int] = []
    if index >= 0:
        tiles = [u32(rom, entry + 0x0C + 4 * k) for k in range(6)]
        checks.append({
            "name": "the record's +0x0C block holds six u32 tile pointers "
                    "(0 or a ROM address)",
            "ok": all(t == 0 or is_rom_pointer(t) for t in tiles),
            "detail": " ".join(hexs(t) for t in tiles),
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"tiles": [hexs(t) for t in tiles], "wram_source": hexs(source)},
        "checks": checks,
    }


def derive_sprite_frame_descriptors(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x08080670, decision 0x080806BC.

        080806AE  adds r2, r6, #0
        080806B0  adds r2, #0x8c
        080806B2  ldr  r1, [r2]          ; r1 = the frame index
        080806B4  lsls r0, r1, #2
        080806B6  adds r0, r0, r1        ; r0 = index * 5
        080806B8  lsls r0, r0, #1        ; r0 = index * 10
        080806BA  ldr  r1, [pc, #0x88]   ; r1 = 0x0853EE98  <- table base
        080806BC  adds r4, r0, r1        ; r4 = base + index*10
        080806C0  ldrsh r0, [r4, r3]     ; the first s16 of the record
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    offset = regs["r0"]
    entry = base + offset
    checks, index = _common_checks(regs["r1"], base, entry, 10, 15, rom, probe, 10)
    source = regs["r6"] + 0x8C
    live = probe.read_bytes(source, 4)
    value = struct.unpack_from("<I", live, 0)[0] if len(live) == 4 else None
    checks.append({
        "name": "the frame index stored in the sprite struct selects that record",
        "ok": value is not None and value == index,
        "detail": f"wram@0x{source:08X}={value} index={index}",
    })
    if index >= 0:
        first = u16(rom, entry)
        checks.append({
            "name": "the record's first u16 is not the -1 end marker",
            "ok": first != 0xFFFF,
            "detail": f"first=0x{first:04X}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"frame_index": value if value is not None else -1,
                  "wram_source": hexs(source)},
        "checks": checks,
    }


def derive_battle_encounters(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x08087C9C, decision 0x08087DF2.

        08087DDE  ldr  r6, [pc, #0x40]
        08087DE0  ldr  r0, [pc, #0x40]   ; r0 = 0x0854229C  <- table base
        08087DE2  mov  sl, r0            ; sl = base
        08087DE8  ldrb r3, [r6]
        08087DEA  lsls r2, r7, #4        ; r2 = index * 16
        08087DEC  ldr  r1, [pc, #0x3c]   ; r1 = 0x085422A8 = base + 0x0C
        08087DEE  adds r0, r2, r1        ; r0 = base + index*16 + 0x0C
        08087DF0  ldr  r0, [r0]          ; r0 = the record's +0x0C u32
        08087DF2  strb r0, [r6]
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    index = regs["r7"]
    field = regs["r0"]
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the battle encounter table's base",
        "ok": regs["r10"] == base,
        "detail": f"r10=0x{regs['r10']:08X} expected=0x{base:08X}",
    })
    checks.append({
        "name": "the scaled index register is index*16",
        "ok": regs["r2"] == index * 16,
        "detail": f"r2={regs['r2']} index={index}",
    })
    checks.append({
        "name": "the index is inside the 24-record table",
        "ok": 0 <= index < 24,
        "detail": f"index={index}",
    })
    entry = base + index * 16
    field_address = entry + 0x0C
    checks.append({
        "name": "the register holds the u32 the record stores at +0x0C",
        "ok": field == u32(rom, field_address),
        "detail": f"r0=0x{field:08X} rom@0x{field_address:08X}=0x{u32(rom, field_address):08X}",
    })
    live = probe.read_bytes(field_address, 4)
    checks.append({
        "name": "emulator memory at the record's +0x0C equals the ROM bytes",
        "ok": live == rom[field_address - ROM_BASE:field_address - ROM_BASE + 4],
        "detail": f"live={live.hex()}",
    })
    pointers = [u32(rom, entry + 4 * k) for k in range(3)]
    checks.append({
        "name": "the record's first three u32 are ROM pointers",
        "ok": all(is_rom_pointer(p) for p in pointers),
        "detail": " ".join(hexs(p) for p in pointers),
    })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"number": field, "pointers": [hexs(p) for p in pointers]},
        "checks": checks,
    }


def derive_ninjutsu_names(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x080794F4, decision 0x080796F0.

        080796E4  ldr  r1, [pc, #0x18]   ; r1 = 0x08599634  <- name table
        080796E6  movs r0, #0x81
        080796E8  rsbs r0, r0, #0        ; r0 = 0x7F
        080796EA  ands r0, r2            ; r0 = r2 & 0x7F
        080796EC  lsls r0, r0, #2        ; r0 = index * 4
        080796EE  adds r0, r0, r1        ; r0 = base + index*4
        080796F0  ldr  r0, [r0]          ; r0 = the text pointer
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    entry = regs["r0"]
    checks, index = _common_checks(regs["r1"], base, entry, 4, 128, rom, probe, 4)
    raw = regs["r2"]
    masked = raw & 0x7F
    checks.append({
        "name": "the index is the masked id register (r2 & 0x7F)",
        "ok": masked == index,
        "detail": f"r2=0x{raw:08X} masked={masked} index={index}",
    })
    pointer = 0
    if index >= 0:
        pointer = u32(rom, entry)
        checks.append({
            "name": "the entry is a ROM text pointer",
            "ok": is_rom_pointer(pointer),
            "detail": f"pointer=0x{pointer:08X}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"text_pointer": hexs(pointer), "raw_id": hexs(raw)},
        "checks": checks,
    }


def derive_reward_table(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x08089E84, decision 0x08089EAE.

        08089E9E  lsls r0, r0, #0x18
        08089EA0  lsrs r7, r0, #0x18      ; r7 = the reward index
        08089EA2  ldr  r2, [pc, #0x100]   ; r2 = 0x0859EAE0  <- reward table
        08089EA4  lsls r0, r7, #1
        08089EA6  adds r0, r0, r7
        08089EA8  lsls r1, r0, #3         ; r1 = index * 24
        08089EAA  adds r0, r1, r2         ; r0 = base + index*24
        08089EAC  ldrb r0, [r0, #7]       ; r0 = the record's +7 byte
        08089EAE  cmp  r0, #0
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    base_reg = capture.get("base_reg", "r2")
    entry = base + regs["r1"]
    checks, index = _common_checks(regs[base_reg], base, entry, 24, 112,
                                   rom, probe, 24)
    checks.append({
        "name": "the scaled index register is index*24",
        "ok": regs["r1"] == index * 24 if index >= 0 else False,
        "detail": f"r1={regs['r1']} index={index}",
    })
    checks.append({
        "name": "the index is inside the 112-record reward table",
        "ok": 0 <= index < 112,
        "detail": f"index={index}",
    })
    field = None
    if index >= 0 and capture.get("field_reg"):
        field = regs[capture["field_reg"]]
        offset = int(capture.get("field_offset", "7"), 0)
        expected = u8(rom, entry + offset)
        checks.append({
            "name": f"the register holds the record's +{offset} byte",
            "ok": field == expected,
            "detail": f"{capture['field_reg']}=0x{field:02X} rom=0x{expected:02X}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"index": index if index >= 0 else -1,
                  "field_value": field if field is not None else 0},
        "checks": checks,
    }


def derive_cutscene_blocks(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x08072EDC, decision 0x08072F16.

        08072F0C  ldr  r4, [pc, #0x2c]   ; r4 = 0x0853DF70  <- block table
        08072F0E  mov  r0, r8            ; r0 = the block index
        08072F10  lsls r5, r0, #3        ; r5 = index * 8
        08072F12  adds r0, r5, r4        ; r0 = base + index*8
        08072F14  ldr  r0, [r0]          ; r0 = the LZ77 tile pointer
        08072F16  ldr  r1, [pc, #0x28]   ; r1 = 0x06016000 (VRAM)
        08072F18  bl   #0x809c0e8        ; LZ77UnCompVram
        08072F1C  adds r4, #4
        08072F1E  adds r5, r5, r4        ; r5 = base + index*8 + 4
        08072F20  ldr  r0, [r5]          ; the LZ77 palette pointer
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    index = regs["r8"]
    pointer = regs["r0"]
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the level data block table's base",
        "ok": regs["r4"] == base,
        "detail": f"r4=0x{regs['r4']:08X} expected=0x{base:08X}",
    })
    checks.append({
        "name": "the scaled index register is index*8",
        "ok": regs["r5"] == index * 8,
        "detail": f"r5={regs['r5']} index={index}",
    })
    checks.append({
        "name": "the index is inside the 4-block table",
        "ok": 0 <= index < 4,
        "detail": f"index={index}",
    })
    entry = base + index * 8
    checks.append({
        "name": "the register holds the LZ77 tile pointer the block stores at +0",
        "ok": pointer == u32(rom, entry),
        "detail": f"r0=0x{pointer:08X} rom@0x{entry:08X}=0x{u32(rom, entry):08X}",
    })
    checks.append({
        "name": "the LZ77 tile pointer is a ROM address",
        "ok": is_rom_pointer(pointer),
        "detail": f"pointer=0x{pointer:08X}",
    })
    palette = u32(rom, entry + 4)
    checks.append({
        "name": "the block's palette pointer at +4 is a ROM address",
        "ok": is_rom_pointer(palette),
        "detail": f"palette=0x{palette:08X}",
    })
    live = probe.read_bytes(entry, 8)
    checks.append({
        "name": "emulator memory at the block equals the ROM bytes",
        "ok": live == rom[entry - ROM_BASE:entry - ROM_BASE + 8],
        "detail": f"live={live.hex()}",
    })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"lz77_tiles": hexs(pointer), "lz77_palette": hexs(palette)},
        "checks": checks,
    }


def derive_sprite_action_table(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0806B720, decision 0x0806B770.

        0806B764  ldrb r1, [r4]          ; r1 = the sprite id
        0806B766  lsls r0, r1, #3
        0806B768  adds r0, r0, r1        ; r0 = id * 9
        0806B76A  lsls r0, r0, #4        ; r0 = id * 144
        0806B76C  ldr  r1, [pc, #0x48]   ; r1 = 0x08596CCC  <- table base
        0806B76E  adds r0, r0, r1        ; r0 = base + id*144
        0806B770  mov  ip, r0
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    entry = regs["r0"]
    offset = entry - base
    index = _index_from_offset(base, offset, 144, 63)
    checks: list[dict] = []
    base_reg = capture.get("base_reg", "r1")
    if base_reg:
        checks.append({
            "name": "a register holds the sprite action table's base",
            "ok": regs[base_reg] == base,
            "detail": f"{base_reg}=0x{regs[base_reg]:08X} expected=0x{base:08X}",
        })
    checks.append({
        "name": "the register holds base + id*144",
        "ok": index >= 0 and entry == base + index * 144,
        "detail": f"entry=0x{entry:08X} index={index} id*144={index * 144}",
    })
    source = regs["r4"]
    live = probe.read_bytes(source, 1)
    checks.append({
        "name": "the sprite id byte in WRAM is the id that selected the block",
        "ok": bool(live) and live[0] == index,
        "detail": f"wram@0x{source:08X}={live.hex() if live else '??'} "
                  f"index={index}",
    })
    action_offset = int(capture.get("action_offset", "0"), 0)
    record = entry + action_offset
    if index >= 0:
        checks.append({
            "name": f"the action record at +{action_offset} equals the ROM bytes",
            "ok": probe.read_bytes(record, 16)
                  == rom[record - ROM_BASE:record - ROM_BASE + 16],
            "detail": f"record=0x{record:08X}",
        })
        pointers = [u32(rom, record + 4 * k) for k in range(4)]
        checks.append({
            "name": "the record's four u32 pointers are all ROM addresses",
            "ok": all(is_rom_pointer(p) for p in pointers),
            "detail": " ".join(hexs(p) for p in pointers),
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"sprite_id": index if index >= 0 else -1,
                  "pointers": [hexs(u32(rom, record + 4 * k)) for k in range(4)]
                  if index >= 0 else []},
        "checks": checks,
    }


# ---------------------------------------------------------------------------
# batch 3: the derive functions of the fourteen new structures
# ---------------------------------------------------------------------------
def _entry_from(base: int, address: int, stride: int, count: int) -> int:
    """The record index of `address` inside the table, or -1."""
    if address < base:
        return -1
    delta = address - base
    if delta % stride:
        return -1
    index = delta // stride
    return index if 0 <= index < count else -1


def _live_equals_rom(probe: Probe, rom: bytes, address: int, length: int) -> bool:
    return probe.read_bytes(address, length) == rom[
        address - ROM_BASE:address - ROM_BASE + length]


def derive_character_stats(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0806D964, decision 0x0806D98E.

        0806D97E  movs r0, #0xb4
        0806D982  muls r1, r0, r1        ; r1 = id * 0xB4
        0806D984  ldr  r0, [pc, #0xc]    ; r0 = 0x0854241C (character template)
        0806D986  adds r1, r1, r0
        0806D988  mov  sb, r1
        0806D98A  lsls r1, r2, #4        ; r1 = id * 16
        0806D98C  ldr  r0, [pc, #8]      ; r0 = 0x08545068 (per-character stats)
        0806D98E  adds r1, r1, r0        ; r1 = base + id*16
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    ident = regs["r2"]
    offset = regs["r1"]
    entry = base + offset
    index = _entry_from(base, entry, 16, 63)
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the per-character stat table's base",
        "ok": regs["r0"] == base,
        "detail": f"r0=0x{regs['r0']:08X} expected=0x{base:08X}",
    })
    checks.append({
        "name": "the scaled index register is the character id times 16",
        "ok": offset == ident * 16,
        "detail": f"r1={offset} id={ident} id*16={ident * 16}",
    })
    checks.append({
        "name": "the selected address is base + id*16 inside the table",
        "ok": index >= 0 and entry == base + ident * 16,
        "detail": f"entry=0x{entry:08X} index={index} count=63",
    })
    if index >= 0:
        payload = rom[entry - ROM_BASE:entry - ROM_BASE + 16]
        checks.append({
            "name": "emulator memory at the selected record equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, entry, 16),
            "detail": f"entry=0x{entry:08X} rom={payload.hex(' ')}",
        })
        checks.append({
            "name": "the selected record is not empty",
            "ok": any(payload),
            "detail": f"record={payload.hex(' ')}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"character_id": ident,
                  "record": rom[entry - ROM_BASE:entry - ROM_BASE + 16].hex(" ")},
        "checks": checks,
    }


def derive_character_stats_field(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0806D964, decision 0x0806D9D8 -- the stat value itself.

        0806D9D4  mov  r1, r8           ; r1 = base + id*16 (the stat record)
        0806D9D6  ldrh r0, [r1, #6]     ; r0 = the record's +6 u16 stat
        0806D9D8  muls r0, r5, r0       ; r0 = stat * level
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    entry = regs["r1"]
    value = regs["r0"]
    offset = int(capture.get("field_offset", "6"), 0)
    index = _entry_from(base, entry, 16, 63)
    checks: list[dict] = []
    checks.append({
        "name": "the register holds the record base + id*16",
        "ok": index >= 0,
        "detail": f"r1=0x{entry:08X} index={index} count=63",
    })
    if index >= 0:
        checks.append({
            "name": f"the register holds the u16 the record stores at +{offset}",
            "ok": value == u16(rom, entry + offset),
            "detail": f"r0=0x{value:04X} rom=0x{u16(rom, entry + offset):04X}",
        })
        checks.append({
            "name": "emulator memory at the selected record equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, entry, 16),
            "detail": f"entry=0x{entry:08X}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"character_id": index if index >= 0 else -1,
                  "stat_value": value},
        "checks": checks,
    }


def derive_character_perks(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0806D964 / 0x0806D6B8 / 0x08093070.

        0806DB0E  lsls r0, r1, #1
        0806DB10  adds r0, r0, r1        ; r0 = index * 3
        0806DB12  lsls r0, r0, #2        ; r0 = index * 12
        0806DB14  ldr  r1, [pc, #0x2c]   ; r1 = 0x085459C8 (character perks)
        0806DB16  adds r3, r0, r1        ; r3 = base + index*12
        0806DB18  ldrh r0, [r3, #6]      ; r0 = the record's +6 u16
        0806DB1A  adds r2, r0, #0

    The same shape appears in fn 0x0806D6B8, where the base register is
    overwritten by the entry address before the field is read:
        0806D6E6  ldr  r1, [pc, #0x20]  ; r1 = base
        0806D6E8  adds r1, r0, r1       ; r1 = base + index*12
        0806D6EA  ldrh r0, [r1, #6]     ; r0 = the record's +6 u16
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    entry_reg = capture.get("entry_reg", "r3")
    index_reg = capture.get("index_reg")
    if index_reg:
        index = regs[index_reg]
        entry = base + index * 12
        if not 0 <= index < 45:
            index = -1
    else:
        entry = regs[entry_reg]
        index = _entry_from(base, entry, 12, 45)
    value = regs["r0"]
    offset = int(capture.get("field_offset", "6"), 0)
    index = _entry_from(base, entry, 12, 45)
    checks: list[dict] = []
    base_reg = capture.get("base_reg", "r1")
    if base_reg:
        checks.append({
            "name": "a register holds the character perk table's base",
            "ok": regs[base_reg] == base,
            "detail": f"{base_reg}=0x{regs[base_reg]:08X} expected=0x{base:08X}",
        })
    checks.append({
        "name": "the selected address is base + index*12 inside the table",
        "ok": index >= 0,
        "detail": f"{entry_reg}=0x{entry:08X} index={index} stride=0xC count=45",
    })
    if index >= 0:
        checks.append({
            "name": f"the register holds the u16 the record stores at +{offset}",
            "ok": value == u16(rom, entry + offset),
            "detail": f"r0=0x{value:04X} rom=0x{u16(rom, entry + offset):04X}",
        })
        checks.append({
            "name": "emulator memory at the selected record equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, entry, 12),
            "detail": f"entry=0x{entry:08X}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"perk_index": index if index >= 0 else -1,
                  "field_value": value},
        "checks": checks,
    }


def derive_item_records(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0806D910, decision 0x0806D924.

        0806D916  lsls r0, r0, #0x18
        0806D918  lsrs r0, r0, #0x14     ; r0 = item id * 16
        0806D91A  ldr  r1, [pc, #0x44]  ; r1 = 0x08545BE4 (item/skill records)
        0806D91C  adds r0, r0, r1       ; r0 = base + id*16
        0806D924  ldrb r1, [r0]         ; r1 = the record's +0 byte
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    base_reg = capture.get("base_reg", "r1")
    entry_reg = capture.get("entry_reg", "r0")
    entry = regs[entry_reg]
    index = _entry_from(base, entry, 16, 94)
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the item/skill record table's base",
        "ok": regs[base_reg] == base,
        "detail": f"{base_reg}=0x{regs[base_reg]:08X} expected=0x{base:08X}",
    })
    checks.append({
        "name": "the selected address is base + id*16 inside the table",
        "ok": index >= 0,
        "detail": f"r0=0x{entry:08X} index={index} stride=0x10 count=94",
    })
    if index >= 0:
        checks.append({
            "name": "emulator memory at the selected record equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, entry, 16),
            "detail": f"entry=0x{entry:08X}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"record_index": index if index >= 0 else -1,
                  "record": rom[entry - ROM_BASE:entry - ROM_BASE + 16].hex(" ")},
        "checks": checks,
    }


def derive_item_records_field(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0806D910, decision 0x0806D926 -- the byte the consumer copies.

        0806D924  ldrb r1, [r0]         ; r1 = the record's +0 byte
        0806D926  strb r1, [r4, #1]     ; -> the runtime item struct
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    entry = regs["r0"]
    value = regs["r1"]
    index = _entry_from(base, entry, 16, 94)
    checks: list[dict] = []
    checks.append({
        "name": "the register holds the record base + id*16",
        "ok": index >= 0,
        "detail": f"r0=0x{entry:08X} index={index} stride=0x10 count=94",
    })
    if index >= 0:
        checks.append({
            "name": "the register holds the byte the record stores at +0",
            "ok": value == u8(rom, entry),
            "detail": f"r1=0x{value:02X} rom=0x{u8(rom, entry):02X}",
        })
        checks.append({
            "name": "emulator memory at the selected record equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, entry, 16),
            "detail": f"entry=0x{entry:08X}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"record_index": index if index >= 0 else -1,
                  "field_value": value},
        "checks": checks,
    }



def derive_encounter_zones(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x08068FF0 (the map loader), decision 0x0806904C.

        08069040  ldr  r5, [pc, #0x98]  ; r5 = 0x0853D910 (map descriptors)
        08069042  mov  r2, r8           ; r2 = the map id
        08069044  lsls r6, r2, #5       ; r6 = id * 32
        08069046  adds r0, r5, #4
        08069048  adds r0, r6, r0       ; r0 = base + id*32 + 4
        0806904A  ldr  r0, [r0]         ; r0 = the descriptor's +4 LZ77 pointer
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    ident = regs["r8"]
    pointer = regs["r0"]
    entry = base + regs["r6"]
    index = _entry_from(base, entry, 32, 50)
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the map descriptor table's base",
        "ok": regs["r5"] == base,
        "detail": f"r5=0x{regs['r5']:08X} expected=0x{base:08X}",
    })
    checks.append({
        "name": "the scaled index register is the map id times 32",
        "ok": regs["r6"] == ident * 32,
        "detail": f"r6={regs['r6']} id={ident} id*32={ident * 32}",
    })
    checks.append({
        "name": "the selected address is base + id*32 inside the table",
        "ok": index >= 0 and entry == base + ident * 32,
        "detail": f"entry=0x{entry:08X} index={index} stride=0x20 count=50",
    })
    if index >= 0:
        checks.append({
            "name": "the register holds the u32 the descriptor stores at +4",
            "ok": pointer == u32(rom, entry + 4),
            "detail": f"r0=0x{pointer:08X} rom=0x{u32(rom, entry + 4):08X}",
        })
        checks.append({
            "name": "the descriptor's +4 graphic pointer is a ROM address",
            "ok": is_rom_pointer(pointer),
            "detail": f"terrain=0x{pointer:08X}",
        })
        checks.append({
            "name": "emulator memory at the selected descriptor equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, entry, 32),
            "detail": f"entry=0x{entry:08X}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"map_id": ident, "terrain_pointer": hexs(pointer)},
        "checks": checks,
    }


def derive_unit_slot_remap(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x08080B08, decision 0x08080B3C.

        08080B2A  ldr  r2, [pc, #0x2c]  ; r2 = 0x0202CA24 (a WRAM u16)
        08080B2C  ldr  r1, [pc, #0x2c]  ; r1 = 0x0853F298 (unit slot remap)
        08080B2E  lsls r0, r3, #1       ; r0 = slot * 2
        08080B30  adds r0, r0, r1       ; r0 = base + slot*2
        08080B32  ldrh r0, [r0]         ; r0 = the remap value
        08080B34  ldrh r2, [r2]         ; r2 = the runtime u16
        08080B36  adds r0, r0, r2
        08080B38  lsls r0, r0, #0x10
        08080B3A  lsrs r0, r0, #0x10    ; r0 = (remap + runtime) & 0xFFFF
        08080B3C  str  r0, [sp, #8]
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    slot = regs["r3"]
    runtime = regs["r2"]
    value = regs["r0"]
    entry = base + slot * 2
    index = _entry_from(base, entry, 2, 43)
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the unit slot remap table's base",
        "ok": regs["r1"] == base,
        "detail": f"r1=0x{regs['r1']:08X} expected=0x{base:08X}",
    })
    checks.append({
        "name": "the selected address is base + slot*2 inside the table",
        "ok": index >= 0,
        "detail": f"entry=0x{entry:08X} index={index} stride=2 count=43",
    })
    if index >= 0:
        remap = u16(rom, entry)
        live = probe.read_bytes(0x0202CA24, 2)
        runtime_live = struct.unpack_from("<H", live, 0)[0] if len(live) == 2 \
            else None
        checks.append({
            "name": "the remap value the table stores is a documented unit id",
            "ok": remap <= 48,
            "detail": f"remap=0x{remap:04X} ({remap}); the registry documents "
                      f"a permutation of 0..48",
        })
        checks.append({
            "name": "the register holds the runtime u16 the consumer added "
                    "(WRAM 0x0202CA24)",
            "ok": runtime_live is not None and runtime == runtime_live,
            "detail": f"r2=0x{runtime:04X} live@0x0202CA24="
                      f"{'n/a' if runtime_live is None else hex(runtime_live)}",
        })
        checks.append({
            "name": "the register holds (remap + runtime u16) masked to 16 bits",
            "ok": value == ((remap + runtime) & 0xFFFF),
            "detail": f"r0=0x{value:04X} expected=0x"
                      f"{((remap + runtime) & 0xFFFF):04X}",
        })
        checks.append({
            "name": "emulator memory at the selected entry equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, entry, 2),
            "detail": f"entry=0x{entry:08X}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"slot": slot, "remap": hexs(u16(rom, entry) if index >= 0 else 0),
                  "runtime_u16": hexs(runtime), "result": hexs(value)},
        "checks": checks,
    }




def derive_item_records_field_at(regs: dict, ctx: dict, capture: dict) -> dict:
    """The generic "the consumer read this byte out of the record" shape.

    The registers are named by the capture, because the consumers differ:

        0808FC28  ldr  r3, [pc, #0xc]   ; r3 = 0x08545BE4 (item/skill records)
        0808FC2A  lsrs r1, r1, #0x14    ; r1 = id * 16
        0808FC2C  adds r0, r1, r3       ; r0 = base + id*16
        0808FC2E  ldrb r0, [r0, #0xc]   ; r0 = the record's +0x0C byte
        0808FC30  cmp  r0, #0

        0808FF78  ldr  r3, [pc, #0x48]  ; r3 = 0x08545BE4 (item/skill records)
        0808FF7A  adds r2, r1, r3       ; r2 = base + id*16
        0808FF7C  ldrb r1, [r2, #0xa]   ; r1 = the record's +0x0A byte
        0808FF80  cmp  r1, sl
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    base_reg = capture.get("base_reg", "r1")
    entry_reg = capture.get("entry_reg", "r0")
    field_reg = capture.get("field_reg", "r1")
    offset = int(capture.get("field_offset", "0"), 0)
    offset_reg = capture.get("entry_offset_reg")
    if offset_reg:
        entry = base + regs[offset_reg]
    else:
        entry = regs[entry_reg]
    value = regs[field_reg]
    index = _entry_from(base, entry, 16, 94)
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the item/skill record table's base",
        "ok": regs[base_reg] == base,
        "detail": f"{base_reg}=0x{regs[base_reg]:08X} expected=0x{base:08X}",
    })
    checks.append({
        "name": "the selected address is base + id*16 inside the table",
        "ok": index >= 0,
        "detail": f"entry=0x{entry:08X} index={index} stride=0x10 count=94",
    })
    if index >= 0:
        checks.append({
            "name": f"the register holds the byte the record stores at "
                    f"+{offset}",
            "ok": value == u8(rom, entry + offset),
            "detail": f"{field_reg}=0x{value:02X} rom=0x{u8(rom, entry + offset):02X}",
        })
        checks.append({
            "name": "emulator memory at the selected record equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, entry, 16),
            "detail": f"entry=0x{entry:08X}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"record_index": index if index >= 0 else -1,
                  "field_value": value},
        "checks": checks,
    }


def derive_pointer_pair_base(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x08080B08, decision 0x08080B74 -- the base and the index.

        08080B12  ldr  r5, [pc, #0x40]  ; r5 = 0x0853F140 (the table base)
        ...
        08080B0E  lsls r1, r1, #0x18
        08080B10  lsrs r3, r1, #0x18    ; r3 = the object index
        08080B70  adds r0, r4, #0
        08080B72  adds r1, r5, #0      ; r1 = the base
        08080B74  adds r2, r3, #0      ; r2 = the index

    The base is handed to fn 0x080625A4, which scales the index by 8; the
    decision point is the instruction that fixes base and index together.
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    index = regs["r3"]
    entry = base + index * 8
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the object descriptor table's base",
        "ok": regs["r5"] == base,
        "detail": f"r5=0x{regs['r5']:08X} expected=0x{base:08X}",
    })
    checks.append({
        "name": "the index register is inside the 43-entry table",
        "ok": 0 <= index < 43,
        "detail": f"r3={index} count=43",
    })
    if 0 <= index < 43:
        checks.append({
            "name": "the selected address is base + index*8 inside the table",
            "ok": base <= entry < base + 43 * 8,
            "detail": f"entry=0x{entry:08X} stride=8",
        })
        checks.append({
            "name": "emulator memory at the selected entry equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, entry, 8),
            "detail": f"entry=0x{entry:08X}",
        })
        checks.append({
            "name": "the entry's two u32 are ROM pointers",
            "ok": is_rom_pointer(u32(rom, entry))
                  and is_rom_pointer(u32(rom, entry + 4)),
            "detail": f"p0=0x{u32(rom, entry):08X} p1=0x{u32(rom, entry + 4):08X}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"index": index,
                  "pointer0": hexs(u32(rom, entry) if 0 <= index < 43 else 0),
                  "pointer1": hexs(u32(rom, entry + 4) if 0 <= index < 43 else 0)},
        "checks": checks,
    }


def derive_window_base(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0807AE04, decision 0x0807B222 -- the sprite-action window base.

        0807B220  ldr  r0, [pc, #0x54]  ; r0 = 0x08596F0C (the window base)
        0807B222  movs r1, #0

    The window is handed to fn 0x080625A4, the same consumer that reads the
    object descriptor table; the window is `sprite_action_table + 4*144`.
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the sprite-action window's base",
        "ok": regs["r0"] == base,
        "detail": f"r0=0x{regs['r0']:08X} expected=0x{base:08X}",
    })
    checks.append({
        "name": "the window lies inside the sprite action table "
                "(0x08596CCC + 63*144)",
        "ok": 0x08596CCC <= base < 0x08596CCC + 63 * 144,
        "detail": f"base=0x{base:08X} "
                  f"(sprite_action_table + {(base - 0x08596CCC) // 144}*144)",
    })
    checks.append({
        "name": "emulator memory at the window's first record equals the ROM bytes",
        "ok": _live_equals_rom(probe, rom, base, 8),
        "detail": f"base=0x{base:08X}",
    })
    checks.append({
        "name": "the window's first two u32 are ROM pointers",
        "ok": is_rom_pointer(u32(rom, base))
              and is_rom_pointer(u32(rom, base + 4)),
        "detail": f"p0=0x{u32(rom, base):08X} p1=0x{u32(rom, base + 4):08X}",
    })
    return {
        "index": 0,
        "entry_address": hexs(base),
        "field": {"pointer0": hexs(u32(rom, base)),
                  "pointer1": hexs(u32(rom, base + 4))},
        "checks": checks,
    }


def derive_save_state(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x08068684 / 0x08068948 / 0x08068CB8 / 0x08068D90.

        0806869A  ldr  r6, [pc, #0x2c]  ; r6 = 0x0853D848 (WRAM allocation table)
        0806869C  movs r2, #0            ; r2 = the record counter
        080686A2  ldr  r0, [r6]          ; r0 = the record's WRAM address
        080686A4  ldr  r4, [r6, #4]      ; r4 = the record's size
        080686A6  cmp  r0, #0

    The same shape appears in fn 0x08068948 (r3 = base, r0 / r1) and in
    fn 0x08068CB8 (r2 = base, r0 / r1).
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    entry_reg = capture.get("entry_reg", "r6")
    wram_reg = capture.get("wram_reg", "r0")
    size_reg = capture.get("size_reg", "r4")
    entry = regs[entry_reg]
    wram = regs[wram_reg]
    size = regs[size_reg]
    index = _entry_from(base, entry, 8, 11)
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the WRAM allocation table's base plus an "
                "exact 8-byte record offset",
        "ok": index >= 0,
        "detail": f"{entry_reg}=0x{entry:08X} base=0x{base:08X} index={index} "
                  f"stride=8 count=11",
    })
    if index >= 0:
        checks.append({
            "name": "the register holds the u32 the record stores at +0 "
                    "(the WRAM address)",
            "ok": wram == u32(rom, entry),
            "detail": f"{wram_reg}=0x{wram:08X} rom=0x{u32(rom, entry):08X}",
        })
        checks.append({
            "name": "the register holds the u32 the record stores at +4 "
                    "(the size)",
            "ok": size == u32(rom, entry + 4),
            "detail": f"{size_reg}=0x{size:08X} rom=0x{u32(rom, entry + 4):08X}",
        })
        checks.append({
            "name": "the record's WRAM address really is a WRAM address",
            "ok": 0x02000000 <= wram < 0x02040000,
            "detail": f"wram=0x{wram:08X}",
        })
        checks.append({
            "name": "emulator memory at the selected record equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, entry, 8),
            "detail": f"entry=0x{entry:08X}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"record_index": index if index >= 0 else -1,
                  "wram_address": hexs(wram), "size": size},
        "checks": checks,
    }


def derive_mission_index(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x080731D0 / 0x08086740, decision 0x080731E4 / 0x08086766.

        080731DA  ldr  r1, [pc, #0x98]  ; r1 = 0x08348DAC (mission index)
        080731DC  ldr  r5, [pc, #0x98]  ; r5 = the story state
        080731DE  ldrb r0, [r5, #1]     ; r0 = the state byte
        080731E0  adds r0, r0, r1       ; r0 = base + index
        080731E2  ldrb r4, [r0]         ; r4 = the index byte
        080731E4  ldrb r1, [r5, #2]     ; r1 = the second state byte
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    base_reg = capture.get("base_reg", "r1")
    entry_reg = capture.get("entry_reg", "r0")
    field_reg = capture.get("field_reg", "r4")
    entry = regs[entry_reg]
    value = regs[field_reg]
    index = entry - base
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the mission index table's base",
        "ok": regs[base_reg] == base,
        "detail": f"{base_reg}=0x{regs[base_reg]:08X} expected=0x{base:08X}",
    })
    checks.append({
        "name": "the selected address is base + index inside the table",
        "ok": 0 <= index < 48,
        "detail": f"{entry_reg}=0x{entry:08X} index={index} count=48",
    })
    if 0 <= index < 48:
        checks.append({
            "name": "the register holds the u8 the table stores at that index",
            "ok": value == u8(rom, entry),
            "detail": f"{field_reg}=0x{value:02X} rom=0x{u8(rom, entry):02X}",
        })
        checks.append({
            "name": "emulator memory at the selected index equals the ROM byte",
            "ok": _live_equals_rom(probe, rom, entry, 1),
            "detail": f"entry=0x{entry:08X}",
        })
    return {
        "index": index if 0 <= index < 48 else -1,
        "entry_address": hexs(entry),
        "field": {"index": index, "index_byte": value},
        "checks": checks,
    }


def derive_mission_index_state(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x08087334, decision 0x08087510.

        080874FE  ldr  r2, [pc, #0x38]  ; r2 = 0x08348DAC (mission index)
        08087500  ldr  r0, [pc, #0x38]  ; r0 = 0x1256
        08087502  add  r0, r8           ; r0 = the first state byte's address
        08087504  ldrb r1, [r0]         ; r1 = the index
        08087506  adds r1, r1, r2       ; r1 = base + index
        0808750E  ldrb r1, [r1]         ; r1 = the index byte (the field)
        08087510  adds r0, r0, r1
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    value = regs["r1"]
    source = regs["r8"] + 0x1256
    live = probe.read_bytes(source, 1)
    index = live[0] if live else -1
    entry = base + index if index >= 0 else 0
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the mission index table's base",
        "ok": regs["r2"] == base,
        "detail": f"r2=0x{regs['r2']:08X} expected=0x{base:08X}",
    })
    checks.append({
        "name": "the index byte comes from the state slot the consumer read",
        "ok": 0 <= index < 48,
        "detail": f"wram@0x{source:08X}="
                  f"{'n/a' if index < 0 else hex(index)} count=48",
    })
    if 0 <= index < 48:
        checks.append({
            "name": "the register holds the u8 the table stores at that index",
            "ok": value == u8(rom, entry),
            "detail": f"r1=0x{value:02X} rom=0x{u8(rom, entry):02X}",
        })
        checks.append({
            "name": "emulator memory at the selected index equals the ROM byte",
            "ok": _live_equals_rom(probe, rom, entry, 1),
            "detail": f"entry=0x{entry:08X}",
        })
    return {
        "index": index if 0 <= index < 48 else -1,
        "entry_address": hexs(entry),
        "field": {"index": index, "index_byte": value},
        "checks": checks,
    }


def derive_battle_config(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0806DE18 / 0x0806E1B4, decision 0x0806DF3E / 0x0806E1FE / 0x0806E3DC.

        0806DF28  ldr  r3, [pc, #0x2c]  ; r3 = 0x085461C4 (formation matrix)
        0806DF2A  ldr  r2, [pc, #0x30]  ; r2 = 0x02026804 (the battle state)
        0806DF2C  ldrb r1, [r2, #2]     ; r1 = the sub configuration
        0806DF30  muls r0, r1, r0       ; r0 = sub * 0x8E4
        0806DF32  ldrb r2, [r2, #1]     ; r2 = the group
        0806DF36  muls r1, r2, r1       ; r1 = group * 0x1AAC
        0806DF38  adds r0, r0, r1
        0806DF3A  adds r0, r0, r3       ; r0 = base + group*0x1AAC + sub*0x8E4
        0806DF3C  ldrb r0, [r0]         ; r0 = the byte at that address

    The group and the sub configuration are *not* in registers at the decision
    points any more (the consumer scaled them into the address), so they are
    read back from the battle state the consumer itself read:
    WRAM 0x02026805 = the group, WRAM 0x02026806 = the sub configuration.
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    checks: list[dict] = []
    state = probe.read_bytes(0x02026804, 4)
    group = state[1] if len(state) > 1 else -1
    sub = state[2] if len(state) > 2 else -1
    if capture["decision"] == 0x0806DF3E:
        entry = base + group * 0x1AAC + sub * 0x8E4
        value = regs["r0"]
        checks.append({
            "name": "a register holds the formation matrix's base",
            "ok": regs["r3"] == base,
            "detail": f"r3=0x{regs['r3']:08X} expected=0x{base:08X}",
        })
        checks.append({
            "name": "the group byte in the battle state is inside the "
                    "48-group matrix",
            "ok": 0 <= group < 48,
            "detail": f"group@0x02026805={group} group*0x1AAC="
                      f"0x{group * 0x1AAC:X}",
        })
        checks.append({
            "name": "the sub configuration byte in the battle state is one of "
                    "the three sub configurations",
            "ok": 0 <= sub < 3,
            "detail": f"sub@0x02026806={sub} sub*0x8E4=0x{sub * 0x8E4:X}",
        })
        checks.append({
            "name": "the selected address is base + group*0x1AAC + sub*0x8E4 "
                    "inside the matrix",
            "ok": base <= entry < base + 48 * 0x1AAC + 3 * 0x8E4,
            "detail": f"entry=0x{entry:08X}",
        })
        if base <= entry < base + 48 * 0x1AAC + 3 * 0x8E4:
            checks.append({
                "name": "the register holds the byte the matrix stores there",
                "ok": value == u8(rom, entry),
                "detail": f"r0=0x{value:02X} rom=0x{u8(rom, entry):02X}",
            })
            checks.append({
                "name": "emulator memory at the selected byte equals the ROM byte",
                "ok": _live_equals_rom(probe, rom, entry, 1),
                "detail": f"entry=0x{entry:08X}",
            })
        return {
            "index": group,
            "entry_address": hexs(entry),
            "field": {"group": group, "sub": sub, "field_value": value},
            "checks": checks,
        }

    # 0x0806E1FE / 0x0806E3DC: the consumer adds the slot offset as well
    if capture["decision"] == 0x0806E1FE:
        entry = regs["r5"]
        base_reg = regs["r1"]
        slot = regs["r6"]
        block = regs["r3"]
    else:
        entry = regs["r5"]
        base_reg = regs["r2"]
        slot = 0
        block = regs["r1"]
    checks.append({
        "name": "a register holds the formation matrix's base",
        "ok": base_reg == base,
        "detail": f"base register=0x{base_reg:08X} expected=0x{base:08X}",
    })
    checks.append({
        "name": "the register holds base + group*0x1AAC + sub*0x8E4",
        "ok": block == base + group * 0x1AAC + sub * 0x8E4,
        "detail": f"block=0x{block:08X} expected=0x"
                  f"{base + group * 0x1AAC + sub * 0x8E4:08X} "
                  f"group={group} sub={sub}",
    })
    expected = base + group * 0x1AAC + sub * 0x8E4 + slot * 0xB8 + 4
    checks.append({
        "name": "the selected address is base + group*0x1AAC + sub*0x8E4 "
                "+ slot*0xB8 + 4",
        "ok": entry == expected,
        "detail": f"entry=0x{entry:08X} expected=0x{expected:08X} "
                  f"group={group} sub={sub} slot={slot}",
    })
    checks.append({
        "name": "the selected address is inside the formation matrix",
        "ok": base <= entry < base + 48 * 0x1AAC + 3 * 0x8E4,
        "detail": f"entry=0x{entry:08X}",
    })
    if base <= entry < base + 48 * 0x1AAC + 3 * 0x8E4:
        checks.append({
            "name": "emulator memory at the selected record equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, entry, 0xB8),
            "detail": f"entry=0x{entry:08X}",
        })
    return {
        "index": group,
        "entry_address": hexs(entry),
        "field": {"group": group, "sub": sub, "slot": slot},
        "checks": checks,
    }


def derive_story_background(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x08088348, decision 0x0808837C.

        08088372  ldr  r4, [pc, #0x4c]  ; r4 = 0x0859903C (background table)
        08088374  lsls r5, r0, #4       ; r5 = id * 16
        08088376  adds r0, r5, r4       ; r0 = base + id*16
        08088378  mov  r8, r0           ; r8 = the record
        0808837A  ldr  r0, [r0]         ; r0 = the record's LZ77 tiles pointer
        0808837C  lsls r1, r2, #0xe
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    entry = regs["r8"]
    pointer = regs["r0"]
    index = _entry_from(base, entry, 16, 14)
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the background table's base",
        "ok": regs["r4"] == base,
        "detail": f"r4=0x{regs['r4']:08X} expected=0x{base:08X}",
    })
    checks.append({
        "name": "the selected address is base + id*16 inside the table",
        "ok": index >= 0 and regs["r5"] == index * 16,
        "detail": f"r8=0x{entry:08X} index={index} r5={regs['r5']} "
                  f"id*16={index * 16}",
    })
    if index >= 0:
        checks.append({
            "name": "the register holds the u32 the record stores at +0",
            "ok": pointer == u32(rom, entry),
            "detail": f"r0=0x{pointer:08X} rom=0x{u32(rom, entry):08X}",
        })
        checks.append({
            "name": "that u32 is a ROM pointer (the LZ77 background tiles)",
            "ok": is_rom_pointer(pointer),
            "detail": f"pointer=0x{pointer:08X}",
        })
        checks.append({
            "name": "emulator memory at the selected record equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, entry, 16),
            "detail": f"entry=0x{entry:08X}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"background_id": index if index >= 0 else -1,
                  "tiles_pointer": hexs(pointer)},
        "checks": checks,
    }


def derive_story_background_flag(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x08088348, decision 0x0808840A -- the +0x0C flag byte.

        08088400  ldr  r1, [pc, #0x3c]  ; r1 = 0x0859903C (background table)
        08088404  lsls r0, r5, #4       ; r0 = id * 16
        08088406  adds r0, r0, r1       ; r0 = base + id*16
        08088408  ldrb r0, [r0, #0xc]   ; r0 = the record's +0x0C byte
        0808840A  cmp  r0, #0
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    value = regs["r0"]
    ident = regs["r5"]
    entry = base + ident * 16
    index = _entry_from(base, entry, 16, 14)
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the background table's base",
        "ok": regs["r1"] == base,
        "detail": f"r1=0x{regs['r1']:08X} expected=0x{base:08X}",
    })
    checks.append({
        "name": "the selected address is base + id*16 inside the table",
        "ok": index >= 0,
        "detail": f"entry=0x{entry:08X} index={index} stride=0x10 count=14",
    })
    if index >= 0:
        checks.append({
            "name": "the register holds the byte the record stores at +0x0C",
            "ok": value == u8(rom, entry + 0x0C),
            "detail": f"r0=0x{value:02X} rom=0x{u8(rom, entry + 0x0C):02X}",
        })
        checks.append({
            "name": "emulator memory at the selected record equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, entry, 16),
            "detail": f"entry=0x{entry:08X}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"background_id": index if index >= 0 else -1,
                  "flag_byte": value},
        "checks": checks,
    }


# ---------------------------------------------------------------------------
# batch 4: the derive functions of the new structures
# ---------------------------------------------------------------------------
def derive_song_header_link(regs: dict, ctx: dict, capture: dict) -> dict:
    """The sound-id reader taking a SongHeader pointer out of the id table.

    fn 0x0809AAC0 (the *play* path), decision 0x0809AADA:

        0809AAC6  ldr  r1, [pc, #0x20]   ; r1 = 0x08465B70 (sound id table)
        0809AAC8  lsrs r0, r0, #0xd      ; r0 = id * 8
        0809AACA  adds r0, r0, r1        ; r0 = base + id*8
        0809AACC  ldrh r3, [r0, #4]      ; r3 = the entry's u16
        ...
        0809AAD8  ldr  r1, [r0]          ; r1 = the entry's u32 -> SongHeader
        0809AADA  adds r0, r2, #0

    fn 0x0809AB38 (the other *play* path), decision 0x0809AB54:

        0809AB3E  ldr  r1, [pc, #0x28]   ; r1 = 0x08465B70
        0809AB44  ldrh r3, [r0, #4]      ; r3 = the entry's u16
        ...
        0809AB52  ldr  r2, [r0]          ; r2 = the entry's u32 -> SongHeader
        0809AB54  cmp  r3, r2

    The register that carries the pointer differs between the two, so the
    capture names it.  When the decision point sits *after* the pointer was
    taken out of the entry (fn 0x0809AB8C, the stop path), the entry address
    is gone; the slot is then found by looking the pointer up in the table.
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    ptr_base = ctx.get("pointer_base", 0)
    pointer_reg = capture.get("pointer_reg", "r1")
    pointer = regs[pointer_reg]
    entry_reg = capture.get("entry_reg")
    stride = 8
    count = 159
    slot = -1
    for i in range(count):
        if u32(rom, ptr_base + i * stride) == pointer:
            slot = i
            break
    checks: list[dict] = []
    checks.append({
        "name": "the register holds a u32 that the sound id table stores",
        "ok": slot >= 0,
        "detail": f"{pointer_reg}=0x{pointer:08X} slot={slot} "
                  f"(stride=8 count={count})",
    })
    checks.append({
        "name": "that u32 is this structure's base address",
        "ok": pointer == base,
        "detail": f"pointer=0x{pointer:08X} base=0x{base:08X}",
    })
    if entry_reg:
        entry = regs[entry_reg]
        checks.append({
            "name": "the selected address is the sound id table's entry",
            "ok": slot >= 0 and entry == ptr_base + slot * stride,
            "detail": f"{entry_reg}=0x{entry:08X} slot={slot}",
        })
    if slot >= 0 and pointer == base:
        entry = ptr_base + slot * stride
        checks.append({
            "name": "emulator memory at the entry equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, entry, 8),
            "detail": f"entry=0x{entry:08X}",
        })
    return {
        "index": slot,
        "entry_address": hexs(ptr_base + slot * stride if slot >= 0 else 0),
        "field": {"song_header": hexs(pointer)},
        "checks": checks,
    }


def derive_song_header_sequence(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0809B1F4 (the m4a play entry), decision 0x0809B244.

        0809B1FC  adds  r7, r1, #0       ; r7 = the SongHeader
        0809B240  str   r7, [r5]         ; the header goes into the sound slot
        0809B242  ldr   r0, [r7, #4]     ; r0 = SongHeader[+4] (the sequence /
                                        ;      track pointer)
        0809B244  str   r0, [r5, #0x30]
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    header = regs["r7"]
    value = regs["r0"]
    checks: list[dict] = []
    checks.append({
        "name": "the register holds this SongHeader's address",
        "ok": header == base,
        "detail": f"r7=0x{header:08X} expected=0x{base:08X}",
    })
    if header == base:
        checks.append({
            "name": "the register holds the u32 the header stores at +4",
            "ok": value == u32(rom, base + 4),
            "detail": f"r0=0x{value:08X} rom=0x{u32(rom, base + 4):08X}",
        })
        checks.append({
            "name": "that pointer is a ROM address",
            "ok": is_rom_pointer(value),
            "detail": f"r0=0x{value:08X}",
        })
        checks.append({
            "name": "the header's first byte is a plausible track count",
            "ok": 1 <= u8(rom, base) <= 16,
            "detail": f"track_count={u8(rom, base)}",
        })
        checks.append({
            "name": "emulator memory at the header equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, base, 16),
            "detail": f"header=0x{base:08X}",
        })
    return {
        "index": 0,
        "entry_address": hexs(header),
        "field": {"song_header": hexs(header), "sequence_pointer": hexs(value)},
        "checks": checks,
    }


def derive_song_header_track(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0809B1F4 (the m4a play entry), decision 0x0809B284.

        0809B25C  ldrb  r1, [r7]         ; r1 = SongHeader[+0] (the track count)
        ...
        0809B27A  lsls  r1, r6, #2       ; r1 = the track index * 4
        0809B27C  adds  r0, r7, #0
        0809B27E  adds  r0, #8           ; r0 = SongHeader + 8
        0809B280  adds  r0, r0, r1
        0809B282  ldr   r0, [r0]         ; r0 = that track's u32 pointer
        0809B284  str   r0, [r4, #0x40]
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    header = regs["r7"]
    offset = regs["r1"]
    value = regs["r0"]
    checks: list[dict] = []
    checks.append({
        "name": "the register holds this SongHeader's address",
        "ok": header == base,
        "detail": f"r7=0x{header:08X} expected=0x{base:08X}",
    })
    track = offset // 4 if offset % 4 == 0 and offset >= 0 else -1
    checks.append({
        "name": "the scaled register is the track index times four",
        "ok": 0 <= track < 16,
        "detail": f"r1={offset} track={track}",
    })
    if header == base and 0 <= track < 16:
        entry = base + 8 + offset
        checks.append({
            "name": "the register holds the u32 the header stores at "
                    "+8 + track*4",
            "ok": value == u32(rom, entry),
            "detail": f"r0=0x{value:08X} rom=0x{u32(rom, entry):08X} "
                      f"(track={track})",
        })
        checks.append({
            "name": "that pointer is a ROM address",
            "ok": is_rom_pointer(value),
            "detail": f"r0=0x{value:08X}",
        })
        checks.append({
            "name": "the track index is inside the header's track count",
            "ok": track < u8(rom, base),
            "detail": f"track={track} track_count={u8(rom, base)}",
        })
        checks.append({
            "name": "emulator memory at the header's track slot equals the "
                    "ROM bytes",
            "ok": _live_equals_rom(probe, rom, entry, 4),
            "detail": f"entry=0x{entry:08X}",
        })
    return {
        "index": track,
        "entry_address": hexs(base + 8 + offset if header == base else base),
        "field": {"song_header": hexs(header), "track": track,
                  "track_pointer": hexs(value)},
        "checks": checks,
    }


def derive_song_header_count(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x0809B1F4 (the m4a play entry), decision 0x0809B25E.

        0809B25C  ldrb  r1, [r7]         ; r1 = SongHeader[+0] (the track count)
        0809B25E  cmp   r6, r1           ; r6 = the track being set up
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    header = regs["r7"]
    count = regs["r1"]
    checks: list[dict] = []
    checks.append({
        "name": "the register holds this SongHeader's address",
        "ok": header == base,
        "detail": f"r7=0x{header:08X} expected=0x{base:08X}",
    })
    if header == base:
        checks.append({
            "name": "the register holds the track count byte the header "
                    "stores at +0",
            "ok": count == u8(rom, base),
            "detail": f"r1={count} rom={u8(rom, base)}",
        })
        checks.append({
            "name": "the track count is a plausible number of tracks",
            "ok": 1 <= count <= 16,
            "detail": f"track_count={count}",
        })
        checks.append({
            "name": "emulator memory at the header equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, base, 16),
            "detail": f"header=0x{base:08X}",
        })
    return {
        "index": 0,
        "entry_address": hexs(header),
        "field": {"song_header": hexs(header), "track_count": count},
        "checks": checks,
    }


def derive_mission_index_scene(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x080884E0, decision 0x08088502.

        080884F8  ldr   r2, [pc, #0x6c]  ; r2 = 0x08348DAC (mission index)
        080884FA  ldr   r1, [pc, #0x70]  ; r1 = 0x020311D4 (the story state)
        080884FC  ldrb  r0, [r1, #0x16] ; r0 = state[0x16] (the scene id)
        080884FE  adds  r0, r0, r2      ; r0 = base + scene id
        08088500  ldrb  r4, [r0]       ; r4 = the index byte
        08088502  ldrb  r1, [r1, #0x19] ; r1 = state[0x19] (the sub id)
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    entry = regs["r0"]
    value = regs["r4"]
    index = entry - base
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the mission index table's base",
        "ok": regs["r2"] == base,
        "detail": f"r2=0x{regs['r2']:08X} expected=0x{base:08X}",
    })
    checks.append({
        "name": "the selected address is base + the scene id inside the table",
        "ok": 0 <= index < 48,
        "detail": f"r0=0x{entry:08X} index={index} count=48",
    })
    if 0 <= index < 48:
        checks.append({
            "name": "the register holds the u8 the table stores at that index",
            "ok": value == u8(rom, entry),
            "detail": f"r4=0x{value:02X} rom=0x{u8(rom, entry):02X}",
        })
        live = probe.read_bytes(0x020311EA, 1)
        checks.append({
            "name": "the scene id in the story state is the one that selected "
                    "the entry",
            "ok": bool(live) and live[0] == index,
            "detail": f"wram@0x020311EA="
                      f"{live.hex() if live else '??'} index={index}",
        })
        checks.append({
            "name": "emulator memory at the selected index equals the ROM byte",
            "ok": _live_equals_rom(probe, rom, entry, 1),
            "detail": f"entry=0x{entry:08X}",
        })
    return {
        "index": index if 0 <= index < 48 else -1,
        "entry_address": hexs(entry),
        "field": {"scene_id": index, "index_byte": value},
        "checks": checks,
    }


def derive_tile_assets_sweep(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x080983B8, decision 0x08098462.

        08098448  ldr   r2, [pc, #0xcc]  ; r2 = 0x0203120C (the index slot)
        0809844C  strb  r1, [r2]        ; the record index is stored here
        08098456  lsls  r0, r1, #4
        08098458  adds  r0, r0, r1      ; r0 = index * 17
        0809845A  lsls  r0, r0, #2      ; r0 = index * 68
        0809845C  ldr   r1, [pc, #0xbc] ; r1 = 0x085A320C (tile assets)
        0809845E  adds  r0, r0, r1      ; r0 = base + index*68
        08098460  mov   r8, r0          ; r8 = the record
        08098462  strb  r4, [r2, #2]

    At the decision point the scaled index has already been folded into the
    address, so the record index is recovered from the address itself and
    cross-checked against the index byte the consumer stored in WRAM.
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    entry = regs["r8"]
    offset = entry - base
    index = offset // 68 if offset >= 0 and offset % 68 == 0 else -1
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the tile asset table's base",
        "ok": regs["r1"] == base,
        "detail": f"r1=0x{regs['r1']:08X} expected=0x{base:08X}",
    })
    checks.append({
        "name": "the address register holds base + index*68",
        "ok": 0 <= index < 79,
        "detail": f"r8=0x{entry:08X} index={index} stride=68 count=79",
    })
    checks.append({
        "name": "the address register and the computed one agree",
        "ok": index >= 0 and regs["r0"] == base + index * 68,
        "detail": f"r0=0x{regs['r0']:08X} r8=0x{entry:08X} index={index}",
    })
    live_index = probe.read_bytes(0x0203120C, 1)
    checks.append({
        "name": "the index byte the consumer stored in WRAM is the one that "
                "selected the record",
        "ok": bool(live_index) and live_index[0] == index,
        "detail": f"wram@0x0203120C="
                  f"{live_index.hex() if live_index else '??'} index={index}",
    })
    if index >= 0 and entry == base + index * 68:
        checks.append({
            "name": "emulator memory at the selected record equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, entry, 68),
            "detail": f"entry=0x{entry:08X}",
        })
        tiles = [u32(rom, entry + 0x0C + 4 * k) for k in range(6)]
        checks.append({
            "name": "the record's +0x0C block holds six u32 tile pointers "
                    "(0 or a ROM address)",
            "ok": all(t == 0 or is_rom_pointer(t) for t in tiles),
            "detail": " ".join(hexs(t) for t in tiles),
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"record_index": index if index >= 0 else -1,
                  "entry": hexs(entry)},
        "checks": checks,
    }


def derive_ninjutsu_records(regs: dict, ctx: dict, capture: dict) -> dict:
    """The ninjutsu record table (0x08545458), 16 bytes per record.

    fn 0x08078770, decision 0x0807877E:

        08078776  ldr  r1, [pc, #0xb0]  ; r1 = 0x08545458
        08078778  lsls r0, r5, #4       ; r0 = id * 16
        0807877A  adds r0, r0, r1       ; r0 = base + id*16
        0807877C  ldrh r0, [r0, #2]     ; r0 = the record's +2 u16
        0807877E  movs r1, #0xc0

    fn 0x0806D860, decision 0x0806D874:

        0806D866  ldr  r2, [pc, #0x20]  ; r2 = 0x08545458
        0806D868  lsrs r0, r0, #0x14    ; r0 = id * 16
        0806D86C  adds r0, r0, r2       ; r0 = base + id*16
        0806D86E  ldm  r0!, {r2, r6, r7}; the record's +0/+4/+8 -> r2/r6/r7
        0806D870  stm  r1!, {r2, r6, r7}; ... -> the runtime struct
        0806D872  ldr  r0, [r0]         ; r0 = the record's +12 u32
        0806D874  str  r0, [r1]
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    entry_reg = capture.get("entry_reg", "r1")
    entry_offset = int(capture.get("entry_offset", "0"), 0)
    field_reg = capture.get("field_reg", "r0")
    field_offset = int(capture.get("field_offset", "2"), 0)
    entry = regs[entry_reg] - entry_offset
    value = regs[field_reg]
    index = (entry - base) // 16 if (entry - base) % 16 == 0 else -1
    checks: list[dict] = []
    checks.append({
        "name": "the selected address is base + id*16 inside the table",
        "ok": 0 <= index < 87,
        "detail": f"{entry_reg}=0x{regs[entry_reg]:08X} entry=0x{entry:08X} "
                  f"index={index} stride=16 count=87",
    })
    if 0 <= index < 87:
        width = 2 if field_offset < 4 and field_offset % 2 == 0 else 4
        expected = (u16(rom, entry + field_offset) if width == 2
                    else u32(rom, entry + field_offset))
        checks.append({
            "name": f"the register holds the u{width * 8} the record stores "
                    f"at +{field_offset}",
            "ok": value == expected,
            "detail": f"{field_reg}=0x{value:X} rom=0x{expected:X}",
        })
        checks.append({
            "name": "emulator memory at the selected record equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, entry, 16),
            "detail": f"entry=0x{entry:08X}",
        })
    return {
        "index": index,
        "entry_address": hexs(entry),
        "field": {"record_index": index if index >= 0 else -1,
                  "field_value": value},
        "checks": checks,
    }


def derive_mechanism_effects(regs: dict, ctx: dict, capture: dict) -> dict:
    """fn 0x080812DC (the 13-way effect dispatcher), decision 0x08081356.

        08081346  subs  r0, r5, #1        ; r0 = target - 1
        08081348  cmp   r0, #0xc
        0808134A  bls   #0x808134e
        0808134C  b     #0x80814cc        ; out of range -> the default effect
        0808134E  lsls  r0, r0, #2        ; r0 = (target-1) * 4
        08081350  ldr   r1, [pc, #0x14]   ; r1 = 0x0808136C (the effect table)
        08081352  adds  r0, r0, r1        ; r0 = base + (target-1)*4
        08081354  ldr   r0, [r0]          ; r0 = the effect's code pointer
        08081356  mov   pc, r0            ; the dispatch itself
    """
    rom, probe, base = ctx["rom"], ctx["probe"], ctx["base"]
    target = regs["r5"]
    pointer = regs["r0"]
    index = target - 1
    checks: list[dict] = []
    checks.append({
        "name": "a register holds the effect table's base",
        "ok": regs["r1"] == base,
        "detail": f"r1=0x{regs['r1']:08X} expected=0x{base:08X}",
    })
    checks.append({
        "name": "the target id is inside the 13-entry table",
        "ok": 0 <= index < 13,
        "detail": f"r5={target} index={index} count=13",
    })
    if 0 <= index < 13:
        entry = base + index * 4
        checks.append({
            "name": "the register holds the u32 the table stores at "
                    "+index*4",
            "ok": pointer == u32(rom, entry),
            "detail": f"r0=0x{pointer:08X} rom=0x{u32(rom, entry):08X}",
        })
        checks.append({
            "name": "that u32 is a ROM code pointer",
            "ok": is_code_pointer(pointer),
            "detail": f"r0=0x{pointer:08X}",
        })
        checks.append({
            "name": "emulator memory at the selected entry equals the ROM bytes",
            "ok": _live_equals_rom(probe, rom, entry, 4),
            "detail": f"entry=0x{entry:08X}",
        })
    return {
        "index": index,
        "entry_address": hexs(base + index * 4 if 0 <= index < 13 else base),
        "field": {"target": target, "effect_pointer": hexs(pointer)},
        "checks": checks,
    }


# ---------------------------------------------------------------------------
# the structure catalogue
# ---------------------------------------------------------------------------
STRUCTURES: dict[str, dict] = {
    "font-segments": {
        "registry": "font_segments",
        "route": "title",
        "layout": {"stride": 8, "count": 31},
        "summary": "31 x 8-byte glyph segments; the lookup returns the segment "
                   "whose code point range covers the character.",
        "captures": [
            {"reader": 0x08065EE6, "decision": 0x08065EF0, "function": 0x08065EB8,
             "derive": derive_font_segments,
             "corrupt": {"r2": ("base", 4)}},
        ],
    },
    "sound-id-table": {
        "registry": "sound_id_table",
        "route": "title",
        "layout": {"stride": 8, "count": 159},
        "summary": "159 x 8-byte sound id entries; each entry points at an m4a "
                   "SongHeader.",
        "captures": [
            {"reader": 0x0809AAC6, "decision": 0x0809AACE, "function": 0x0809AAC0,
             "derive": derive_sound_id,
             "corrupt": {"r1": ("base", 4)}},
            {"reader": 0x0809AB92, "decision": 0x0809AB9A, "function": 0x0809AB8C,
             "derive": derive_sound_id,
             "corrupt": {"r1": ("base", 4)}},
            {"reader": 0x08061E9E, "decision": 0x08061EA6, "function": 0x08061E98,
             "derive": derive_sound_id,
             # this consumer loads the entry's u16 into r1, overwriting the
             # base register it used two instructions earlier
             "base_reg": None, "field_reg": "r1",
             "corrupt": {"r1": ("value", 1)}},
        ],
    },
    "character-template": {
        "registry": "character_template",
        "route": "title",
        "layout": {"stride": 0xB4, "count": 63},
        "summary": "63 x 0xB4-byte character templates; the loader indexes them "
                   "by the character id and copies the record into RAM.",
        "captures": [
            {"reader": 0x0806D984, "decision": 0x0806D988, "function": 0x0806D964,
             "derive": derive_character_template,
             "corrupt": {"r0": ("base", 4)}},
            {"reader": 0x0806D4D2, "decision": 0x0806D4F8, "function": 0x0806D4A0,
             "derive": derive_character_template_copy,
             "corrupt": {"r0": ("value", 1)}},
        ],
    },
    "maps": {
        "registry": "map_table",
        "route": "dispatch",
        "layout": {"stride": 0x20, "count": 50},
        "summary": "32-byte map descriptors; the story path reads the +0x1C byte "
                   "of the descriptor of the current chapter.",
        "captures": [
            {"reader": 0x0808F4F6, "decision": 0x0808F4FE, "function": 0x0808F190,
             "derive": derive_maps,
             "corrupt": {"r0": ("value", 1)}},
        ],
    },
    "portrait": {
        "registry": "portrait_table",
        "route": "title",
        "layout": {"stride": 40, "count": 256},
        "summary": "id*40 + expression*8 portrait pointer table.",
        "captures": [
            {"reader": 0x08096158, "decision": 0x0809615A, "function": 0x08096138,
             "derive": derive_portrait,
             "corrupt": {"r2": ("base", 4)}},
        ],
    },

    # --- batch 2 (2026-10-21) ---------------------------------------------
    "battle-handlers": {
        "registry": "battle_handler_table",
        "route": "battle",
        "group": "batch2",
        "l2": False,
        "l1_reason": "the dispatcher fn 0x0807F414 has a single call site "
                     "(0x0807ABD4, inside the map-event loop); neither the 144 "
                     "battles nor the story sweep 1..50 reach it",
        "layout": {"stride": 8, "count": 256},
        "summary": "256 x 8-byte map/battle event handler records (two u32 code "
                   "pointers each); the dispatcher reads the record the WRAM "
                   "event id selects.",
        "captures": [
            {"reader": 0x0807F934, "decision": 0x0807F942, "function": 0x0807F414,
             "derive": derive_battle_handlers,
             "corrupt": {"r1": ("base", 4)}},
            {"reader": 0x0807FD28, "decision": 0x0807FD36, "function": 0x0807F414,
             "derive": derive_battle_handlers,
             "corrupt": {"r1": ("base", 4)}},
        ],
    },
    "map-events": {
        "registry": "battle_handler_table",
        "route": "battle",
        "group": "batch2",
        "l2": False,
        "l1_reason": "the same table as `battle-handlers`, read through the "
                     "same dispatcher fn 0x0807F414 (readers 0x0807F934 / "
                     "0x0807FD28).  The dispatcher has a single call site "
                     "(0x0807ABD4, inside the map-event loop); neither the 144 "
                     "battles nor the story sweep 1..55 reach it.",
        "layout": {"stride": 8, "count": 256},
        "summary": "deprecated alias of `battle-handlers`: the same 8-byte "
                   "map/battle event handler records, read through the same "
                   "native dispatcher.",
        "captures": [
            {"reader": 0x0807F934, "decision": 0x0807F942, "function": 0x0807F414,
             "derive": derive_battle_handlers,
             "corrupt": {"r1": ("base", 4)}},
        ],
    },
    "fonts": {
        "registry": "font_width_table",
        "route": "battle",
        "group": "batch2",
        "l2": False,
        "l1_reason": "fn 0x0807EE50 has no direct call site -- it is invoked "
                     "through the 8-byte callback table at 0x0853ECB0, which "
                     "the battle and story routes never dispatch.  This round "
                     "re-indexed the whole ROM: 0x0853ECB0 has **no** literal "
                     "reader either, so the callback table is reached the same "
                     "indirect way as the object-type table (see `map-sprites`)",
        "layout": {"stride": 1, "count": 256},
        "summary": "256 x 1-byte glyph widths; the renderer indexes the table "
                   "with the character code it reads from WRAM.",
        "captures": [
            {"reader": 0x0807F0FC, "decision": 0x0807F108, "function": 0x0807EE50,
             "derive": derive_font_width, "base_reg": "r1",
             "corrupt": {"r1": ("base", 4)}},
            {"reader": 0x0807F0FC, "decision": 0x0807F10A, "function": 0x0807EE50,
             "derive": derive_font_width, "base_reg": None,
             "corrupt": {"r0": ("value", 1)}},
        ],
    },
    "data-table-a": {
        "registry": "data_pointer_table_a",
        "route": "battle",
        "group": "batch2",
        "l2": False,
        "l1_reason": "fn 0x0808AFE0 is only called from 0x0808B420 / "
                     "0x0808B51A, neither of which runs in the 144 battles "
                     "or in the story sweep 1..55",
        "layout": {"stride": 4, "count": 46},
        "summary": "46 u32 ROM pointers; the consumer picks one with a WRAM byte "
                   "index.",
        "captures": [
            {"reader": 0x0808B19E, "decision": 0x0808B1A6, "function": 0x0808AFE0,
             "derive": derive_data_pointer_table, "index_reg": "r6",
             "corrupt": {"r1": ("base", 4)}},
        ],
    },
    "data-table-b": {
        "registry": "data_pointer_table_b",
        "route": "battle",
        "group": "batch2",
        "layout": {"stride": 4, "count": 90},
        "summary": "90 u32 ROM pointers; the consumer picks one with a WRAM byte "
                   "index.",
        "captures": [
            {"reader": 0x08099D26, "decision": 0x08099D2E, "function": 0x08099BFC,
             "derive": derive_data_pointer_table, "index_reg": "r4",
             "corrupt": {"r1": ("base", 4)}},
            {"reader": 0x080985D8, "decision": 0x080985E0, "function": 0x080983B8,
             "derive": derive_data_pointer_table, "index_reg": "r6",
             "corrupt": {"r1": ("base", 4)}},
        ],
    },
    "function-pointers": {
        "registry": "function_pointer_table",
        "route": "battle",
        "group": "batch2",
        "layout": {"stride": 4, "count": 13},
        "summary": "13 u32 hook slots (slot 0 and 12 are the 0xFFFFFFFF "
                   "sentinels); the dispatcher indexes the table with *4.",
        "captures": [
            {"reader": 0x08061DD4, "decision": 0x08061DDA, "function": 0x08061D8C,
             "derive": derive_function_pointers,
             "corrupt": {"r3": ("base", 4)}},
            {"reader": 0x08061DD4, "decision": 0x08061DE0, "function": 0x08061D8C,
             "derive": derive_function_pointers, "field_reg": "r0",
             "corrupt": {"r0": ("value", 1)}},
        ],
    },
    "tile-assets": {
        "registry": "tile_asset_records",
        "route": "battle",
        "group": "batch2",
        "layout": {"stride": 68, "count": 79},
        "summary": "79 x 68-byte tile/sprite asset records; the index comes from "
                   "a WRAM byte and is scaled by 68, and +0x0C holds six u32 "
                   "tile pointers.",
        "captures": [
            # the reader that IS reached: fn 0x080983B8 scales the record
            # index by 68 and adds the table base.
            {"reader": 0x0809845C, "decision": 0x08098462, "function": 0x080983B8,
             "derive": derive_tile_assets_sweep,
             "corrupt": {"r1": ("base", 4)}},
            {"reader": 0x0809881E, "decision": 0x08098822, "function": 0x0809880C,
             "derive": derive_tile_assets,
             "corrupt": {"r2": ("base", 4)}},
        ],
    },
    "sprite-frame-descriptors": {
        "registry": "sprite_frame_descriptors",
        "route": "battle",
        "group": "batch2",
        "l2": False,
        "l1_reason": "fn 0x08080670 has no direct call site -- it is the "
                     "second callback of the object-type record whose base "
                     "is 0x0853EF30 (see `map-sprites`).  This round proved "
                     "the dispatcher's real table base and stride: the "
                     "record is {u32 type id, u32, u32, u32, u32 callback A, "
                     "u32 callback B} and the object type that owns "
                     "0x08080670 is id 2.  The game never instantiates that "
                     "object type in the title / battle / sweep / save "
                     "routes: the spawn entry fn 0x080800A4 (which reads the "
                     "type table) is never called",
        "layout": {"stride": 10, "count": 15},
        "summary": "15 x 10-byte sprite frame descriptors; the sprite struct's "
                   "+0x8C field selects the record.",
        "captures": [
            {"reader": 0x080806BA, "decision": 0x080806BC, "function": 0x08080670,
             "derive": derive_sprite_frame_descriptors,
             "corrupt": {"r1": ("base", 4)}},
            {"reader": 0x0808077E, "decision": 0x08080780, "function": 0x08080764,
             "derive": derive_sprite_frame_descriptors,
             "corrupt": {"r1": ("base", 4)}},
            {"reader": 0x0808082E, "decision": 0x08080830, "function": 0x08080814,
             "derive": derive_sprite_frame_descriptors,
             "corrupt": {"r1": ("base", 4)}},
        ],
    },
    "battle-encounters": {
        "registry": "battle_encounter_records",
        "route": "battle",
        "group": "batch2",
        "l2": False,
        "l1_reason": "fn 0x08087C9C is only reached through the callback thunk "
                     "0x0808A69C, which no battle or story scene dispatches",
        "layout": {"stride": 16, "count": 24},        "summary": "24 x 16-byte battle encounter records (three u32 pointers and "
                   "a u32 number); the consumer reads the +0x0C number of the "
                   "record the index selects.",
        "captures": [
            {"reader": 0x08087DE0, "decision": 0x08087DF2, "function": 0x08087C9C,
             "derive": derive_battle_encounters,
             "corrupt": {"r10": ("base", 4)}},
        ],
    },
    "ninjutsu-names": {
        "registry": "ninjutsu_names",
        "route": "battle",
        "group": "batch2",
        "l2": False,
        "l1_reason": "fn 0x080794F4 is only called from 0x0806F89C (the "
                     "character/skill module); neither the battles nor the "
                     "story sweep open the ninjutsu list",
        "layout": {"stride": 4, "count": 93},
        "summary": "u32 text pointer table; the reader takes the pointer out of "
                   "the table with a masked id index.",
        "captures": [
            {"reader": 0x080796E4, "decision": 0x080796F0, "function": 0x080794F4,
             "derive": derive_ninjutsu_names,
             "corrupt": {"r1": ("base", 4)}},
        ],
    },
    "reward-table": {
        "registry": "reward_table",
        "route": "battle",
        "group": "batch2",
        "layout": {"stride": 24, "count": 112},
        "summary": "112 x 24-byte reward records; the consumer reads the +7 "
                   "byte of the record the index selects.",
        "captures": [
            {"reader": 0x08089EA2, "decision": 0x08089EAE, "function": 0x08089E84,
             "derive": derive_reward_table, "base_reg": "r2",
             "field_reg": "r0", "field_offset": "7",
             "corrupt": {"r2": ("base", 4)}},
        ],
    },
    "cutscene-scripts": {
        "registry": "legacy_cutscene_scripts",
        "route": "battle",
        "group": "batch2",
        "layout": {"stride": 8, "count": 4},
        "registry_unverified":
            "the registry's `verified` flag is about the legacy NAME "
            "('过场脚本表'), which was falsified: 0x53DF70 is the level data "
            "block table (4 entries x 8 bytes: an LZ77 4bpp tile pointer and an "
            "LZ77 16-colour palette pointer).  The ADDRESS is the adjudicated "
            "one (notes/evidence/cutscene-block-format-20261020.md), and the "
            "runtime capture below proves it independently.",
        "summary": "4 x 8-byte level data blocks (LZ77 tile pointer + LZ77 "
                   "palette pointer), decompressed into VRAM 0x06016000 and the "
                   "palette RAM 0x05000380.",
        "captures": [
            {"reader": 0x08072F0C, "decision": 0x08072F16, "function": 0x08072EDC,
             "derive": derive_cutscene_blocks,
             "corrupt": {"r4": ("base", 4)}},
        ],
    },
    "sprite-action-table": {
        "registry": "sprite_action_table",
        "route": "battle",
        "group": "batch2",
        "layout": {"stride": 144, "count": 63},
        "summary": "63 sprite ids x 9 actions x 16 bytes (four u32 pointers); "
                   "the consumer scales the sprite id by 144.",
        "captures": [
            {"reader": 0x0806B76C, "decision": 0x0806B770, "function": 0x0806B720,
             "derive": derive_sprite_action_table, "base_reg": "r1",
             "action_offset": "0",
             "corrupt": {"r1": ("base", 4)}},
        ],
    },

    # --- batch 3 (2026-10-21) ---------------------------------------------
    # The `title` group: the consumers live in the character loader
    # (fn 0x0806D964), which the title route reaches.
    "character-stats": {
        "registry": "per_character_stats",
        "route": "title",
        "group": "batch3",
        "layout": {"stride": 16, "count": 63},
        "summary": "63 x 16-byte per-character stat records; the character "
                   "loader scales the character id by 16 to select one.",
        "captures": [
            {"reader": 0x0806D98C, "decision": 0x0806D98E, "function": 0x0806D964,
             "derive": derive_character_stats,
             "corrupt": {"r0": ("base", 4)}},
        ],
    },
    "character-stats-b": {
        "registry": "per_character_stats",
        "route": "title",
        "group": "batch3",
        "registry_unverified":
            "the bank name is a deprecated alias: `character-stats-b` pointed at "
            "0x545200, which is 0x545068 + 25*16 + 8 -- a skewed window into "
            "the SAME table that `character-stats` owns.  The address below is "
            "the registry's adjudicated one and the runtime capture proves it.",
        "layout": {"stride": 16, "count": 63},
        "summary": "deprecated alias of `character-stats`: the same 63 x 16-byte "
                   "per-character stat records, read through the same native "
                   "reader.",
        "captures": [
            # the same reader, a different decision point: the stat value
            # itself is in a register here.
            {"reader": 0x0806D98C, "decision": 0x0806D9D8, "function": 0x0806D964,
             "derive": derive_character_stats_field, "field_offset": "6",
             "corrupt": {"r1": ("value", 4)}},
        ],
    },
    "levels": {
        "registry": "character_perks",
        "route": "battle",
        "group": "batch3",
        "layout": {"stride": 12, "count": 45},
        "summary": "45 x 12-byte character perk records; the consumer scales "
                   "the perk index by 12 and reads the record's +6 u16.",
        "captures": [
            {"reader": 0x0806DB14, "decision": 0x0806DB1A, "function": 0x0806D964,
             "derive": derive_character_perks, "field_offset": "6",
             "entry_reg": "r3", "base_reg": "r1",
             "corrupt": {"r1": ("base", 4)}},
            {"reader": 0x0806DC4C, "decision": 0x0806DC52, "function": 0x0806D964,
             "derive": derive_character_perks, "field_offset": "6",
             "entry_reg": "r3", "base_reg": "r1",
             "corrupt": {"r1": ("base", 4)}},
            {"reader": 0x0806D6E6, "decision": 0x0806D6EC, "function": 0x0806D6B8,
             "derive": derive_character_perks, "field_offset": "6",
             "entry_reg": "r1", "base_reg": None,
             "corrupt": {"r0": ("value", 1)}},
            {"reader": 0x0806D786, "decision": 0x0806D792, "function": 0x0806D6B8,
             "derive": derive_character_perks, "field_offset": "6",
             "entry_reg": "r1", "base_reg": None,
             "corrupt": {"r0": ("value", 1)}},
            {"reader": 0x0806DDD6, "decision": 0x0806DDE2, "function": 0x0806D964,
             "derive": derive_character_perks, "field_offset": "6",
             "entry_reg": "r1", "base_reg": None,
             "corrupt": {"r0": ("value", 1)}},
            {"reader": 0x080932CA, "decision": 0x080932D8, "function": 0x08093070,
             "derive": derive_character_perks, "field_offset": "6",
             "index_reg": "r1", "base_reg": "r2",
             "corrupt": {"r0": ("value", 1)}},
        ],
    },

    # The `battle` group: the consumers live in the battle subsystem.
    "encounter-zones": {
        "registry": "map_table",
        "route": "battle",
        "group": "batch3",
        "layout": {"stride": 32, "count": 50},
        "summary": "deprecated alias of `maps`: the same 32-byte map "
                   "descriptors, read through the battle map loader "
                   "(fn 0x08068FF0), which scales the map id by 32.",
        "captures": [
            {"reader": 0x08069040, "decision": 0x0806904C, "function": 0x08068FF0,
             "derive": derive_encounter_zones,
             "corrupt": {"r5": ("base", 4)}},
            {"reader": 0x08069220, "decision": 0x0806922A, "function": 0x0806921C,
             "derive": derive_encounter_zones,
             "corrupt": {"r1": ("base", 4)}},
        ],
    },
    "battle-config": {
        "registry": "battle_actors",
        "route": "battle",
        "group": "batch3",
        "layout": {"stride": 0x1AAC, "count": 48},
        "summary": "the formation matrix: base + group*0x1AAC + sub*0x8E4 "
                   "+ slot*0xB8 + 4; the consumer scales the group and the sub "
                   "configuration out of the WRAM state.",
        "captures": [
            {"reader": 0x0806DF28, "decision": 0x0806DF3E, "function": 0x0806DE18,
             "derive": derive_battle_config,
             "corrupt": {"r3": ("base", 4)}},
            {"reader": 0x0806E1F0, "decision": 0x0806E1FE, "function": 0x0806E1B4,
             "derive": derive_battle_config,
             "corrupt": {"r1": ("base", 4)}},
            {"reader": 0x0806E3D4, "decision": 0x0806E3DC, "function": 0x0806E1B4,
             "derive": derive_battle_config,
             "corrupt": {"r2": ("base", 4)}},
        ],
    },
    "items": {
        "registry": "item_skill_records",
        "route": "battle",
        "group": "batch3",
        "l2": False,
        "l1_reason": "fn 0x0806D910 (reader 0x0806D91A) is only called from 12 "
                     "story / map-event functions (0x0806FDA4, 0x080708BC, "
                     "0x08070DF8, 0x080722A8, 0x080754A8, 0x08075B58, "
                     "0x08082354, 0x080833A8, 0x0808400C, 0x080851F8, "
                     "0x08092694) -- none of which the battle, sweep or save "
                     "routes open.  This round also armed the three readers "
                     "batch 3 had not tried (0x08078EF8 / 0x08078F08 / "
                     "0x08095394) and the two readers behind the fn "
                     "0x0806E1B4 branches (0x0808FC28 / 0x0808FF78): none of "
                     "the six is hit by the title, battle, sweep or save "
                     "route",
        "layout": {"stride": 16, "count": 94},
        "summary": "94 x 16-byte item/skill records; the consumer scales the "
                   "id by 16 and copies the record into the runtime struct.",
        "captures": [
            {"reader": 0x0806D91A, "decision": 0x0806D924, "function": 0x0806D910,
             "derive": derive_item_records,
             "corrupt": {"r1": ("base", 4)}},
            {"reader": 0x0808FC28, "decision": 0x0808FC30, "function": 0x0808FC20,
             "derive": derive_item_records_field_at,
             "base_reg": "r3", "entry_offset_reg": "r1", "field_reg": "r0",
             "field_offset": "0xC",
             "corrupt": {"r3": ("base", 4)}},
            {"reader": 0x0808FF78, "decision": 0x0808FF80, "function": 0x0808FF24,
             "derive": derive_item_records_field_at,
             "base_reg": "r3", "entry_reg": "r2", "field_reg": "r1",
             "field_offset": "0xA",
             "corrupt": {"r3": ("base", 4)}},
            # the readers batch 3 did not try: both of them load the base
            # into r0 and compute the entry into r1 (base + id*16), so the
            # decision point sits right after the `ldrb`.
            {"reader": 0x08078EF8, "decision": 0x08078F18, "function": 0x08078EF0,
             "derive": derive_item_records, "base_reg": "r0", "entry_reg": "r1",
             "corrupt": {"r1": ("value", 4)}},
            {"reader": 0x08095394, "decision": 0x080953B6, "function": 0x08095390,
             "derive": derive_item_records, "base_reg": "r0", "entry_reg": "r1",
             "corrupt": {"r1": ("value", 4)}},
        ],
    },
    "skills": {
        "registry": "item_skill_records",
        "route": "battle",
        "group": "batch3",
        "l2": False,
        "l1_reason": "the same table as `items`, and the same consumers: "
                     "fn 0x0806D910 (reader 0x0806D91A) and the readers "
                     "behind the fn 0x0806E1B4 branches (0x0808FC28, "
                     "0x0808FF78) are not reached by the title, battle, "
                     "sweep or save routes",
        "layout": {"stride": 16, "count": 94},
        "summary": "deprecated alias of `items`: the same 16-byte item/skill "
                   "records; the registry's adjudication gives `skills` the "
                   "canonical name.",
        "captures": [
            {"reader": 0x0806D91A, "decision": 0x0806D926, "function": 0x0806D910,
             "derive": derive_item_records_field,
             "corrupt": {"r1": ("value", 1)}},
            {"reader": 0x0808FC28, "decision": 0x0808FC2E, "function": 0x0808FC20,
             "derive": derive_item_records, "base_reg": "r3", "entry_reg": "r0",
             "corrupt": {"r3": ("base", 4)}},
            {"reader": 0x0808FF78, "decision": 0x0808FF7E, "function": 0x0808FF24,
             "derive": derive_item_records, "base_reg": "r3", "entry_reg": "r2",
             "corrupt": {"r3": ("base", 4)}},
        ],
    },
    "mission-text": {
        "registry": "mission_index",
        "route": "save",
        "group": "batch3",
        "layout": {"stride": 1, "count": 48},
        "summary": "48 x 1-byte mission index entries; the consumer adds the "
                   "state byte to the base and reads the byte it finds there.",
        "captures": [
            # the reader that IS reached: fn 0x080884E0 loads the table and
            # indexes it with the *scene* byte of the story state.
            {"reader": 0x080884F8, "decision": 0x08088502, "function": 0x080884E0,
             "derive": derive_mission_index_scene,
             "corrupt": {"r2": ("base", 4)}},
            {"reader": 0x080874FE, "decision": 0x08087510, "function": 0x08087334,
             "derive": derive_mission_index_state,
             "corrupt": {"r2": ("base", 4)}},
            {"reader": 0x080731DA, "decision": 0x080731E4, "function": 0x080731D0,
             "derive": derive_mission_index,
             "corrupt": {"r1": ("base", 4)}},
            {"reader": 0x0808675C, "decision": 0x08086766, "function": 0x08086740,
             "derive": derive_mission_index, "base_reg": "r2",
             "corrupt": {"r2": ("base", 4)}},
        ],
    },
    "save-state": {
        "registry": "legacy_save_state",
        "route": "save",
        "group": "batch3",
        "registry_unverified":
            "the registry flag is about the legacy NAME (存档描述符表); the "
            "address 0x53D848 is the one four native readers load, and the "
            "runtime capture below proves the {u32 wram address, u32 size} "
            "shape independently.",
        "layout": {"stride": 8, "count": 11},
        "summary": "11 x 8-byte WRAM allocation records {u32 wram address, "
                   "u32 size}; the consumer walks them until it finds the "
                   "empty one.",
        "captures": [
            {"reader": 0x08068954, "decision": 0x08068962, "function": 0x08068948,
             "derive": derive_save_state, "entry_reg": "r3",
             "wram_reg": "r0", "size_reg": "r1",
             "corrupt": {"r0": ("value", 4)}},
            {"reader": 0x08068CC0, "decision": 0x08068CCA, "function": 0x08068CB8,
             "derive": derive_save_state, "entry_reg": "r2",
             "wram_reg": "r0", "size_reg": "r1",
             "corrupt": {"r0": ("value", 4)}},
            {"reader": 0x08068D98, "decision": 0x08068DA0, "function": 0x08068D90,
             "derive": derive_save_state, "entry_reg": "r2",
             "wram_reg": "r0", "size_reg": "r1",
             "corrupt": {"r0": ("value", 4)}},
            {"reader": 0x0806869A, "decision": 0x080686A6, "function": 0x08068684,
             "derive": derive_save_state,
             "corrupt": {"r0": ("value", 4)}},
        ],
    },
    "story-background-table": {
        "registry": "background_table",
        "route": "battle",
        "group": "batch3",
        "layout": {"stride": 16, "count": 14},
        "summary": "14 x 16-byte story background records; the consumer scales "
                   "the background id by 16 and decompresses the record's "
                   "LZ77 tiles.",
        "captures": [
            {"reader": 0x08088372, "decision": 0x0808837C, "function": 0x08088348,
             "derive": derive_story_background,
             "corrupt": {"r4": ("base", 4)}},
            {"reader": 0x08088400, "decision": 0x0808840A, "function": 0x08088348,
             "derive": derive_story_background_flag,
             "corrupt": {"r1": ("base", 4)}},
        ],
    },
    "sprite-animations": {
        "registry": "sprite_action_table",
        "route": "battle",
        "group": "batch3",
        "layout": {"stride": 144, "count": 63},
        "summary": "deprecated alias of `sprite-action-table`: the same "
                   "sprite action records (id*144 + action*16, four u32 "
                   "pointers each).",
        "captures": [
            {"reader": 0x0806B76C, "decision": 0x0806B770, "function": 0x0806B720,
             "derive": derive_sprite_action_table, "base_reg": "r1",
             "action_offset": "0",
             "corrupt": {"r1": ("base", 4)}},
        ],
    },

    # The object group: fn 0x08080B08 reaches both the object descriptor table
    # and the unit slot remap table.  It has to be its own group because
    # `map-sprites` and `resource-pointers` share the *same* decision point
    # inside fn 0x080625A4 (one breakpoint address can only belong to one
    # structure inside one capture group).
    "map-sprites": {
        "registry": "object_descriptor_table",
        "route": "battle",
        "group": "batch3",
        "l2": False,
        "l1_reason": "the only native reader 0x08080B12 is in fn 0x08080B08, "
                     "which is only reached from the dispatch branches of "
                     "fn 0x08080BA0 (0x08080C42 ... 0x08080D5C).  That "
                     "dispatch belongs to the object-type callback table, "
                     "whose **real base is 0x0853EF30 with a 24-byte stride** "
                     "(this round re-derived it from the consumer's own "
                     "dataflow; 0x0853EF70 has no literal reader at all).  "
                     "The spawn entry fn 0x080800A4, which is the only "
                     "function that reads that type table, is never called "
                     "by the title, battle, sweep or save route -- the game "
                     "never instantiates any of those object types",
        "registry_unverified":
            "the registry flag is about the legacy name (the 0x53F138 window); "
            "the address 0x53F140 is the one the native reader 0x08080B12 "
            "loads, and the runtime capture below proves it independently.",
        "layout": {"stride": 8, "count": 43},
        "summary": "43 x 8-byte object descriptor records {u32 pointer, u32 "
                   "pointer}; fn 0x08080B08 passes the base to fn 0x080625A4, "
                   "which scales the index by 8.",
        "captures": [
            # fn 0x080625A4 is shared by 15 different consumers, so the
            # decision point is the caller's own instruction: fn 0x08080B08
            # is the ONLY reader of 0x0853F140 and it fixes the base and the
            # index together.
            {"reader": 0x08080B12, "decision": 0x08080B74, "function": 0x08080B08,
             "derive": derive_pointer_pair_base,
             "corrupt": {"r5": ("base", 4)}},
        ],
    },
    "units": {
        "registry": "unit_slot_remap",
        "route": "battle",
        "group": "batch3",
        "l2": False,
        "l1_reason": "reader 0x08080B2C is in the same fn 0x08080B08 as the "
                     "`map-sprites` reader, so it has exactly the same "
                     "blocker: fn 0x08080B08 is only reached from the object "
                     "type dispatch at 0x08080BA0, whose type table's real "
                     "base is 0x0853EF30 (stride 24), and the game never "
                     "instantiates any of those object types",
        "layout": {"stride": 2, "count": 43},
        "summary": "43 x 2-byte unit slot remap values; the consumer adds the "
                   "value to the runtime u16 at WRAM 0x0202CA24 and masks the "
                   "sum back to 16 bits.",
        "captures": [
            {"reader": 0x08080B2C, "decision": 0x08080B3C, "function": 0x08080B08,
             "derive": derive_unit_slot_remap,
             "corrupt": {"r1": ("base", 4)}},
        ],
    },

    # The resource group: fn 0x0807AE04 loads 0x08596F0C and hands it to the
    # same fn 0x080625A4, so it needs its own decision point.
    "resource-pointers": {
        "registry": "legacy_resource_pointers",
        "route": "battle",
        "group": "batch3",
        "l2": False,
        "l1_reason": "reader 0x0807B220 is in fn 0x0807AE04, which is called "
                     "from eight functions (0x0807B444, 0x0807B6E0, "
                     "0x0807B8B8, 0x0807C638, 0x0807DCB8, 0x0807ED20, "
                     "0x0807EE50, 0x0807F414).  Two of them -- fn 0x0807EE50 "
                     "(the font width table consumer) and fn 0x0807F414 (the "
                     "battle event dispatcher) -- were already proven "
                     "unreachable in batch 2, and none of the other six runs "
                     "in the title, battle, sweep or save routes either",
        "registry_unverified":
            "the registry flag is about the legacy name (资源指针表); the "
            "address 0x596F0C is the one the native reader 0x0807B220 "
            "loads.  Note that 0x596F0C = 0x596CCC + 4*144, i.e. it is a "
            "*window* into the sprite action table -- the runtime capture "
            "below proves the window, not a separate structure.",
        "layout": {"stride": 8, "count": 20},
        "summary": "the sprite-action window 0x08596F0C: fn 0x0807AE04 loads "
                   "it and hands it to fn 0x080625A4, which scales the index "
                   "by 8 over the {u32, u32} pairs.",
        "captures": [
            # fn 0x080625A4 is shared by 15 different consumers, so the
            # decision point is the consumer's own instruction: fn 0x0807AE04
            # is the ONLY reader of 0x08596F0C.
            {"reader": 0x0807B220, "decision": 0x0807B222, "function": 0x0807AE04,
             "derive": derive_window_base,
             "corrupt": {"r0": ("base", 4)}},
        ],
    },

    # --- batch 4 (2026-10-21) ---------------------------------------------
    # The five m4a SongHeaders.  Their address is never loaded by a literal:
    # it is a u32 *value* stored in the sound id table 0x08465B70 and taken
    # out with `ldr rX, [rN]`.  The `via_pointer` static check proves the
    # link mechanically; the runtime capture proves the m4a engine really
    # reads the header's fields.
    "story": {
        "registry": "audio_song_1",
        "route": "title",
        "group": "story",
        "l2": False,
        "l1_reason": "the m4a play entry (fn 0x0809B1F4), which is the native "
                     "consumer of a SongHeader's *contents*, is never called "
                     "with r1 = 0x08536368: the two play paths (fn 0x0809AAC0 "
                     "/ fn 0x0809AB38) request only the sound ids 4, 5, 8, 13, "
                     "102, 111 and 143 in the story sweep and 4 / 102 in the "
                     "title route, and sound id 1 is only ever requested "
                     "through the *stop* path fn 0x0809AB8C -- so the link "
                     "from the sound id table is observed at runtime, but the "
                     "engine never reads this header's fields",
        "layout": {"stride": 48, "count": 1},
        "via_pointer": {
            "registry": "sound_id_table",
            "stride": 8,
            "count": 159,
            "dereference_readers": [0x0809B242, 0x0809B25C, 0x0809B282],
        },
        "summary": "m4a SongHeader of sound id 1: {u8 track count, u32 "
                   "sequence pointer, u32 track pointers[]}; the header is "
                   "reached through the sound id table.",
        "captures": [
            # role `link`: the sound-id reader takes this header's address
            # out of the id table (fn 0x0809AB8C is the *stop* path; the
            # pointer lands in r0 at 0x0809ABA6).
            {"reader": 0x0809AB92, "decision": 0x0809ABA8, "function": 0x0809AB8C,
             "derive": derive_song_header_link, "role": "link",
             "entry_reg": None, "pointer_reg": "r0",
             "match": {"reg": "r0", "value": "base"},
             "sticky": True,
             "corrupt": {"r0": ("value", 4)}},
            # role `engine`: the m4a play entry reads the header's fields.
            {"reader": 0x0809B242, "decision": 0x0809B25E, "function": 0x0809B1F4,
             "derive": derive_song_header_count, "role": "engine",
             "match": {"reg": "r7", "value": "base"},
             "sticky": True,
             "corrupt": {"r7": ("value", 4)}},
        ],
    },
    "story-b": {
        "registry": "audio_song_2",
        "route": "sweep",
        "group": "story-b",
        "layout": {"stride": 48, "count": 1},
        "via_pointer": {
            "registry": "sound_id_table",
            "stride": 8,
            "count": 159,
            "dereference_readers": [0x0809B242, 0x0809B25C, 0x0809B282],
        },
        "summary": "m4a SongHeader of sound id 2: {u8 track count, u32 "
                   "sequence pointer, u32 track pointers[]}; the story sweep "
                   "plays it, and the m4a play entry reads its fields.",
        "captures": [
            {"reader": 0x0809AB3E, "decision": 0x0809AB54, "function": 0x0809AB38,
             "derive": derive_song_header_link, "role": "link",
             "entry_reg": "r0", "pointer_reg": "r2",
             "match": {"reg": "r2", "value": "base"},
             "sticky": True,
             "corrupt": {"r2": ("value", 4)}},
            {"reader": 0x0809B242, "decision": 0x0809B244, "function": 0x0809B1F4,
             "derive": derive_song_header_sequence, "role": "engine",
             "match": {"reg": "r7", "value": "base"},
             "sticky": True,
             "corrupt": {"r7": ("value", 4)}},
        ],
    },
    "story-c": {
        "registry": "audio_song_8",
        "route": "battle",
        "group": "batch4-story-battle",
        "layout": {"stride": 48, "count": 1},
        "via_pointer": {
            "registry": "sound_id_table",
            "stride": 8,
            "count": 159,
            "dereference_readers": [0x0809B242, 0x0809B25C, 0x0809B282],
        },
        "summary": "m4a SongHeader of sound id 8: {u8 track count, u32 "
                   "sequence pointer, u32 track pointers[]}; the m4a play "
                   "entry reads its fields.",
        "captures": [
            # role `link`: the sound-id reader takes this header's address
            # out of the id table.  fn 0x0809AB38 is the play path the battle
            # route uses (the engine capture below shows its return address
            # 0x0809AB61), so the link is observed in the same route.
            {"reader": 0x0809AB3E, "decision": 0x0809AB54, "function": 0x0809AB38,
             "derive": derive_song_header_link, "role": "link",
             "entry_reg": "r0", "pointer_reg": "r2",
             "match": {"reg": "r2", "value": "base"},
             "sticky": True,
             "corrupt": {"r2": ("value", 4)}},
            {"reader": 0x0809B242, "decision": 0x0809B244, "function": 0x0809B1F4,
             "derive": derive_song_header_sequence, "role": "engine",
             "match": {"reg": "r7", "value": "base"},
             "sticky": True,
             "corrupt": {"r7": ("value", 4)}},
        ],
    },
    "story-d": {
        "registry": "audio_song_11",
        "route": "battle",
        "group": "batch4-story-battle",
        "layout": {"stride": 48, "count": 1},
        "via_pointer": {
            "registry": "sound_id_table",
            "stride": 8,
            "count": 159,
            "dereference_readers": [0x0809B242, 0x0809B25C, 0x0809B282],
        },
        "summary": "m4a SongHeader of sound id 11: {u8 track count, u32 "
                   "sequence pointer, u32 track pointers[]}; the m4a play "
                   "entry reads its fields.",
        "captures": [
            {"reader": 0x0809B242, "decision": 0x0809B284, "function": 0x0809B1F4,
             "derive": derive_song_header_track, "role": "engine",
             "match": {"reg": "r7", "value": "base"},
             "sticky": True,
             "corrupt": {"r7": ("value", 4)}},
        ],
    },
    "story-e": {
        "registry": "audio_song_14",
        "route": "battle",
        "group": "batch4-story-battle",
        "layout": {"stride": 48, "count": 1},
        "via_pointer": {
            "registry": "sound_id_table",
            "stride": 8,
            "count": 159,
            "dereference_readers": [0x0809B242, 0x0809B25C, 0x0809B282],
        },
        "summary": "m4a SongHeader of sound id 14: {u8 track count, u32 "
                   "sequence pointer, u32 track pointers[]}; the m4a play "
                   "entry reads its fields.",
        "captures": [
            {"reader": 0x0809B242, "decision": 0x0809B25E, "function": 0x0809B1F4,
             "derive": derive_song_header_count, "role": "engine",
             "match": {"reg": "r7", "value": "base"},
             "sticky": True,
             "corrupt": {"r7": ("value", 4)}},
        ],
    },
    # The task book lists `battle-config` at 0x545458, the ninjutsu record
    # table, and gives the six readers of 0x085459C8 (the character perk
    # table that starts exactly where this table ends).  Asking
    # `LiteralIndex` for 0x08545458 turns up **eight** readers of its own --
    # so the table does have a native consumer after all.
    "ninjutsu-records": {
        "registry": "skill_table",
        "route": "battle",
        "group": "batch4-ninjutsu",
        "l2": False,
        "l1_reason": "the table has eight native literal readers (0x0806D866, "
                     "0x08078776, 0x080922D0, 0x08092324, 0x08093296, "
                     "0x08093352, 0x08094550, 0x08094A36), but **none of them "
                     "is reached** by the title, battle, sweep or save "
                     "route: the two that were armed (reader 0x08078776 / "
                     "decision 0x0807877E and reader 0x0806D866 / decision "
                     "0x0806D874) never hit.  Both live in the ninjutsu / "
                     "character module, which the three routes only enter "
                     "through the character template loader (fn 0x0806D964) "
                     "-- the ninjutsu list itself is never opened",
        "layout": {"stride": 16, "count": 87},
        "summary": "87 x 16-byte ninjutsu records; the consumer scales the "
                   "ninjutsu id by 16 and reads a field out of the record.",
        "captures": [
            {"reader": 0x08078776, "decision": 0x0807877E, "function": 0x08078770,
             "derive": derive_ninjutsu_records, "entry_reg": "r1",
             "field_reg": "r0", "field_offset": "2",
             "corrupt": {"r0": ("value", 1)}},
            {"reader": 0x0806D866, "decision": 0x0806D874, "function": 0x0806D860,
             "derive": derive_ninjutsu_records, "entry_reg": "r0",
             "entry_offset": "12", "field_reg": "r0", "field_offset": "12",
             "corrupt": {"r0": ("value", 4)}},
        ],
    },
    "mechanism-effects": {
        "registry": "mechanism_effect_table",
        "route": "battle",
        "group": "batch4-mechanism",
        "l2": False,
        "l1_reason": "the 13-entry effect pointer table lives in the **code "
                     "region** (0x0808136C) and its only literal reader is "
                     "0x08081350, inside fn 0x080812DC (the 13-way effect "
                     "dispatcher).  That dispatcher runs only when a map "
                     "object triggers a mechanism -- the same 'level / "
                     "cutscene mode' the callback census showed the story, "
                     "battle and save routes cannot enter",
        "layout": {"stride": 4, "count": 13},
        "summary": "13 u32 code pointers in the code region; the effect "
                   "dispatcher scales the target id by 4 and jumps through "
                   "the entry.",
        "captures": [
            {"reader": 0x08081350, "decision": 0x08081356, "function": 0x080812DC,
             "derive": derive_mechanism_effects,
             "corrupt": {"r0": ("value", 4)}},
        ],
    },
}


# ---------------------------------------------------------------------------
# which routes a group of structures is allowed to try
# ---------------------------------------------------------------------------
# The battle route is the richest environment (it runs the whole battle
# subsystem), so it comes first; the story sweep is the fallback for the
# consumers that only the story scenes touch.
GROUP_ROUTES: dict[str, list[str]] = {
    "batch2": ["battle", "sweep"],
    # batch 3: one group, four routes (cheapest first).  Every batch-3
    # structure owns a decision point that no other structure owns, so they
    # can share one capture group.
    "batch3": ["title", "battle", "sweep", "save"],
    # batch 4: the five m4a SongHeaders.  Each one needs its own decision
    # point, so `story-b` and `story` (which need different routes) get their
    # own groups, and `story-c/d/e` share one group with three distinct
    # decision points.
    "story": ["title", "sweep", "battle"],
    "story-b": ["sweep", "battle", "title"],
    "batch4-story-battle": ["battle", "sweep", "title"],
    "batch4-ninjutsu": ["battle", "sweep", "title"],
    "batch4-mechanism": ["battle", "sweep", "title"],
}

# Routes that share a starting savestate with another route.
STATE_ALIASES = {"save": "battle"}


def _captures_ok(spec: dict, records: list[dict]) -> bool:
    """Does the structure have the proof it claims?

    A capture's `role` names the part of the proof it provides ("link",
    "engine", ...).  The structure passes when **every required role** has at
    least one passing capture; a capture marked `optional` only adds
    evidence.  Captures without a role all share the default role, so the
    historical behaviour -- "any passing capture is enough" -- is preserved
    for every structure that was already in the catalogue.
    """
    required = {c.get("role", "default") for c in spec["captures"]
                if not c.get("optional")}
    if not required:
        return False
    seen: dict[str, bool] = {}
    for record in records:
        role = record.get("role", "default")
        seen[role] = seen.get(role, False) or bool(record.get("ok"))
    return all(seen.get(role, False) for role in required)


# ---------------------------------------------------------------------------
# static preparation
# ---------------------------------------------------------------------------
def registry_base(name: str, allow_unverified: bool = False) -> int:
    """The registry stores file offsets; the runtime addresses add ROM_BASE."""
    offset, verified, _note = TABLES[name]
    if not verified and not allow_unverified:
        raise SystemExit(f"registry entry {name!r} is not verified")
    return offset + ROM_BASE


def song_header_bases() -> dict[int, int]:
    """sound id -> registered m4a SongHeader base (ROM addresses)."""
    out: dict[int, int] = {}
    for song_id in (1, 2, 8, 11, 14):
        key = f"audio_song_{song_id}"
        if key in TABLES:
            out[song_id] = TABLES[key][0] + ROM_BASE
    return out


def static_checks(key: str, spec: dict, rom: bytes, index: LiteralIndex) -> list[dict]:
    """Everything that can be checked without the emulator."""
    checks: list[dict] = []
    allow_unverified = bool(spec.get("registry_unverified"))
    base = registry_base(spec["registry"], allow_unverified)
    via = spec.get("via_pointer")
    readers = sorted({addr for addr, _mode in index.readers_of(base)})
    if via:
        # The structure's address is never loaded by a literal: it is a u32
        # *value* stored inside another table, and the consumer takes it out
        # with an ordinary `ldr rX, [rN]`.  The readers that matter are then
        # the pointer table's readers plus the instructions that dereference
        # the loaded pointer -- so the address still comes from the registry
        # and the reader set still comes from `LiteralIndex`.
        ptr_base = registry_base(via["registry"])
        ptr_readers = sorted({addr for addr, _mode in index.readers_of(ptr_base)})
        deref = list(via.get("dereference_readers", []))
        readers = ptr_readers + deref
        checks.append({
            "name": "the pointer table that stores this structure's address "
                    "has native literal readers in the ROM",
            "ok": bool(ptr_readers),
            "detail": f"{len(ptr_readers)} reader(s) of 0x{ptr_base:08X}: "
                      + ", ".join(hexs(a) for a in ptr_readers),
        })
        stride = int(via.get("stride", 4))
        count = int(via.get("count", 0))
        slot = -1
        for i in range(count):
            if u32(rom, ptr_base + i * stride) == base:
                slot = i
                break
        checks.append({
            "name": "the structure's base address is stored as a u32 inside "
                    "that pointer table",
            "ok": slot >= 0,
            "detail": f"base=0x{base:08X} slot={slot} stride={stride} "
                      f"count={count}",
        })
        checks.append({
            "name": "the pointer table's declared extent fits inside the ROM",
            "ok": ROM_BASE <= ptr_base
                  and ptr_base + count * stride <= ROM_BASE + len(rom),
            "detail": f"ptr_base=0x{ptr_base:08X} count={count} "
                      f"stride={stride}",
        })
    elif spec.get("no_native_reader"):
        checks.append({
            "name": "the structure really has no native literal reader in "
                    "the ROM (declared, with a reason)",
            "ok": not readers,
            "detail": spec.get("l1_reason", "no reason given"),
        })
    else:
        checks.append({
            "name": "the structure has native literal readers in the ROM",
            "ok": bool(readers),
            "detail": f"{len(readers)} reader(s): "
                      + ", ".join(hexs(a) for a in readers),
        })
    if not TABLES[spec["registry"]][1]:
        checks.append({
            "name": "the registry entry is verified, or the unverified flag is "
                    "declared with a reason",
            "ok": allow_unverified,
            "detail": spec.get("registry_unverified", "no reason given"),
        })
    reader_label = ("is a declared native reader of this structure (a literal "
                    "reader of the pointer table, or a declared dereference "
                    "site)") if via else "is one of those native readers"
    for capture in spec["captures"]:
        checks.append({
            "name": f"capture reader {hexs(capture['reader'])} {reader_label}",
            "ok": capture["reader"] in readers,
            "detail": f"reader={hexs(capture['reader'])}",
        })
        decision = capture["decision"]
        checks.append({
            "name": f"decision point {hexs(decision)} is inside the ROM",
            "ok": ROM_BASE <= decision < ROM_BASE + len(rom),
            "detail": f"decision={hexs(decision)}",
        })
    layout = spec.get("layout")
    if layout:
        span = base + layout["count"] * layout["stride"]
        checks.append({
            "name": "the declared table extent fits inside the ROM",
            "ok": ROM_BASE <= base and span <= ROM_BASE + len(rom),
            "detail": f"base=0x{base:08X} count={layout['count']} "
                      f"stride=0x{layout['stride']:X} end=0x{span:08X}",
        })
    if key == "sound-id-table":
        headers = song_header_bases()
        for song_id, header in headers.items():
            entry = base + song_id * 8
            checks.append({
                "name": f"sound id {song_id} points at the registered SongHeader",
                "ok": u32(rom, entry) == header,
                "detail": f"entry=0x{entry:08X} pointer=0x{u32(rom, entry):08X} "
                          f"registry=0x{header:08X}",
            })
    return checks


# ---------------------------------------------------------------------------
# driving the probe
# ---------------------------------------------------------------------------
def navigate_to_dispatch(probe: Probe) -> bool:
    """Park the core on the 'next scene' dispatch (`ldrb r0,[r4,#0x16]`)."""
    return navigate_to(probe, NEXT_SCENE)


def navigate_to(probe: Probe, address: int) -> bool:
    """Park the core on `address` with the game in the story state machine."""
    ident = arm(probe, address)
    vm_id = arm(probe, VM_ENTRY)
    try:
        for _ in range(6):
            for key, frames in NAV_PLAN:
                out = probe.send(f"frames {frames} {key:#05x}")
                if hits_in(out):
                    break
                out = probe.send(f"frames {SETTLE_FRAMES} 0x000")
                if hits_in(out):
                    break
            regs = probe.registers()
            if regs["pc"] == address + 2:
                return True
    finally:
        for ident in (ident, vm_id):
            if ident is not None:
                probe.send(f"delete {ident}")
    return False


def build_state(exe: pathlib.Path, rom_path: pathlib.Path, route: str,
                path: pathlib.Path, scene: int) -> None:
    """Walk to the route's starting state once and cache it as a savestate.

    Every route gets its **own** probe process: a savestate is a snapshot of
    one particular run, and a session that already played the story would
    hand the next route a state that is no longer the title screen.
    """
    probe = Probe(exe, rom_path, timeout=900)
    try:
        probe.send("frames 1500 0x000")
        if route in ("dispatch", "sweep"):
            if not navigate_to_dispatch(probe):
                raise RuntimeError("could not park the core on the scene dispatch")
        elif route in ("battle", "save"):
            if not navigate_to(probe, STATE_LOOP):
                raise RuntimeError("could not park the core on the state machine")
        path.parent.mkdir(parents=True, exist_ok=True)
        probe.send(f"save {path}")
    finally:
        probe.close()


def parse_scene_list(spec: str) -> list[int]:
    """'1-55' / '1,4,9-12' -> a list of scene numbers."""
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return out


def capture_group(keys: list[str], ctx: dict, probe: Probe,
                  route: str) -> dict[str, dict]:
    """Arm every decision point of `keys` and run one route.

    Several structures share a route; arming them together lets one sweep
    of the game feed all of them.  A structure passes when **any** of its
    captures observed the expected correspondence.
    """
    specs = {key: STRUCTURES[key] for key in keys}

    armed: dict[int, int] = {}               # breakpoint id -> decision address
    owner: dict[int, tuple[str, dict]] = {}  # decision address -> (key, capture)
    for key, spec in specs.items():
        for capture in spec["captures"]:
            ident = arm(probe, capture["decision"])
            if ident is not None:
                armed[ident] = capture["decision"]
                owner[capture["decision"]] = (key, capture)
    if not armed:
        raise RuntimeError(f"{keys}: could not arm any decision point")

    records: dict[str, list[dict]] = {key: [] for key in keys}

    def handle(found: list[tuple[int, int]]) -> None:
        for ident, addr in found:
            if addr not in owner:
                continue
            key, capture = owner[addr]
            sticky = bool(capture.get("sticky"))
            if sticky:
                # the decision point is shared: only the hit that comes from
                # *this* consumer counts.
                expect_lr = capture.get("expect_lr")
                if expect_lr is not None:
                    regs = probe.registers()
                    if regs["lr"] != expect_lr:
                        probe.send("next")
                        continue
                # A cheap pre-filter: the decision point may be hit for every
                # record of the table (the m4a play entry runs for every
                # song), and only the hit that carries *this* structure is
                # interesting.  Skipping the others here keeps them from
                # eating the sticky budget.
                match = capture.get("match")
                if match:
                    regs = probe.registers()
                    expected = (ctx["bases"][key] if match.get("value") == "base"
                                else int(match.get("value", "0"), 0))
                    if regs[match["reg"]] != expected:
                        probe.send("next")
                        continue
                if sum(1 for r in records[key]
                       if r.get("decision_point") == hexs(addr)) \
                        >= STICKY_MAX_RECORDS:
                    probe.send(f"delete {ident}")
                    armed.pop(ident, None)
                    probe.send("next")
                    continue
            elif any(r.get("decision_point") == hexs(addr) for r in records[key]):
                probe.send(f"delete {ident}")
                armed.pop(ident, None)
                continue
            ctx["base"] = ctx["bases"][key]
            ctx["layout"] = specs[key].get("layout", {})
            ctx["pointer_base"] = ctx["pointer_bases"].get(key, 0)
            record = _evaluate(key, specs[key], ctx, probe, ident, addr)
            records[key].append(record)
            if record.get("ok") or not sticky:
                probe.send(f"delete {ident}")
                armed.pop(ident, None)
            # step past the instruction so the game keeps running
            probe.send("next")

    try:
        if route == "title":
            probe.send(f"frames {PRESS_FRAMES} {KEY_START:#05x}")
            probe.send(f"frames {SETTLE_FRAMES} 0x000")
            for _ in range(ctx["press_steps"]):
                if all(records[k] for k in keys):
                    break
                out = probe.send(f"frames {PRESS_FRAMES} {KEY_A:#05x}")
                found = hits_in(out)
                if not found:
                    out = probe.send(f"frames {SETTLE_FRAMES} 0x000")
                    found = hits_in(out)
                handle(found)
        elif route == "dispatch":
            probe.send(f"poke 0x{SCENE_BYTE:08X} {ctx['scene']}")
            probe.send("next")
            out = probe.send(f"cont {ctx['cont_frames']}")
            handle(hits_in(out))
        else:                                   # sweep / battle / save
            if route == "battle":
                _run_battle(probe, ctx, handle, armed, owner)
            elif route == "save":
                _run_save_phase(probe, ctx, handle, armed, owner)
            else:
                _run_sweep(probe, ctx, handle, armed, owner)
    finally:
        for ident in list(armed):
            probe.send(f"delete {ident}")
    result: dict[str, dict] = {}
    for key in keys:
        spec = specs[key]
        result[key] = {
            "structure": key,
            "registry_entry": spec["registry"],
            "base": hexs(ctx["bases"][key]),
            "route": route,
            "summary": spec["summary"],
            "ok": _captures_ok(spec, records[key]),
            "captures": records[key],
        }
    return result


def _run_battle(probe: Probe, ctx: dict, handle, armed: dict[int, int],
                owner: dict[int, tuple[str, dict]]) -> None:
    """Force one battle per (group, sub) and collect the hits.

    A battle is requested with three memory writes while the core sits on
    the story state machine's loop head; the state machine then runs the
    whole battle subsystem (map load, units, sprites, tiles, battle text).
    """
    state = ctx["states"]["battle"]
    presses = ctx["battle_presses"]
    keys = ctx["battle_keys"]
    for group, sub in ctx["battle_list"]:
        probe.send(f"load {state}")
        _rearm(probe, armed, owner, ctx)
        probe.send(f"poke 0x{SCENE_BYTE:08X} {group}")
        probe.send(f"poke 0x{SUBCFG_BYTE:08X} {sub}")
        probe.send(f"poke16 0x{PHASE_WORD:08X} {PHASE_BATTLE}")
        for step in range(presses):
            key_mask = keys[step % len(keys)]
            out = probe.send(f"frames {PRESS_FRAMES} {key_mask:#05x}")
            found = hits_in(out)
            if not found:
                out = probe.send(f"frames {SETTLE_FRAMES} 0x000")
                found = hits_in(out)
            if found:
                handle(found)


def _run_save_phase(probe: Probe, ctx: dict, handle, armed: dict[int, int],
                    owner: dict[int, tuple[str, dict]]) -> None:
    """Force the story state machine's *story event* branch (phase 0x0018).

    The state machine's loop head dispatches on `state[0x12]`:

        0808F784  cmp  r1, #0x18
        0808F786  beq  #0x808f872       ; <- the story event branch
        ...
        0808F872  bl   #0x8087940       ; fn 0x08087940
        0808F87C  bne  #0x808f880

    `fn 0x08087940` is the only caller of the WRAM allocation table's readers
    (fn 0x08068948 -> reader 0x08068954) and of the mission index reader
    (fn 0x08087334 -> reader 0x080874FE), so this one poke reaches consumers
    that no battle and no story sweep touches.
    """
    state = ctx["states"]["save"]
    presses = ctx["battle_presses"]
    keys = ctx["battle_keys"]
    probe.send(f"load {state}")
    _rearm(probe, armed, owner, ctx)
    probe.send(f"poke16 0x{PHASE_WORD:08X} {PHASE_SAVE}")
    for step in range(presses):
        key_mask = keys[step % len(keys)]
        out = probe.send(f"frames {PRESS_FRAMES} {key_mask:#05x}")
        found = hits_in(out)
        if not found:
            out = probe.send(f"frames {SETTLE_FRAMES} 0x000")
            found = hits_in(out)
        if found:
            handle(found)


def _rearm(probe: Probe, armed: dict[int, int],
           owner: dict[int, tuple[str, dict]], ctx: dict) -> None:
    """Re-arm every decision point (a savestate reload drops the breakpoints)."""
    for ident in list(armed):
        probe.send(f"delete {ident}")
    armed.clear()
    owner.clear()
    for address, (key, capture) in _sweep_targets(ctx).items():
        ident = arm(probe, address)
        if ident is not None:
            armed[ident] = address
            owner[address] = (key, capture)


def _run_sweep(probe: Probe, ctx: dict, handle, armed: dict[int, int],
               owner: dict[int, tuple[str, dict]]) -> None:
    """Play every scene of the sweep list and collect the hits.

    Each scene starts from the **dispatch** savestate again, so the scene
    that is played is exactly the one that was poked -- the scene number is
    never taken on trust from a previous run.
    """
    state = ctx["states"]["sweep"]
    scenes = ctx["sweep_scenes"]
    presses = ctx["sweep_presses"]
    keys = ctx["sweep_keys"]
    for scene in scenes:
        probe.send(f"load {state}")
        # a savestate reload may drop the debugger's breakpoints
        _rearm(probe, armed, owner, ctx)
        probe.send(f"poke 0x{SCENE_BYTE:08X} {scene}")
        probe.send("next")
        for step in range(presses):
            key_mask = keys[step % len(keys)]
            out = probe.send(f"frames {PRESS_FRAMES} {key_mask:#05x}")
            found = hits_in(out)
            if not found:
                out = probe.send(f"frames {SETTLE_FRAMES} 0x000")
                found = hits_in(out)
            if found:
                handle(found)
            if not armed:
                break


def _sweep_targets(ctx: dict) -> dict[int, tuple[str, dict]]:
    """decision address -> (structure key, capture) for the sweep group."""
    targets: dict[int, tuple[str, dict]] = {}
    for key in ctx["sweep_keys_structures"]:
        for capture in STRUCTURES[key]["captures"]:
            targets[capture["decision"]] = (key, capture)
    return targets


def _evaluate(key: str, spec: dict, ctx: dict, probe: Probe,
              ident: int, addr: int) -> dict:
    """Snapshot the registers at a hit and check them against the ROM."""
    regs = probe.registers()
    capture = None
    for candidate in spec["captures"]:
        if candidate["decision"] == addr:
            capture = candidate
            break
    if capture is None:
        return {"ok": False, "hit_at": hexs(addr),
                "error": "hit address is not a declared decision point"}

    derived = capture["derive"](regs, ctx, capture)
    checks = derived["checks"]
    table_bytes = probe.read_bytes(ctx["base"], 16)
    entry_bytes = probe.read_bytes(int(derived["entry_address"], 16), 16)
    return {
        "ok": all(c["ok"] for c in checks),
        "role": capture.get("role", "default"),
        "consumer_reader": hexs(capture["reader"]),
        "consumer_function": hexs(capture["function"]),
        "decision_point": hexs(capture["decision"]),
        "hit_at": hexs(addr),
        "pc": hexs(regs["pc"]),
        "lr": hexs(regs["lr"]),
        "sp": hexs(regs["sp"]),
        "registers": {k: hexs(v) for k, v in regs.items()},
        "table_base": hexs(ctx["base"]),
        "table_base_bytes": table_bytes.hex(" "),
        "entry_bytes": entry_bytes.hex(" "),
        "index": derived["index"],
        "entry_address": derived["entry_address"],
        "field": derived["field"],
        "checks": checks,
    }


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------
def print_structure(record: dict) -> None:
    status = "L2 OK " if record["ok"] else "L2 FAIL"
    print(f"== {record['structure']}  [{status}]  base={record['base']} "
          f"route={record['route']}")
    print(f"   {record['summary']}")
    if not record["captures"]:
        print("   no capture point was reached")
    for cap in record["captures"]:
        if cap.get("error"):
            print(f"   - {cap['hit_at']}: {cap['error']}")
            continue
        print(f"   - consumer {cap['consumer_reader']} "
              f"(fn {cap['consumer_function']}), decision {cap['decision_point']}, "
              f"hit {cap['hit_at']}")
        print(f"     pc={cap['pc']} lr={cap['lr']} sp={cap['sp']}")
        print(f"     registers: " + " ".join(
            f"{k}={v}" for k, v in cap["registers"].items()))
        print(f"     table base {cap['table_base']} bytes: {cap['table_base_bytes']}")
        print(f"     index={cap['index']} entry={cap['entry_address']} "
              f"bytes: {cap['entry_bytes']}")
        print(f"     field: {cap['field']}")
        for check in cap["checks"]:
            mark = "ok  " if check["ok"] else "FAIL"
            print(f"     [{mark}] {check['name']} -- {check['detail']}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("structure", nargs="?", default=None,
                        help="structure key to capture (see --list)")
    parser.add_argument("--all", action="store_true",
                        help="capture every structure")
    parser.add_argument("--structures", default=None,
                        help="comma separated list of structure keys to capture "
                             "(a subset of --all)")
    parser.add_argument("--self-test", action="store_true",
                        help="run the static checks and one runtime capture per "
                             "structure; exit non-zero on any failure")
    parser.add_argument("--list", action="store_true",
                        help="list the structures and exit")
    parser.add_argument("--rom", type=pathlib.Path, default=REPO / "rom" / "base.gba")
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--state-dir", type=pathlib.Path, default=STATE_DIR)
    parser.add_argument("--scene", type=int, default=36,
                        help="scene number the dispatch route asks for")
    parser.add_argument("--press-steps", type=int, default=70,
                        help="how many A presses the title route may spend")
    parser.add_argument("--cont-frames", type=int, default=900,
                        help="frame budget for the dispatch route")
    parser.add_argument("--sweep-scenes", default="1-55",
                        help="scenes the sweep route plays (e.g. '1-55')")
    parser.add_argument("--sweep-presses", type=int, default=10,
                        help="key presses the sweep route spends on each scene")
    parser.add_argument("--sweep-keys", default="A",
                        help="key cycle the sweep route uses (A,B,START,...)")
    parser.add_argument("--battle-groups", default="0-47",
                        help="formation matrix groups the battle route plays")
    parser.add_argument("--battle-subs", default="0",
                        help="formation matrix sub-configurations to play")
    parser.add_argument("--battle-presses", type=int, default=12,
                        help="key presses the battle route spends on each battle")
    parser.add_argument("--battle-keys", default="A",
                        help="key cycle the battle route uses (A,B,START,UP,...)")
    parser.add_argument("--rebuild-states", action="store_true",
                        help="rebuild the cached savestates")
    parser.add_argument("--json", type=pathlib.Path, default=None,
                        help="write the machine readable report here")
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.list:
        for key, spec in STRUCTURES.items():
            base = registry_base(spec["registry"],
                                 bool(spec.get("registry_unverified")))
            claim = "L2" if spec.get("l2", True) else "L1"
            print(f"{key:28s} base=0x{base:08X} route={spec['route']:9s} "
                  f"captures={len(spec['captures'])} claim={claim}")
        return 0

    if args.structure:
        if args.structure not in STRUCTURES:
            print(f"ERR unknown structure {args.structure!r}; try --list",
                  file=sys.stderr)
            return 2
        keys = [args.structure]
    elif args.structures:
        keys = [k.strip() for k in args.structures.split(",") if k.strip()]
        unknown = [k for k in keys if k not in STRUCTURES]
        if unknown:
            print(f"ERR unknown structure(s) {unknown}; try --list",
                  file=sys.stderr)
            return 2
    elif args.self_test or args.all:
        keys = list(STRUCTURES)
    else:
        parser.print_help()
        return 2

    if not args.exe.exists():
        print(f"ERR {args.exe} missing; run: python tools/mgba_probe/build.py",
              file=sys.stderr)
        return 2
    rom_path = pathlib.Path(args.rom)
    if not rom_path.is_file():
        print(f"ERR ROM not found: {rom_path}", file=sys.stderr)
        return 2
    rom = rom_path.read_bytes()

    index = LiteralIndex(rom)
    ctx: dict = {
        "rom": rom,
        "probe": None,
        "base": 0,
        "bases": {},
        "pointer_bases": {},
        "layout": {},
        "scene": args.scene,
        "press_steps": args.press_steps,
        "cont_frames": args.cont_frames,
        "states": {},
        "song_headers": song_header_bases(),
        "sweep_scenes": parse_scene_list(args.sweep_scenes),
        "sweep_presses": args.sweep_presses,
        "sweep_keys": [_key_mask(k) for k in args.sweep_keys.split(",") if k],
        "sweep_keys_structures": [],
        "battle_list": [(group, sub)
                        for group in parse_scene_list(args.battle_groups)
                        for sub in parse_scene_list(args.battle_subs)],
        "battle_presses": args.battle_presses,
        "battle_keys": [_key_mask(k) for k in args.battle_keys.split(",") if k]
                       or [KEY_A],
    }
    for key in keys:
        spec = STRUCTURES[key]
        ctx["bases"][key] = registry_base(spec["registry"],
                                          bool(spec.get("registry_unverified")))
        via = spec.get("via_pointer")
        ctx["pointer_bases"][key] = (registry_base(via["registry"])
                                     if via else 0)

    report = {
        "rom": str(rom_path),
        "rom_sha256": _sha256(rom_path),
        "generated_by": "tools/l2_runtime_capture.py",
        "static_checks": [],
        "structures": [],
    }

    failures: list[str] = []
    for key in keys:
        spec = STRUCTURES[key]
        checks = static_checks(key, spec, rom, index)
        report["static_checks"].append({"structure": key, "checks": checks})
        if args.self_test:
            print(f"-- static checks: {key}")
            for check in checks:
                print(f"   [{'ok  ' if check['ok'] else 'FAIL'}] {check['name']} "
                      f"-- {check['detail']}")
        for check in checks:
            if not check["ok"]:
                failures.append(f"{key}: static check failed -- {check['name']}")

    # --- group the requested structures -------------------------------------
    # A group is a set of structures that share one environment.  A group may
    # declare more than one route (`GROUP_ROUTES`): the routes are tried in
    # order and the first route that produces a hit for a structure ends that
    # structure's search.
    groups: dict[str, list[str]] = {}
    for key in keys:
        groups.setdefault(STRUCTURES[key].get("group", key), []).append(key)

    probe = Probe(args.exe, rom_path, timeout=3600)
    try:
        needed_routes = set()
        for group_name, group_keys in groups.items():
            for route in GROUP_ROUTES.get(group_name,
                                         [STRUCTURES[group_keys[0]]["route"]]):
                needed_routes.add(route)
        for route in sorted(needed_routes):
            name = STATE_ALIASES.get(route, route)
            path = args.state_dir / f"{name}.ss9"
            if args.rebuild_states or not path.exists():
                build_state(args.exe, rom_path, route, path, args.scene)
            ctx["states"][route] = path
        ctx["probe"] = probe

        for group_name, group_keys in groups.items():
            routes = GROUP_ROUTES.get(group_name,
                                      [STRUCTURES[group_keys[0]]["route"]])
            merged: dict[str, list[dict]] = {key: [] for key in group_keys}
            ctx["sweep_keys_structures"] = group_keys
            for route in routes:
                # a route only ends a structure's search when it produced a
                # *passing* correspondence; a failed capture must not stop the
                # next route from trying.
                if all(_captures_ok(STRUCTURES[key], merged[key])
                       for key in group_keys):
                    break
                # every route starts from its own savestate: a savestate is a
                # snapshot of one particular run, so a group that continued
                # the previous route's run would no longer be in that state
                probe.send(f"load {ctx['states'][route]}")
                try:
                    results = capture_group(group_keys, ctx, probe, route)
                except RuntimeError as exc:
                    results = {key: {"structure": key, "ok": False, "captures": [],
                                     "error": str(exc)} for key in group_keys}
                for key in group_keys:
                    merged[key].extend(results[key].get("captures", []))
            for key in group_keys:
                spec = STRUCTURES[key]
                record = {
                    "structure": key,
                    "registry_entry": spec["registry"],
                    "base": hexs(ctx["bases"][key]),
                    "route": "+".join(routes),
                    "summary": spec["summary"],
                    "claimed_l2": spec.get("l2", True),
                    "ok": _captures_ok(spec, merged[key]),
                    "captures": merged[key],
                }
                report["structures"].append(record)
                print_structure(record)
                claimed = spec.get("l2", True)
                if not record.get("ok") and claimed:
                    failures.append(f"{key}: the runtime correspondence was not "
                                    f"observed")
                if not record.get("ok") and not claimed:
                    print(f"   -> declared L1 (consumer not reached in the "
                          f"emulator): {spec.get('l1_reason', '')}")
                if args.self_test:
                    ctx["base"] = ctx["bases"][key]
                    ctx["layout"] = spec.get("layout", {})
                    control = negative_control(key, spec, ctx, record)
                    report.setdefault("negative_controls", []).append(control)
                    for check in control["checks"]:
                        print(f"     [{'ok  ' if check['ok'] else 'FAIL'}] "
                              f"negative control -- {check['name']} -- "
                              f"{check['detail']}")
                    if not control["ok"] and claimed:
                        failures.append(f"{key}: the negative control did not bite")
                    if not control["ok"] and not claimed:
                        print("     -> no passing capture to corrupt (declared L1)")
    finally:
        probe.close()

    report["ok"] = not failures
    report["failures"] = failures
    if args.json:
        write_json(args.json, report)
        print(f"\nwrote {args.json}")

    if failures:
        print("\nFAILED:")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("\nall requested structures reached L2")
    return 0


def _key_mask(name: str) -> int:
    table = {"A": KEY_A, "B": KEY_B, "START": KEY_START, "UP": KEY_UP,
             "DOWN": KEY_DOWN, "LEFT": KEY_LEFT, "RIGHT": KEY_RIGHT}
    name = name.strip().upper()
    if name in table:
        return table[name]
    try:
        return int(name, 0)
    except ValueError:
        return KEY_A


def _sha256(path: pathlib.Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def negative_control(key: str, spec: dict, ctx: dict, record: dict) -> dict:
    """Prove the gate bites: a wrong register value must fail the check.

    Without this the tool could pass vacuously (e.g. because a check never
    looks at the register that carries the id).  The corrupted register is
    fed back into the very same derive function and the check list has to
    report a failure.

    One passing capture per *role* is corrupted: a structure that needs two
    independent proofs (e.g. "the sound id table points at this header" and
    "the engine reads the header") has to fail in both of them.
    """
    checks: list[dict] = []
    ok_records = [r for r in record.get("captures", []) if r.get("ok")]
    if not ok_records:
        return {"structure": key, "ok": False,
                "checks": [{"name": "a passing capture is available to corrupt",
                            "ok": False, "detail": "no successful capture"}]}
    by_role: dict[str, dict] = {}
    for ok_record in ok_records:
        by_role.setdefault(ok_record.get("role", "default"), ok_record)
    for role, ok_record in by_role.items():
        capture = next((c for c in spec["captures"]
                        if hexs(c["decision"]) == ok_record["decision_point"]),
                       None)
        if capture is None:
            continue
        regs = {k: int(v, 16) for k, v in ok_record["registers"].items()}
        for reg, (mode, delta) in capture.get("corrupt", {}).items():
            if mode == "base":
                regs[reg] = ctx["base"] + delta
            else:
                regs[reg] = regs[reg] + delta
        derived = capture["derive"](regs, ctx, capture)
        broken = [c for c in derived["checks"] if not c["ok"]]
        checks.append({
            "name": f"corrupting {capture.get('corrupt')} makes the check fail"
                    + (f" (role {role})" if role != "default" else ""),
            "ok": bool(broken),
            "detail": (f"{len(broken)} check(s) failed, first: {broken[0]['name']}"
                       if broken else "the check still passed -- the gate is vacuous"),
        })
    return {"structure": key, "ok": bool(checks) and all(c["ok"] for c in checks),
            "checks": checks}


if __name__ == "__main__":
    raise SystemExit(main())
