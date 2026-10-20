#!/usr/bin/env python3
"""Measure the original's ``0xFBFF`` corrupt terminator and the remake's copy.

The original ROM carries exactly one corrupted component terminator.  At
``0x0825A8E4`` the trailer of character 26, visual slot 2, frame 2 reads
``0xFBFF`` where every other frame reads ``0xFFFF``.  The signed value of
``0xFBFF`` is -1025, so the common renderer -- which only accepts -1 as the
end of a component list -- does **not** stop there.  It steps on by one
20 byte component at a time and reads the data behind the frame as if it
were more components.  The reverse side closed this as a **corrupt
terminator**, not as a new format:

* the base run reads ``0x0825A8E4 = 0xFBFF`` then ``0x0825A8F8 = 0x00FF``,
  ``0x0825A90C = 0x0100`` and ``0x0825A920 = 0xA8D0`` -- four reads, one
  component apart, so the renderer overran the frame;
* the one byte control ROM (``0x0825A8E5``: ``0xFB`` -> ``0xFF``) reads
  ``0x0825A8E4 = 0xFFFF`` (-1) and stops immediately, producing exactly one
  legal object.

This tool verifies the ROM side from the local ``rom/base.gba`` (byte,
renderer instruction windows, and the patched control ROM's hash) and reads
the runtime traces from the reverse work tree when it is available.  It also
reports what the remake's generated catalog does with the same frame.

Usage::

    python3 tools/butano/measure_s49_rule_fbff.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

#: The ROM under study.  Its hash is pinned everywhere else as well.
ROM = "rom/base.gba"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

#: The file offset of the corrupted trailer (GBA address 0x0825A8E4).
TRAILER_OFFSET = 0x25A8E4
TRAILER_BYTES = "fffb0000"

#: The one byte repair the reverse side signed: normalise the high byte of
#: the trailer from 0xFB to 0xFF.
REPAIR_OFFSET = 0x25A8E5
REPAIR_BEFORE = 0xFB
REPAIR_AFTER = 0xFF
CONTROL_ROM_SHA256 = (
    "3f55e607829db4497a1f49200514777c89df01f3624fd849005b96247502507a"
)

#: The renderer's instruction windows, hashed by the reverse side's signed
#: manifest.  They are re-hashed from the local ROM here.
RENDERER_WINDOWS = (
    ("0x080629FC", "0x08062A0A", "1eec74c4d5fbbe612ea235443537b5f670eb656f460b623059ad4bdb6adda3fa"),
    ("0x080631F6", "0x08063214", "139cfdb1b42f080558791e74aab2d726cfb36e703555991b437065e744b32af7"),
)

#: The reverse work tree.  It is not part of this tree, so the runtime
#: traces are optional; everything else is verified locally.
DEFAULT_REVERSE_ROOT = "/Users/altair/github/gba-naruto-reverse"
FBFF_ARTIFACT = "artifacts/character-fbff-runtime-v1"

#: The ROM derived visual catalog the remake ships.
CATALOG = "butano-sequel/graphics/battle_unit_visual_catalog.json"

#: The character, visual slot and frame the corrupt trailer belongs to.
FBFF_CHARACTER_ID = 26
FBFF_VISUAL_SLOT = 2
FBFF_FRAME_INDEX = 2

#: The field names the reverse side's exporter uses for the defect.  The
#: remake has to use the same vocabulary, otherwise the corruption is
#: swallowed silently.
TERMINATOR_FIELDS = ("frame_trailer_raw_hex", "renderer_terminator")


class RuleEvidenceError(RuntimeError):
    """The original evidence is missing or does not match the pinned bytes."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def measure_rom(root: Path) -> dict[str, Any]:
    """Verify the ROM byte, the renderer windows and the control ROM."""

    path = root / ROM
    if not path.is_file():
        raise RuleEvidenceError(f"missing the ROM under study: {path}")
    data = path.read_bytes()
    digest = sha256_bytes(data)
    if digest != ROM_SHA256:
        raise RuleEvidenceError(
            f"{path} hashes to {digest}, but the ROM under study is "
            f"{ROM_SHA256}"
        )

    trailer = data[TRAILER_OFFSET: TRAILER_OFFSET + 4]
    if trailer.hex() != TRAILER_BYTES:
        raise RuleEvidenceError(
            f"the trailer at {TRAILER_OFFSET:#x} is {trailer.hex()}, not "
            f"{TRAILER_BYTES}"
        )

    patched = bytearray(data)
    if patched[REPAIR_OFFSET] != REPAIR_BEFORE:
        raise RuleEvidenceError(
            f"the byte at {REPAIR_OFFSET:#x} is "
            f"{patched[REPAIR_OFFSET]:#04x}, not {REPAIR_BEFORE:#04x}"
        )
    patched[REPAIR_OFFSET] = REPAIR_AFTER
    control_digest = sha256_bytes(bytes(patched))

    windows = []
    for start, end, expected in RENDERER_WINDOWS:
        begin = int(start, 16) - 0x08000000
        finish = int(end, 16) - 0x08000000
        actual = sha256_bytes(data[begin:finish])
        if actual != expected:
            raise RuleEvidenceError(
                f"the renderer window {start}..{end} hashes to {actual}, "
                f"not {expected}"
            )
        windows.append({"start": start, "end": end, "sha256": actual})

    return {
        "rom": ROM,
        "rom_sha256": digest,
        "trailer_offset": TRAILER_OFFSET,
        "trailer_gba_address": f"0x{0x08000000 + TRAILER_OFFSET:08X}",
        "trailer_bytes": trailer.hex(),
        "trailer_signed_value": int.from_bytes(
            trailer[:2], "little", signed=True
        ),
        "repair": {
            "file_offset": REPAIR_OFFSET,
            "gba_address": f"0x{0x08000000 + REPAIR_OFFSET:08X}",
            "before": REPAIR_BEFORE,
            "after": REPAIR_AFTER,
            "changed_byte_count": 1,
        },
        "control_rom_sha256": control_digest,
        "control_rom_sha256_expected": CONTROL_ROM_SHA256,
        "renderer_windows": windows,
    }


