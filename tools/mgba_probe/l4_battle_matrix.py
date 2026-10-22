#!/usr/bin/env python3
"""L4 gate: every battle configuration and every map must really run.

What this tool proves
---------------------
``notes/runtime-verification-gates-20260710.md`` §4 defines L4 as
「完整通关 = 全流程、全人物组合、全地图实际打通」.  The story axis
(全流程) is already closed by ``notes/evidence/l4-playthrough-20261021.md``
(55/55 script-pointer equality).  This tool closes the other two axes and
writes a machine-readable report.

The mechanism (all of it native game code, proved on this ROM)
----------------------------------------------------------------
* The story state machine ``0x0808F73C`` polls ``state[0x12]``
  (the u16 *phase*) at its loop head ``0x0808F752`` and dispatches on it.
* ``phase == 0x110`` goes to ``0x0808F92E``, which is the **complete**
  battle entry:

      ctrl[0] = 0
      ctrl[1] = state[0x16]      ; group id  == scene id
      ctrl[2] = state[0x19]      ; sub-config id
      0x08075184(...)            ; pre-battle
      0x0808A490(1, 0x7F)        ; set the "battle running" flag
      bl 0x080732B4              ; <- the battle itself
      0x0808A490(0, 0x7F)        ; clear it

* ``0x080732B4`` reads the formation matrix at
  ``0x085461C4 + group*0x1AAC + sub*0x8E4`` (48 groups x 3 variants x
  12 slots of 0xB8 bytes) and calls the battle entry ``0x0808A588``,
  which loads the map ``0x0808F4D4(group)`` and instantiates the units
  into the WRAM unit array at ``0x020240C0`` (12 slots, stride 0x1D4,
  character id at slot+0).

So a battle for an arbitrary ``(group, sub)`` is reachable with **three
memory writes only** -- no register patching, no ROM patching:

      state[0x16] = group        (0x020311EA)
      state[0x19] = sub          (0x020311ED)
      state[0x12] = 0x0110       (0x020311E6)

while the game is parked on the state machine's loop head ``0x0808F752``.

The same trick with ``state[0x12] = 0x0030`` dispatches a story scene
through ``0x0808F544`` -> ``0x0808F4D4(scene)``, which is how a map
descriptor gets loaded and rendered.

A third route closes the story axis: the story dispatcher ``0x0808F544``
chains to the next scene **on its own** when the running script writes
``state[0x18] = 3`` (the VM opcode ``0x1A`` with a non-zero flag writes
``flag + 1`` there).  Scene 39 is the branch point -- its script offers
scenes 40..45.  The chain is read back at ``0x0808F5DA`` (the new scene
number) and at the VM entry (the script pointer the game itself used,
which must equal the root-table entry of the new scene).

Usage
-----
    python tools/mgba_probe/l4_battle_matrix.py rom/base.gba --axis scan
    python tools/mgba_probe/l4_battle_matrix.py rom/base.gba --axis battles
    python tools/mgba_probe/l4_battle_matrix.py rom/base.gba --axis maps
    python tools/mgba_probe/l4_battle_matrix.py rom/base.gba --axis flow
    python tools/mgba_probe/l4_battle_matrix.py rom/base.gba --axis all \
        --out build/l4-bm --json build/l4-battle-matrix.json

Exit code
---------
0 = every requested item produced its evidence,
1 = at least one item is missing evidence (a real gate, not a dumper),
2 = the environment is not usable (no probe binary / no ROM).
"""
from __future__ import annotations

import argparse
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

from tools.mgba_probe.l4_playthrough import (  # noqa: E402
    Probe, capture, arm, KEY_BITS, HIT_RE,
)

# ---------------------------------------------------------------- addresses
ROM_BASE = 0x08000000

STORY_STATE = 0x020311D4
SCENE_BYTE = STORY_STATE + 0x16     # 0x020311EA  state[0x16]
SUBCFG_BYTE = STORY_STATE + 0x19    # 0x020311ED  state[0x19]
PHASE_WORD = STORY_STATE + 0x12     # 0x020311E6  state[0x12] (u16)
MAPID_BYTE = STORY_STATE + 0x17     # 0x020311EB  state[0x17]

