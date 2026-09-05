#!/usr/bin/env python3
"""Export exact ROM byte ranges reached by the game's MP2K/m4a graph."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from tools.extract_audio_assets import TONE_SIZE, extract_assets
    from tools.extract_audio_resource_sets import (
        ACTIVE_IDS,
        EMPTY_DESCRIPTOR,
        MASTER_OFFSET,
        MASTER_STRIDE,
        ROM_BASE,
        SOUND_ID_COUNT,
        extract,
    )
except ModuleNotFoundError:  # direct ``python tools/...`` execution
    from extract_audio_assets import TONE_SIZE, extract_assets
    from extract_audio_resource_sets import (
        ACTIVE_IDS,
        EMPTY_DESCRIPTOR,
        MASTER_OFFSET,
        MASTER_STRIDE,
        ROM_BASE,
        SOUND_ID_COUNT,
        extract,
    )


ROM_PATH = Path("rom/base.gba")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PRODUCER_PATH = Path("tools/export_rom_m4a_byte_inventory.py")
DENSE_AUDIO_WINDOW = (0x466068, 0x53D5F4)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    gaps = []
    classified = 0
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


def build_manifest(root: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    rom = (root / ROM_PATH).read_bytes()
    rom_sha256 = _sha256(rom)
    if rom_sha256 != ROM_SHA256:
        raise ValueError(f"base ROM SHA-256 changed: {rom_sha256}")

    catalog = extract(rom)
    assets = extract_assets(rom)
    entries = catalog["entries"]
    active_ids = set(ACTIVE_IDS)
    claims: list[dict[str, Any]] = []

    for sound_id in range(SOUND_ID_COUNT):
        if sound_id in active_ids:
            continue
        start = MASTER_OFFSET + sound_id * MASTER_STRIDE
        claims.append(
            _claim(
                rom,
                f"m4a-empty-sound-id-{sound_id:03d}",
                "m4a_empty_sound_id_entry",
                start,
                start + MASTER_STRIDE,
                {
                    "sound_id": sound_id,
                    "descriptor_pointer": f"0x{EMPTY_DESCRIPTOR:08X}",
                },
            )
        )

    track_references: dict[int, list[dict[str, int]]] = {}
    for entry in entries:
        descriptor_offset = entry["descriptor_offset"]
        descriptor_end = descriptor_offset + 8 + entry["track_count"] * 4
        claims.append(
            _claim(
                rom,
                f"m4a-song-header-{entry['sound_id']:03d}",
                "m4a_song_header",
                descriptor_offset,
                descriptor_end,
                {
                    "sound_ids": [entry["sound_id"]],
                    "track_count": entry["track_count"],
                    "voicegroup_pointer": f"0x{entry['voicegroup_ptr']:08X}",
                    "track_pointers": [
                        f"0x{pointer:08X}" for pointer in entry["track_ptrs"]
                    ],
                },
            )
        )
        for track_index, pointer in enumerate(entry["track_ptrs"]):
            track_references.setdefault(pointer - ROM_BASE, []).append(
                {"sound_id": entry["sound_id"], "track_index": track_index}
            )

    for track in assets["tracks"]:
        start = track["offset"]
        claims.append(
            _claim(
                rom,
                f"m4a-track-{start:06x}",
                "m4a_track_stream",
                start,
                start + track["size"],
                {"references": track_references[start]},
            )
        )

    tone_indices: dict[int, int] = {}
    wave_references: dict[int, list[int]] = {}
    for tone in assets["tones"]:
        voicegroup_offset = tone["voicegroup_offset"]
        tone_index = tone_indices.get(voicegroup_offset, 0)
        tone_indices[voicegroup_offset] = tone_index + 1
        start = tone["offset"]
        subject = {
            "voicegroup_offset": voicegroup_offset,
            "tone_index": tone_index,
            "tone_type": tone["type"],
            "pointer": f"0x{tone['pointer']:08X}",
        }
        if "wave_offset" in tone:
            subject["wave_offset"] = tone["wave_offset"]
            wave_references.setdefault(tone["wave_offset"], []).append(start)
        claims.append(
            _claim(
                rom,
                f"m4a-tone-{start:06x}",
                "m4a_tone_record",
                start,
                start + TONE_SIZE,
                subject,
            )
        )

    for wave in assets["waves"]:
        start = wave["offset"]
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

    track_reference_count = sum(entry["track_count"] for entry in entries)
    summary = {
        "sound_id_count": SOUND_ID_COUNT,
        "active_sound_id_count": len(entries),
        "empty_sound_id_count": SOUND_ID_COUNT - len(entries),
        "song_header_count": len(entries),
        "track_reference_count": track_reference_count,
        "track_stream_count": len(assets["tracks"]),
        "voicegroup_count": len(assets["voicegroup_offsets"]),
        "tone_record_count": len(assets["tones"]),
        "wave_count": len(assets["waves"]),
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/rom-m4a-byte-inventory-v1/manifest.json"),
    )
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    output = args.output if args.output.is_absolute() else root / args.output
    manifest = build_manifest(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