def measure_reverse_tree(reverse_root: Path) -> dict[str, Any]:
    """Read the signed runtime traces, when the reverse tree is there."""

    manifest_path = reverse_root / FBFF_ARTIFACT / "manifest.json"
    if not manifest_path.is_file():
        return {
            "available": False,
            "reason": (
                f"the reverse work tree has no {FBFF_ARTIFACT}/manifest.json "
                f"at {reverse_root}"
            ),
        }
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    traces = {}
    for side in ("base", "control"):
        trace_path = reverse_root / FBFF_ARTIFACT / side / "renderer-loop.json"
        if not trace_path.is_file():
            raise RuleEvidenceError(
                f"missing the runtime trace: {trace_path}"
            )
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        traces[side] = {
            "path": str(trace_path.relative_to(reverse_root)),
            "sha256": sha256_file(trace_path),
            "hits": [
                {
                    "pointer": hit["pointer"],
                    "raw_u16": hit["raw_u16"],
                    "signed_value": hit["signed_value"],
                }
                for hit in trace["hits"]
            ],
        }
    return {
        "available": True,
        "manifest_path": str(manifest_path.relative_to(reverse_root)),
        "manifest_sha256": sha256_file(manifest_path),
        "schema": manifest.get("schema"),
        "base_rom_sha256": manifest.get("base_rom", {}).get("sha256"),
        "control_rom_sha256": manifest.get("control_rom", {}).get("sha256"),
        "conclusion": manifest.get("conclusion", {}),
        "traces": traces,
    }


def measure_catalog(root: Path) -> dict[str, Any]:
    """Report what the remake's generated catalog does with the frame."""

    path = root / CATALOG
    if not path.is_file():
        raise RuleEvidenceError(f"missing the ROM derived catalog: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    for entry in payload.get("entries", []):
        if entry.get("character_id") != FBFF_CHARACTER_ID:
            continue
        visuals = entry.get("visuals", [])
        if FBFF_VISUAL_SLOT >= len(visuals):
            continue
        visual = visuals[FBFF_VISUAL_SLOT]
        for frame in visual.get("frames", []):
            if frame.get("frame_index") != FBFF_FRAME_INDEX:
                continue
            components = frame.get("components", [])
            trailer_value = (
                components[-1].get("next_tile_index") if components else None
            )
            return {
                "catalog": CATALOG,
                "character_id": FBFF_CHARACTER_ID,
                "visual_slot": FBFF_VISUAL_SLOT,
                "semantic": visual.get("semantic"),
                "frame_index": FBFF_FRAME_INDEX,
                "frame_pointer_hex": frame.get("frame_pointer_hex"),
                "component_count": frame.get("component_count"),
                "trailer_value": trailer_value,
                "trailer_hex": (
                    f"{trailer_value:04x}" if trailer_value is not None else None
                ),
                "recorded_fields": {
                    field: frame.get(field) for field in TERMINATOR_FIELDS
                },
                "records_the_defect": all(
                    field in frame for field in TERMINATOR_FIELDS
                ),
            }
    raise RuleEvidenceError(
        f"{path} has no character {FBFF_CHARACTER_ID} slot "
        f"{FBFF_VISUAL_SLOT} frame {FBFF_FRAME_INDEX}"
    )


def measure(root: Path, reverse_root: Path) -> dict[str, Any]:
    return {
        "schema": "konoha.s49-rule-fbff.v1",
        "rom": measure_rom(root),
        "reverse_tree": measure_reverse_tree(reverse_root),
        "catalog": measure_catalog(root),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument(
        "--reverse-root",
        default=os.environ.get("KONOHA_REVERSE_ROOT", DEFAULT_REVERSE_ROOT),
    )
    args = parser.parse_args(argv)
    try:
        payload = measure(
            Path(args.root).resolve(), Path(args.reverse_root).resolve()
        )
    except RuleEvidenceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