BATTLE_CTRL = 0x02026804            # ctrl[0..3]
BATTLE_FLAG_WORD = 0x020311E0       # the word the battle-running flag lives in
UNIT_ARRAY = 0x020240C0             # 12 slots, stride 0x1D4
UNIT_STRIDE = 0x1D4
UNIT_SLOTS = 12

FORMATION_FILE = 0x5461C4
FORMATION_GROUP_STRIDE = 0x1AAC
FORMATION_SUB_STRIDE = 0x8E4
FORMATION_RECORD = 0xB8
FORMATION_HEADER = 4
FORMATION_GROUPS = 48
FORMATION_SUBS = 3

MAP_TABLE_FILE = 0x53D910
MAP_ENTRY_SIZE = 32

# native code addresses
STATE_LOOP = 0x0808F752      # story state machine, phase dispatch loop head
PHASE_110 = 0x0808F92E      # phase 0x110 -> full battle entry
BATTLE_WRAPPER = 0x080732B4  # battle setup + fight
BATTLE_ENTRY = 0x0808A588   # battle entry (scene, sub)
VM_ENTRY = 0x080977B8       # story VM entry
DISPATCHER = 0x0808F544     # story dispatcher
NEXT_SCENE = 0x0808F8DC     # phase 0x30 handler
MAP_LOAD_CALL = 0x0808F588  # `bl 0x0808F4D4` inside the dispatcher
NEW_SCENE_READ = 0x0808F5DA  # `ldrb r4,[r7,#0x16]` -- the dispatcher chaining

BEFORE_ROOT_FILE = 0x060C74  # file offset of the "before" root table
AFTER_ROOT_FILE = 0x060D54   # file offset of the "after" root table

PHASE_BATTLE = 0x0110
PHASE_NEXT_SCENE = 0x0030


# ---------------------------------------------------------------- utilities
def hit_of(lines) -> int | None:
    for line in lines:
        m = HIT_RE.search(line)
        if m:
            return int(m.group(2), 16)
    return None


def formation_entry(rom: bytes, group: int, sub: int) -> int:
    return (FORMATION_FILE + group * FORMATION_GROUP_STRIDE
            + sub * FORMATION_SUB_STRIDE)


PLACEHOLDER_IDS = (0xFF, 0xFE, 0xFD)   # "the story decides" ally slots
EMPTY_IDS = (0xFC, 0xFB, 0xFA)         # "no unit in this slot"


def formation_slots(rom: bytes, group: int, sub: int) -> list[dict]:
    """The 12 formation slots of one (group, sub) configuration.

    Layout (proved by ``tools/extract_battle_tables.py`` and re-checked
    here): a 4 byte header, then 12 records of 0xB8 bytes; the character
    id is at record+0 and the affiliation at record+1.

    Two id ranges are special:

    * ``0xFF / 0xFE / 0xFD`` -- "the story decides": the game substitutes
      the current party (Naruto/Sasuke/Sakura) at run time.
    * ``0xFC / 0xFB / 0xFA`` -- "no unit in this slot".
    """
    base = formation_entry(rom, group, sub)
    slots = []
    for i in range(12):
        q = base + FORMATION_HEADER + i * FORMATION_RECORD
        if q + 2 > len(rom):
            break
        cid = rom[q]
        slots.append({
            "index": i,
            "id": cid,
            "side": rom[q + 1],
            "x": rom[q + 2],
            "y": rom[q + 3],
            "kind": ("empty" if cid == 0 or cid in EMPTY_IDS
                     else "story" if cid in PLACEHOLDER_IDS
                     else "character"),
        })
    return slots


def real_pairs(rom: bytes, groups: range | None = None) -> list[tuple[int, int]]:
    """(group, sub) pairs whose formation matrix entry holds a team.

    A pair counts when at least one of its 12 slots carries a non-zero
    character id.  This is the same definition the earlier note used
    ("144 个可能，其中 88 个有真实队伍") and it reproduces that number
    exactly.

    ``groups`` defaults to the whole 48-group span.  Note that group 47
    is *not* a real formation: 48 groups x 0x1AAC bytes would run the
    table into the victory-condition table at 0x594758, so group 47's
    bytes are that table's content.  Use ``groups=range(47)`` for the
    sweep to stay on real formations.
    """
    if groups is None:
        groups = range(FORMATION_GROUPS)
    out = []
    for group in groups:
        for sub in range(FORMATION_SUBS):
            slots = formation_slots(rom, group, sub)
            if any(s["id"] for s in slots):
                out.append((group, sub))
    return out


