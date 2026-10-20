#!/usr/bin/env python3
"""Measure the original's move range overlay and the remake's conformance.

The original S49 paints the reachable area of the battlefield with a cyan
overlay.  The overlay is **not** one flat tint: the original walks over the
map with a dither mask, so the same map colour comes out as several
different overlay colours depending on where the mask lets the overlay
through.  The remake blends one flat overlay colour into the map, so its
overlay field does not match the original's.

This tool measures both sides from the recorded frames:

* the original side is ``walk-original-a24/step-19-A.png`` (the frame with
  the move range drawn) minus ``step-20-A.png`` (the same battlefield without
  it);
* the remake side is ``walk-remake-dd-a30-banner2/step-20-A.png`` minus
  ``step-21-A.png``.

Both original frames are pinned by SHA-256, because the rule is about those
bytes and not about "how the original looked".  Nothing here is copied from a
note: every number is measured from the pixels.

The gate that consumes this measurement is
``tests/test_s49_rule_move_grid.py``.

Usage::

    python3 tools/butano/measure_s49_rule_move_grid.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

#: The original walk.  Step 19 draws the move range, step 20 is the same
#: battlefield with the range gone.
ORIGINAL_WALK = "artifacts/s49-fidelity-20261019-v1/walk-original-a24"
ORIGINAL_GRID_FRAME = "step-19-A.png"
ORIGINAL_PLAIN_FRAME = "step-20-A.png"

#: The remake walk.  Its step 20 draws the move range, step 21 is the same
#: battlefield with the range gone.
REMAKE_WALK = "artifacts/s49-fidelity-20261019-v1/walk-remake-dd-a30-banner2"
REMAKE_GRID_FRAME = "step-20-A.png"
REMAKE_PLAIN_FRAME = "step-21-A.png"

#: The two original frames are pinned by hash.  A re-recorded walk has a
#: different hash and must not silently replace the evidence.
PINNED_ORIGINAL_HASHES = {
    ORIGINAL_GRID_FRAME: (
        "cb2da0d5132cbe6018d21e1748a87cfec2678c32ddf588b74086d2f5f317f2fe"
    ),
    ORIGINAL_PLAIN_FRAME: (
        "c6611ae713930fc9a4eacd09379a3483a42b27a044f57c05319833878497d3bd"
    ),
}

#: The battlefield area.  The bottom 32 rows are the HUD, not the map.
FIELD_AREA = (0, 0, 240, 128)

#: The blue channel a colour needs to count as part of the cyan move range
#: overlay.  The map underneath has a much lower blue channel.
CYAN_MIN_BLUE = 150


class RuleEvidenceError(RuntimeError):
    """The original evidence is missing or is not the pinned bytes."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_image(path: Path):
    from PIL import Image

    if not Path(path).is_file():
        raise RuleEvidenceError(f"missing evidence frame: {path}")
    image = Image.open(path).convert("RGB")
    if image.size != (240, 160):
        raise RuleEvidenceError(
            f"{path} is {image.size}, not a 240x160 GBA frame"
        )
    return image


def measure_overlay(grid, plain) -> dict[str, Any]:
    """Measure the overlay that turns ``plain`` into ``grid``."""

    grid_px = grid.load()
    plain_px = plain.load()
    x0, y0, x1, y1 = FIELD_AREA

    pairs: dict[tuple[tuple[int, int, int], tuple[int, int, int]], int] = {}
    changed = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            base = plain_px[x, y]
            tinted = grid_px[x, y]
            if base == tinted:
                continue
            changed += 1
            pairs[(base, tinted)] = pairs.get((base, tinted), 0) + 1

    if not pairs:
        raise RuleEvidenceError(
            "the move range frame differs from the plain frame nowhere; "
            "the overlay could not be measured"
        )

    overlays = {tinted for (_base, tinted) in pairs}
    cyans = {colour for colour in overlays if colour[2] >= CYAN_MIN_BLUE}
    cyan_pairs = {
        (base, overlay): count
        for (base, overlay), count in pairs.items()
        if overlay in cyans
    }
    bases_with_several_cyan_overlays = {
        base
        for (base, _overlay) in cyan_pairs
        if len(
            {
                other
                for (other_base, other) in cyan_pairs
                if other_base == base
            }
        )
        > 1
    }
    return {
        "changed_pixels": changed,
        "distinct_base_to_overlay_pairs": len(pairs),
        "distinct_overlay_colours": len(overlays),
        "cyan_overlay_colours": len(cyans),
        "cyan_pairs": len(cyan_pairs),
        "bases_with_several_cyan_overlays": len(
            bases_with_several_cyan_overlays
        ),
        "cyan_pixels": sum(cyan_pairs.values()),
    }


def measure(root: Path) -> dict[str, Any]:
    """Measure the original's overlay and the remake's conformance to it."""

    original_dir = root / ORIGINAL_WALK
    remake_dir = root / REMAKE_WALK

    original_hashes = {}
    for name, pinned in PINNED_ORIGINAL_HASHES.items():
        path = original_dir / name
        if not path.is_file():
            raise RuleEvidenceError(
                f"missing original evidence frame: {path}"
            )
        digest = sha256_file(path)
        if digest != pinned:
            raise RuleEvidenceError(
                f"{path} hashes to {digest}, but the pinned original frame "
                f"is {pinned}"
            )
        original_hashes[name] = digest

    original = measure_overlay(
        load_image(original_dir / ORIGINAL_GRID_FRAME),
        load_image(original_dir / ORIGINAL_PLAIN_FRAME),
    )
    remake = measure_overlay(
        load_image(remake_dir / REMAKE_GRID_FRAME),
        load_image(remake_dir / REMAKE_PLAIN_FRAME),
    )

    original_px = load_image(original_dir / ORIGINAL_GRID_FRAME).load()
    remake_px = load_image(remake_dir / REMAKE_GRID_FRAME).load()
    x0, y0, x1, y1 = FIELD_AREA
    different = sum(
        1
        for y in range(y0, y1)
        for x in range(x0, x1)
        if original_px[x, y] != remake_px[x, y]
    )

    return {
        "schema": "konoha.s49-rule-move-grid.v1",
        "inputs": {
            "original_grid_frame": (
                f"{ORIGINAL_WALK}/{ORIGINAL_GRID_FRAME}"
            ),
            "original_plain_frame": (
                f"{ORIGINAL_WALK}/{ORIGINAL_PLAIN_FRAME}"
            ),
            "remake_grid_frame": f"{REMAKE_WALK}/{REMAKE_GRID_FRAME}",
            "remake_plain_frame": f"{REMAKE_WALK}/{REMAKE_PLAIN_FRAME}",
            "original_frame_sha256": original_hashes,
        },
        "field_area": list(FIELD_AREA),
        "original": original,
        "remake": remake,
        "original_vs_remake_different_pixels": different,
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
