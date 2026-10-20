#!/usr/bin/env python3
"""Identify which exported character frame a rendered GBA frame is showing.

The battle scene draws a unit as a 32x64 sprite whose pixels come from the
original game's ``character-battle-visuals-v1`` export.  Recovering the frame
index from a rendered PNG is only possible because the export also ships the
unit's 16 colour BGR555 palette, which makes the screen RGB -> palette index
mapping an exact lookup rather than a nearest-neighbour guess:

* a screen pixel whose RGB is in the unit's palette maps to that palette index;
* a screen pixel whose RGB is NOT in the palette was covered by something else
  (a cursor, another sprite, the UI) and carries no information about the
  unit's frame;
* the exported frame PNGs are palette indexed with the same 16 colours, so the
  comparison is done in palette index space.

A candidate frame is accepted only when every pixel that is opaque in the
frame *and* visible on screen carries the same palette index ("true mismatch"
must be zero).  A frame that merely lands on similar colours is rejected.

The tool writes a JSON receipt so a claim can be re-run and cited.  It never
guesses: when no frame reaches zero true mismatch, the receipt records that
fact instead of naming a frame.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REVERSE_ROOT = Path("/Users/altair/github/gba-naruto-reverse")
DEFAULT_VISUALS = Path("artifacts/character-battle-visuals-v1")
SCREEN_SIZE = (240, 160)
# The export stores one BGR555 entry per palette slot.
PALETTE_ENTRY_BYTES = 2


class MeasureError(RuntimeError):
    """The frame cannot be measured as declared."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bgr555_to_rgb(entry: int) -> tuple[int, int, int]:
    """Decode one little-endian BGR555 entry into 8 bit RGB."""
    red = entry & 0x1F
    green = (entry >> 5) & 0x1F
    blue = (entry >> 10) & 0x1F
    return ((blue << 3) | (blue >> 2), (green << 3) | (green >> 2), (red << 3) | (red >> 2))


def load_palette(path: Path) -> list[tuple[int, int, int]]:
    raw = Path(path).read_bytes()
    if len(raw) % PALETTE_ENTRY_BYTES:
        raise MeasureError(f"palette size {len(raw)} is not a multiple of 2")
    entries = []
    for offset in range(0, len(raw), PALETTE_ENTRY_BYTES):
        entries.append(bgr555_to_rgb(int.from_bytes(raw[offset:offset + 2], "little")))
    return entries


def screen_index_map(image: Image.Image, palette: Sequence[tuple[int, int, int]]) -> list[int]:
    """Map a rendered frame to palette indices, using -1 for foreign colours."""
    lookup = {color: index for index, color in enumerate(palette)}
    raw = image.convert("RGB").tobytes()
    pixels = [
        (raw[offset], raw[offset + 1], raw[offset + 2])
        for offset in range(0, len(raw), 3)
    ]
    return [lookup.get(pixel, -1) for pixel in pixels]


def frame_index_map(image: Image.Image) -> list[int]:
    """Read the palette indices of an exported frame PNG."""
    if image.mode != "P":
        raise MeasureError(f"exported frame must be palette indexed, got {image.mode}")
    return list(image.tobytes())


def _anchor_candidates(
    screen: Sequence[int],
    width: int,
    height: int,
    frame: Sequence[int],
    frame_width: int,
    frame_height: int,
) -> list[tuple[int, int]]:
    """Screen origins whose anchor pixel agrees with the frame's anchor."""
    opaque = [index for index, value in enumerate(frame) if value != 0]
    if not opaque:
        return []
    counts: dict[int, int] = {}
    for index in opaque:
        value = frame[index]
        counts[value] = counts.get(value, 0) + 1
    anchor_value = max(counts, key=lambda value: (counts[value], -value))
    anchor_index = next(index for index in opaque if frame[index] == anchor_value)
    anchor_x = anchor_index % frame_width
    anchor_y = anchor_index // frame_width
    positions = []
    for y in range(height - frame_height + 1):
        row = y * width
        for x in range(width - frame_width + 1):
            if screen[row + x + anchor_y * width + anchor_x] == anchor_value:
                positions.append((x, y))
    return positions


def match_frame(
    screen: Sequence[int],
    width: int,
    height: int,
    frame: Sequence[int],
    frame_width: int,
    frame_height: int,
    region: tuple[int, int, int, int] | None,
) -> dict[str, int]:
    """Score one exported frame against the screen at every candidate origin."""
    if region is not None:
        x0, y0, x1, y1 = region
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(width, x1)
        y1 = min(height, y1)
    else:
        x0, y0, x1, y1 = 0, 0, width, height

    best = {"matched": 0, "covered": 0, "true_mismatch": 1 << 30, "x": -1, "y": -1}
    opaque = [index for index, value in enumerate(frame) if value != 0]
    if not opaque:
        return best
    for origin_x, origin_y in _anchor_candidates(
        screen, width, height, frame, frame_width, frame_height
    ):
        if origin_x < x0 or origin_y < y0 or origin_x + frame_width > x1 or origin_y + frame_height > y1:
            continue
        matched = 0
        covered = 0
        mismatch = 0
        for index in opaque:
            dx = index % frame_width
            dy = index // frame_width
            value = screen[(origin_y + dy) * width + origin_x + dx]
            if value == -1:
                covered += 1
            elif value == frame[index]:
                matched += 1
            else:
                mismatch += 1
        if mismatch < best["true_mismatch"] or (
            mismatch == best["true_mismatch"] and matched > best["matched"]
        ):
            best = {
                "matched": matched,
                "covered": covered,
                "true_mismatch": mismatch,
                "x": origin_x,
                "y": origin_y,
            }
        if mismatch == 0:
            break
    return best


