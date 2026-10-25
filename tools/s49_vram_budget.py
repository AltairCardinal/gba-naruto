#!/usr/bin/env python3
"""S49 stream E - VRAM budget and 4bpp/8bpp feasibility for the battle overlay.

Question this tool answers
--------------------------
The original GBA stores the S49 battle overlay ("BG2") as 32 tiles of **4bpp**
tile data (1024 bytes).  Butano 21.7.1 has no "pack and upload 4bpp tiles"
path: its `bn::tile` storage is natively 8bpp (one byte per pixel).  The
roadmap therefore priced a 64-80 h engine fork to add that path.

The insight that can make the fork unnecessary: **4bpp/8bpp is a storage
format, not an output format.**  The same overlay pixels can be stored 8bpp.
If the overlay fits in VRAM as 8bpp, the engine fork is bypassed entirely.

This tool measures, from real emulator state:

  1. a per-step VRAM occupancy profile of the remake's 35-step walk
     (character region 0x06000000-0x0600FFFF vs screen-block region
     0x06010000-0x06017FFF, and per char-base slot),
  2. the same profile for the original ROM at the battle-14 entry state,
  3. the project-recorded baseline GPU dumps of the remake at its overlay
     moment (cross-check dataset, ROM 02bf3573),
  4. where each side's overlay tile data actually lives (by content, not by
     assumption), and
  5. the resulting 8bpp feasibility verdict with byte-level numbers.

Everything is derived from dumped bytes; nothing is asserted from source
reading alone.

Usage
-----
    python tools/s49_vram_budget.py --out build/s49-vram/budget.json

Outputs (all under --work-dir, default build/s49-vram):
    walk/                 remake walk savestates + screenshots
    vram/<step>.bin       raw 0x18000-byte VRAM image per walk step
    original/vram.bin     raw 0x18000-byte VRAM image of the original ROM
    budget.json           the report
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import queue
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

# ---------------------------------------------------------------- constants

VRAM_BASE = 0x06000000
VRAM_SIZE = 0x18000
CHAR_REGION = (0x00000, 0x10000)    # 64 KiB of character (tile) data
SCREEN_REGION = (0x10000, 0x18000)  # 32 KiB of screen-block (tilemap) data
CHAR_BLOCK_SIZE = 0x4000
SCREEN_BLOCK_SIZE = 0x800

DISPCNT_ADDR = 0x04000000
BGCNT_ADDRES = [0x04000008, 0x0400000A, 0x0400000C, 0x0400000E]
REGS_SIZE = 0x40

# GBA DISPCNT: bits 0-2 enable BG0-2 (mode 0), bit 8 enables BG2 (modes 1-2),
# bit 9 enables BG3, bit 12 enables BG0 and bit 13 enables BG1 (mode 0 only).
DISPCNT_BG_ENABLE = {0: 12, 1: 13, 2: 8, 3: 9}

REPO = pathlib.Path(__file__).resolve().parent.parent

DEFAULT_ROM = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba")
DEFAULT_PROBE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"
DEFAULT_BIOS = REPO / "recomp" / "bios" / "gba_bios.bin"
DEFAULT_BOOT_LUA = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\tools\butano\mgba_boot_input_sequence.lua")
DEFAULT_ORIGINAL_ROM = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_ORIGINAL_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-entry.ss9")
DEFAULT_ORIGINAL_TILES = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\s49-original-movegrid-tilemap-v1"
    r"\bg2-tiles-4bpp.bin")
DEFAULT_ORIGINAL_PALETTE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\s49-original-movegrid-tilemap-v1"
    r"\bg2-palette.bin")

# The remake's overlay colours, transcribed from
# butano-sequel/game/include/konoha/battle_range_ui_style.h
# (battle_range_ui_*_color) together with the palette index each one is
# written to (battle_range_ui_palette_index).
REMAKE_OVERLAY_COLORS = [
    ("grid_secondary", 225, (8, 13, 17)),
    ("move_primary", 226, (3, 25, 31)),
    ("move_secondary", 227, (1, 13, 21)),
    ("attack_primary", 228, (31, 7, 0)),
    ("attack_secondary", 229, (20, 5, 0)),
    ("cursor_primary", 230, (31, 23, 0)),
    ("cursor_secondary", 231, (18, 13, 0)),
    ("target_primary", 232, (21, 31, 0)),
    ("target_secondary", 233, (10, 16, 0)),
    ("blocked_primary", 234, (9, 9, 9)),
    ("blocked_secondary", 235, (4, 4, 4)),
]

ARTIFACTS = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\artifacts")

# Project-recorded GPU dumps of the remake (baseline ROM 02bf3573).  They are
# the only in-tree VRAM images of the remake at its move-grid overlay moment.
RECORDED_REMADE_DUMPS = [
    "s49-remake-gpu-baseline-step20-v1",
    "s49-remake-gpu-20261021-v2",
    "s49-remake-gpu-20261020-v1",
    "s49-remake-gpu-overlaybaked-20261021-v1",
]

# The walk key sequence is fixed by the project baseline (2x Down then 32x A).
WALK_KEYS = ["Down", "Down"] + ["A"] * 32
# 240 zero-input frames (the baseline value) is NOT enough on the current
# local build: the two Down presses land before the preparation menu exists,
# so the cursor stays on "team/equipment" and the walk never enters the
# battle.  600 frames lets the menu settle first and reproduces the baseline
# walk (step-20-A shows the move-grid overlay).
WALK_ZERO_FRAMES = 600
WALK_SETTLE_FRAMES = 90
WALK_HOLD_FRAMES = 4

# The remake's overlay tiles are written with exactly these palette indices
# (battle_range_ui_palette_index in
# butano-sequel/game/include/konoha/battle_range_ui_style.h).
OVERLAY_PALETTE_INDICES = set(range(225, 236))
# battle_range_ui_logical_tile_count (77 logical 8x8 tiles).
REMAKE_OVERLAY_LOGICAL_TILES = 77

# Both sides put the move-grid overlay at BG priority 2.
OVERLAY_PRIORITY = 2


# ---------------------------------------------------------------- helpers

def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- probe

class ProbeError(RuntimeError):
    pass


class Probe:
    """Minimal driver for the headless mGBA probe (build/mgba-probe).

    The probe's `echo` command is the per-command sentinel mechanism, but the
    CLI splits its argument on whitespace, so the sentinel token must not
    contain a space or the reader would wait forever for a token that the
    probe never prints.
    """

    def __init__(self, rom, bios=None, exe=None, timeout=1800.0):
        self.exe = pathlib.Path(exe or DEFAULT_PROBE)
        if not self.exe.exists():
            raise ProbeError(f"probe executable missing: {self.exe}")
        command = [str(self.exe), str(rom)]
        if bios:
            command += ["--bios", str(bios)]
        self._deadline = time.monotonic() + timeout
        self._command_index = 0
        self._proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8",
            errors="replace", bufsize=1,
        )
        self._stderr_lines: list[str] = []
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        self._queue: queue.Queue = queue.Queue()
        threading.Thread(target=self._pump_stdout, daemon=True).start()
        banner = self._readline()
        if banner is None:
            raise ProbeError("probe closed stdout before READY")
        if banner.strip() != "READY":
            self._stderr_lines.append(f"banner: {banner.rstrip()}")

    def _pump_stdout(self) -> None:
        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            self._queue.put(line.rstrip("\r\n"))
        self._queue.put(None)

    def _drain_stderr(self) -> None:
        assert self._proc.stderr is not None
        for line in self._proc.stderr:
            self._stderr_lines.append(line.rstrip("\r\n"))

    def _readline(self) -> str | None:
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise ProbeError("probe timed out")
        try:
            line = self._queue.get(timeout=remaining)
        except queue.Empty:
            raise ProbeError("probe timed out") from None
        return line

    def command(self, command: str) -> list[str]:
        sentinel = f"___S49_END_{self._command_index}___"
        self._command_index += 1
        try:
            self._proc.stdin.write(f"{command}\n")
            self._proc.stdin.write(f"echo {sentinel}\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise ProbeError(f"probe exited before '{command}': {exc}") from exc
        output: list[str] = []
        while True:
            line = self._readline()
            if line is None:
                break
            if line == sentinel:
                break
            output.append(line)
        return output

    def dump(self, address: int, length: int) -> bytes:
        output = self.command(f"dump 0x{address:08X} {length}")
        if not output or not output[0].startswith("DUMP "):
            raise ProbeError(
                f"dump 0x{address:08X} failed: {' | '.join(output[:3])}")
        payload = []
        for line in output[1:]:
            if line == "ENDDUMP":
                break
            payload.append(line.strip())
        data = bytes.fromhex("".join(payload))
        if len(data) != length:
            raise ProbeError(
                f"dump 0x{address:08X} short: {len(data)} != {length}")
        return data

    def close(self) -> None:
        try:
            self._proc.stdin.write("quit\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        try:
            self._proc.stdin.close()
        except Exception:
            pass
        try:
            self._proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._proc.kill()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


# ---------------------------------------------------------------- capture

def walk_states(walk_dir: pathlib.Path) -> list[pathlib.Path]:
    return sorted(walk_dir.glob("step-*.ss9"))


def capture_walk(rom, bios, lua, walk_dir: pathlib.Path,
                 rom_sha: str) -> dict:
    """Re-record the remake walk from power-on with the project's own Lua."""
    walk_dir.mkdir(parents=True, exist_ok=True)
    child_env = dict(os.environ)
    child_env.update({
        "MGBA_BOOT_SEQUENCE_OUTPUT_DIR": str(walk_dir),
        "MGBA_BOOT_SEQUENCE_DONE_MARKER": str(walk_dir / "done.json"),
        "MGBA_BOOT_SEQUENCE_ROM_SHA256": rom_sha,
        "MGBA_BOOT_SEQUENCE_KEY_SEQUENCE": ",".join(WALK_KEYS),
        "MGBA_BOOT_SEQUENCE_ZERO_INPUT_FRAMES": str(WALK_ZERO_FRAMES),
        "MGBA_BOOT_SEQUENCE_SETTLE_FRAMES": str(WALK_SETTLE_FRAMES),
        "MGBA_BOOT_SEQUENCE_HOLD_FRAMES": str(WALK_HOLD_FRAMES),
    })
    command = [
        sys.executable, str(REPO / "tools" / "mgba_probe" / "probe_client.py"),
        "--rom", str(rom),
        "--bios", str(bios),
        "--cmd", f"script {lua}",
        "--cmd", "frames 12000 0x000",
        "--out", str(walk_dir.parent / "capture.json"),
    ]
    completed = subprocess.run(command, env=child_env,
                               capture_output=True, text=True)
    if completed.returncode != 0:
        raise ProbeError(
            "walk capture failed: "
            f"{completed.stdout[-500:]} {completed.stderr[-500:]}")
    return {
        "rom_sha256": rom_sha,
        "key_sequence": ",".join(WALK_KEYS),
        "zero_input_frames": WALK_ZERO_FRAMES,
        "settle_frames": WALK_SETTLE_FRAMES,
        "hold_frames": WALK_HOLD_FRAMES,
        "state_count": len(walk_states(walk_dir)),
        "states": [p.name for p in walk_states(walk_dir)],
    }


