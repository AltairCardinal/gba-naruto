#!/usr/bin/env python3
"""Write-back path for the m4a SongHeaders behind the sound-ID table.

The sound-ID table at ROM file ``0x465B70`` holds 8 bytes per row; each row
points at a **m4a SongHeader**:

    +0x00 u8   track_count
    +0x01 u8   block_count
    +0x02 u16  pad
    +0x04 u32  voicegroup_ptr      (12-byte tone records)
    +0x08 u32  track_ptr[track_count]

Writing a *track pointer* is what lets the sequel swap a piece of music
without touching anything else.  The **block format of a track is not
proved**, so -- exactly like the ``units`` offset table -- the writer only
accepts a pointer that already occurs in the same table (a "repoint to an
existing native target"); anything else is refused rather than guessed.

Write-back model: copy the native header, overwrite only the named track
pointer, keep every other byte raw.

Usage:
    python tools/import_audio_song.py rom/base.gba --sound-id 1
    python tools/import_audio_song.py rom/base.gba --sound-id 1 \\
        --set track0=0x08535CFC --out build/naruto.gba
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lib.io import write_json  # noqa: E402

SOUND_ID_TABLE = 0x465B70
SOUND_ID_ROW_SIZE = 8
SOUND_ID_COUNT = 159
ROM_BASE = 0x08000000
HEADER_SIZE = 8


class WriteBackError(ValueError):
    """Raised when an author change is not representable in the ROM record."""


def sound_id_offset(sound_id: int) -> int:
    if not 0 <= sound_id < SOUND_ID_COUNT:
        raise WriteBackError(
            f"sound id {sound_id} outside 0..{SOUND_ID_COUNT - 1}")
    return SOUND_ID_TABLE + sound_id * SOUND_ID_ROW_SIZE


def read_song_header(rom: bytes, sound_id: int) -> dict:
    """One SongHeader, resolved through the sound-ID table."""
    off = sound_id_offset(sound_id)
    if off + 4 > len(rom):
        raise WriteBackError("ROM too small for the sound id table")
    pointer = struct.unpack_from("<I", rom, off)[0]
    if not ROM_BASE <= pointer < ROM_BASE + len(rom):
        raise WriteBackError(
            f"sound id {sound_id} points outside the ROM (0x{pointer:08X})")
    base = pointer - ROM_BASE
    track_count = rom[base]
    block_count = rom[base + 1]
    voicegroup = struct.unpack_from("<I", rom, base + 4)[0]
    tracks = [struct.unpack_from("<I", rom, base + HEADER_SIZE + i * 4)[0]
              for i in range(track_count)]
    return {
        "sound_id": sound_id,
        "pointer": pointer,
        "offset": base,
        "offset_hex": f"0x{base:06X}",
        "track_count": track_count,
        "block_count": block_count,
        "voicegroup_ptr": voicegroup,
        "track_ptrs": tracks,
    }


def native_track_pointers(rom: bytes) -> set[int]:
    """Every track pointer the ROM already uses (the safe target set)."""
    out: set[int] = set()
    for sid in range(SOUND_ID_COUNT):
        off = SOUND_ID_TABLE + sid * SOUND_ID_ROW_SIZE
        if off + 4 > len(rom):
            break
        pointer = struct.unpack_from("<I", rom, off)[0]
        if not ROM_BASE <= pointer < ROM_BASE + len(rom):
            continue
        base = pointer - ROM_BASE
        count = rom[base]
        if count > 64:
            continue
        for i in range(count):
            track_off = base + HEADER_SIZE + i * 4
            if track_off + 4 > len(rom):
                break
            out.add(struct.unpack_from("<I", rom, track_off)[0])
    return out


def write_song_track(rom: bytearray, sound_id: int, track_index: int,
                     pointer: int) -> dict:
    """Repoint one track of a SongHeader, in place.

    Only a pointer that already occurs as a track pointer somewhere in the
    sound table is accepted: the track block format is not proved, so a new
    target cannot be validated.
    """
    header = read_song_header(bytes(rom), sound_id)
    if not 0 <= track_index < header["track_count"]:
        raise WriteBackError(
            f"track {track_index} outside 0..{header['track_count'] - 1}")
    value = int(pointer)
    if value not in native_track_pointers(bytes(rom)):
        raise WriteBackError(
            f"track pointer 0x{value:08X} does not occur in the sound table; "
            f"the track block format is not proved, so only repointing to an "
            f"existing native track is allowed")
    off = header["offset"] + HEADER_SIZE + track_index * 4
    rom[off:off + 4] = value.to_bytes(4, "little")
    return {
        "sound_id": sound_id,
        "track_index": track_index,
        "offset": off,
        "pointer": value,
    }


# --- CLI --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("rom", help="ROM path (a copy is patched, never the original)")
    parser.add_argument("--sound-id", type=int, required=True)
    parser.add_argument("--set", action="append", default=[], dest="sets",
                        help="trackN=pointer change (repeatable)")
    parser.add_argument("--out", help="write the patched ROM copy here")
    parser.add_argument("--json", help="write the read-back report here")
    args = parser.parse_args(argv)

    rom_path = pathlib.Path(args.rom)
    rom = bytearray(rom_path.read_bytes())

    changes: dict[int, int] = {}
    for pair in args.sets:
        if "=" not in pair:
            raise SystemExit(f"--set expects trackN=pointer, got {pair!r}")
        key, raw = pair.split("=", 1)
        key = key.strip().lower()
        if not key.startswith("track"):
            raise SystemExit(f"--set expects trackN=pointer, got {pair!r}")
        changes[int(key[5:])] = int(raw.strip(), 0)
    if not changes:
        parser.error("no --set change given")

    applied = []
    for track_index, pointer in sorted(changes.items()):
        applied.append(write_song_track(rom, args.sound_id, track_index, pointer))

    if args.out:
        out_path = pathlib.Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(bytes(rom))

    readback = read_song_header(bytes(rom), args.sound_id)
    report = {"applied": applied, "read_back": readback}
    if args.json:
        write_json(args.json, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
