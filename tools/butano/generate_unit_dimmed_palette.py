#!/usr/bin/env python3
"""Emit the OBJ palette the original ROM uses for units that are not acting.

Question this answers: the original draws an inactive unit in greyscale while
the remake draws it in full colour.  `battle_unit_visual_catalog.json` shows
every slot the remake extracted carries its own `palette_pointer`, and scanning
all 62 characters x 9 slots for a greyscale palette finds **zero** — so the
greyscale is not an extracted asset.  It has to be something the game writes
into palette RAM while it runs.

That is what the GPU probe reads.  Dumping PRAM at the original's command-menu
frame (`walk-original-a24/step-18-A.ss9`) shows five OBJ banks in use, and one of
them is greyscale in 15 of its 16 entries:

    index  unit palette (bank 1)   dimmed palette (bank 3)
      0    (198,132,255)           (165,165,165)
      1    (33,33,33)               (33,33,33)
      2    (82,90,99)               (90,90,90)
      3    (41,41,99)               (99,99,99)
      4    (255,0,0)                (49,49,49)
      5    (239,189,165)            (198,198,198)
      6    (198,132,107)            (148,148,148)
      7    (132,82,49)              (90,90,90)
      8    (123,132,115)            (107,107,107)
      9    (74,74,74)               (74,74,74)
     10    (74,107,206)             (214,214,214)
     11    (49,49,115)              (156,156,156)
     12    (255,255,255)            (255,255,255)
     13    (206,206,206)            (206,206,206)
     14    (165,165,165)            (165,165,165)
     15    (0,8,8)                  (0,8,8)

Index 0 is the transparent slot in the colour bank and is magenta there; in the
dimmed bank it is light grey.  The dimmed unit is nevertheless drawn over the
grass, so the sprite tiles do not use index 0 as their transparent pixel.

The greys are evenly spread, which is what ruled out a computed desaturation:
`max(r,g,b)`, `(r+g+b)/3` and the luma-weighted form reproduce at most 8 of the
14 greys that actually appear in the frame.  The original ships a palette.

This tool writes that palette out as a Butano sprite palette asset and a
receipt naming the probe inputs it came from.  It refuses to guess: if the PRAM
dump or its inputs are missing it fails instead of falling back to a hand-typed
table, because the whole point of the round trip is that the numbers are read
out of the ROM rather than asserted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.butano.capture_s49_gpu_state import palette_entries  # noqa: E402

DEFAULT_DUMP = (
    ROOT
    / "artifacts/s49-original-gpu-20261020-v2/step-18-cmdmenu"
)
GRAPHICS = ROOT / "butano-sequel/graphics"
OUTPUT_BMP = GRAPHICS / "battle_unit_dimmed_palette.bmp"
OUTPUT_JSON = GRAPHICS / "battle_unit_dimmed_palette.json"
RECEIPT = ROOT / "artifacts/s49-original-gpu-20261020-v2/dimmed-palette-receipt.json"

# OBJ palette banks live after the 0x200-byte background palette RAM.
OBJ_PALETTE_BANK_OFFSET = 0x200
BANK_BYTES = 32
# The bank the command-menu frame uses for the unit that is not acting.
DIMMED_BANK = 3
# The bank the same frame uses for that unit's full-colour self.
COLOUR_BANK = 1

class DimmedPaletteError(RuntimeError):
    """The palette could not be read out of the ROM's palette RAM."""


def read_banks(dump_dir: Path) -> list[list[tuple[int, int, int]]]:
    dump_dir = Path(dump_dir)
    pram = dump_dir / "pram.bin"
    inputs = dump_dir / "inputs.json"
    if not pram.is_file() or not inputs.is_file():
        raise DimmedPaletteError(
            f"{dump_dir} is not a complete GPU probe run; run "
            f"tools/butano/capture_s49_gpu_state.py first"
        )
    payload = json.loads(inputs.read_text(encoding="utf-8"))
    if payload.get("schema") != "konoha.mgba-gpu-state-inputs.v1":
        raise DimmedPaletteError(f"{inputs} is not a GPU probe receipt")
    return palette_entries(pram.read_bytes())


