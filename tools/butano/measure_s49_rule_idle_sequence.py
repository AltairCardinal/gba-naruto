#!/usr/bin/env python3
"""Measure the original's field unit redraw cadence and the remake's model.

The original S49 redraws the field unit on essentially every frame.  The
evidence is a 1800 frame zero input sweep taken from the battle 14 entry
savestate: inside the unit's own art the drawn image changes on 182 of 191
frame transitions, and 30 of the 32 frames of one cycle are mutually
different images.  The change is **not** a moving silhouette: the best
overall shift is always (0, 0) and most transitions keep the silhouette mask
bit for bit.  What changes is the unit's **outline colour**: the changed
pixels are exactly the pixels holding one palette index (the 1 px outline),
and that index is rewritten every frame.  See
``notes/s49-field-frame-order-20261020.md``.

The ROM's field slot (``field_idle_and_movement``) tells a different story:
every character's 32 frame animation holds one of three frames for eight
frames at a time.  The remake implements exactly that, so the remake shows
at most three distinct images per 32 frame cycle where the original shows
thirty.

That contradiction is the point of this measurement: the original's *per
frame* redraw is not explained by the ROM's hold field, so the frame order
(``帧序``) of the original's field animation is still open on the reverse
side.  This tool reports both sides so the gate can say which one the
remake has to match.

Usage::

    python3 tools/butano/measure_s49_rule_idle_sequence.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

#: The zero input sweep taken from the S49 battle 14 entry savestate.
SWEEP = "artifacts/s49-fidelity-20261019-v1/original-idle-sweep"

#: How many frames of the sweep are measured.  The period search needs
#: several periods and the original's cycle is 32 frames long.
FRAMES = 192

#: The first frame of the sweep is pinned: the measurement is about those
#: bytes.
PINNED_FIRST_FRAME_SHA256 = (
    "7bb28820bd83fb89de189d1b0e36f76b54e349690383670dd42079c80d7a80da"
)

#: The ROM derived visual catalog the remake ships.  Its field slot
#: timelines are the model the remake implements.
CATALOG = "butano-sequel/graphics/battle_unit_visual_catalog.json"

#: The semantic name the reverse side gives the field slot.
FIELD_SLOT = "field_idle_and_movement"

#: The columns of the changed region that hold the selection bracket and the
#: facing indicator rather than the unit's own art.  The left edge of the
#: changed region plus this many columns is where the unit's art starts.
BRACKET_COLUMNS = 9


class RuleEvidenceError(RuntimeError):
    """The original evidence is missing or is not the pinned bytes."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_image(path: Path):
    from PIL import Image

    if not Path(path).is_file():
        raise RuleEvidenceError(f"missing evidence frame: {path}")
    return Image.open(path).convert("RGB")


def _signatures(images) -> list[tuple[int, int, int, int, int] | None]:
    from PIL import ImageChops

    signatures: list[tuple[int, int, int, int, int] | None] = []
    for index in range(1, len(images)):
        difference = ImageChops.difference(images[index - 1], images[index])
        box = difference.getbbox()
        if box is None:
            signatures.append(None)
            continue
        bands = difference.split()
        peak = ImageChops.lighter(
            ImageChops.lighter(bands[0], bands[1]),
            bands[2],
        )
        changed = sum(
            count for value, count in enumerate(peak.histogram()) if value
        )
        signatures.append(
            (box[0], box[1], box[2] - 1, box[3] - 1, changed)
        )
    return signatures


def _distinct(images, region) -> list[str]:
    return [
        hashlib.sha256(image.crop(region).tobytes()).hexdigest()
        for image in images
    ]


def measure_original(root: Path) -> dict[str, Any]:
    """Measure the original's redraw cadence from the recorded sweep."""

    sweep = root / SWEEP
    frames = sorted(sweep.glob("frame-*.png"))
    if len(frames) < FRAMES:
        raise RuleEvidenceError(
            f"the original idle sweep has {len(frames)} frames, {FRAMES} "
            "are needed"
        )

    digest = sha256_file(frames[0])
    if digest != PINNED_FIRST_FRAME_SHA256:
        raise RuleEvidenceError(
            f"{frames[0]} hashes to {digest}, but the pinned sweep starts at "
            f"{PINNED_FIRST_FRAME_SHA256}"
        )

    images = [_load_image(path) for path in frames[:FRAMES]]
    signatures = _signatures(images)
    if not any(signatures):
        raise RuleEvidenceError("the original idle sweep never changes")

    bounds = [
        min(item[0] for item in signatures if item),
        min(item[1] for item in signatures if item),
        max(item[2] for item in signatures if item),
        max(item[3] for item in signatures if item),
    ]
    full_region = (bounds[0], bounds[1], bounds[2] + 1, bounds[3] + 1)
    sprite_region = (
        bounds[0] + BRACKET_COLUMNS,
        bounds[1],
        bounds[2] + 1,
        bounds[3] + 1,
    )

    def cadence(region) -> dict[str, Any]:
        poses = _distinct(images, region)
        window = poses[:32]
        return {
            "region": list(region),
            "distinct_images_in_32_frames": len(set(window)),
            "identical_neighbouring_frames_in_32": sum(
                1
                for index in range(1, len(window))
                if window[index] == window[index - 1]
            ),
            "changed_transitions": sum(1 for item in signatures if item),
            "total_transitions": len(signatures),
        }

    return {
        "sweep": SWEEP,
        "first_frame_sha256": digest,
        "frames_measured": len(images),
        "changed_region_bbox": bounds,
        "full_region": cadence(full_region),
        "sprite_region": cadence(sprite_region),
    }


def measure_rom_model(root: Path) -> dict[str, Any]:
    """Measure the ROM's field slot timelines the remake ships."""

    path = root / CATALOG
    if not path.is_file():
        raise RuleEvidenceError(f"missing the ROM derived catalog: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))

    cycle_lengths: dict[int, int] = {}
    distinct_per_cycle: dict[int, int] = {}
    characters = 0
    for entry in payload.get("entries", []):
        for visual in entry.get("visuals", []):
            if visual.get("semantic") != FIELD_SLOT or not visual.get("valid"):
                continue
            characters += 1
            for animation in visual.get("animations", []):
                total = int(animation.get("total_duration", 0))
                frames = {
                    int(step["frame_index"])
                    for step in animation.get("steps", [])
                }
                cycle_lengths[total] = cycle_lengths.get(total, 0) + 1
                if total not in distinct_per_cycle:
                    distinct_per_cycle[total] = len(frames)
                else:
                    distinct_per_cycle[total] = max(
                        distinct_per_cycle[total], len(frames)
                    )
    if not characters:
        raise RuleEvidenceError(
            f"{path} has no valid {FIELD_SLOT} slot to measure"
        )
    return {
        "catalog": CATALOG,
        "characters_with_a_field_slot": characters,
        "cycle_length_to_animations": cycle_lengths,
        "cycle_length_to_max_distinct_frames": distinct_per_cycle,
    }


def measure(root: Path) -> dict[str, Any]:
    return {
        "schema": "konoha.s49-rule-idle-sequence.v1",
        "original": measure_original(root),
        "rom_model": measure_rom_model(root),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    try:
        payload = measure(Path(args.root).resolve())
    except RuleEvidenceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
