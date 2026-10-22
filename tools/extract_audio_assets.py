#!/usr/bin/env python3
"""Extract m4a track streams, voicegroups, and reachable DirectSound waves."""
from __future__ import annotations

import argparse
import json
import struct
import wave
from pathlib import Path

try:
    from tools.extract_audio_resource_sets import MASTER_OFFSET, ROM_BASE, extract
except ModuleNotFoundError:  # direct ``python tools/...`` execution
    from extract_audio_resource_sets import MASTER_OFFSET, ROM_BASE, extract

TONE_SIZE = 12
WAVE_HEADER_SIZE = 16
FREQ_SCALE = 1024
VALID_TONE_TYPES = {0, 1, 2, 3, 4, 8, 9, 10, 11, 12, 0x40, 0x80}


def rom_offset(pointer: int, size: int) -> int:
    offset = pointer - ROM_BASE
    if not 0 <= offset < size:
        raise ValueError(f"pointer 0x{pointer:08X} is outside ROM")
    return offset


def parse_wave(rom: bytes, offset: int) -> dict | None:
    if offset + WAVE_HEADER_SIZE > len(rom):
        return None
    type_flags, status, frequency_raw, loop_start, sample_count = struct.unpack_from(
        "<HHIII", rom, offset
    )
    end = offset + WAVE_HEADER_SIZE + sample_count
    if frequency_raw == 0 or sample_count == 0 or loop_start > sample_count or end > len(rom):
        return None
    sample_rate = round(frequency_raw / FREQ_SCALE)
    if not 1000 <= sample_rate <= 96000:
        return None
    return {
        "offset": offset,
        "offset_hex": f"0x{offset:06X}",
        "type_flags": type_flags,
        "status": status,
        "frequency_raw": frequency_raw,
        "sample_rate": sample_rate,
        "loop_start": loop_start,
        "sample_count": sample_count,
        "data_offset": offset + WAVE_HEADER_SIZE,
        "data_end": end,
    }


def write_wave(path: Path, signed_pcm: bytes, sample_rate: int) -> None:
    # RIFF 8-bit PCM is unsigned, while m4a DirectSound samples are signed.
    unsigned_pcm = bytes(value ^ 0x80 for value in signed_pcm)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(1)
        output.setframerate(sample_rate)
        output.writeframes(unsigned_pcm)


def extract_assets(rom: bytes) -> dict:
    catalog = extract(rom)
    entries = catalog["entries"]
    descriptor_offsets = {entry["descriptor_offset"] for entry in entries}
    track_offsets = {
        rom_offset(pointer, len(rom))
        for entry in entries
        for pointer in entry["track_ptrs"]
    }
    boundaries = sorted(track_offsets | descriptor_offsets)
    tracks = []
    for offset in sorted(track_offsets):
        end = next((item for item in boundaries if item > offset), None)
        if end is None or end <= offset:
            raise ValueError(f"no boundary for track at 0x{offset:X}")
        tracks.append({
            "offset": offset,
            "offset_hex": f"0x{offset:06X}",
            "size": end - offset,
            "raw_hex": rom[offset:end].hex(),
        })

    voicegroup_offsets = sorted({
        rom_offset(entry["voicegroup_ptr"], len(rom)) for entry in entries
    })
    tones = []
    waves_by_offset: dict[int, dict] = {}
    type_counts: dict[str, int] = {}
    for group_index, start in enumerate(voicegroup_offsets):
        end = voicegroup_offsets[group_index + 1] if group_index + 1 < len(voicegroup_offsets) else MASTER_OFFSET
        for offset in range(start, end - TONE_SIZE + 1, TONE_SIZE):
            tone_type, key, length, pan_sweep, pointer, attack, decay, sustain, release = struct.unpack_from(
                "<BBBBIBBBB", rom, offset
            )
            if tone_type not in VALID_TONE_TYPES:
                break
            if tone_type == 0:
                if not ROM_BASE <= pointer < ROM_BASE + len(rom):
                    break
                wave_header = pointer - ROM_BASE
                if wave_header + WAVE_HEADER_SIZE > len(rom):
                    break
                frequency_raw = struct.unpack_from("<I", rom, wave_header + 4)[0]
                if not 1000 * FREQ_SCALE <= frequency_raw <= 96000 * FREQ_SCALE:
                    break
            type_counts[str(tone_type)] = type_counts.get(str(tone_type), 0) + 1
            tone = {
                "offset": offset,
                "offset_hex": f"0x{offset:06X}",
                "voicegroup_offset": start,
                "type": tone_type,
                "key": key,
                "length": length,
                "pan_sweep": pan_sweep,
                "pointer": pointer,
                "attack": attack,
                "decay": decay,
                "sustain": sustain,
                "release": release,
            }
            if tone_type == 0 and ROM_BASE <= pointer < ROM_BASE + len(rom):
                wave_info = parse_wave(rom, pointer - ROM_BASE)
                if wave_info is not None:
                    tone["wave_offset"] = wave_info["offset"]
                    waves_by_offset.setdefault(wave_info["offset"], wave_info)
            tones.append(tone)

    return {
        "format": "Nintendo/MP2K m4a reachable audio assets",
        "song_count": len(entries),
        "track_count": len(tracks),
        "voicegroup_count": len(voicegroup_offsets),
        "tone_count": len(tones),
        "tone_type_counts": type_counts,
        "wave_count": len(waves_by_offset),
        "tracks": tracks,
        "voicegroup_offsets": voicegroup_offsets,
        "tones": tones,
        "waves": list(waves_by_offset.values()),
    }


def write_assets(rom: bytes, result: dict, output_dir: Path) -> None:
    tracks_dir = output_dir / "tracks"
    waves_dir = output_dir / "waves"
    tracks_dir.mkdir(parents=True, exist_ok=True)
    waves_dir.mkdir(parents=True, exist_ok=True)
    for stale in tracks_dir.glob("track_*.bin"):
        stale.unlink()
    for stale in waves_dir.glob("wave_*.wav"):
        stale.unlink()
    for track in result["tracks"]:
        offset = track["offset"]
        (tracks_dir / f"track_{offset:06X}.bin").write_bytes(
            rom[offset:offset + track["size"]]
        )
    for item in result["waves"]:
        pcm = rom[item["data_offset"]:item["data_end"]]
        write_wave(waves_dir / f"wave_{item['offset']:06X}_{item['sample_rate']}hz.wav", pcm, item["sample_rate"])
    manifest = dict(result)
    for track in manifest["tracks"]:
        track.pop("raw_hex", None)
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("build/audio-v2"))
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    result = extract_assets(rom)
    write_assets(rom, result, args.output_dir)
    print(json.dumps({key: result[key] for key in ("song_count", "track_count", "voicegroup_count", "tone_count", "wave_count")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