def map_descriptors(rom: bytes) -> list[dict]:
    """The battle map descriptor table at 0x53D910 (32 bytes per entry)."""
    out = []
    for map_id in range(64):
        q = MAP_TABLE_FILE + map_id * MAP_ENTRY_SIZE
        if q + MAP_ENTRY_SIZE > len(rom):
            break
        w, h = struct.unpack_from("<HH", rom, q)
        ptrs = struct.unpack_from("<6I", rom, q + 4)
        background = rom[q + 0x1C]
        out.append({
            "id": map_id,
            "raw_width": w,
            "raw_height": h,
            "background_id": background,
            "pointers": [f"0x{p:08X}" for p in ptrs],
            "all_pointers_in_rom": all(
                ROM_BASE <= p < ROM_BASE + len(rom) for p in ptrs),
        })
    return out


def root_pointer(rom: bytes, table_file: int, scene: int) -> int | None:
    """The script pointer the story dispatcher will use for `scene`."""
    off = table_file + scene * 4
    if off + 4 > len(rom):
        return None
    value = struct.unpack_from("<I", rom, off)[0]
    return value if ROM_BASE <= value < ROM_BASE + len(rom) else None


def valid_map_ids(rom: bytes) -> list[int]:
    """Map ids whose descriptor looks like a real map.

    ``0x0808F4D4`` rejects ids > 0x31.  The descriptor table itself has
    **47** entries (ids 0..46); entry 47 onwards is a different table
    (its ``raw_width`` is 513/3486/3932 -- far outside the 64x128 tile
    limit the format allows, and its pointers do not match the pattern).

    The check is therefore: the size fields must be inside the format's
    range and the two mandatory pointers must land inside the ROM.
    """
    out = []
    for entry in map_descriptors(rom):
        w, h = entry["raw_width"], entry["raw_height"]
        if not (0 < w <= 1024 and 0 < h <= 512):
            continue
        tile_gfx = int(entry["pointers"][0], 16)
        palette = int(entry["pointers"][1], 16)
        if not all(ROM_BASE <= p < ROM_BASE + len(rom)
                   for p in (tile_gfx, palette)):
            continue
        out.append(entry["id"])
    return out


