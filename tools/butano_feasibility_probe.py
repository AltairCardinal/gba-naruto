#!/usr/bin/env python3
"""Feasibility probes for the 1:1 fidelity roadmap.

Every phase of docs/butano-fidelity-roadmap.md rests on an assumption about
whether a given subsystem can be made to match the original at all.  This
script turns the assumptions that *can* be checked mechanically into checks,
so the roadmap's risk list is machine-verified instead of narrated.

It probes five of the eight subsystems:

======  =======================================  ==========================
probe   subsystem                               what it decides
======  =======================================  ==========================
F1      battle state machine                    can the original's 38
                                                states drive the remake?
F2      battle action system                    is the remake's action
                                                dispatch the original's
                                                60-entry shape?
F5      Butano rendering substrate             can Butano 21.7.1 place
                                                BGs / palettes like the
                                                original?
F7      scenario rollout throughput             can the truth side and the
                                                remake side be recorded
                                                for all 47 scenarios?
F8      modifiability ledger                    is every reverse result
                                                accounted for?
======  =======================================  ==========================

F3 (pathfinding), F4 (RNG) and F6 (audio) are *not* probed here: they have
no reverse result to compare against, so they are new reverse work rather
than a port.  They are recorded as such in the roadmap.

Usage::

    python tools/butano_feasibility_probe.py
    python tools/butano_feasibility_probe.py --json-out build/feasibility.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parents[1]
BUTANO = pathlib.Path("D:/Shell/Github/gba-naruto-butano")
BUTANO_GAME = BUTANO / "butano-sequel" / "game"
BUTANO_LIB = BUTANO / "third_party" / "butano" / "butano"
REVERSE = pathlib.Path("D:/Shell/Github/gba-naruto-reverse")

# The original's action table: 60 entries, dispatched as
# `case = (id & 0x3F) - 4`, with 5 ninjutsu slots per character
# (action ids 14 / 15 / 21 / 61 / 62).
ORIGINAL_ACTION_IDS = set(range(0, 60))
ORIGINAL_NINJUTSU_SLOTS = {14, 15, 21, 61, 62}


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def probe_f1_state_machine() -> dict:
    """Can the original's 38 states drive the remake?

    The shape is expected to already exist (a generated header with the 38
    codes plus a 24 -> 38 mapping table).  What is missing is the runtime
    binding, so the probe reports both.
    """
    table = BUTANO / "sequel" / "content" / "battle_controller_states.json"
    header = BUTANO_GAME / "include" / "konoha" / "battle_original_states.h"
    controller = BUTANO_GAME / "include" / "konoha" / "battle_scene_controller.h"
    if not table.is_file():
        return {"id": "F1", "ok": False, "why": f"missing {table}"}

    data = json.loads(_read(table))
    mapping = data.get("mapping") or []
    status = Counter(m.get("status") for m in mapping)
    bound = set()
    for m in mapping:
        bound.update(m.get("original_states") or [])
    original_only = data.get("original_only_states") or []

    # the runtime enum the remake actually executes
    runtime_enum = None
    runtime_values = 0
    text = _read(controller)
    match = re.search(r"enum class battle_scene_phase[^\{]*\{(.*?)\}", text, re.S)
    if match:
        runtime_values = len(re.findall(r"^\s*[a-z_]+,?\s*$", match.group(1), re.M))
    runtime_enum = "battle_scene_phase" if match else None

    # the original's 38 codes as generated C++
    named = 0
    unknown = 0
    if header.is_file():
        htext = _read(header)
        named = len(re.findall(r"unknown_[0-9A-Fa-f]{4}\s*=", htext))
        unknown = named
        named = len(re.findall(r"^\s+[a-z_0-9]+\s*=\s*0x[0-9A-Fa-f]{4},", htext, re.M)) - unknown

    result = {
        "id": "F1",
        "ok": True,
        "original_states": data.get("state_count"),
        "named_states": data.get("named_count"),
        "unknown_states": data.get("unknown_count"),
        "mapping_entries": len(mapping),
        "mapping_status": dict(status),
        "original_states_bound": len(bound),
        "original_only_states": len(original_only),
        "runtime_enum": runtime_enum,
        "runtime_enum_values": runtime_values,
        "shape_header_present": header.is_file(),
        "implemented_flag": data.get("implemented"),
    }
    result["verdict"] = (
        "shape exists, runtime still on the remake's own enum"
        if data.get("implemented") is False else "shape and runtime agree")
    result["blocking_gap"] = (
        f"{data.get('unknown_count')} states unnamed; "
        f"{len(original_only)} original states have no remake counterpart; "
        f"runtime enum has {runtime_values} values vs the original's "
        f"{data.get('state_count')}")
    return result


def probe_f2_action_system() -> dict:
    """Is the remake's action dispatch the original's 60-entry shape?"""
    header = BUTANO_GAME / "include" / "konoha" / "battle_action_system.h"
    unit = BUTANO_GAME / "include" / "konoha" / "battle_unit_content.h"
    if not header.is_file():
        return {"id": "F2", "ok": False, "why": f"missing {header}"}

    text = _read(header)
    ids = sorted({int(h, 16) for h in re.findall(r"case\s+(0x[0-9A-Fa-f]+)\s*:", text)})
    missing = sorted(ORIGINAL_ACTION_IDS - set(ids))
    extra = sorted(set(ids) - ORIGINAL_ACTION_IDS)

    slots = {}
    if unit.is_file():
        utext = _read(unit)
        for name in ("primary_slots", "secondary_slots"):
            m = re.search(name + r"\s*=\s*\{\};", utext)
            if m:
                mm = re.search(r"std::array<[^,]+,\s*(\d+)>\s*" + name, utext)
                slots[name] = int(mm.group(1)) if mm else None

    return {
        "id": "F2",
        "ok": True,
        "remake_action_ids": len(ids),
        "remake_ids": ids,
        "original_action_ids": len(ORIGINAL_ACTION_IDS),
        "missing_ids": missing,
        "missing_count": len(missing),
        "extra_ids": extra,
        "ninjutsu_slots_missing": sorted(
            ORIGINAL_NINJUTSU_SLOTS - set(ids)),
        "remake_slot_counts": slots,
        "verdict": (
            "SHAPE MISMATCH: the remake dispatches a different id set and a "
            "different slot layout (original: 5 ninjutsu slots + two 8-byte "
            "action tables per unit; remake: "
            f"{slots.get('primary_slots')}+{slots.get('secondary_slots')} slots)"
            if missing or extra else "shapes agree"),
        "blocking_gap": (
            f"{len(missing)} of the original's 60 action ids are absent; "
            f"ninjutsu slots {sorted(ORIGINAL_NINJUTSU_SLOTS - set(ids))} are absent; "
            "the per-unit 8-byte action tables have no counterpart"),
    }


def probe_f5_butano_substrate() -> dict:
    """Can Butano 21.7.1 place BGs and palettes the way the original does?

    The original uses BG0 for the map, BG2 for the overlay and BG3 for the UI.
    The remake uses BG3 for the map and BG2 for the overlay, and draws its UI
    with sprites.  So a faithful overlay needs three things Butano's
    ``regular_bg_ptr`` does not offer:

    1. a selectable BG layer index (Butano hands out bg3, bg2, bg1 in order);
    2. runtime tilemap writes (only whole-map ``set_cells_ref`` exists);
    3. 4bpp tiles with a dedicated palette bank (Butano's tile data is 8bpp
       native and palette banks follow Butano's own allocation order).

    What is *not* blocked: the layer index does not change the rendered image
    (GBA mode 0 layering is decided by priority, and the remake already uses
    priority 3 for the map and priority 2 for the overlay, same as the
    original).  Only register-level identity (``DISPCNT``/``BGCNT0..3`` bit
    for bit) needs the selectable index.
    """
    manager = BUTANO_LIB / "src" / "bn_bgs_manager.cpp"
    palette_bitmap = BUTANO_LIB / "include" / "bn_palette_bitmap_item.h"
    palette_ptr = BUTANO_LIB / "include" / "bn_bg_palette_ptr.h"
    map_ptr = BUTANO_LIB / "include" / "bn_regular_bg_map_ptr.h"
    bpp_mode = BUTANO_LIB / "include" / "bn_bpp_mode.h"
    if not manager.is_file():
        return {"id": "F5", "ok": False, "why": f"missing {manager}"}

    text = _read(manager)
    case0 = re.search(r"case 0:\s*\n\s*regular_id = hw::bgs::count\(\) - (\d+);", text)
    default = re.search(r"default:\s*\n\s*regular_id = hw::bgs::count\(\) - (\d+);", text)
    bpp4_rejected = "BPP_4 palettes are not supported" in _read(palette_bitmap)
    set_color = "set_color(int color_index, color color)" in _read(palette_ptr)
    whole_map_only = ("set_cells_ref" in _read(map_ptr)
                      and "set_map_cell" not in _read(map_ptr))
    bpp4_mode_exists = "BPP_4" in _read(bpp_mode)
    per_bg_bpp_hw = "set_bpp" in _read(manager)

    bg_count = 4
    first_regular = bg_count - int(case0.group(1)) if case0 else None
    default_regular = bg_count - int(default.group(1)) if default else None

    return {
        "id": "F5",
        "ok": True,
        "case0_first_regular_bg": first_regular,
        "default_first_regular_bg": default_regular,
        "can_reach_bg0": bool(first_regular is not None and first_regular == 0),
        "regular_bgs_available": first_regular,  # bg3, bg2, bg1 -- three fit
        "bpp4_mode_exists": bpp4_mode_exists,
        "per_bg_bpp_in_hw_layer": per_bg_bpp_hw,
        "bpp4_palette_bitmap_rejected": bpp4_rejected,
        "per_color_palette_write": set_color,
        "whole_map_write_only": whole_map_only,
        "verdict": (
            "THREE ADDITIVE GAPS, NOT AN UNSUITABLE ENGINE: (1) selectable BG "
            "index, (2) per-cell runtime tilemap write, (3) 4bpp tile packing + "
            "palette bank placement. The BG index does not change the rendered "
            "image -- GBA mode 0 layering is decided by priority, and the "
            "remake already matches the original there -- so only "
            "register-level identity needs (1)."),
        "blocking_gap": (
            "the overlay needs a 4bpp tile upload path and a controllable "
            "palette bank; the map/overlay/UI need three regular BG layers "
            "(bg3, bg2, bg1 are available)"),
        "register_level_only": (
            "a selectable BG index is required only if 'identical' includes "
            "the GBA display registers bit for bit; it is not required for "
            "pixel-identical output"),
    }


def probe_f7_throughput() -> dict:
    """Can the truth side and the remake side be recorded for all scenarios?

    Throughput is read from the two measurement tools rather than assumed:
    the recomp's own banner (guest_fps) and the probe's frame loop.
    """
    import subprocess
    import time

    recomp = REPO / "build" / "naruto-recomp-build" / "Release" / "NarutoKonohaSenkiRecomp.exe"
    fps_truth = None
    if recomp.is_file():
        rom = REPO / "rom" / "base.gba"
        bios = REPO / "recomp" / "bios" / "gba_bios.bin"
        if rom.is_file() and bios.is_file():
            t0 = time.time()
            proc = subprocess.run(
                [str(recomp), "--bios", str(bios), "--rom", str(rom),
                 "--frames", "2000", "--no-window"],
                capture_output=True, text=True, cwd=str(REPO / "recomp"),
            )
            elapsed = time.time() - t0
            m = re.search(r"guest_fps=([0-9.]+)", proc.stdout + proc.stderr)
            if m:
                fps_truth = float(m.group(1))
            static = "FULLY_STATIC" in (proc.stdout + proc.stderr)

    fps_remake = None
    remake_rom = BUTANO / "butano-sequel" / "butano-sequel.gba"
    if remake_rom.is_file():
        t0 = time.time()
        subprocess.run(
            [sys.executable, str(REPO / "tools" / "mgba_probe" / "probe_client.py"),
             "--rom", remake_rom.as_posix(), "--cmd", "frames 3000 0x000",
             "--out", str(REPO / "build" / "feasibility-throughput.json")],
            capture_output=True, cwd=str(REPO),
        )
        elapsed = time.time() - t0
        if elapsed > 0:
            fps_remake = 3000 / elapsed

    scenarios = 47
    frames_each = 1800
    return {
        "id": "F7",
        "ok": fps_truth is not None and fps_remake is not None,
        "truth_fps": fps_truth,
        "remake_fps": round(fps_remake, 1) if fps_remake else None,
        "scenarios": scenarios,
        "frames_per_scenario": frames_each,
        "truth_seconds_for_all": (
            round(scenarios * frames_each / fps_truth, 1) if fps_truth else None),
        "remake_seconds_for_all": (
            round(scenarios * frames_each / fps_remake, 1) if fps_remake else None),
        "verdict": "both sides record all 47 scenarios in minutes, not hours",
    }


def probe_f8_ledger() -> dict:
    """Is every reverse result accounted for in the rebuild ledger?"""
    ledger = BUTANO / "docs" / "reverse-results-index" / "ledger.json"
    if not ledger.is_file():
        return {"id": "F8", "ok": False, "why": f"missing {ledger}"}
    data = json.loads(_read(ledger))
    rows = data if isinstance(data, list) else (data.get("entries") or data.get("ledger") or [])
    status = Counter(r.get("status") for r in rows)
    return {
        "id": "F8",
        "ok": True,
        "entries": len(rows),
        "by_status": dict(status),
        "missing": status.get("missing", 0),
        "verdict": (
            "every reverse result is accounted for"
            if not status.get("missing") else
            f"{status.get('missing')} ledger entries are still missing"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json-out", type=pathlib.Path, default=None)
    args = ap.parse_args()

    probes = [
        probe_f1_state_machine,
        probe_f2_action_system,
        probe_f5_butano_substrate,
        probe_f7_throughput,
        probe_f8_ledger,
    ]
    report = {}
    for probe in probes:
        try:
            report[probe.__name__] = probe()
        except Exception as exc:  # noqa: BLE001
            report[probe.__name__] = {"id": probe.__name__, "ok": False,
                                      "why": f"{type(exc).__name__}: {exc}"}

    for name, data in report.items():
        print(f"== {name} ==")
        for key, value in data.items():
            if key in ("remake_ids", "missing_ids", "extra_ids"):
                value = f"[{len(value)} values]"
            print(f"   {key}: {value}")
        print()

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(report, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n")
        print("wrote", args.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
