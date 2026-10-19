#!/usr/bin/env python3
"""Compare the original's inactive-unit sprite with the remake's, by silhouette.

The remake draws the unit that is not acting in full colour; the original draws
it with a greyscale palette.  That raises the obvious question: are the two
pictures even the same artwork?  If they are, the difference is one palette
swap plus a position offset.  If they are not, the remake is missing art.

The original side is produced by re-rendering the captured frame with the
greyscale OBJ bank replaced by the unit's own colour bank, so the unit comes
back in colour.  Both sides are then reduced to "not grass" masks and compared
over every plausible alignment, because the two builds place the unit
differently.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.butano import render_scenario_41_gpu as renderer  # noqa: E402

DUMP = ROOT / "artifacts/s49-original-gpu-20261020-v2/step-18"
REMAKE_FRAME = (
    ROOT
    / "artifacts/s49-fidelity-20261019-v1/walk-remake-dd-a30-chakrafix/step-18-A.png"
)
WINDOW = (74, 44, 118, 108)

GRASS = frozenset(
    {
        (173, 173, 49),
        (198, 198, 66),
        (132, 189, 49),
        (198, 239, 82),
        (123, 156, 41),
        (156, 231, 66),
        (222, 222, 90),
        (148, 148, 33),
        (115, 140, 33),
        (231, 255, 107),
        (199, 199, 199),
        (84, 189, 49),
    }
)


def colourised_original() -> Image.Image:
    """Render the captured frame with the dimmed bank replaced by the colour one."""

    io = (DUMP / "io.bin").read_bytes()
    pram = bytearray((DUMP / "pram.bin").read_bytes())
    oam = (DUMP / "oam.bin").read_bytes()
    vram = (DUMP / "vram.bin").read_bytes()
    dimmed = 0x200 + 3 * 32
    colour = 0x200 + 1 * 32
    pram[dimmed:dimmed + 32] = pram[colour:colour + 32]
    return Image.frombytes(
        "RGB",
        (240, 160),
        renderer.render_mode0(io, bytes(pram), oam, vram),
    )


def not_grass(image: Image.Image, window) -> set[tuple[int, int]]:
    x0, y0, x1, y1 = window
    pixels = image.load()
    return {
        (x, y)
        for y in range(y0, y1)
        for x in range(x0, x1)
        if pixels[x, y] not in GRASS
    }


def best_alignment(left, right) -> tuple[float, int, int]:
    best = (0.0, 0, 0)
    for dx in range(-26, 27):
        for dy in range(-18, 19):
            shifted = {(x + dx, y + dy) for x, y in right}
            union = left | shifted
            if not union:
                continue
            iou = len(left & shifted) / len(union)
            if iou > best[0]:
                best = (iou, dx, dy)
    return best


def main() -> int:
    original = colourised_original()
    remake = Image.open(REMAKE_FRAME).convert("RGB")
    left = not_grass(original, WINDOW)
    right = not_grass(remake, WINDOW)
    iou, dx, dy = best_alignment(left, right)
    print(f"non-grass pixels in the window: original {len(left)}, remake {len(right)}")
    print(f"best silhouette IoU = {iou:.3f} at dx={dx} dy={dy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