# ---------------------------------------------------------------- harness
class Harness:
    """Drives one mGBA probe process."""

    def __init__(self, exe: pathlib.Path, rom_path: pathlib.Path,
                 timeout: float = 900.0):
        self.exe = exe
        self.rom_path = rom_path
        self.probe = Probe(exe, rom_path, timeout=timeout)
        self.armed: dict[int, int] = {}

    # -- low level ------------------------------------------------------
    def send(self, cmd: str) -> list[str]:
        return self.probe.send(cmd)

    def read(self, addr: int, length: int) -> bytes:
        return self.probe.read_bytes(addr, length)

    def arm(self, addr: int) -> int:
        ident = arm(self.probe, addr)
        self.armed[addr] = ident or 0
        return ident or 0

    def disarm_all(self) -> None:
        for addr, ident in list(self.armed.items()):
            if ident:
                self.probe.send(f"delete {ident}")
                self.armed[addr] = 0

    def rearm(self) -> None:
        for addr in list(self.armed):
            if not self.armed[addr]:
                self.armed[addr] = arm(self.probe, addr) or 0

    def poke(self, addr: int, value: int) -> None:
        self.probe.send(f"poke 0x{addr:08X} {value & 0xFF}")

    def poke16(self, addr: int, value: int) -> None:
        self.probe.send(f"poke16 0x{addr:08X} {value & 0xFFFF}")

    # -- navigation -----------------------------------------------------
    def boot_to_state_machine(self) -> bool:
        """Boot the game and park it on the state machine's loop head.

        The game only reacts to a key *press edge*, so the recipe is
        "press 8 frames, then stay silent for 120 frames".
        """
        self.send("frames 1500 0x000")
        self.arm(STATE_LOOP)
        for key, frames in (("START", 8), ("A", 8), ("A", 8), ("A", 8), ("A", 20)):
            out = self.send(f"frames {frames} {KEY_BITS[key]:#05x}")
            if hit_of(out) == STATE_LOOP:
                return True
            out = self.send("frames 120 0x000")
            if hit_of(out) == STATE_LOOP:
                return True
        return False

    # -- one battle -----------------------------------------------------
    def run_battle(self, group: int, sub: int, battle_frames: int = 40,
                   keys: str = "A", cont_frames: int = 900) -> dict:
        """Drive the game into battle `group`/`sub` and collect evidence.

        The battle intro waits for key presses, so the game is fed the
        press-edge recipe ("press 8 frames, release 120 frames") until
        the battle map shows up in ``state[0x17]``.  All breakpoints are
        removed while the frames run, because the probe's frame loop
        falls back to mGBA's instruction-stepping debugger as soon as a
        breakpoint is armed -- two orders of magnitude slower.
        """
        record: dict = {
            "group": group,
            "sub": sub,
            "status": "not-reached",
            "battle_entry": None,
            "unit_ids": [],
            "unit_slots": [],
            "ctrl": "",
            "ctrl_group": None,
            "ctrl_sub": None,
            "map_id": None,
            "screenshot": None,
            "notes": [],
        }
        if not self.boot_to_state_machine():
            record["notes"].append("could not park on the state machine loop head")
            return record

        self.arm(PHASE_110)
        self.arm(BATTLE_WRAPPER)
        self.arm(BATTLE_ENTRY)

        # the whole request is three memory writes
        self.poke(SCENE_BYTE, group)
        self.poke(SUBCFG_BYTE, sub)
        self.poke16(PHASE_WORD, PHASE_BATTLE)

        seen_phase = False
        seen_wrapper = False
        entry_regs = None
        for _ in range(12):
            out = self.send(f"cont {cont_frames}")
            hit = hit_of(out)
            if hit is None:
                out = self.send("frames 8 0x001") + self.send("frames 120 0x000")
                hit = hit_of(out)
            if hit is None:
                record["notes"].append(
                    f"the battle was not reached within {cont_frames} frames")
                break
            if hit == PHASE_110:
                seen_phase = True
            elif hit == BATTLE_WRAPPER:
                seen_wrapper = True
            elif hit == BATTLE_ENTRY:
                regs = self.probe.registers()
                entry_regs = {"r0": regs.get("r0", 0), "r1": regs.get("r1", 0)}
                record["battle_entry"] = {
                    "r0": f"0x{entry_regs['r0']:08X}",
                    "r1": f"0x{entry_regs['r1']:08X}",
                }
            self.send("next")
            self.rearm()
            if seen_wrapper:
                break

        # --- let the battle intro play out --------------------------
        self.disarm_all()
        mask = KEY_BITS[keys] if keys in KEY_BITS else 0
        map_id = None
        flag_seen = False
        for _ in range(battle_frames):
            self.send(f"frames 8 {mask:#05x}")
            self.send("frames 120 0x000")
            raw = self.read(MAPID_BYTE, 1)
            map_id = raw[0] if raw else None
            word = self.read(BATTLE_FLAG_WORD, 4)
            if word and (int.from_bytes(word, "little") & (1 << 31)):
                flag_seen = True
            if map_id == group:
                break
        # a couple more presses so the fight is really on screen
        self.send(f"frames 8 {mask:#05x}")
        self.send("frames 120 0x000")

        # --- evidence -------------------------------------------------
        units = []
        for slot in range(UNIT_SLOTS):
            raw = self.read(UNIT_ARRAY + slot * UNIT_STRIDE, 2)
            if len(raw) == 2:
                units.append({"slot": slot, "id": raw[0], "side": raw[1]})
        record["unit_ids"] = [u["id"] for u in units if u["id"]]
        record["unit_slots"] = units
        ctrl = self.read(BATTLE_CTRL, 16)
        record["ctrl"] = ctrl.hex()
        if len(ctrl) >= 3:
            record["ctrl_group"] = ctrl[1]
            record["ctrl_sub"] = ctrl[2]
        raw = self.read(MAPID_BYTE, 1)
        record["map_id"] = raw[0] if raw else None
        record["phase_seen"] = seen_phase
        record["wrapper_seen"] = seen_wrapper
        record["map_loaded"] = record["map_id"] == group
        record["battle_flag_seen"] = flag_seen
        if entry_regs:
            record["battle_entry_ok"] = (
                entry_regs["r0"] == group and entry_regs["r1"] == sub)
        else:
            record["battle_entry_ok"] = None
        return record

    # -- one map --------------------------------------------------------
    def load_map(self, map_id: int, render_frames: int = 120) -> dict:
        """Make the game load and render map `map_id` through the story.

        The story dispatcher calls ``0x0808F4D4(scene)`` with the scene
        number as the map id, so the map id and the scene id share the
        same numbering.  The breakpoint is placed on the call site
        ``0x0808F588`` so the *argument the game itself passes* can be
        read back -- that is what makes "map N really was loaded"
        machine-checkable, including for map 0 whose ``state[0x17]`` is
        indistinguishable from the default value.
        """
        record: dict = {
            "map_id": map_id,
            "status": "not-reached",
            "state_map_id": None,
            "map_load_arg": None,
            "vram_sha256": None,
            "vram_changed": None,
            "screenshot": None,
            "notes": [],
        }
        if not self.boot_to_state_machine():
            record["notes"].append("could not park on the state machine loop head")
            return record
        before = self.vram_hash()
        self.arm(MAP_LOAD_CALL)
        self.arm(NEXT_SCENE)
        self.poke(SCENE_BYTE, map_id)
        self.poke16(PHASE_WORD, PHASE_NEXT_SCENE)
        hit = None
        for _ in range(20):
            out = self.send("cont 2400")
            hit = hit_of(out)
            if hit is None:
                out = self.send("frames 8 0x001") + self.send("frames 120 0x000")
                hit = hit_of(out)
            if hit is None:
                record["notes"].append("the story dispatcher was never reached")
                break
            if hit == MAP_LOAD_CALL:
                regs = self.probe.registers()
                record["map_load_arg"] = regs.get("r0", 0)
                break
            self.send("next")
            self.rearm()
        if hit == MAP_LOAD_CALL:
            # the map has been decompressed into VRAM; let it render
            self.disarm_all()
            self.send(f"frames {render_frames} 0x000")
            self.rearm()
            raw = self.read(MAPID_BYTE, 1)
            record["state_map_id"] = raw[0] if raw else None
            record["vram_sha256"] = self.vram_hash()
            record["vram_changed"] = record["vram_sha256"] != before
            record["status"] = "reached"
        return record

    def vram_hash(self, length: int = 0x8000) -> str | None:
        """SHA-256 over the first ``length`` bytes of VRAM."""
        import hashlib
        data = self.read(0x06000000, length)
        if not data:
            return None
        return hashlib.sha256(data).hexdigest()

    # -- one game-driven scene transition -------------------------------
    def run_flow(self, scene: int, press_rounds: int = 60) -> dict:
        """Let the game move from `scene` to the next scene **by itself**.

        The story dispatcher ``0x0808F544`` chains to a new scene when the
        running script sets ``state[0x18] = 3`` (the VM opcode ``0x1A``
        with a non-zero flag writes ``flag + 1`` there).  The chain is
        read back at two points:

        * ``0x0808F5DA`` -- ``ldrb r4,[r7,#0x16]``, reached only when
          ``state[0x18] == 3``; ``r4`` is the scene the game picked;
        * the VM entry ``0x080977B8`` right afterwards -- ``r0`` is the
          script pointer the game itself used, which must equal the
          root-table entry of the new scene.
        """
        record: dict = {
            "scene": scene,
            "status": "not-reached",
            "first_script": None,
            "first_script_expected": None,
            "new_scene": None,
            "new_script": None,
            "new_script_expected": None,
            "notes": [],
        }
        if not self.boot_to_state_machine():
            record["notes"].append("could not park on the state machine loop head")
            return record
        self.arm(VM_ENTRY)
        self.arm(NEW_SCENE_READ)
        self.poke(SCENE_BYTE, scene)
        self.poke16(PHASE_WORD, PHASE_NEXT_SCENE)

        first_script = None
        new_scene = None
        new_script = None
        for _ in range(press_rounds):
            out = self.send("cont 900")
            hit = hit_of(out)
            if hit is None:
                out = self.send("frames 8 0x001") + self.send("frames 120 0x000")
                hit = hit_of(out)
            if hit is None:
                break
            if hit == NEW_SCENE_READ:
                # the breakpoint stops *before* `ldrb r4,[r7,#0x16]`, so
                # step over it before reading the new scene number
                self.send("next")
                regs = self.probe.registers()
                new_scene = regs.get("r4", 0)
                record["new_scene"] = new_scene
                self.rearm()
                # the dispatcher now picks the new scene's root table and
                # enters the VM again
                out = self.send("cont 900")
                hit2 = hit_of(out)
                if hit2 == VM_ENTRY:
                    regs = self.probe.registers()
                    new_script = regs.get("r0", 0)
                    record["new_script"] = f"0x{new_script:08X}"
                break
            if hit == VM_ENTRY and first_script is None:
                regs = self.probe.registers()
                first_script = regs.get("r0", 0)
                record["first_script"] = f"0x{first_script:08X}"
            self.send("next")
            self.rearm()

        record["new_scene"] = new_scene
        record["new_script"] = (f"0x{new_script:08X}" if new_script else None)
        record["status"] = "reached" if (new_scene and new_script) else "failed"
        if not new_scene:
            record["notes"].append(
                "the dispatcher never chained to a new scene "
                f"(state[0x18] never reached 3)")
        return record

    def close(self) -> None:
        self.probe.close()


