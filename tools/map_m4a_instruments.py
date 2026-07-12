#!/usr/bin/env python3
"""Map executed m4a note events through voicegroups to terminal instruments."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

try:
    from tools.extract_audio_assets import parse_wave
    from tools.render_m4a_midi import execute_track
except ModuleNotFoundError:  # direct ``python tools/...`` execution
    from extract_audio_assets import parse_wave
    from render_m4a_midi import execute_track

ROM_BASE = 0x08000000
TONE_SIZE = 12


def parse_tone(rom: bytes, offset: int) -> dict:
    if not 0 <= offset <= len(rom) - TONE_SIZE:
        raise ValueError(f"tone offset 0x{offset:X} outside ROM")
    raw = rom[offset:offset + TONE_SIZE]
    return {
        "offset": offset,
        "type": raw[0],
        "key": raw[1],
        "length": raw[2],
        "pan_sweep": raw[3],
        "pointer": int.from_bytes(raw[4:8], "little"),
        "attack": raw[8],
        "decay": raw[9],
        "sustain": raw[10],
        "release": raw[11],
    }


def resolve_tone(rom: bytes, voicegroup_offset: int, voice: int, key: int) -> dict:
    parent = parse_tone(rom, voicegroup_offset + voice * TONE_SIZE)
    if parent["type"] != 0x80:
        return {"parent": parent, "terminal": parent, "drum": False}
    table = parent["pointer"] - ROM_BASE
    child = parse_tone(rom, table + key * TONE_SIZE)
    if child["type"] == 0x80:
        raise ValueError(f"nested drum tone at 0x{child['offset']:X} is unsupported")
    return {"parent": parent, "terminal": child, "drum": True}


def analyze(rom: bytes, bank: dict, decoded: dict) -> dict:
    command_map = {command["offset"]: command for track in decoded["tracks"] for command in track["commands"]}
    tracks = {track["offset"]: track for track in decoded["tracks"]}
    terminal_counts: Counter[int] = Counter()
    wave_counts: Counter[int] = Counter()
    song_rows = []
    drum_notes = 0
    missing = []
    for song in bank["entries"]:
        voicegroup = song["voicegroup_ptr"] - ROM_BASE
        song_types: Counter[int] = Counter()
        song_waves: Counter[int] = Counter()
        song_drums = 0
        for pointer in song["track_ptrs"]:
            timeline = execute_track(tracks[pointer - ROM_BASE], command_map)
            for event in timeline["events"]:
                if event["type"] != "note":
                    continue
                resolved = resolve_tone(rom, voicegroup, event["voice"], event["key"])
                terminal = resolved["terminal"]
                terminal_counts[terminal["type"]] += 1
                song_types[terminal["type"]] += 1
                if resolved["drum"]:
                    drum_notes += 1
                    song_drums += 1
                if terminal["type"] == 0:
                    wave_offset = terminal["pointer"] - ROM_BASE
                    wave = parse_wave(rom, wave_offset)
                    if wave is None:
                        missing.append({"sound_id": song["sound_id"], "voice": event["voice"], "key": event["key"], "wave_offset": wave_offset})
                    else:
                        wave_counts[wave_offset] += 1
                        song_waves[wave_offset] += 1
        song_rows.append({
            "sound_id": song["sound_id"],
            "note_count": sum(song_types.values()),
            "drum_note_count": song_drums,
            "terminal_type_counts": {f"0x{key:02X}": value for key, value in sorted(song_types.items())},
            "wave_offsets": [f"0x{offset:06X}" for offset in sorted(song_waves)],
        })
    note_count = sum(terminal_counts.values())
    direct_count = terminal_counts[0]
    return {
        "format": "Executed m4a note -> voicegroup -> terminal tone coverage",
        "song_count": len(song_rows),
        "note_count": note_count,
        "drum_note_count": drum_notes,
        "terminal_type_counts": {f"0x{key:02X}": value for key, value in sorted(terminal_counts.items())},
        "directsound_note_count": direct_count,
        "directsound_coverage": direct_count / note_count if note_count else 0,
        "unique_wave_count": len(wave_counts),
        "missing_wave_count": len(missing),
        "missing_waves": missing,
        "wave_usage": [{"offset": offset, "offset_hex": f"0x{offset:06X}", "note_count": count} for offset, count in sorted(wave_counts.items())],
        "songs": song_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument("--bank", type=Path, default=Path("sequel/content/audio/bank.json"))
    parser.add_argument("--decoded", type=Path, default=Path("build/audio-v2/tracks-decoded.json"))
    parser.add_argument("--output", type=Path, default=Path("build/audio-v2/instrument-map.json"))
    args = parser.parse_args()
    result = analyze(
        args.rom.read_bytes(),
        json.loads(args.bank.read_text(encoding="utf-8")),
        json.loads(args.decoded.read_text(encoding="utf-8")),
    )
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "song_count", "note_count", "drum_note_count", "terminal_type_counts",
        "directsound_coverage", "unique_wave_count", "missing_wave_count"
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
