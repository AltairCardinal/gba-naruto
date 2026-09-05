#!/usr/bin/env python3
"""Independently rebuild and verify the MP2K/m4a ROM byte inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
MASTER_OFFSET = 0x465B70
MASTER_STRIDE = 8
EMPTY_DESCRIPTOR = 0x08466068
SOUND_ID_COUNT = 159
ACTIVE_IDS = (
    tuple(range(1, 19))
    + tuple(range(51, 55))
    + tuple(range(101, 159))
)
TONE_SIZE = 12
WAVE_HEADER_SIZE = 16
FREQ_SCALE = 1024
VALID_TONE_TYPES = {0, 1, 2, 3, 4, 8, 9, 10, 11, 12, 0x40, 0x80}
PRODUCER_PATH = Path("tools/export_rom_m4a_byte_inventory.py")
DENSE_AUDIO_WINDOW = (0x466068, 0x53D5F4)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rom_offset(pointer: int, rom_size: int) -> int:
    offset = pointer - ROM_BASE
    if not 0 <= offset < rom_size:
        raise ValueError(f"pointer 0x{pointer:08X} is outside ROM")
    return offset


def _claim(
    rom: bytes,
    identifier: str,
    semantic_class: str,
    start: int,
    end: int,
    subject: dict[str, Any],
) -> dict[str, Any]:
    if start < 0 or start >= end or end > len(rom):
        raise ValueError(f"audio claim {identifier} is outside ROM")
    return {
        "id": identifier,
        "range": [start, end],
        "semantic_class": semantic_class,
        "bytes_sha256": _sha256(rom[start:end]),
        "subject": subject,
    }


def _parse_wave(rom: bytes, offset: int) -> dict[str, int] | None:
    if offset + WAVE_HEADER_SIZE > len(rom):
        return None
    type_flags, status, frequency_raw, loop_start, sample_count = struct.unpack_from(
        "<HHIII", rom, offset
    )
    end = offset + WAVE_HEADER_SIZE + sample_count
    if (
        frequency_raw == 0
        or sample_count == 0
        or loop_start > sample_count
        or end > len(rom)
    ):
        return None
    sample_rate = round(frequency_raw / FREQ_SCALE)
    if not 1000 <= sample_rate <= 96000:
        return None
    return {
        "offset": offset,
        "type_flags": type_flags,
        "status": status,
        "frequency_raw": frequency_raw,
        "sample_rate": sample_rate,
        "loop_start": loop_start,
        "sample_count": sample_count,
        "data_end": end,
    }


def _dense_window(
    rom: bytes, claims: list[dict[str, Any]]
) -> dict[str, Any]:
    start, end = DENSE_AUDIO_WINDOW
    included = sorted(
        (max(start, claim["range"][0]), min(end, claim["range"][1]))
        for claim in claims
        if claim["range"][0] < end and start < claim["range"][1]
    )
    cursor = start
    classified = 0
    gaps = []
    for range_start, range_end in included:
        if range_start < cursor:
            raise ValueError("audio claims overlap inside the dense window")
        if cursor < range_start:
            gaps.append(
                {
                    "range": [cursor, range_start],
                    "bytes_sha256": _sha256(rom[cursor:range_start]),
                }
            )
        classified += range_end - range_start
        cursor = range_end
    if cursor < end:
        gaps.append(
            {
                "range": [cursor, end],
                "bytes_sha256": _sha256(rom[cursor:end]),
            }
        )
    return {
        "range": [start, end],
        "classified_bytes": classified,
        "unclaimed_bytes": sum(
            item["range"][1] - item["range"][0] for item in gaps
        ),
        "unclaimed_ranges": gaps,
    }


def _build_expected(root: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    rom = (root / ROM_PATH).read_bytes()
    rom_sha256 = _sha256(rom)
    if rom_sha256 != ROM_SHA256:
        raise ValueError(f"base ROM SHA-256 changed: {rom_sha256}")

    claims: list[dict[str, Any]] = []
    active_ids = set(ACTIVE_IDS)
    entries = []
    for sound_id in range(SOUND_ID_COUNT):
        master_offset = MASTER_OFFSET + sound_id * MASTER_STRIDE
        descriptor_pointer, player_config = struct.unpack_from(
            "<II", rom, master_offset
        )
        if sound_id not in active_ids:
            if descriptor_pointer != EMPTY_DESCRIPTOR or player_config != 0:
                raise ValueError(f"empty sound ID {sound_id} changed")
            claims.append(
                _claim(
                    rom,
                    f"m4a-empty-sound-id-{sound_id:03d}",
                    "m4a_empty_sound_id_entry",
                    master_offset,
                    master_offset + MASTER_STRIDE,
                    {
                        "sound_id": sound_id,
                        "descriptor_pointer": f"0x{EMPTY_DESCRIPTOR:08X}",
                    },
                )
            )
            continue

        if descriptor_pointer == EMPTY_DESCRIPTOR:
            raise ValueError(f"active sound ID {sound_id} became empty")
        descriptor_offset = _rom_offset(descriptor_pointer, len(rom))
        track_count, block_count, priority, reverb = struct.unpack_from(
            "<BBBB", rom, descriptor_offset
        )
        if not 1 <= track_count <= 16:
            raise ValueError(
                f"sound ID {sound_id} has invalid track count {track_count}"
            )
        voicegroup_pointer = struct.unpack_from("<I", rom, descriptor_offset + 4)[0]
        _rom_offset(voicegroup_pointer, len(rom))
        track_pointers = list(
            struct.unpack_from(
                f"<{track_count}I", rom, descriptor_offset + 8
            )
        )
        for pointer in track_pointers:
            _rom_offset(pointer, len(rom))
        entries.append(
            {
                "sound_id": sound_id,
                "descriptor_offset": descriptor_offset,
                "track_count": track_count,
                "block_count": block_count,
                "priority": priority,
                "reverb": reverb,
                "voicegroup_pointer": voicegroup_pointer,
                "track_pointers": track_pointers,
            }
        )

    descriptor_offsets = {entry["descriptor_offset"] for entry in entries}
    track_offsets = {
        _rom_offset(pointer, len(rom))
        for entry in entries
        for pointer in entry["track_pointers"]
    }
    track_boundaries = sorted(track_offsets | descriptor_offsets)
    track_references: dict[int, list[dict[str, int]]] = {}
    voicegroup_offsets = sorted(
        {
            _rom_offset(entry["voicegroup_pointer"], len(rom))
            for entry in entries
        }
    )

    for entry in entries:
        descriptor_offset = entry["descriptor_offset"]
        claims.append(
            _claim(
                rom,
                f"m4a-song-header-{entry['sound_id']:03d}",
                "m4a_song_header",
                descriptor_offset,
                descriptor_offset + 8 + entry["track_count"] * 4,
                {
                    "sound_ids": [entry["sound_id"]],
                    "track_count": entry["track_count"],
                    "voicegroup_pointer": (
                        f"0x{entry['voicegroup_pointer']:08X}"
                    ),
                    "track_pointers": [
                        f"0x{pointer:08X}"
                        for pointer in entry["track_pointers"]
                    ],
                },
            )
        )
        for track_index, pointer in enumerate(entry["track_pointers"]):
            track_references.setdefault(pointer - ROM_BASE, []).append(
                {"sound_id": entry["sound_id"], "track_index": track_index}
            )

    for start in sorted(track_offsets):
        end = next(
            (boundary for boundary in track_boundaries if boundary > start),
            None,
        )
        if end is None or end <= start:
            raise ValueError(f"no boundary for track at 0x{start:X}")
        claims.append(
            _claim(
                rom,
                f"m4a-track-{start:06x}",
                "m4a_track_stream",
                start,
                end,
                {"references": track_references[start]},
            )
        )

    tones = []
    waves_by_offset: dict[int, dict[str, int]] = {}
    for group_index, voicegroup_offset in enumerate(voicegroup_offsets):
        end = (
            voicegroup_offsets[group_index + 1]
            if group_index + 1 < len(voicegroup_offsets)
            else MASTER_OFFSET
        )
        tone_index = 0
        for offset in range(voicegroup_offset, end - TONE_SIZE + 1, TONE_SIZE):
            (
                tone_type,
                key,
                length,
                pan_sweep,
                pointer,
                attack,
                decay,
                sustain,
                release,
            ) = struct.unpack_from("<BBBBIBBBB", rom, offset)
            if tone_type not in VALID_TONE_TYPES:
                break
            if tone_type == 0:
                if not ROM_BASE <= pointer < ROM_BASE + len(rom):
                    break
                frequency_raw = struct.unpack_from(
                    "<I", rom, pointer - ROM_BASE + 4
                )[0]
                if not 1000 * FREQ_SCALE <= frequency_raw <= 96000 * FREQ_SCALE:
                    break
            tone = {
                "offset": offset,
                "voicegroup_offset": voicegroup_offset,
                "tone_index": tone_index,
                "tone_type": tone_type,
                "pointer": pointer,
            }
            if tone_type == 0:
                wave = _parse_wave(rom, pointer - ROM_BASE)
                if wave is not None:
                    tone["wave_offset"] = wave["offset"]
                    waves_by_offset.setdefault(wave["offset"], wave)
            tones.append(tone)
            tone_index += 1

    wave_references: dict[int, list[int]] = {}
    for tone in tones:
        if "wave_offset" in tone:
            wave_references.setdefault(tone["wave_offset"], []).append(
                tone["offset"]
            )
        subject = {
            "voicegroup_offset": tone["voicegroup_offset"],
            "tone_index": tone["tone_index"],
            "tone_type": tone["tone_type"],
            "pointer": f"0x{tone['pointer']:08X}",
        }
        if "wave_offset" in tone:
            subject["wave_offset"] = tone["wave_offset"]
        claims.append(
            _claim(
                rom,
                f"m4a-tone-{tone['offset']:06x}",
                "m4a_tone_record",
                tone["offset"],
                tone["offset"] + TONE_SIZE,
                subject,
            )
        )

    for start, wave in waves_by_offset.items():
        claims.append(
            _claim(
                rom,
                f"m4a-wave-{start:06x}",
                "m4a_directsound_wave",
                start,
                wave["data_end"],
                {
                    "type_flags": wave["type_flags"],
                    "status": wave["status"],
                    "frequency_raw": wave["frequency_raw"],
                    "sample_rate": wave["sample_rate"],
                    "loop_start": wave["loop_start"],
                    "sample_count": wave["sample_count"],
                    "tone_offsets": wave_references[start],
                },
            )
        )

    claims.sort(key=lambda claim: (claim["range"], claim["id"]))
    for previous, current in zip(claims, claims[1:]):
        if current["range"][0] < previous["range"][1]:
            raise ValueError(
                f"audio claims overlap: {previous['id']} and {current['id']}"
            )

    semantic_class_counts: dict[str, int] = {}
    semantic_class_bytes: dict[str, int] = {}
    for claim in claims:
        semantic_class = claim["semantic_class"]
        semantic_class_counts[semantic_class] = (
            semantic_class_counts.get(semantic_class, 0) + 1
        )
        semantic_class_bytes[semantic_class] = (
            semantic_class_bytes.get(semantic_class, 0)
            + claim["range"][1]
            - claim["range"][0]
        )

    summary = {
        "sound_id_count": SOUND_ID_COUNT,
        "active_sound_id_count": len(entries),
        "empty_sound_id_count": SOUND_ID_COUNT - len(entries),
        "song_header_count": len(entries),
        "track_reference_count": sum(
            entry["track_count"] for entry in entries
        ),
        "track_stream_count": len(track_offsets),
        "voicegroup_count": len(voicegroup_offsets),
        "tone_record_count": len(tones),
        "wave_count": len(waves_by_offset),
        "claim_count": len(claims),
        "byte_count": sum(semantic_class_bytes.values()),
    }
    return {
        "schema": "rom-m4a-byte-inventory-v1",
        "base_rom": {
            "path": ROM_PATH.as_posix(),
            "size": len(rom),
            "sha256": rom_sha256,
        },
        "producer": {
            "path": PRODUCER_PATH.as_posix(),
            "sha256": _sha256((root / PRODUCER_PATH).read_bytes()),
        },
        "summary": summary,
        "semantic_class_counts": dict(sorted(semantic_class_counts.items())),
        "semantic_class_bytes": dict(sorted(semantic_class_bytes.items())),
        "dense_audio_window": _dense_window(rom, claims),
        "claims": claims,
        "limitations": [
            "Only bytes reached by the fixed sound table, song headers, track streams, voicegroups, and DirectSound wave headers are classified.",
            "The 318 bytes in dense_audio_window.unclaimed_ranges remain unknown and are not inferred to be audio padding.",
            "Semantic cue names and audible rendering quality are outside this byte-inventory claim.",
        ],
    }


def verify_manifest(root: Path, manifest: object) -> dict[str, Any]:
    errors: list[str] = []
    try:
        expected = _build_expected(root)
    except (OSError, ValueError, struct.error) as error:
        return {
            "schema": "rom-m4a-byte-inventory-verification-v1",
            "verified": False,
            "claim_count": 0,
            "byte_count": 0,
            "errors": [str(error)],
        }
    if manifest != expected:
        errors.append("manifest differs from independent parse")
    return {
        "schema": "rom-m4a-byte-inventory-verification-v1",
        "verified": not errors,
        "claim_count": expected["summary"]["claim_count"],
        "byte_count": expected["summary"]["byte_count"],
        "sound_id_count": expected["summary"]["sound_id_count"],
        "active_sound_id_count": expected["summary"]["active_sound_id_count"],
        "empty_sound_id_count": expected["summary"]["empty_sound_id_count"],
        "track_reference_count": expected["summary"]["track_reference_count"],
        "track_stream_count": expected["summary"]["track_stream_count"],
        "voicegroup_count": expected["summary"]["voicegroup_count"],
        "tone_record_count": expected["summary"]["tone_record_count"],
        "wave_count": expected["summary"]["wave_count"],
        "unclaimed_dense_window_bytes": expected["dense_audio_window"][
            "unclaimed_bytes"
        ],
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("artifacts/rom-m4a-byte-inventory-v1/manifest.json"),
    )
    args = parser.parse_args()
    path = args.manifest if args.manifest.is_absolute() else args.root / args.manifest
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        report = verify_manifest(args.root, manifest)
    except (OSError, json.JSONDecodeError) as error:
        report = {
            "schema": "rom-m4a-byte-inventory-verification-v1",
            "verified": False,
            "claim_count": 0,
            "byte_count": 0,
            "errors": [str(error)],
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