# ---------------------------------------------------------------- registers

def decode_registers(regs: bytes) -> dict:
    def u16(offset):
        return regs[offset] | (regs[offset + 1] << 8)

    dispcnt = u16(0)
    bgcnts = [u16(off - DISPCNT_ADDR) for off in BGCNT_ADDRES]
    bgs = []
    for index, value in enumerate(bgcnts):
        bgs.append({
            "bg": index,
            "bgcnt": value,
            "priority": value & 3,
            "char_base": ((value >> 2) & 3) * CHAR_BLOCK_SIZE,
            "char_base_block": (value >> 2) & 3,
            "mosaic": (value >> 6) & 1,
            "color_mode": (value >> 6) & 3,
            "bpp": 8 if (value >> 7) & 1 else 4,
            "screen_base": ((value >> 8) & 0x1F) * SCREEN_BLOCK_SIZE,
            "screen_base_block": (value >> 8) & 0x1F,
            "overflow": (value >> 14) & 1,
            "screen_size": (value >> 14) & 3,
            "enabled": bool((dispcnt >> DISPCNT_BG_ENABLE[index]) & 1),
        })
    return {
        "dispcnt": dispcnt,
        "dispcnt_hex": f"0x{dispcnt:04X}",
        "mode": (dispcnt >> 14) & 3,
        "forced_blank": bool((dispcnt >> 7) & 1),
        "obj_1d": bool((dispcnt >> 6) & 1),
        "obj_2d": bool((dispcnt >> 11) & 1),
        "bgs": bgs,
    }


