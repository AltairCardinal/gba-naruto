#!/usr/bin/env python3
"""Extractor for the m4a SongHeaders behind the sound-ID table.

The sound-ID table at ROM file ``0x465B70`` holds 8 bytes per row; each row
points at a **m4a SongHeader**:

    +0x00 u8   track_count
    +0x01 u8   block_count
    +0x02 u16  pad
    +0x04 u32  voicegroup_ptr      (12-byte tone records)
    +0x08 u32  track_ptr[track_count]

Five of those headers are what the legacy content banks called ``story``,
``story-b``, ``story-c``, ``story-d`` and ``story-e`` -- their bases were
4 bytes late because the legacy extractor anchored on the ``voicegroup_ptr``
field instead of the header start.  Proved in
``notes/evidence/story-table-family-20261020.md``.

The native reader of the voicegroup field is ``0x0809B242 ldr r0,[r7,#4]``;
the sound id is computed as ``sound_id * 8`` at ``0x0809AAC8``.

The tool fails loudly (non-zero exit) when the ROM does not have the layout
it assumes.

Usage:
    python tools/audio_song_headers.py rom/base.gba
    python tools/audio_song_headers.py rom/base.gba --sound-id 2
    python tools/audio_song_headers.py rom/base.gba --json build/audio-songs.json
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

# The five legacy banks and the sound id they actually are, with the
# header's true base (the legacy base was 4 bytes late).
LEGACY_BANKS = {
    1: ("story", 0x536368),
    2: ("story-b", 0x536BC4),
    8: ("story-c", 0x538FEC),
    11: ("story-d", 0x53AB74),
    14: ("story-e", 0x53C3BC),
}

# The native reader of the voicegroup pointer, and the id computation.
VOICE_GROUP_READER = 0x0809B242
SOUND_ID_SCALER = 0x0809AAC8

# The "no song" sentinel header: zero tracks and this voicegroup value.
EMPTY_HEADER = 0x40000000


class SongHeaderError(ValueError):
    """Raised when the ROM does not have the layout this tool assumes."""


def read_sound_id_table(rom: bytes) -> list[int]:
    """The SongHeader pointer of every sound id (0 when the row is empty)."""
    out: list[int] = []
    for sid in range(SOUND_ID_COUNT):
        off = SOUND_ID_TABLE + sid * SOUND_ID_ROW_SIZE
        if off + 4 > len(rom):
            break
        out.append(struct.unpack_from("<I", rom, off)[0])
    return out


def read_song_header(rom: bytes, pointer: int) -> dict:
    """Parse one SongHeader at a ROM address."""
    if not 0x08000000 <= pointer < 0x08000000 + len(rom):
        raise SongHeaderError(
            f"pointer 0x{pointer:08X} is outside the ROM image")
    off = pointer - 0x08000000
    track_count = rom[off]
    block_count = rom[off + 1]
    voicegroup = struct.unpack_from("<I", rom, off + 4)[0]
    tracks = []
    for i in range(track_count):
        tracks.append(struct.unpack_from("<I", rom, off + 8 + i * 4)[0])
    return {
        "pointer": pointer,
        "offset": off,
        "offset_hex": f"0x{off:06X}",
        "track_count": track_count,
        "block_count": block_count,
        "voicegroup_ptr": voicegroup,
        "track_ptrs": tracks,
    }


def validate(rom: bytes, table: list[int]) -> list[str]:
    problems: list[str] = []
    if len(table) < 15:
        problems.append(f"sound id table has only {len(table)} rows")
    for sid, pointer in enumerate(table):
        if pointer == 0:
            continue
        try:
            header = read_song_header(rom, pointer)
        except SongHeaderError as exc:
            problems.append(f"sound id {sid}: {exc}")
            continue
        if header["track_count"] == 0 and header["voicegroup_ptr"] == EMPTY_HEADER:
            # the "no song" sentinel header (0 tracks, sentinel voicegroup)
            header["empty"] = True
            continue
        header["empty"] = False
        if header["track_count"] > 64:
            problems.append(
                f"sound id {sid}: track_count {header['track_count']} is absurd")
        for i, track in enumerate(header["track_ptrs"]):
            if not 0x08000000 <= track < 0x08000000 + len(rom):
                problems.append(
                    f"sound id {sid}: track {i} pointer 0x{track:08X} "
                    f"is outside the ROM")
        if not 0x08000000 <= header["voicegroup_ptr"] < 0x08000000 + len(rom):
            problems.append(
                f"sound id {sid}: voicegroup 0x{header['voicegroup_ptr']:08X} "
                f"is outside the ROM")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("rom", nargs="?", default="rom/base.gba")
    parser.add_argument("--sound-id", type=int,
                        help="only show this sound id")
    parser.add_argument("--json", help="write the machine-readable report here")
    args = parser.parse_args(argv)

    rom_path = pathlib.Path(args.rom)
    if not rom_path.is_file():
        print(f"ROM not found: {rom_path}", file=sys.stderr)
        return 1
    rom = rom_path.read_bytes()

    table = read_sound_id_table(rom)
    problems = validate(rom, table)

    rows = []
    for sid, pointer in enumerate(table):
        if pointer == 0:
            continue
        if args.sound_id is not None and sid != args.sound_id:
            continue
        try:
            header = read_song_header(rom, pointer)
        except SongHeaderError as exc:
            problems.append(f"sound id {sid}: {exc}")
            continue
        if header["track_count"] == 0 and header["voicegroup_ptr"] == EMPTY_HEADER:
            continue
        header["sound_id"] = sid
        header["legacy_bank"] = LEGACY_BANKS.get(sid, (None, None))[0]
        rows.append(header)

    report = {
        "rom": str(rom_path),
        "sound_id_table": SOUND_ID_TABLE,
        "sound_id_table_hex": f"0x{SOUND_ID_TABLE:06X}",
        "row_size": SOUND_ID_ROW_SIZE,
        "voicegroup_reader": f"0x{VOICE_GROUP_READER:08X}",
        "sound_id_scaler": f"0x{SOUND_ID_SCALER:08X}",
        "headers": rows,
        "problems": problems,
    }
    if args.json:
        write_json(args.json, report)

    print(f"sound id table 0x{SOUND_ID_TABLE:06X}, {SOUND_ID_ROW_SIZE} bytes/row")
    print(f"voicegroup reader 0x{VOICE_GROUP_READER:08X}, "
          f"id = sound_id*8 at 0x{SOUND_ID_SCALER:08X}")
    print()
    print(f'{"id":>4} {"header":<10} {"tracks":>6} {"blocks":>6} '
          f'{"voicegroup":<12} legacy bank')
    for header in rows:
        bank = header["legacy_bank"] or ""
        print(f'{header["sound_id"]:>4} {header["offset_hex"]:<10} '
              f'{header["track_count"]:>6} {header["block_count"]:>6} '
              f'0x{header["voicegroup_ptr"]:08X}  {bank}')
    print()
    if problems:
        print("PROBLEMS:")
        for problem in problems:
            print("  -", problem)
        return 1
    print("SELF-CHECK: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