def dimmed_palette(dump_dir: Path = DEFAULT_DUMP) -> tuple[
    list[tuple[int, int, int]], list[tuple[int, int, int]]
]:
    """Return the (dimmed, colour) palettes read out of palette RAM."""

    banks = read_banks(dump_dir)
    dimmed = banks[OBJ_PALETTE_BANK_OFFSET // BANK_BYTES + DIMMED_BANK]
    colour = banks[OBJ_PALETTE_BANK_OFFSET // BANK_BYTES + COLOUR_BANK]
    if len(dimmed) != 16:
        raise DimmedPaletteError("the dimmed bank does not hold 16 entries")
    return dimmed, colour


def check_against_the_frame(palette, frame_path: Path) -> dict[str, object]:
    """Confirm the dump explains the greys the recorded frame actually shows."""

    if not frame_path.is_file():
        raise DimmedPaletteError(f"missing reference frame: {frame_path}")
    frame = Image.open(frame_path).convert("RGB")
    pixels = frame.load()
    observed = {pixels[x, y] for y in range(46, 104) for x in range(84, 116)}
    greys = {c for c in observed if c[0] == c[1] == c[2]}
    covered = greys & set(palette)
    # The frame's window also holds the selection brackets and the unit's own
    # colour bank, so a couple of greys come from elsewhere; what matters is
    # that the bank accounts for most of them.
    if len(covered) < 10:
        raise DimmedPaletteError(
            f"the dimmed bank explains only {len(covered)} of the frame's "
            f"{len(greys)} greys: {sorted(greys)}"
        )
    grey_entries = [c for c in palette if c[0] == c[1] == c[2]]
    if len(grey_entries) < 15:
        raise DimmedPaletteError(
            f"the bank is not a greyscale palette: {len(grey_entries)}/16 grey"
        )
    return {
        "frame": str(frame_path),
        "greys_in_frame": len(greys),
        "greys_explained_by_the_bank": len(covered),
        "greys_from_other_objects": [list(c) for c in sorted(greys - set(palette))],
        "bank_entries": len(grey_entries),
    }


TRANSPARENT = (197, 131, 255)


def write_palette(palette, bmp_path: Path = OUTPUT_BMP, json_path: Path = OUTPUT_JSON):
    """Write a 16-entry sprite palette in the shape Butano's asset tool reads.

    Index 0 is replaced by the remake's transparent magenta.  The original's
    dimmed bank has a light grey at index 0, but that entry is never rendered
    there -- the original's dimmed sprite keeps its transparent pixels
    transparent.  The remake's unit art, on the other hand, uses index 0 for
    roughly half of every sprite, so a light grey there would paint a grey box
    around every dimmed unit.
    """

    palette = [TRANSPARENT] + [tuple(entry) for entry in palette[1:]]
    image = Image.new("P", (8, 8), 0)
    flat: list[int] = []
    for entry in palette:
        flat.extend(entry)
    # Butano keeps a 4bpp palette in 16 slots; pad the rest with black.
    flat.extend([0, 0, 0] * (48 - len(flat)))
    image.putpalette(flat)
    # Index the first sixteen pixels so the BMP actually carries the colours.
    image.putdata(list(range(16)) + [0] * 48)
    bmp_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(bmp_path, format="BMP", bits=4)
    json_path.write_text(
        json.dumps({"type": "sprite_palette"}, indent=2) + "\n", encoding="utf-8"
    )


def build(
    dump_dir: Path = DEFAULT_DUMP,
    frame_path: Path | None = None,
    bmp_path: Path = OUTPUT_BMP,
    json_path: Path = OUTPUT_JSON,
    receipt_path: Path = RECEIPT,
    write: bool = True,
) -> dict[str, object]:
    dimmed, colour = dimmed_palette(dump_dir)
    inputs = json.loads((Path(dump_dir) / "inputs.json").read_text(encoding="utf-8"))
    frame = frame_path
    if frame is None:
        frame = ROOT / "artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-18-A.png"
    report = check_against_the_frame(dimmed, frame)
    if write:
        write_palette(dimmed, Path(bmp_path), Path(json_path))
    payload = {
        "schema": "konoha.s49-unit-dimmed-palette.v1",
        "source": {
            "probe_inputs": inputs,
            "pram_sha256": hashlib.sha256(
                (Path(dump_dir) / "pram.bin").read_bytes()
            ).hexdigest(),
            "obj_palette_bank": DIMMED_BANK,
            "colour_bank_for_comparison": COLOUR_BANK,
        },
        "dimmed": [list(entry) for entry in dimmed],
        "colour": [list(entry) for entry in colour],
        "frame_check": report,
        "outputs": {"bmp": str(bmp_path), "json": str(json_path)},
    }
    if write:
        Path(receipt_path).parent.mkdir(parents=True, exist_ok=True)
        Path(receipt_path).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump-dir", type=Path, default=DEFAULT_DUMP)
    parser.add_argument("--frame", type=Path, default=None)
    parser.add_argument("--bmp", type=Path, default=OUTPUT_BMP)
    parser.add_argument("--json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="read the palette and print it without writing any file",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = build(
            args.dump_dir,
            args.frame,
            args.bmp,
            args.json,
            args.receipt,
            write=not args.dry_run,
        )
    except DimmedPaletteError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "dimmed": payload["dimmed"],
                "frame_check": payload["frame_check"],
                "outputs": payload["outputs"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