# ---------------------------------------------------------------- vram analysis

def analyze_vram(vram: bytes) -> dict:
    char_lo, char_hi = CHAR_REGION
    screen_lo, screen_hi = SCREEN_REGION
    char = vram[char_lo:char_hi]
    screen = vram[screen_lo:screen_hi]

    def nonzero(block):
        return sum(1 for byte in block if byte)

    def high_water(block):
        index = len(block)
        while index > 0 and block[index - 1] == 0:
            index -= 1
        return index

    char_blocks = []
    for index in range(4):
        lo = index * CHAR_BLOCK_SIZE
        piece = char[lo:lo + CHAR_BLOCK_SIZE]
        char_blocks.append({
            "char_base": lo,
            "label": f"0x{lo:05X}",
            "nonzero": nonzero(piece),
            "free_bytes": CHAR_BLOCK_SIZE - nonzero(piece),
            "high_water": high_water(piece),
        })

    screen_blocks = []
    for index in range(32):
        lo = index * SCREEN_BLOCK_SIZE
        piece = screen[lo:lo + SCREEN_BLOCK_SIZE]
        screen_blocks.append({
            "screen_block": index,
            "vram_offset": char_hi + lo,
            "nonzero": nonzero(piece),
            "free_bytes": SCREEN_BLOCK_SIZE - nonzero(piece),
            "high_water": high_water(piece),
        })

    return {
        "char_nonzero": nonzero(char),
        "char_free_bytes": len(char) - nonzero(char),
        "char_high_water": high_water(char),
        "screen_nonzero": nonzero(screen),
        "screen_free_bytes": len(screen) - nonzero(screen),
        "screen_high_water": high_water(screen),
        "total_nonzero": nonzero(vram),
        "total_size": len(vram),
        "char_blocks": char_blocks,
        "screen_blocks": screen_blocks,
    }


