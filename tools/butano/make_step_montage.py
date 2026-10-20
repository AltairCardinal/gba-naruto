#!/usr/bin/env python3
"""Build a labelled contact sheet from a captured walk directory.

Reading a step's content off a contact sheet is exactly what invalidated three
S49 pairing baselines before: the sheet is a lossy view, so a conclusion drawn
from it is a hypothesis, not evidence.  This tool therefore has one job only --
produce a sheet that is cheap to *look* at, so a candidate screen can be
identified quickly and then confirmed by opening that single frame at full
resolution.

The tool never rewrites, filters or scores anything.  It copies whole frames
without cropping, scaling or recolouring them, and it labels each cell with the
step number and the key that produced it, so the sheet can be turned back into
exact file names.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from PIL import Image

STEP_PATTERN = re.compile(r"^step-(\d+)-(.+)\.png$")
DEFAULT_COLUMNS = 5
DEFAULT_SCALE = 2


class MontageError(RuntimeError):
    """The walk directory could not be turned into a sheet as declared."""


def collect_steps(directory: Path) -> list[tuple[int, str, Path]]:
    """Return (step number, key label, png path) for every step of one walk."""
    steps: list[tuple[int, str, Path]] = []
    for path in sorted(directory.glob("step-*.png")):
        match = STEP_PATTERN.match(path.name)
        if not match:
            continue
        steps.append((int(match.group(1)), match.group(2), path))
    if not steps:
        raise MontageError(f"no step images found in {directory}")
    return steps


def read_key_sequence(directory: Path) -> dict[int, str]:
    """Map step number to the key that produced it, from the capture receipt."""
    receipt = directory / "inputs.json"
    if not receipt.is_file():
        return {}
    data = json.loads(receipt.read_text())
    keys = data.get("keys") or []
    result: dict[int, str] = {}
    for index, key in enumerate(keys):
        result[index + 1] = str(key)
    return result


def build_sheet(
    steps: list[tuple[int, str, Path]],
    key_sequence: dict[int, str],
    columns: int,
    scale: int,
) -> Image.Image:
    """Compose the sheet: one whole frame per cell, no filtering."""
    frames: list[tuple[int, str, Image.Image]] = []
    for number, label, path in steps:
        with Image.open(path) as image:
            frames.append((number, label, image.convert("RGB")))

    frame_width, frame_height = frames[0][2].size
    cell_width = frame_width * scale
    cell_height = frame_height * scale
    rows = (len(frames) + columns - 1) // columns
    sheet = Image.new(
        "RGB",
        (columns * cell_width, rows * cell_height),
        (16, 16, 16),
    )
    for index, (number, label, frame) in enumerate(frames):
        column = index % columns
        row = index // columns
        if frame.size != (frame_width, frame_height):
            raise MontageError(
                f"frame size mismatch: {label} is {frame.size}, expected "
                f"{(frame_width, frame_height)}"
            )
        scaled = frame.resize((cell_width, cell_height), Image.NEAREST)
        sheet.paste(scaled, (column * cell_width, row * cell_height))
        key = key_sequence.get(number, label)
        _stamp(sheet, column * cell_width, row * cell_height, number, key)
    return sheet


def _stamp(
    sheet: Image.Image,
    x: int,
    y: int,
    number: int,
    key: str,
) -> None:
    """Write a small label block into the top-left corner of one cell.

    The label uses the bitmap default font so the tool needs no font files and
    no external dependencies.
    """
    from PIL import ImageDraw

    draw = ImageDraw.Draw(sheet)
    text = f"{number:02d} {key}"
    box = draw.textbbox((0, 0), text)
    width = box[2] - box[0]
    height = box[3] - box[1]
    draw.rectangle(
        (x, y, x + width + 4, y + height + 4),
        fill=(0, 0, 0),
    )
    draw.text((x + 2, y + 2), text, fill=(255, 255, 0))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("walk", type=Path, help="capture directory to sheet")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output png path (default: <walk>-montage.png next to the walk)",
    )
    parser.add_argument("--columns", type=int, default=DEFAULT_COLUMNS)
    parser.add_argument("--scale", type=int, default=DEFAULT_SCALE)
    args = parser.parse_args()

    walk = args.walk.resolve()
    if not walk.is_dir():
        raise MontageError(f"not a directory: {walk}")
    steps = collect_steps(walk)
    sheet = build_sheet(
        steps,
        read_key_sequence(walk),
        max(1, args.columns),
        max(1, args.scale),
    )
    out = args.out or walk.parent / f"{walk.name}-montage.png"
    sheet.save(out)
    print(f"wrote {out} ({sheet.size[0]}x{sheet.size[1]}) from {len(steps)} steps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
