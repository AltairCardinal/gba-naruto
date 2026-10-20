#!/usr/bin/env python3
"""Self-check for every ROM write-back path this repository owns.

The write-back model is the repository-wide one: **copy a native entry, then
overwrite only the fields whose meaning is known**; unknown bytes are copied
raw.  A write-back path counts as usable only when a tool can

1. read a native entry out of the ROM,
2. apply an author-supplied change to it, and
3. read the result back and assert that it equals the author input.

This script does exactly that, once per structure, on a **copy** of the ROM
(``rom/base.gba`` is never modified).  For every structure it prints the
author input and the read-back value, and it fails (non-zero exit) when they
differ, when an unknown byte moved, or when a write-back path raises.

Usage:
    python tools/writeback_paths.py rom/base.gba
    python tools/writeback_paths.py rom/base.gba --json build/writeback-paths.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, Callable

ROOT = pathlib.Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import import_audio_song as ias  # noqa: E402
import import_battle_config as ibc  # noqa: E402
import import_character_template as ict  # noqa: E402
import import_reward as irr  # noqa: E402
import import_sprite_action as isa  # noqa: E402
import import_story_script as iss  # noqa: E402
from tools.lib.io import write_json  # noqa: E402


class Case:
    """One write-back path exercised end to end."""

    def __init__(self, key: str, rom: str, title: str,
                 run: Callable[[bytes], dict[str, Any]]):
        self.key = key
        self.rom = rom
        self.title = title
        self.run = run


def _mismatch(label: str, author: Any, read_back: Any) -> str:
    if author == read_back:
        return ""
    return f"{label}: author={author!r} read_back={read_back!r}"


def _untouched_diff(native: bytes, patched: bytes, touched: set[int]) -> list[str]:
    out = []
    for i in range(min(len(native), len(patched))):
        if i in touched:
            continue
        if native[i] != patched[i]:
            out.append(f"unknown byte 0x{i:X} changed "
                       f"0x{native[i]:02X} -> 0x{patched[i]:02X}")
    return out


def _donor(native_value: Any, candidates: list[Any]) -> Any:
    """First candidate that differs from the native value.

    A write-back that writes the value that is already there would make the
    round-trip assertion vacuous, so every case has to change something.
    """
    for candidate in candidates:
        if candidate != native_value:
            return candidate
    raise AssertionError("no distinct donor value available")


# --- character template (0x54241C) -----------------------------------------

def case_character_template(base: bytes) -> dict[str, Any]:
    rom = bytearray(base)
    off = ict.template_offset(1)
    native = bytes(rom[off:off + ict.TEMPLATE_STRIDE])
    changes = {
        "attr_a": 20,
        "hp_base": 90,
        "entries2": [{"slot": 0, "index": 2, "value": 3, "gate": 0}],
    }
    applied = ict.write_character_template(rom, 1, changes)
    read_back = ict.read_character_template(rom, 1)
    patched = bytes(rom[off:off + ict.TEMPLATE_STRIDE])
    problems = [
        _mismatch("attr_a", applied["attr_a"], read_back["attr_a"]),
        _mismatch("hp_base", applied["hp_base"], read_back["hp_base"]),
        _mismatch("entries2[0].value", applied["entries2"][0]["value"],
                  read_back["entries2"][0]["value"]),
        _mismatch("entries2[0].index", applied["entries2"][0]["index"],
                  read_back["entries2"][0]["index"]),
    ]
    touched = set()
    for offset, name, size in ict.TEMPLATE_FIELDS:
        if name in changes:
            touched.update(range(offset, offset + size))
    touched.update({0x48, 0x49, 0x4A})   # entries2 slot 0 (index/value/gate)
    problems += _untouched_diff(native, patched, touched)
    if native == patched:
        problems.append("the author change did not modify any byte")
    return {
        "author": {
            "attr_a": applied["attr_a"],
            "hp_base": applied["hp_base"],
            "entries2[0]": applied["entries2"][0],
        },
        "read_back": {
            "attr_a": read_back["attr_a"],
            "hp_base": read_back["hp_base"],
            "entries2[0]": read_back["entries2"][0],
        },
        "problems": [p for p in problems if p],
    }


# --- battle record table (0x545458, the audit's "battle-config") ------------

def case_battle_record(base: bytes) -> dict[str, Any]:
    rom = bytearray(base)
    index = 5
    off = ict.battle_record_offset(index)
    native = bytes(rom[off:off + ict.BATTLE_RECORD_STRIDE])
    changes = {"growth_type": 3, "growth_amount": 120}
    applied = ict.write_battle_record(rom, index, changes)
    read_back = ict.read_battle_record(rom, index)
    patched = bytes(rom[off:off + ict.BATTLE_RECORD_STRIDE])
    problems = [
        _mismatch("growth_type", applied["growth_type"], read_back["growth_type"]),
        _mismatch("growth_amount", applied["growth_amount"],
                  read_back["growth_amount"]),
    ]
    touched = {0x0C, 0x0E, 0x0F}
    problems += _untouched_diff(native, patched, touched)
    if native == patched:
        problems.append("the author change did not modify any byte")
    return {
        "author": {"growth_type": applied["growth_type"],
                   "growth_amount": applied["growth_amount"]},
        "read_back": {"growth_type": read_back["growth_type"],
                      "growth_amount": read_back["growth_amount"]},
        "problems": [p for p in problems if p],
    }


# --- sprite action table (0x596CCC) ---------------------------------------

def case_sprite_action(base: bytes) -> dict[str, Any]:
    rom = bytearray(base)
    off = isa.entry_offset(4, 0)
    native = bytes(rom[off:off + isa.ACTION_ENTRY_STRIDE])
    entry = isa.read_sprite_action(rom, 4, 0)
    # author change: reuse a *different* native gfx pointer of the same sprite
    donor = _donor(
        entry["gfx"],
        [isa.read_sprite_action(rom, 4, a)["gfx"] for a in range(9)],
    )
    changes = {"gfx": donor}
    applied = isa.write_sprite_action(rom, 4, 0, changes)
    read_back = isa.read_sprite_action(rom, 4, 0)
    patched = bytes(rom[off:off + isa.ACTION_ENTRY_STRIDE])
    problems = [_mismatch("gfx", applied["gfx"], read_back["gfx"])]
    problems += _untouched_diff(native, patched, {0x08, 0x09, 0x0A, 0x0B})
    if native == patched:
        problems.append("the author change did not modify any byte")
    return {
        "author": {"gfx": f"0x{applied['gfx']:08X}"},
        "read_back": {"gfx": f"0x{read_back['gfx']:08X}"},
        "problems": [p for p in problems if p],
    }


# --- resource pointer window (0x596F0C = sprite 4 / action 0) --------------

def case_resource_pointers(base: bytes) -> dict[str, Any]:
    rom = bytearray(base)
    off = isa.RESOURCE_WINDOW_OFFSET
    native = bytes(rom[off:off + isa.ACTION_ENTRY_STRIDE])
    entry = isa.read_action_entry_at(rom, off)
    donor = _donor(
        entry["frames"],
        [isa.read_sprite_action(rom, 4, a)["frames"] for a in range(9)],
    )
    changes = {"frames": donor}
    applied = isa.write_action_entry_at(rom, off, changes)
    read_back = isa.read_action_entry_at(rom, off)
    patched = bytes(rom[off:off + isa.ACTION_ENTRY_STRIDE])
    problems = [_mismatch("frames", applied["frames"], read_back["frames"])]
    problems += _untouched_diff(native, patched, {0x00, 0x01, 0x02, 0x03})
    if native == patched:
        problems.append("the author change did not modify any byte")
    return {
        "author": {"frames": f"0x{applied['frames']:08X}"},
        "read_back": {"frames": f"0x{read_back['frames']:08X}"},
        "problems": [p for p in problems if p],
    }


# --- story VM roots (0x060C74 / 0x060D54 / 0x060E34 / 0x060EF0) -----------

def case_story_vm_roots(base: bytes) -> dict[str, Any]:
    rom = bytearray(base)
    root = iss.read_root_pointer(rom, "before", 1)
    instructions = iss.scan_script(rom, root)
    portraits = [i for i in instructions if i["op"] == 0x08]
    native_value = rom[portraits[0]["offset"] + 1]
    # author change: reuse another native portrait id of the same script
    donor = next(
        rom[p["offset"] + 1] for p in portraits[1:]
        if rom[p["offset"] + 1] != native_value
    )
    patch = {"opcode": 0x08, "occurrence": 0, "field": "portrait", "value": donor}
    before_root = iss.read_root_pointer(rom, "before", 1)
    before_len = len(iss.scan_script(rom, before_root))
    applied = iss.patch_story_script(rom, "before", 1, [patch])
    read_back = iss.read_story_field(rom, "before", 1, 0x08, 0, "portrait")
    after_root = iss.read_root_pointer(rom, "before", 1)
    after_len = len(iss.scan_script(rom, after_root))
    problems = [
        _mismatch("portrait", patch["value"], read_back["value"]),
        "" if before_root == after_root else
        f"root pointer moved: {before_root} -> {after_root}",
        "" if before_len == after_len else
        f"script length changed: {before_len} -> {after_len}",
        "" if native_value != patch["value"] else
        "the author change did not modify any byte",
    ]
    return {
        "author": {"portrait": patch["value"],
                   "offset": f"0x{applied['patches'][0]['offset']:06X}"},
        "read_back": {"portrait": read_back["value"],
                      "offset": f"0x{read_back['offset']:06X}"},
        "problems": [p for p in problems if p],
    }


# --- map descriptor table (0x53D910, alias of "encounter-zones") -----------

def case_encounter_zones(base: bytes) -> dict[str, Any]:
    rom = bytearray(base)
    map_id = 1
    off = ibc.map_entry_offset(map_id)
    native = bytes(rom[off:off + ibc.ROM_BATTLE_SCENARIO_ENTRY_SIZE])
    # author change: the +0x1C byte the legacy bank called zone_id
    changes = {"background_id": 2}
    applied = ibc.write_map_entry(rom, map_id, changes)
    read_back = ibc.read_map_entry(rom, map_id)
    patched = bytes(rom[off:off + ibc.ROM_BATTLE_SCENARIO_ENTRY_SIZE])
    problems = [_mismatch("background_id", applied["background_id"],
                           read_back["background_id"])]
    problems += _untouched_diff(native, patched, {0x1C})
    if native == patched:
        problems.append("the author change did not modify any byte")
    return {
        "author": {"background_id": applied["background_id"]},
        "read_back": {"background_id": read_back["background_id"]},
        "problems": [p for p in problems if p],
    }


# --- formation matrix (0x5461C4, "positions") ------------------------------

def case_positions(base: bytes) -> dict[str, Any]:
    rom = bytearray(base)
    off = ibc.formation_record_offset(0, 0, 0)
    native = bytes(rom[off:off + ibc.FORMATION_RECORD_STRIDE])
    changes = {"x": 3, "y": 5}
    applied = ibc.write_formation_record(rom, 0, 0, 0, changes)
    read_back = ibc.read_formation_record(rom, 0, 0, 0)
    patched = bytes(rom[off:off + ibc.FORMATION_RECORD_STRIDE])
    problems = [
        _mismatch("x", applied["x"], read_back["x"]),
        _mismatch("y", applied["y"], read_back["y"]),
    ]
    problems += _untouched_diff(native, patched, {0x02, 0x03})
    if native == patched:
        problems.append("the author change did not modify any byte")
    return {
        "author": {"x": applied["x"], "y": applied["y"]},
        "read_back": {"x": read_back["x"], "y": read_back["y"]},
        "problems": [p for p in problems if p],
    }


# --- reward table (0x59EAE0) ------------------------------------------------

def case_reward_table(base: bytes) -> dict[str, Any]:
    rom = bytearray(base)
    index = 0
    off = irr.record_offset(index)
    native = bytes(rom[off:off + irr.REWARD_STRIDE])
    # author change: the gold field plus one tail slot's item id.  The slot
    # list is a single field, so the whole tail area is "touched"; the two
    # unknown bytes at +0x16/+0x17 must stay raw.
    donor_item = 3
    changes = {
        "gold": 500,
        "slots": [
            {"category": 0, "item_id": donor_item},
            {"category": 1, "item_id": 5},
        ],
    }
    applied = irr.write_reward_record(rom, index, changes)
    read_back = irr.read_reward_record(rom, index)
    patched = bytes(rom[off:off + irr.REWARD_STRIDE])
    problems = [
        _mismatch("gold", applied["gold"], read_back["gold"]),
        _mismatch("slots[0].item_id", applied["slots"][0]["item_id"],
                  read_back["slots"][0]["item_id"]),
        _mismatch("slots[0].category_tag", applied["slots"][0]["category_tag"],
                  read_back["slots"][0]["category_tag"]),
        _mismatch("slots[1].item_id", applied["slots"][1]["item_id"],
                  read_back["slots"][1]["item_id"]),
    ]
    touched = {0x00, 0x01}
    touched.update(range(irr.REWARD_TAIL_OFFSET, irr.REWARD_TAIL_END))
    problems += _untouched_diff(native, patched, touched)
    if native == patched:
        problems.append("the author change did not modify any byte")
    return {
        "author": {
            "gold": applied["gold"],
            "slots": applied["slots"],
        },
        "read_back": {
            "gold": read_back["gold"],
            "slots": [s for s in read_back["slots"] if not s["empty"]],
        },
        "problems": [p for p in problems if p],
    }


# --- scene object descriptor table (0x53F140, "map-sprites") ---------------

def case_map_sprites(base: bytes) -> dict[str, Any]:
    rom = bytearray(base)
    native = ibc.read_object_descriptor_pointer(rom, 2)["pointer"]
    donor = _donor(native, [ibc.read_object_descriptor_pointer(rom, s)["pointer"]
                             for s in range(ibc.OBJECT_DESCRIPTOR_TABLE_COUNT)])
    applied = ibc.write_object_descriptor_pointer(rom, 2, donor)
    read_back = ibc.read_object_descriptor_pointer(rom, 2)
    problems = [_mismatch("pointer", applied["pointer"], read_back["pointer"])]
    if native == applied["pointer"]:
        problems.append("the author change did not modify any byte")
    return {
        "author": {"pointer": f"0x{applied['pointer']:08X}"},
        "read_back": {"pointer": f"0x{read_back['pointer']:08X}"},
        "problems": [p for p in problems if p],
    }


# --- m4a SongHeader (behind the sound id table) ----------------------------

def _audio_song_case(sound_id: int):
    """Build the round-trip case for one m4a SongHeader."""

    def run(base: bytes) -> dict[str, Any]:
        rom = bytearray(base)
        header = ias.read_song_header(bytes(rom), sound_id)
        native = ias.native_track_pointers(bytes(rom))
        donor = _donor(header["track_ptrs"][0],
                       [p for p in header["track_ptrs"][1:]] + sorted(native))
        applied = ias.write_song_track(rom, sound_id, 0, donor)
        read_back = ias.read_song_header(bytes(rom), sound_id)
        off = header["offset"]
        patched = bytes(rom[off:off + ias.HEADER_SIZE +
                             header["track_count"] * 4])
        # only the 4 bytes of track 0 may move
        problems = [
            _mismatch("track0", applied["pointer"], read_back["track_ptrs"][0]),
            _mismatch("track_count", header["track_count"],
                      read_back["track_count"]),
            _mismatch("voicegroup", header["voicegroup_ptr"],
                      read_back["voicegroup_ptr"]),
        ]
        problems += _untouched_diff(
            bytes(base[off:off + ias.HEADER_SIZE + header["track_count"] * 4]),
            patched, {0x08, 0x09, 0x0A, 0x0B})
        if read_back["track_ptrs"][0] == header["track_ptrs"][0]:
            problems.append("the author change did not modify any byte")
        # a target that the ROM does not use must be refused
        try:
            ias.write_song_track(rom, sound_id, 1, 0x08FFFFFF)
            problems.append(
                "the writer accepted a track pointer the ROM never uses")
        except ias.WriteBackError:
            pass
        return {
            "author": {"track0": f"0x{applied['pointer']:08X}"},
            "read_back": {
                "track0": f"0x{read_back['track_ptrs'][0]:08X}",
                "track_count": read_back["track_count"],
                "voicegroup": f"0x{read_back['voicegroup_ptr']:08X}",
            },
            "problems": [p for p in problems if p],
        }

    return run


# --- level data block table (0x53DF70, "cutscene-scripts") -----------------

def case_cutscene_scripts(base: bytes) -> dict[str, Any]:
    """One level data block entry: a (gfx, palette) pointer pair.

    The native reader at 0x08072F0C walks the table with a stride of **8**
    bytes, so an entry holds two pointers, not one.  The self-check
    therefore rewrites one of the two and proves the other one is left
    alone -- a check that a 4-byte-per-entry model could not express.
    """
    rom = bytearray(base)
    entry = 1
    off = ibc.STAGE_POINTER_TABLE_FILE + entry * ibc.STAGE_POINTER_STRIDE
    native = bytes(rom[off:off + ibc.STAGE_POINTER_STRIDE])
    donors = [ibc.read_stage_pointer(rom, s)["pointer"]
              for s in range(ibc.STAGE_POINTER_SLOT_COUNT)]
    donor = _donor(ibc.read_stage_entry(rom, entry)["gfx_ptr"], donors)
    applied = ibc.write_stage_entry(rom, entry, {"gfx_ptr": donor})
    read_back = ibc.read_stage_entry(rom, entry)
    patched = bytes(rom[off:off + ibc.STAGE_POINTER_STRIDE])
    problems = [
        _mismatch("gfx_ptr", applied["gfx_ptr"], read_back["gfx_ptr"]),
        _mismatch("palette_ptr",
                  ibc.read_stage_entry(base, entry)["palette_ptr"],
                  read_back["palette_ptr"]),
    ]
    # only the gfx pointer may move; the palette pointer and the padding
    # of the neighbouring slot must stay raw
    problems += _untouched_diff(native, patched, {0x00, 0x01, 0x02, 0x03})
    if native == patched:
        problems.append("the author change did not modify any byte")
    # the table must not be addressable beyond its 4 entries -- the old
    # 16-slot model let an index reach 0x53DFB0, the start of the next table
    try:
        ibc.write_stage_pointer(rom, ibc.STAGE_POINTER_SLOT_COUNT, 0x0812DEE4)
        problems.append("the table accepted an index past its last slot")
    except ibc.WriteBackError:
        pass
    return {
        "author": {"gfx_ptr": f"0x{applied['gfx_ptr']:08X}"},
        "read_back": {
            "gfx_ptr": f"0x{read_back['gfx_ptr']:08X}",
            "palette_ptr": f"0x{read_back['palette_ptr']:08X}",
        },
        "problems": [p for p in problems if p],
    }


# --- WRAM allocation table (0x53D848, legacy "save-state") ------------------

def case_save_state(base: bytes) -> dict[str, Any]:
    rom = bytearray(base)
    native = ibc.read_wram_alloc(rom, 9)
    donor = _donor(
        (native["wram_addr"], native["size"]),
        [(ibc.read_wram_alloc(rom, i)["wram_addr"], ibc.read_wram_alloc(rom, i)["size"])
         for i in range(ibc.WRAM_ALLOC_TABLE_COUNT)],
    )
    applied = ibc.write_wram_alloc(rom, 9, donor[0], donor[1])
    read_back = ibc.read_wram_alloc(rom, 9)
    problems = [
        _mismatch("wram_addr", applied["wram_addr"], read_back["wram_addr"]),
        _mismatch("size", applied["size"], read_back["size"]),
    ]
    if (native["wram_addr"], native["size"]) == (applied["wram_addr"], applied["size"]):
        problems.append("the author change did not modify any byte")
    return {
        "author": {"wram_addr": f"0x{applied['wram_addr']:08X}",
                   "size": applied["size"]},
        "read_back": {"wram_addr": f"0x{read_back['wram_addr']:08X}",
                      "size": read_back["size"]},
        "problems": [p for p in problems if p],
    }


# --- u16 offset table (0x53F298, legacy "units") ---------------------------

def case_units(base: bytes) -> dict[str, Any]:
    rom = bytearray(base)
    native = ibc.read_unit_offset(rom, 0)["value"]
    donor = _donor(native, [ibc.read_unit_offset(rom, i)["value"]
                             for i in range(64)])
    applied = ibc.write_unit_offset(rom, 0, donor)
    read_back = ibc.read_unit_offset(rom, 0)
    problems = [_mismatch("value", applied["value"], read_back["value"])]
    if native == applied["value"]:
        problems.append("the author change did not modify any byte")
    # the constraint must actually bite: a non-native offset has to be refused
    try:
        ibc.write_unit_offset(rom, 1, 0xBEEF)
        problems.append("write_unit_offset accepted a non-native offset")
    except ibc.WriteBackError:
        pass
    return {
        "author": {"value": applied["value"]},
        "read_back": {"value": read_back["value"]},
        "problems": [p for p in problems if p],
    }


CASES: list[Case] = [
    Case("story-vm-roots", "0x060C74", "剧情脚本 VM 四根表", case_story_vm_roots),
    Case("character-template", "0x54241C", "角色定义表", case_character_template),
    Case("battle-config", "0x545458", "战斗记录表", case_battle_record),
    Case("sprite-action-table", "0x596CCC", "精灵动作表", case_sprite_action),
    Case("resource-pointers", "0x596F0C", "资源指针（动作表窗口）", case_resource_pointers),
    Case("encounter-zones", "0x53D910", "地图描述符表（encounter-zones 别名）", case_encounter_zones),
    Case("positions", "0x5461C4", "战斗编成矩阵", case_positions),
    Case("audio-song-1", "0x536368", "m4a SongHeader（sound id 1）",
         _audio_song_case(1)),
    Case("audio-song-2", "0x536BC4", "m4a SongHeader（sound id 2）",
         _audio_song_case(2)),
    Case("audio-song-8", "0x538FEC", "m4a SongHeader（sound id 8）",
         _audio_song_case(8)),
    Case("audio-song-11", "0x53AB74", "m4a SongHeader（sound id 11）",
         _audio_song_case(11)),
    Case("audio-song-14", "0x53C3BC", "m4a SongHeader（sound id 14）",
         _audio_song_case(14)),
    Case("reward-table", "0x59EAE0", "战斗奖励表", case_reward_table),
    Case("map-sprites", "0x53F140", "场景对象描述符指针表", case_map_sprites),
    Case("cutscene-scripts", "0x53DF70", "关卡数据指针表", case_cutscene_scripts),
    Case("save-state", "0x53D848", "WRAM 分配表", case_save_state),
    Case("units", "0x53F298", "u16 偏移表", case_units),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("rom", nargs="?", default="rom/base.gba",
                        help="ROM to copy from (default: rom/base.gba)")
    parser.add_argument("--json", help="write the machine-readable report here")
    args = parser.parse_args(argv)

    rom_path = pathlib.Path(args.rom)
    if not rom_path.is_file():
        print(f"ROM not found: {rom_path}")
        return 1
    base = rom_path.read_bytes()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    results = []
    failures = 0
    for case in CASES:
        try:
            outcome = case.run(base)
            problems = outcome["problems"]
        except Exception as exc:  # a write-back path that raises is a failure
            outcome = {"author": None, "read_back": None,
                       "problems": [f"{type(exc).__name__}: {exc}"]}
            problems = outcome["problems"]
        ok = not problems
        if not ok:
            failures += 1
        results.append({
            "structure": case.key,
            "rom": case.rom,
            "title": case.title,
            "ok": ok,
            "author_input": outcome["author"],
            "read_back": outcome["read_back"],
            "problems": problems,
        })
        status = "PASS" if ok else "FAIL"
        print(f"{status}  {case.key:<20} {case.rom}  {case.title}")
        print(f"      author input : {json.dumps(outcome['author'], ensure_ascii=False)}")
        print(f"      read back    : {json.dumps(outcome['read_back'], ensure_ascii=False)}")
        for problem in problems:
            print(f"      problem      : {problem}")

    print()
    print(f"write-back paths checked: {len(CASES)}  passed: {len(CASES) - failures}  "
          f"failed: {failures}")

    report = {
        "rom": str(rom_path),
        "cases": results,
        "passed": len(CASES) - failures,
        "failed": failures,
    }
    if args.json:
        write_json(args.json, report)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