def find_blob(haystack: bytes, needle: bytes) -> list[int]:
    """All offsets where `needle` occurs inside `haystack`."""
    offsets = []
    start = haystack.find(needle)
    while start != -1:
        offsets.append(start)
        start = haystack.find(needle, start + 1)
    return offsets


def overlay_signature_ratio(data: bytes) -> float:
    if not data:
        return 0.0
    hits = sum(1 for byte in data
               if byte == 0 or byte in OVERLAY_PALETTE_INDICES)
    return round(hits / len(data), 4)


def pick_overlay_bg(registers: dict) -> dict | None:
    """Both sides put the move-grid overlay at BG priority 2."""
    for bg in registers["bgs"]:
        if bg["priority"] == OVERLAY_PRIORITY and bg["bgcnt"]:
            return bg
    return None


def describe_overlay_window(vram: bytes, bg: dict,
                            logical_tiles: int) -> dict:
    """Measure the tile bytes the overlay's own char base holds."""
    stride = 64 if bg["bpp"] == 8 else 32
    base = bg["char_base"]
    span = logical_tiles * stride
    window = vram[base:base + span]
    nonzero = sum(1 for byte in window if byte)
    return {
        "char_base": base,
        "bpp": bg["bpp"],
        "stride_bytes": stride,
        "logical_tiles": logical_tiles,
        "window_bytes": span,
        "window_nonzero": nonzero,
        "window_free_bytes": span - nonzero,
        "window_signature_ratio": overlay_signature_ratio(window),
        "window_vram_start": f"0x{VRAM_BASE + base:08X}",
        "window_vram_end": f"0x{VRAM_BASE + base + span - 1:08X}",
    }


# ---------------------------------------------------------------- dumping

def decode_palette555(data: bytes) -> list[tuple]:
    entries = []
    for index in range(0, len(data) - 1, 2):
        value = data[index] | (data[index + 1] << 8)
        entries.append((value & 0x1F, (value >> 5) & 0x1F,
                        (value >> 10) & 0x1F))
    return entries


