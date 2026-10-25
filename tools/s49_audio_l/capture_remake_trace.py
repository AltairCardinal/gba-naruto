#!/usr/bin/env python3
"""Capture the remake's runtime audio-event trace with the headless mGBA probe.

Stream L (S49 audio wiring).  The remake now records every battle audio
dispatch into a fixed IWRAM ring buffer (``konoha::battle_audio_trace_buffer``,
see ``game/include/konoha/battle_audio_event_trace.h``).  This script

1. reads the built ELF's symbol table to find the ring buffer, its write index
   and its frame counter,
2. drives the remake ROM with the same input walk stream J used
   (600 zero-input frames, Down, Down, A x 32, 300 tail frames),
3. dumps the trace block every frame so each dispatch can be placed on an
   exact emulator frame.

The PSG/DMA register block cannot be used for this: it stays constant while a
Maxmod stream plays, so it carries no cue information.

Usage:
    python tools/s49_audio_l/capture_remake_trace.py --out build/s49-audio-l
"""
from __future__ import annotations

import argparse
import pathlib
import re
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
PROBE_DIR = REPO / "tools" / "s49_audio_probe"
if str(PROBE_DIR) not in sys.path:
    sys.path.insert(0, str(PROBE_DIR))

from probe_driver import (  # noqa: E402  (read-only reuse of stream J's driver)
    KEY_A, KEY_DOWN, Probe, framedump_command, keyseq_command,
    read_dump_series, sha256_file, write_json,
)

REMAKE_ROOT = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\butano-sequel")
DEFAULT_ROM = REMAKE_ROOT / "butano-sequel.gba"
DEFAULT_ELF = REMAKE_ROOT / "butano-sequel.elf"
TRACE_HEADER = REMAKE_ROOT / "game" / "include" / "konoha" / "battle_audio_event_trace.h"

ZERO_INPUT_FRAMES = 600
HOLD_FRAMES = 4
SETTLE_FRAMES = 90
A_ROUNDS = 32
TAIL_FRAMES = 300

TRACE_SYMBOLS = {
    "write_index": "battle_audio_trace_write_index",
    "frame_counter": "battle_audio_trace_frame",
}
ENTRY_SIZE = 8
CAPACITY = 256

TRACE_ADDRESS_RE = re.compile(
    r"battle_audio_trace_buffer_address\s*=\s*(0x[0-9A-Fa-f]+|\d+)")


def trace_buffer_address(header: pathlib.Path) -> int:
    """The fixed EWRAM address of the ring buffer, read out of the header."""
    text = header.read_text(encoding="utf-8")
    match = TRACE_ADDRESS_RE.search(text)
    if not match:
        raise SystemExit(
            f"ERR battle_audio_trace_buffer_address not found in {header}")
    return int(match.group(1), 0)


def read_elf_symbols(path: pathlib.Path) -> dict[str, int]:
    """symbol name -> address for a 32-bit little endian ELF."""
    data = path.read_bytes()
    if data[:4] != b"\x7fELF":
        raise ValueError(f"not an ELF: {path}")
    e_shoff, = struct.unpack_from("<I", data, 0x20)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", data, 0x2E)

    def section(index: int) -> dict:
        offset = e_shoff + index * e_shentsize
        (name, typ, flags, addr, off, size, link, info, align,
         entsize) = struct.unpack_from("<IIIIIIIIII", data, offset)
        return {"name": name, "type": typ, "flags": flags, "addr": addr,
                "offset": off, "size": size, "link": link, "info": info,
                "align": align, "entsize": entsize}

    def string_at(table: bytes, index: int) -> str:
        end = table.find(b"\x00", index)
        return table[index:end].decode("ascii", "replace")

    shstr = section(e_shstrndx)
    shstr_table = data[shstr["offset"]:shstr["offset"] + shstr["size"]]

    symbols: dict[str, int] = {}
    for index in range(e_shnum):
        header = section(index)
        if header["type"] != 2:  # SHT_SYMTAB
            continue
        link = section(header["link"])
        link_table = data[link["offset"]:link["offset"] + link["size"]]
        entry_size = header["entsize"] or 16
        count = header["size"] // entry_size
        for entry in range(count):
            base = header["offset"] + entry * entry_size
            name_index, value, _size, _info, _other, _shndx = struct.unpack_from(
                "<IIIBBH", data, base)
            if name_index == 0:
                continue
            name = string_at(link_table, name_index)
            symbols.setdefault(name, value)
    return symbols


def locate_trace(elf: pathlib.Path, header: pathlib.Path) -> dict:
    symbols = read_elf_symbols(elf)
    result = {"buffer": trace_buffer_address(header)}
    for key, needle in TRACE_SYMBOLS.items():
        matches = {name: address for name, address in symbols.items()
                   if needle in name}
        if not matches:
            raise SystemExit(
                f"ERR symbol {needle!r} not found in {elf}; is the audio event "
                f"trace compiled in?")
        # An inline variable can carry several mangled aliases; the shortest
        # name is the plain one.
        name = sorted(matches, key=len)[0]
        result[key] = matches[name]
        result[f"{key}_symbol"] = name
    return result


