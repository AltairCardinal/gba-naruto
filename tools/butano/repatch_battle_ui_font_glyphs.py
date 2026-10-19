#!/usr/bin/env python3
"""Rebuild the battle UI font glyphs whose source screenshots are still on disk.

`generate_butano_battle_identity_content.py` rebuilds the whole CJK atlas in one
pass, but eight of its source screenshots were never committed and are gone, so
that pass aborts before it writes anything.  Fifty-six of the hundred
screenshot-sourced characters are therefore unreachable, yet the characters that
carry the visible S49 defects (木, 叶, 丸) are all reachable from
``menu-0.png``.

This tool regenerates only the characters whose source image exists and patches
their tiles into the shipped ``battle_ui_font.bmp``, leaving every other tile
byte-identical.  It refuses to touch a character whose source is missing, so a
partial repair can never be mistaken for a full one.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools import generate_butano_battle_identity_content as generator  # noqa: E402

ATLAS_PATH = ROOT / "butano-sequel/graphics/battle_ui_font.bmp"
PREPARATION_ATLAS_PATH = ROOT / "butano-sequel/graphics/battle_preparation_font.bmp"
GLYPH_WIDTH = generator.UI_GLYPH_WIDTH
GLYPH_HEIGHT = generator.UI_GLYPH_HEIGHT
ASCII_GLYPH_COUNT = generator.ASCII_GLYPH_COUNT

# Tables each atlas draws its screenshot crops from.  The preparation atlas
# starts from the UI atlas and then overlays its own, so it needs all three.
UI_TABLES = (
    "SCENARIO_41_ORIGINAL_GLYPH_SOURCES",
    "ORIGINAL_UI_ASCII_GLYPH_SOURCES",
)
PREPARATION_TABLES = UI_TABLES + (
    "PREPARATION_ORIGINAL_GLYPH_SOURCES",
    "PREPARATION_BASE_GLYPH_SOURCES",
    "TARGET_STATUS_ASCII_GLYPH_SOURCES",
)
ATLASES = {
    "ui": (ATLAS_PATH, generator.generate_ui_font_bitmap, UI_TABLES),
    "preparation": (
        PREPARATION_ATLAS_PATH,
        generator.generate_preparation_font_bitmap,
        PREPARATION_TABLES,
    ),
}


class RepatchError(RuntimeError):
    """The atlas could not be repatched as requested."""


def _table_characters(tables) -> list[str]:
    available: set[str] = set()
    for name in tables:
        available |= set(getattr(generator, name))
    return sorted(available)


def characters_with_available_sources(tables=UI_TABLES) -> list[str]:
    """Characters whose crop source still exists in the work tree."""
    sources: dict[str, list[str]] = {}
    for name in tables:
        for character, spec in getattr(generator, name).items():
            sources.setdefault(character, []).append(spec[0])
    return sorted(
        character for character, paths in sources.items()
        if any((ROOT / path).is_file() for path in paths)
    )


def character_index(character: str) -> int:
    characters = generator.load_identity_content(ROOT)["utf8_characters"]
    try:
        return characters.index(character)
    except ValueError as error:
        raise RepatchError(f"character {character!r} is not in the font list") from error


def build_reference_atlas(available, tables=UI_TABLES, builder=None) -> Image.Image:
    """Render the atlas with only the available screenshot crops enabled.

    Characters whose source is missing fall back to the truetype renderer in
    this reference image; their tiles are discarded by the caller, so the
    fallback never reaches the shipped atlas.
    """
    builder = builder or generator.generate_ui_font_bitmap
    available = set(available)
    saved = {name: getattr(generator, name) for name in tables}
    for name in tables:
        setattr(generator, name, {
            character: spec for character, spec in saved[name].items()
            if character in available and (ROOT / spec[0]).is_file()
        })
    try:
        return builder(ROOT)
    finally:
        for name, table in saved.items():
            setattr(generator, name, table)


def repatch(
    atlas_path: Path = ATLAS_PATH,
    output_path: Path | None = None,
    only: list[str] | None = None,
    kind: str = "ui",
) -> dict[str, object]:
    if kind not in ATLASES:
        raise RepatchError(f"unknown atlas kind {kind!r}; expected one of {sorted(ATLASES)}")
    default_path, builder, tables = ATLASES[kind]
    atlas_path = Path(atlas_path) if atlas_path else Path(default_path)
    if not atlas_path.is_file():
        raise RepatchError(f"missing atlas: {atlas_path}")
    available = characters_with_available_sources(tables)
    # ASCII override tables name characters such as "0" that live in the ASCII
    # block, not in the UTF-8 character list, so they have no CJK tile to patch.
    utf8_characters = set(generator.load_identity_content(ROOT)["utf8_characters"])
    available = [c for c in available if c in utf8_characters]
    selected = [character for character in (only if only is not None else available)
                if character in available]
    if only is not None:
        unreachable = sorted(set(only) - set(available))
        if unreachable:
            raise RepatchError(
                f"source screenshot is gone for: {unreachable}")
    if not selected:
        raise RepatchError("no character to repatch")

    with Image.open(atlas_path) as stored:
        stored_image = stored.copy()
    reference = build_reference_atlas(available, tables, builder)
    if reference.size != stored_image.size:
        raise RepatchError(
            f"reference atlas {reference.size} differs from stored {stored_image.size}")
    if reference.getpalette() != stored_image.getpalette():
        raise RepatchError("reference and stored atlases use different palettes")

    patched = stored_image.copy()
    changes = []
    for character in selected:
        index = character_index(character)
        tile = ASCII_GLYPH_COUNT + index
        top = tile * GLYPH_HEIGHT
        box = (0, top, GLYPH_WIDTH, top + GLYPH_HEIGHT)
        # Compare palette indices, not colours: the two atlases share one
        # palette, so an index difference is exactly a glyph difference.
        before = stored_image.crop(box).tobytes()
        after = reference.crop(box).tobytes()
        if before != after:
            patched.paste(reference.crop(box), (0, top))
            changes.append({
                "character": character,
                "tile": tile,
                "changed": True,
            })
        else:
            changes.append({
                "character": character,
                "tile": tile,
                "changed": False,
            })

    output_path = Path(output_path) if output_path else atlas_path
    patched.save(output_path, format="BMP", bits=4)
    return {
        "schema": "konoha.s49-ui-font-repatch.v1",
        "atlas": str(atlas_path),
        "kind": kind,
        "output": str(output_path),
        "requested": len(selected),
        "changed": sum(1 for change in changes if change["changed"]),
        "unchanged": sum(1 for change in changes if not change["changed"]),
        "unreachable_characters": sorted(
            set(_table_characters(tables)) - set(available)),
        "changes": changes,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=sorted(ATLASES), default="ui",
                        help="which atlas to rebuild (default: ui)")
    parser.add_argument("--atlas", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None,
                        help="write the patched atlas here instead of in place")
    parser.add_argument("--only", default=None,
                        help="comma separated characters to repatch")
    parser.add_argument("--report", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    only = args.only.split(",") if args.only else None
    try:
        result = repatch(args.atlas, args.output, only, args.kind)
    except (RepatchError, OSError, ValueError, KeyError) as error:
        print(f"repatch_battle_ui_font_glyphs: {error}", file=sys.stderr)
        return 2
    if args.report:
        args.report.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "kind": result["kind"],
        "requested": result["requested"],
        "changed": result["changed"],
        "unchanged": result["unchanged"],
        "unreachable": len(result["unreachable_characters"]),
        "output": result["output"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