def compare_overlay_palettes(palette_path: pathlib.Path,
                              tiles_path: pathlib.Path) -> dict:
    """Is the remake's 8bpp overlay palette a colour-exact relabelling of the
    original's 4bpp one?  If yes, 8bpp storage reproduces the original's
    pixels and the 4bpp packing upload is unnecessary."""
    result = {
        "original_palette_file": str(palette_path),
        "original_tiles_file": str(tiles_path),
        "available": palette_path.exists() and tiles_path.exists(),
    }
    if not result["available"]:
        return result
    palette = decode_palette555(palette_path.read_bytes())
    tiles = tiles_path.read_bytes()
    used = set()
    for byte in tiles:
        used.add(byte & 0x0F)
        used.add((byte >> 4) & 0x0F)
    result["original_palette_entries"] = [
        {"index": index, "rgb5": list(rgb)} for index, rgb in enumerate(palette)]
    result["original_indices_used_by_tiles"] = sorted(used)
    mapping = []
    all_match = True
    for name, remake_index, rgb in REMAKE_OVERLAY_COLORS:
        hits = [i for i, c in enumerate(palette) if c == rgb]
        entry = {
            "role": name,
            "remake_palette_index": remake_index,
            "remake_rgb5": list(rgb),
            "original_palette_indices_with_same_rgb5": hits,
            "color_identical": bool(hits),
        }
        if hits:
            entry["original_index"] = hits[0]
            entry["index_shift"] = remake_index - hits[0]
            entry["original_index_used_by_tiles"] = hits[0] in used
        else:
            all_match = False
        mapping.append(entry)
    result["mapping"] = mapping
    result["all_colors_identical"] = all_match
    result["every_mapped_original_index_is_used_by_tiles"] = all(
        e.get("original_index_used_by_tiles") for e in mapping)
    shifts = {e.get("index_shift") for e in mapping if "index_shift" in e}
    result["uniform_index_shift"] = (sorted(shifts)[0] if len(shifts) == 1
                                     else None)
    return result


def step_sort_key(path: pathlib.Path):
    match = re.match(r"step-(\d+)-", path.name)
    return int(match.group(1)) if match else 0


def dump_walk(rom, bios, states, vram_dir: pathlib.Path) -> list[dict]:
    vram_dir.mkdir(parents=True, exist_ok=True)
    results = []
    with Probe(rom, bios) as probe:
        for state_path in states:
            output = probe.command(f"load {state_path}")
            if not any(line.startswith("OK load") for line in output):
                raise ProbeError(
                    f"load failed for {state_path.name}: {' | '.join(output)}")
            vram = probe.dump(VRAM_BASE, VRAM_SIZE)
            regs = probe.dump(DISPCNT_ADDR, REGS_SIZE)
            name = state_path.stem
            (vram_dir / f"{name}.bin").write_bytes(vram)
            entry = {
                "step": step_sort_key(state_path),
                "name": name,
                "state": str(state_path),
                "vram_file": str(vram_dir / f"{name}.bin"),
                "vram_sha256": sha256_bytes(vram),
                "registers": decode_registers(regs),
            }
            entry.update(analyze_vram(vram))
            results.append(entry)
    return results