def find_character_resource(
    visuals_root: Path, character_id: int, visual_slot: int
) -> tuple[Path, dict[str, object]]:
    manifest_path = visuals_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for slot in manifest["slots"]:
        if (
            slot.get("character_id") == character_id
            and slot.get("visual_slot") == visual_slot
            and slot.get("populated")
        ):
            resource = visuals_root / f"resource-{slot['resource_id']:03d}"
            return resource, slot
    raise MeasureError(
        f"no populated slot {visual_slot} for character {character_id} in {manifest_path}"
    )


def measure(
    frame_path: Path,
    visuals_root: Path,
    character_id: int,
    visual_slot: int,
    region: tuple[int, int, int, int] | None,
) -> dict[str, object]:
    frame_path = Path(frame_path)
    if not frame_path.is_file():
        raise MeasureError(f"missing frame: {frame_path}")
    resource, slot = find_character_resource(visuals_root, character_id, visual_slot)
    palette_path = resource / "palette-bgr555.bin"
    palette = load_palette(palette_path)
    with Image.open(frame_path) as image:
        if image.size != SCREEN_SIZE:
            raise MeasureError(f"expected a {SCREEN_SIZE[0]}x{SCREEN_SIZE[1]} frame, got {image.size}")
        screen = screen_index_map(image, palette)
    width, height = SCREEN_SIZE

    frame_paths = sorted(resource.glob("frame-*.png"))
    if not frame_paths:
        raise MeasureError(f"no exported frames under {resource}")

    table = []
    for path in frame_paths:
        with Image.open(path) as image:
            frame = frame_index_map(image)
            frame_width, frame_height = image.size
        score = match_frame(screen, width, height, frame, frame_width, frame_height, region)
        table.append(
            {
                "frame": path.name,
                "frame_index": int(path.stem.split("-")[-1]),
                "frame_sha256": sha256_file(path),
                "matched": score["matched"],
                "covered": score["covered"],
                "true_mismatch": score["true_mismatch"],
                "origin": [score["x"], score["y"]],
            }
        )

    accepted = [entry for entry in table if entry["true_mismatch"] == 0]
    accepted.sort(key=lambda entry: (-entry["matched"], entry["frame_index"]))
    chosen = accepted[0] if accepted else None
    return {
        "schema": "konoha.s49-selected-unit-frame.v1",
        "frame": str(frame_path),
        "frame_sha256": sha256_file(frame_path),
        "visuals_root": str(visuals_root),
        "character_id": character_id,
        "visual_slot": visual_slot,
        "resource": str(resource),
        "palette_sha256": sha256_file(palette_path),
        "palette_rgb": [list(color) for color in palette],
        "region": list(region) if region else None,
        "table": table,
        "accepted_count": len(accepted),
        "chosen": chosen,
        "identified": chosen is not None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame", type=Path, required=True)
    parser.add_argument("--visuals-root", type=Path, default=DEFAULT_REVERSE_ROOT / DEFAULT_VISUALS)
    parser.add_argument("--character", type=int, default=1)
    parser.add_argument("--slot", type=int, default=0)
    parser.add_argument(
        "--region",
        default=None,
        help="optional x0,y0,x1,y1 restriction of the search area",
    )
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    region = None
    if args.region:
        parts = [int(value) for value in args.region.split(",")]
        if len(parts) != 4:
            print("measure_s49_selected_unit_frame: region needs x0,y0,x1,y1", flush=True)
            return 2
        region = (parts[0], parts[1], parts[2], parts[3])
    try:
        receipt = measure(args.frame, args.visuals_root, args.character, args.slot, region)
    except (MeasureError, OSError, ValueError, KeyError) as error:
        print(f"measure_s49_selected_unit_frame: {error}", flush=True)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "frame": str(args.frame),
                "identified": receipt["identified"],
                "frame_index": receipt["chosen"]["frame_index"] if receipt["chosen"] else None,
                "matched": receipt["chosen"]["matched"] if receipt["chosen"] else None,
                "true_mismatch": receipt["chosen"]["true_mismatch"] if receipt["chosen"] else None,
                "origin": receipt["chosen"]["origin"] if receipt["chosen"] else None,
                "out": str(args.out),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if receipt["identified"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
