#!/usr/bin/env python3
"""Structurally decode MP2K/m4a track bytecode extracted from the ROM."""
from __future__ import annotations

import argparse
import json
import struct
from collections import Counter
from pathlib import Path

ROM_BASE = 0x08000000
WAIT_TICKS = tuple(range(25)) + (28, 30, 32, 36, 40, 42, 44, 48, 52, 54, 56, 60, 64, 66, 68, 72, 76, 78, 80, 84, 88, 90, 92, 96)
NOTE_TICKS = tuple(range(1, 25)) + (28, 30, 32, 36, 40, 42, 44, 48, 52, 54, 56, 60, 64, 66, 68, 72, 76, 78, 80, 84, 88, 90, 92, 96)
WAIT_NAMES = {0x80 + index: f"W{ticks:02d}" for index, ticks in enumerate(WAIT_TICKS)}
NOTE_NAMES = {0xD0 + index: f"N{ticks:02d}" for index, ticks in enumerate(NOTE_TICKS)}
ONE_ARG = {
    0xBA: "PRIO", 0xBB: "TEMPO", 0xBC: "KEYSH", 0xBD: "VOICE",
    0xBE: "VOL", 0xBF: "PAN", 0xC0: "BEND", 0xC1: "BENDR",
    0xC2: "LFOS", 0xC3: "LFODL", 0xC4: "MOD", 0xC5: "MODT",
    0xC8: "TUNE",
}


class DecodeError(ValueError):
    pass


def decode_track(raw: bytes, base_offset: int) -> list[dict]:
    commands: list[dict] = []
    cursor = 0
    running_note: int | None = None
    while cursor < len(raw):
        start = cursor
        opcode = raw[cursor]
        explicit = opcode >= 0x80
        if explicit:
            cursor += 1
        elif running_note is not None:
            opcode = running_note
        else:
            raise DecodeError(f"parameter 0x{raw[cursor]:02X} without running note at 0x{base_offset + cursor:X}")

        item: dict = {"offset": base_offset + start, "offset_hex": f"0x{base_offset + start:06X}", "opcode": opcode}
        if opcode in WAIT_NAMES:
            item["name"] = WAIT_NAMES[opcode]
        elif opcode == 0xB1:
            item["name"] = "FINE"
        elif opcode in (0xB2, 0xB3):
            item["name"] = "GOTO" if opcode == 0xB2 else "PATT"
            if cursor + 4 > len(raw):
                raise DecodeError(f"truncated {item['name']} at 0x{base_offset + start:X}")
            pointer = struct.unpack_from("<I", raw, cursor)[0]
            cursor += 4
            item["target"] = pointer
            item["target_offset"] = pointer - ROM_BASE
        elif opcode == 0xB4:
            item["name"] = "PEND"
        elif opcode == 0xB5:
            item["name"] = "REPT"
            if cursor + 5 > len(raw):
                raise DecodeError(f"truncated REPT at 0x{base_offset + start:X}")
            item["count"] = raw[cursor]
            item["target"] = struct.unpack_from("<I", raw, cursor + 1)[0]
            item["target_offset"] = item["target"] - ROM_BASE
            cursor += 5
        elif opcode == 0xB9:
            item["name"] = "MEMACC"
            if cursor + 3 > len(raw):
                raise DecodeError(f"truncated MEMACC at 0x{base_offset + start:X}")
            item["args"] = list(raw[cursor:cursor + 3])
            cursor += 3
        elif opcode in ONE_ARG:
            item["name"] = ONE_ARG[opcode]
            if cursor >= len(raw):
                raise DecodeError(f"truncated {item['name']} at 0x{base_offset + start:X}")
            item["value"] = raw[cursor]
            cursor += 1
        elif opcode == 0xCD:
            item["name"] = "XCMD"
            if cursor + 2 > len(raw):
                raise DecodeError(f"truncated XCMD at 0x{base_offset + start:X}")
            item["args"] = list(raw[cursor:cursor + 2])
            cursor += 2
        elif opcode == 0xCE:
            item["name"] = "EOT"
            if cursor < len(raw) and raw[cursor] < 0x80:
                item["key"] = raw[cursor]
                cursor += 1
        elif opcode == 0xCF or opcode in NOTE_NAMES:
            item["name"] = "TIE" if opcode == 0xCF else NOTE_NAMES[opcode]
            running_note = opcode
            args = []
            while cursor < len(raw) and raw[cursor] < 0x80 and len(args) < 3:
                args.append(raw[cursor])
                cursor += 1
            item["args"] = args
        else:
            raise DecodeError(f"unknown opcode 0x{opcode:02X} at 0x{base_offset + start:X}")
        item["size"] = cursor - start
        item["raw_hex"] = raw[start:cursor].hex()
        commands.append(item)
    return commands


def decode_manifest(input_dir: Path) -> dict:
    assets = json.loads((input_dir / "manifest.json").read_text(encoding="utf-8"))
    decoded = []
    counts: Counter[str] = Counter()
    control_targets = []
    for track in assets["tracks"]:
        offset = track["offset"]
        raw = (input_dir / "tracks" / f"track_{offset:06X}.bin").read_bytes()
        commands = decode_track(raw, offset)
        counts.update(command["name"] for command in commands)
        for command in commands:
            if "target_offset" in command:
                control_targets.append(command["target_offset"])
        decoded.append({"offset": offset, "size": len(raw), "command_count": len(commands), "commands": commands})
    known_ranges = [(track["offset"], track["offset"] + track["size"]) for track in assets["tracks"]]
    bad_targets = [target for target in control_targets if not any(start <= target < end for start, end in known_ranges)]
    tracks_with_fine = sum(any(command["name"] == "FINE" for command in item["commands"]) for item in decoded)
    looping_tracks = sum(any(command["name"] == "GOTO" for command in item["commands"]) for item in decoded)
    note_count = sum(
        command["name"] == "TIE" or command["name"].startswith("N")
        for item in decoded for command in item["commands"]
    )
    return {
        "format": "MP2K/m4a structural track command decode",
        "track_count": len(decoded),
        "command_count": sum(item["command_count"] for item in decoded),
        "opcode_counts": dict(sorted(counts.items())),
        "control_target_count": len(control_targets),
        "invalid_control_targets": bad_targets,
        "tracks_with_fine": tracks_with_fine,
        "looping_tracks": looping_tracks,
        "note_count": note_count,
        "tracks": decoded,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path, nargs="?", default=Path("build/audio-v2"))
    parser.add_argument("--output", type=Path, default=Path("build/audio-v2/tracks-decoded.json"))
    args = parser.parse_args()
    result = decode_manifest(args.input_dir)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "track_count", "command_count", "control_target_count",
        "invalid_control_targets", "tracks_with_fine", "looping_tracks", "note_count"
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