def dump_original(rom, bios, state_path, out_dir: pathlib.Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    with Probe(rom, bios) as probe:
        output = probe.command(f"load {state_path}")
        if not any(line.startswith("OK load") for line in output):
            raise ProbeError(
                f"load failed for {state_path}: {' | '.join(output)}")
        vram = probe.dump(VRAM_BASE, VRAM_SIZE)
        regs = probe.dump(DISPCNT_ADDR, REGS_SIZE)
    (out_dir / "vram.bin").write_bytes(vram)
    entry = {
        "rom": str(rom),
        "rom_sha256": sha256_file(rom),
        "state": str(state_path),
        "state_sha256": sha256_file(state_path),
        "vram_file": str(out_dir / "vram.bin"),
        "vram_sha256": sha256_bytes(vram),
        "registers": decode_registers(regs),
    }
    entry.update(analyze_vram(vram))
    return entry


def load_recorded_remake_dumps() -> list[dict]:
    """Project-recorded GPU dumps of the remake (baseline ROM 02bf3573)."""
    out = []
    for name in RECORDED_REMADE_DUMPS:
        directory = ARTIFACTS / name
        vram_path = directory / "vram.bin"
        io_path = directory / "io.bin"
        if not vram_path.exists() or not io_path.exists():
            continue
        vram = vram_path.read_bytes()
        io = io_path.read_bytes()
        entry = {
            "name": name,
            "directory": str(directory),
            "vram_bytes": len(vram),
            "vram_sha256": sha256_bytes(vram),
            "registers": decode_registers(io),
        }
        manifest_path = directory / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            entry["input_state"] = manifest.get("input_state")
        entry.update(analyze_vram(vram))
        bg = pick_overlay_bg(entry["registers"])
        entry["overlay_bg"] = bg
        if bg:
            entry["overlay_window"] = describe_overlay_window(
                vram, bg, REMAKE_OVERLAY_LOGICAL_TILES)
        out.append(entry)
    return out


# ---------------------------------------------------------------- main flow

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True,
                        help="path of the JSON report to write")
    parser.add_argument("--work-dir", default=str(REPO / "build" / "s49-vram"),
                        help="scratch directory (default build/s49-vram)")
    parser.add_argument("--rom", default=str(DEFAULT_ROM))
    parser.add_argument("--bios", default=str(DEFAULT_BIOS))
    parser.add_argument("--probe", default=str(DEFAULT_PROBE))
    parser.add_argument("--boot-lua", default=str(DEFAULT_BOOT_LUA))
    parser.add_argument("--original-rom", default=str(DEFAULT_ORIGINAL_ROM))
    parser.add_argument("--original-state", default=str(DEFAULT_ORIGINAL_STATE))
    parser.add_argument("--original-tiles", default=str(DEFAULT_ORIGINAL_TILES))
    parser.add_argument("--original-palette",
                        default=str(DEFAULT_ORIGINAL_PALETTE))
    parser.add_argument("--force-capture", action="store_true",
                        help="re-record the walk even if states already exist")
    args = parser.parse_args()

    work = pathlib.Path(args.work_dir)
    work.mkdir(parents=True, exist_ok=True)
    walk_dir = work / "walk"
    rom = pathlib.Path(args.rom)
    bios = pathlib.Path(args.bios)
    lua = pathlib.Path(args.boot_lua)

    if not rom.exists():
        print(f"ERR remake ROM missing: {rom}", file=sys.stderr)
        return 2

    rom_sha = sha256_file(rom)
    states = walk_states(walk_dir)
    done_marker = walk_dir / "done.json"
    reuse = (not args.force_capture and len(states) == len(WALK_KEYS) + 1
             and done_marker.exists())
    if reuse:
        try:
            marker = json.loads(done_marker.read_text(encoding="utf-8"))
            reuse = (marker.get("rom_sha256") == rom_sha
                     and marker.get("zero_input_frames") == WALK_ZERO_FRAMES)
        except Exception:
            reuse = False
    captured = None
    if reuse:
        print(f"reusing {len(states)} walk states in {walk_dir}")
    else:
        print(f"capturing walk -> {walk_dir} "
              f"(zero_input_frames={WALK_ZERO_FRAMES})")
        captured = capture_walk(rom, bios, lua, walk_dir, rom_sha)
        states = walk_states(walk_dir)
        if len(states) != len(WALK_KEYS) + 1:
            print(f"ERR expected {len(WALK_KEYS) + 1} walk states, "
                  f"got {len(states)}", file=sys.stderr)
            return 2

    print(f"dumping VRAM for {len(states)} walk steps")
    steps = dump_walk(rom, bios, states, work / "vram")

    print("dumping original ROM VRAM")
    original = dump_original(pathlib.Path(args.original_rom), bios,
                             pathlib.Path(args.original_state),
                             work / "original")

    print("loading project-recorded remake GPU dumps")
    recorded = load_recorded_remake_dumps()

    # ---------------------------------------------------- overlay locations
    overlay_tiles_path = pathlib.Path(args.original_tiles)
    original_tiles_blob = (overlay_tiles_path.read_bytes()
                           if overlay_tiles_path.exists() else b"")
    original_vram = (work / "original" / "vram.bin").read_bytes()
    original_locations = (find_blob(original_vram, original_tiles_blob)
                          if original_tiles_blob else [])
    original_overlay_bg = pick_overlay_bg(original["registers"])
    original_overlay = {
        "bg": original_overlay_bg,
        "tile_blob": str(overlay_tiles_path) if original_tiles_blob else None,
        "tile_blob_sha256": sha256_bytes(original_tiles_blob)
        if original_tiles_blob else None,
        "tile_blob_size": len(original_tiles_blob),
        "blob_offsets_in_vram": original_locations,
        "blob_vram_addresses": [f"0x{VRAM_BASE + off:08X}"
                                 for off in original_locations],
        "tile_bytes_4bpp": len(original_tiles_blob),
        "tile_bytes_8bpp": len(original_tiles_blob) * 2,
    }
    if original_overlay_bg:
        original_overlay["window"] = describe_overlay_window(
            original_vram, original_overlay_bg,
            len(original_tiles_blob) // 32 if original_tiles_blob else 32)

    # Remake: locate the overlay by register (char base + bpp) and measure the
    # tile bytes that char base actually holds.
    palette = compare_overlay_palettes(
        pathlib.Path(args.original_palette),
        pathlib.Path(args.original_tiles))

    remake_overlay = {"steps": []}
    for step in steps:
        bg = pick_overlay_bg(step["registers"])
        entry = {"step": step["step"], "name": step["name"], "bg": bg}
        if bg:
            entry["window"] = describe_overlay_window(
                (work / "vram" / f"{step['name']}.bin").read_bytes(),
                bg, REMAKE_OVERLAY_LOGICAL_TILES)
        remake_overlay["steps"].append(entry)

    # ---------------------------------------------------- 8bpp arithmetic
    original_char_base = (original_overlay_bg or {}).get("char_base")
    original_bpp = (original_overlay_bg or {}).get("bpp")
    tiles_4bpp = original_overlay["tile_bytes_4bpp"]
    tiles_8bpp = original_overlay["tile_bytes_8bpp"]
    delta = tiles_8bpp - tiles_4bpp

    # Where would the same logical tiles land if stored 8bpp?
    # 4bpp tile index n sits at byte n*32; 8bpp tile index n sits at n*64.
    landing = {}
    if original_locations:
        offset_4bpp = original_locations[0]
        index = offset_4bpp // 32
        offset_8bpp = index * 64
        landing = {
            "tile_index_at_4bpp": index,
            "offset_4bpp": offset_4bpp,
            "offset_8bpp_same_index": offset_8bpp,
            "offset_8bpp_hex": f"0x{offset_8bpp:05X}",
            "char_base_slot_at_8bpp": offset_8bpp // CHAR_BLOCK_SIZE,
            "byte_offset_kept": offset_4bpp,
            "tile_index_if_byte_offset_kept": offset_4bpp // 64,
        }

    peak_char = max(steps, key=lambda s: s["char_nonzero"])
    peak_screen = max(steps, key=lambda s: s["screen_nonzero"])
    peak_total = max(steps, key=lambda s: s["total_nonzero"])
    min_char_free = min(s["char_free_bytes"] for s in steps)
    overlay_step = next(
        (s for s in steps if s["name"] == "step-20-A"), peak_char)
    overlay_bg = pick_overlay_bg(overlay_step["registers"])
    overlay_char_block = None
    if overlay_bg:
        overlay_char_block = overlay_bg["char_base"] // CHAR_BLOCK_SIZE
    overlay_block_stats = None
    if overlay_char_block is not None:
        overlay_block_stats = overlay_step["char_blocks"][overlay_char_block]

    recorded_overlay = next(
        (r for r in recorded if r["name"] == "s49-remake-gpu-baseline-step20-v1"),
        recorded[0] if recorded else None)

    verdict = {
        "original_overlay_tiles_4bpp_bytes": tiles_4bpp,
        "original_overlay_tiles_8bpp_bytes": tiles_8bpp,
        "delta_bytes": delta,
        "original_overlay_bg": original_overlay_bg,
        "original_overlay_char_base": original_char_base,
        "original_overlay_bpp": original_bpp,
        "original_8bpp_landing": landing,
        "original_char_free_bytes": original["char_free_bytes"],
        "original_overlay_char_block_free_bytes": (
            original["char_blocks"][original_char_base // CHAR_BLOCK_SIZE][
                "free_bytes"] if original_char_base is not None else None),
        "remake_peak_char_nonzero": peak_char["char_nonzero"],
        "remake_peak_char_step": peak_char["name"],
        "remake_peak_char_free_bytes": peak_char["char_free_bytes"],
        "remake_min_char_free_bytes_over_walk": min_char_free,
        "remake_peak_screen_nonzero": peak_screen["screen_nonzero"],
        "remake_peak_screen_step": peak_screen["name"],
        "remake_peak_screen_free_bytes": peak_screen["screen_free_bytes"],
        "remake_peak_total_nonzero": peak_total["total_nonzero"],
        "remake_peak_total_step": peak_total["name"],
        "remake_overlay_step": overlay_step["name"],
        "remake_overlay_bg": overlay_bg,
        "remake_overlay_char_base": (overlay_bg or {}).get("char_base"),
        "remake_overlay_bpp": (overlay_bg or {}).get("bpp"),
        "remake_overlay_char_block_free_bytes": (
            overlay_block_stats["free_bytes"] if overlay_block_stats else None),
        "remake_overlay_char_block_nonzero": (
            overlay_block_stats["nonzero"] if overlay_block_stats else None),
        "remake_overlay_bytes_already_8bpp":
            REMAKE_OVERLAY_LOGICAL_TILES * 64,
        "remake_headroom_for_another_delta_bytes":
            (min_char_free - delta) if min_char_free is not None else None,
        "palette_all_colors_identical": palette.get("all_colors_identical"),
        "palette_uniform_index_shift": palette.get("uniform_index_shift"),
    }

    report = {
        "schema": "konoha.s49-vram-budget.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool": str(pathlib.Path(__file__).resolve()),
        "remake_rom": {
            "path": str(rom),
            "sha256": rom_sha,
            "size": rom.stat().st_size,
        },
        "walk": {
            "key_sequence": ",".join(WALK_KEYS),
            "zero_input_frames": WALK_ZERO_FRAMES,
            "settle_frames": WALK_SETTLE_FRAMES,
            "hold_frames": WALK_HOLD_FRAMES,
            "state_count": len(states),
            "reused_existing": captured is None,
            "capture": captured,
        },
        "layout_constants": {
            "vram_base": f"0x{VRAM_BASE:08X}",
            "vram_size": VRAM_SIZE,
            "char_region": [f"0x{CHAR_REGION[0]:05X}",
                            f"0x{CHAR_REGION[1]:05X}"],
            "screen_region": [f"0x{SCREEN_REGION[0]:05X}",
                              f"0x{SCREEN_REGION[1]:05X}"],
            "char_base_slots": [0, 0x4000, 0x8000, 0xC000],
            "overlay_priority": OVERLAY_PRIORITY,
            "remake_overlay_logical_tiles": REMAKE_OVERLAY_LOGICAL_TILES,
        },
        "remake": {
            "peak_char_nonzero": peak_char["char_nonzero"],
            "peak_char_step": peak_char["name"],
            "peak_screen_nonzero": peak_screen["screen_nonzero"],
            "peak_screen_step": peak_screen["name"],
            "peak_total_nonzero": peak_total["total_nonzero"],
            "peak_total_step": peak_total["name"],
            "min_char_free_bytes_over_walk": min_char_free,
            "steps": steps,
        },
        "original": original,
        "original_overlay": original_overlay,
        "remake_overlay": remake_overlay,
        "overlay_palette_comparison": palette,
        "recorded_remake_dumps": recorded,
        "verdict_inputs": verdict,
    }

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {out_path}")
    print(f"  remake peak char non-zero : {peak_char['char_nonzero']} "
          f"/ {CHAR_REGION[1] - CHAR_REGION[0]} "
          f"(free {peak_char['char_free_bytes']}) at {peak_char['name']}")
    print(f"  remake peak screen non-zero: {peak_screen['screen_nonzero']} "
          f"/ {SCREEN_REGION[1] - SCREEN_REGION[0]} "
          f"(free {peak_screen['screen_free_bytes']}) at {peak_screen['name']}")
    print(f"  remake overlay (step-20-A): bg={overlay_bg}")
    print(f"  original char non-zero: {original['char_nonzero']} "
          f"(free {original['char_free_bytes']})")
    print(f"  original overlay blob offsets in VRAM: {original_locations}")
    if recorded_overlay:
        print(f"  recorded baseline overlay dump: "
              f"{recorded_overlay['name']} char free "
              f"{recorded_overlay['char_free_bytes']}")
    if palette.get("available"):
        print(f"  overlay palette colour-exact: "
              f"{palette.get('all_colors_identical')} "
              f"(uniform index shift {palette.get('uniform_index_shift')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