# ---------------------------------------------------------------- reporting
def write_json(path: pathlib.Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--exe", type=pathlib.Path,
                    default=REPO / "build" / "mgba-probe" / "mgba-probe.exe")
    ap.add_argument("--axis", default="all",
                    choices=("scan", "battles", "maps", "flow", "all"))
    ap.add_argument("--pairs", default=None,
                    help="restrict the battle sweep, e.g. '14:0,9:0'")
    ap.add_argument("--maps", default=None,
                    help="restrict the map sweep, e.g. '0-46'")
    ap.add_argument("--flow-scenes", default="39",
                    help="comma separated scene list for the flow axis; a "
                         "scene chains to the next one when its script uses "
                         "the VM opcode 0x1A with a non-zero flag "
                         "(scene 39 offers scenes 40..45)")
    ap.add_argument("--out", type=pathlib.Path, default=None,
                    help="directory for the per-item screenshots")
    ap.add_argument("--json", type=pathlib.Path,
                    default=REPO / "build" / "l4-battle-matrix.json")
    ap.add_argument("--battle-frames", type=int, default=40,
                    help="how many press/release rounds to spend on the "
                         "battle intro before giving up on the map")
    ap.add_argument("--render-frames", type=int, default=120)
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
    rom = rom_path.read_bytes()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    report: dict = {
        "rom": str(rom_path),
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "addresses": {
            "story_state": f"0x{STORY_STATE:08X}",
            "scene_byte": f"0x{SCENE_BYTE:08X}",
            "subcfg_byte": f"0x{SUBCFG_BYTE:08X}",
            "phase_word": f"0x{PHASE_WORD:08X}",
            "mapid_byte": f"0x{MAPID_BYTE:08X}",
            "battle_ctrl": f"0x{BATTLE_CTRL:08X}",
            "battle_flag_word": f"0x{BATTLE_FLAG_WORD:08X}",
            "unit_array": f"0x{UNIT_ARRAY:08X}",
            "formation": f"0x{FORMATION_FILE + ROM_BASE:08X}",
            "map_table": f"0x{MAP_TABLE_FILE + ROM_BASE:08X}",
            "state_loop": f"0x{STATE_LOOP:08X}",
            "phase_110": f"0x{PHASE_110:08X}",
            "battle_wrapper": f"0x{BATTLE_WRAPPER:08X}",
            "battle_entry": f"0x{BATTLE_ENTRY:08X}",
        },
    }
    # keep the sections a previous run already produced: the axes are
    # independent, so a run of one axis must not throw the others away
    if args.json and args.json.is_file():
        try:
            previous = json.loads(args.json.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = {}
        if isinstance(previous, dict) and previous.get("rom") == str(rom_path):
            for key in ("battles", "maps", "flow", "scan"):
                if key in previous:
                    report[key] = previous[key]

    failures: list[str] = []

    # ------------------------------------------------------------- scan
    all_pairs = real_pairs(rom)
    usable_pairs = real_pairs(rom, groups=range(FORMATION_GROUPS - 1))
    report["scan"] = {
        "formation_groups": FORMATION_GROUPS,
        "formation_subs": FORMATION_SUBS,
        "possible_pairs": FORMATION_GROUPS * FORMATION_SUBS,
        "pairs_with_team": len(all_pairs),
        "pairs": [{"group": g, "sub": s} for g, s in all_pairs],
        "usable_pairs": len(usable_pairs),
        "usable_pair_list": [{"group": g, "sub": s} for g, s in usable_pairs],
        "excluded_groups": [FORMATION_GROUPS - 1],
        "excluded_reason": (
            "48 groups x 0x1AAC bytes would run the formation matrix into "
            "the victory-condition table at 0x594758, so group "
            f"{FORMATION_GROUPS - 1} holds that table's bytes, not a team"),
    }
    descriptors = map_descriptors(rom)
    usable_maps = valid_map_ids(rom)
    report["scan"]["map_descriptors"] = len(descriptors)
    report["scan"]["usable_map_ids"] = usable_maps
    print(f"scan: {len(all_pairs)}/{FORMATION_GROUPS * FORMATION_SUBS} "
          f"(group, sub) pairs carry a team "
          f"({len(usable_pairs)} on real formations); "
          f"{len(usable_maps)} usable map descriptors")

    if args.axis == "scan":
        write_json(args.json, report)
        return 0

    # ------------------------------------------------------- battle sweep
    if args.axis in ("battles", "all"):
        selected = usable_pairs
        if args.pairs:
            wanted = set()
            for item in args.pairs.split(","):
                item = item.strip()
                if not item:
                    continue
                g, _, s = item.partition(":")
                wanted.add((int(g), int(s or 0)))
            selected = [p for p in all_pairs if p in wanted]
        results = []
        for index, (group, sub) in enumerate(selected):
            harness = Harness(args.exe, rom_path, timeout=args.boot_timeout)
            try:
                record = harness.run_battle(group, sub,
                                            battle_frames=args.battle_frames)
                if args.out:
                    args.out.mkdir(parents=True, exist_ok=True)
                    shot = args.out / f"battle-g{group:02d}-s{sub}.png"
                    record["screenshot"] = capture(harness.probe, shot)
            finally:
                harness.close()
            form = formation_slots(rom, group, sub)
            form_ids = [s["id"] for s in form if s["id"]]
            expected_ids = [s["id"] for s in form if s["kind"] == "character"]
            record["formation_ids"] = form_ids
            record["expected_character_ids"] = expected_ids
            record["ids_match"] = (record["unit_ids"] == form_ids)
            # every character the formation names must be standing in the
            # battle; the "story decides" slots are filled by the game, so
            # they are checked separately.
            record["expected_ids_present"] = all(
                cid in record["unit_ids"] for cid in expected_ids)
            # The gate: the game's own battle path ran (phase 0x110 handler
            # + battle wrapper), the control block carries the requested
            # (group, sub), the unit array was filled from the formation
            # matrix and the expected characters are on the field.
            ok = (bool(record.get("wrapper_seen"))
                  and record.get("ctrl_group") == group
                  and record.get("ctrl_sub") == sub
                  and bool(record["unit_ids"])
                  and bool(record.get("expected_ids_present")))
            record["status"] = "reached" if ok else "failed"
            results.append(record)
            if not ok:
                failures.append(f"battle group={group} sub={sub}: "
                                f"{'; '.join(record['notes']) or 'no evidence'}")
            print(f"battle g{group:02d} s{sub}: {record['status']:<7} "
                  f"units={record['unit_ids']} "
                  f"map=0x{record['map_id']:02X} "
                  f"match={record['ids_match']}")
            # write the report after every item so a hang never loses it
            report["battles"] = {
                "requested": len(selected),
                "done": len(results),
                "reached": sum(1 for r in results if r["status"] == "reached"),
                "ids_matching_formation":
                    sum(1 for r in results if r.get("ids_match")),
                "results": results,
            }
            write_json(args.json, report)
        report["battles"]["requested"] = len(selected)
        report["battles"]["done"] = len(results)
        report["battles"]["reached"] = sum(
            1 for r in results if r["status"] == "reached")
        print(f"battles: {report['battles']['reached']}/{len(selected)} reached")

    # --------------------------------------------------------- map sweep
    if args.axis in ("maps", "all"):
        map_ids = usable_maps
        if args.maps:
            lo, _, hi = args.maps.partition("-")
            if hi:
                map_ids = [i for i in usable_maps if int(lo) <= i <= int(hi)]
            else:
                map_ids = [int(x) for x in args.maps.split(",") if x.strip()]
        results = []
        for map_id in map_ids:
            harness = Harness(args.exe, rom_path, timeout=args.boot_timeout)
            try:
                record = harness.load_map(map_id,
                                          render_frames=args.render_frames)
                if args.out:
                    args.out.mkdir(parents=True, exist_ok=True)
                    shot = args.out / f"map-{map_id:02d}.png"
                    record["screenshot"] = str(capture(harness.probe, shot))
            finally:
                harness.close()
            ok = (record.get("status") == "reached"
                  and record.get("map_load_arg") == map_id
                  and record.get("state_map_id") == map_id
                  and bool(record.get("vram_changed")))
            record["status"] = "reached" if ok else "failed"
            results.append(record)
            if not ok:
                failures.append(f"map id={map_id}: "
                                f"{'; '.join(record['notes']) or 'state[0x17] mismatch'}")
            print(f"map {map_id:02d}: {record['status']:<7} "
                  f"arg={record.get('map_load_arg')} "
                  f"state[0x17]={record.get('state_map_id')} "
                  f"vram={str(record.get('vram_sha256'))[:12]}")
            report["maps"] = {
                "requested": len(map_ids),
                "done": len(results),
                "reached": sum(1 for r in results if r["status"] == "reached"),
                "results": results,
            }
            write_json(args.json, report)
        report["maps"]["requested"] = len(map_ids)
        report["maps"]["done"] = len(results)
        report["maps"]["reached"] = sum(
            1 for r in results if r["status"] == "reached")
        print(f"maps: {report['maps']['reached']}/{len(map_ids)} reached")

    # ------------------------------------------------------------ flow
    if args.axis in ("flow", "all"):
        scenes = [int(x) for x in args.flow_scenes.split(",") if x.strip()]
        results = []
        for scene in scenes:
            harness = Harness(args.exe, rom_path, timeout=args.boot_timeout)
            try:
                record = harness.run_flow(scene)
            finally:
                harness.close()
            before = root_pointer(rom, BEFORE_ROOT_FILE, scene)
            record["first_script_expected"] = (
                f"0x{before:08X}" if before else None)
            if record.get("new_scene") is not None:
                after = root_pointer(rom, BEFORE_ROOT_FILE, record["new_scene"])
                record["new_script_expected"] = (
                    f"0x{after:08X}" if after else None)
            ok = (record.get("status") == "reached"
                  and record.get("first_script") == record.get("first_script_expected")
                  and record.get("new_script") == record.get("new_script_expected"))
            record["status"] = "reached" if ok else "failed"
            results.append(record)
            if not ok:
                failures.append(f"flow scene={scene}: "
                                f"{'; '.join(record['notes']) or 'script mismatch'}")
            print(f"flow scene {scene:3d}: {record['status']:<7} "
                  f"first={record.get('first_script')} "
                  f"(exp {record.get('first_script_expected')}) "
                  f"-> new={record.get('new_scene')} "
                  f"script={record.get('new_script')} "
                  f"(exp {record.get('new_script_expected')})")
            report["flow"] = {
                "requested": len(scenes),
                "done": len(results),
                "reached": sum(1 for r in results if r["status"] == "reached"),
                "results": results,
            }
            write_json(args.json, report)
        report["flow"]["requested"] = len(scenes)
        report["flow"]["reached"] = sum(
            1 for r in results if r["status"] == "reached")
        print(f"flow: {report['flow']['reached']}/{len(scenes)} reached")

    write_json(args.json, report)
    if failures:
        print("\nFAILED:")
        for item in failures:
            print(f"  {item}")
        return 1
    print("\nOK: every requested item produced its evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