def capture(out_dir: pathlib.Path, rom: pathlib.Path, elf: pathlib.Path,
            header: pathlib.Path) -> dict:
    trace = locate_trace(elf, header)
    buffer_address = trace["buffer"]
    # The write index and the frame counter are inline variables; the probe
    # only needs the ring buffer, the write index is derived from the dump
    # content.
    dump_address = buffer_address
    dump_length = CAPACITY * ENTRY_SIZE
    dump_dir = out_dir / "remake-trace"
    dump_dir.mkdir(parents=True, exist_ok=True)

    with Probe(rom, cwd=dump_dir) as probe:
        try:
            probe.run(framedump_command(
                ZERO_INPUT_FRAMES, dump_address, dump_length, 0x000, "z0"))
            probe.run(keyseq_command(
                HOLD_FRAMES, SETTLE_FRAMES, 1, dump_address, dump_length,
                KEY_DOWN, "d"))
            probe.run(keyseq_command(
                HOLD_FRAMES, SETTLE_FRAMES, 1, dump_address, dump_length,
                KEY_DOWN, "e"))
            probe.run(keyseq_command(
                HOLD_FRAMES, SETTLE_FRAMES, A_ROUNDS, dump_address, dump_length,
                KEY_A, "a"))
            probe.run(framedump_command(
                TAIL_FRAMES, dump_address, dump_length, 0x000, "z1"))
        except Exception:
            stderr = probe.stderr
            print(f"probe stderr ({len(stderr)} lines), first 30:")
            for line in stderr[:30]:
                print("   ", line)
            raise

    series = (read_dump_series(dump_dir, "z0") + read_dump_series(dump_dir, "d")
              + read_dump_series(dump_dir, "e") + read_dump_series(dump_dir, "a")
              + read_dump_series(dump_dir, "z1"))
    return {"trace": trace, "series": series, "dump_address": dump_address}


def decode_events(series: list[bytes]) -> list[dict]:
    """Turn the per-frame dumps into the dispatch event list.

    The ring buffer keeps its content, so a dispatch is visible as the slot
    that changed.  An all-zero slot is an empty slot (cue 0 is not a valid
    cue), which is what the freshly cleared buffer looks like.
    """
    events: list[dict] = []
    previous: list[tuple[int, int, int, int]] | None = None
    for frame, blob in enumerate(series):
        entries = []
        for index in range(min(CAPACITY, len(blob) // ENTRY_SIZE)):
            raw = blob[index * ENTRY_SIZE:(index + 1) * ENTRY_SIZE]
            frame_field, kind, cue, handle = struct.unpack("<HBBH", raw[:6])
            entries.append((frame_field, kind, cue, handle))
        if previous is None:
            previous = entries
            continue
        for index, entry in enumerate(entries):
            if entry == previous[index]:
                continue
            if entry == (0, 0, 0, 0):
                continue
            frame_field, kind, cue, handle = entry
            events.append({
                "emulator_frame": frame,
                "trace_frame": frame_field,
                "kind": "music" if kind == 0 else "sound",
                "cue": cue,
                "handle": handle,
                "slot": index,
            })
        previous = entries
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(REPO / "build" / "s49-audio-l"))
    parser.add_argument("--rom", default=str(DEFAULT_ROM))
    parser.add_argument("--elf", default=str(DEFAULT_ELF))
    parser.add_argument("--trace-header", default=str(TRACE_HEADER))
    parser.add_argument("--decode-only", action="store_true")
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out)
    rom = pathlib.Path(args.rom)
    elf = pathlib.Path(args.elf)
    trace_header = pathlib.Path(args.trace_header)
    if not rom.is_file():
        raise SystemExit(f"ERR remake ROM missing: {rom}")
    if not elf.is_file():
        raise SystemExit(f"ERR remake ELF missing: {elf}")

    if args.decode_only:
        dump_dir = out_dir / "remake-trace"
        series = (read_dump_series(dump_dir, "z0")
                  + read_dump_series(dump_dir, "d")
                  + read_dump_series(dump_dir, "e")
                  + read_dump_series(dump_dir, "a")
                  + read_dump_series(dump_dir, "z1"))
        trace = locate_trace(elf, trace_header)
        dump_address = trace["buffer"]
    else:
        print(f"capturing remake trace ... rom={rom.name}")
        captured = capture(out_dir, rom, elf, trace_header)
        series = captured["series"]
        trace = captured["trace"]
        dump_address = captured["dump_address"]

    events = decode_events(series)
    print(f"  dumped frames: {len(series)}")
    print(f"  trace buffer: 0x{dump_address:08X}")
    print(f"  trace events: {len(events)}")
    for event in events[:20]:
        print(f"    f{event['emulator_frame']:5d} {event['kind']:5s} "
              f"cue {event['cue']}")

    write_json(out_dir / "remake_trace.json", {
        "side": "remake",
        "rom": str(rom),
        "rom_sha256": sha256_file(rom),
        "elf": str(elf),
        "trace_buffer_address": dump_address,
        "trace_symbols": {
            key: trace[f"{key}_symbol"] for key in TRACE_SYMBOLS},
        "frame_count": len(series),
        "events": events,
    })
    print(f"wrote {out_dir / 'remake_trace.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
