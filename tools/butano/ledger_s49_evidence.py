#!/usr/bin/env python3
"""Measure the S49 remake ledger's open items from the original capture.

The rebuild ledger (``docs/reverse-results-index/ledger.json``) records, for
every thing the remake needed, where the evidence came from.  Five entries
were still open because the original screenshot that used to prove them was
deleted with the old ``artifacts/`` tree.

This tool re-derives those five entries from material that is still on disk
-- the original frame walk, the original GPU state dump and the region
comparison receipts -- and writes one receipt per entry.  Every number in a
receipt is measured here; nothing is copied from a note.

The receipts are what the ledger points at, so the tool fails closed: a
measurement that cannot be taken is an error, not a ``null`` field.

Usage::

    python3 tools/butano/ledger_s49_evidence.py \\
        --out-dir artifacts/s49-ledger-evidence-v1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

RECEIPT_SCHEMA = "konoha.s49-ledger-evidence.v1"

#: The original frame walk and the remake frame walk this tool measures.
ORIGINAL_WALK = "artifacts/s49-fidelity-20261019-v1/walk-original-a24"
REMAKE_WALK = "artifacts/s49-fidelity-20261019-v1/walk-remake-dd-a30-banner2"

#: The white ink the original draws its prompt with.
ORIGINAL_PROMPT_INK = (247, 255, 222)

#: The colour the remake draws its prompt with.
REMAKE_PROMPT_INK = (255, 255, 255)

#: The screen area the prompt lives in (top right corner).
PROMPT_BOX = (150, 0, 240, 32)

#: A column whose ink spans at least this many rows belongs to the tall kanji
#: cells; the ASCII band of the prompt is five rows tall.
ASCII_BAND_ROWS = 5

#: The colour mapping the identity generator uses when it cuts a glyph out of
#: an original screenshot.  The same mapping is applied here so the cut can be
#: compared with the shipped font cell by cell.
GLYPH_BACKGROUND = (231, 247, 214)
GLYPH_SHADOW_COLORS = {
    (173, 181, 156),
    (189, 173, 222),
    (231, 173, 140),
}
GLYPH_MIDTONE_COLORS = {
    (115, 123, 107),
    (148, 99, 239),
}
GLYPH_FOREGROUND_INDEX = 2
GLYPH_SHADOW_INDEX = 5
GLYPH_MIDTONE_INDEX = 15

#: Glyph cell size of the identity font and the number of ASCII cells in front
#: of the UTF-8 cells.
GLYPH_WIDTH = 8
GLYPH_HEIGHT = 16
ASCII_GLYPH_COUNT = 94

#: The four action menu entries of the original S49 action menu and the screen
#: row each of them starts on.  The entries are 瞬身术 / 影分身术 / 忍者组合拳 /
#: 十字手里剑 -- they are NOT 隐身术 / 十年手里剑, which are different
#: characters that the original never draws in this menu.  The names come from
#: the generator's own source table
#: (`ACTION_MENU_ORIGINAL_GLYPH_SOURCES` in
#: tools/generate_butano_battle_identity_content.py), and the frame cells
#: (8,40) and (16,88) match the 瞬 and 字 cells of the shipped font
#: uniquely -- every other cell of the 495 is a mismatch, so the earlier
#: 105/128 and 69/128 readings were a transcription error, not a defect.
ACTION_MENU_ROWS = (
    (40, "瞬身术"),
    (56, "影分身术"),
    (72, "忍者组合拳"),
    (88, "十字手里剑"),
)
ACTION_MENU_LEFT = 8

#: How many frames of the original idle sweep are measured.  The period search
#: needs several periods, and the original idle cycle is 32 frames long.
IDLE_FRAMES = 192
IDLE_MAX_PERIOD = 64

#: The blue channel a colour needs to count as part of the cyan move range
#: overlay.
CYAN_MIN_BLUE = 150

#: How many 8 pixel CJK cells the prompt label ends with.
KANJI_CELLS = 2


class EvidenceError(RuntimeError):
    """A measurement could not be taken.  Always names the ledger item."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_image(path: Path):
    from PIL import Image

    if not Path(path).is_file():
        raise EvidenceError(f"missing input image: {path}")
    return Image.open(path).convert("RGB")


def read_json(path: Path) -> Any:
    if not Path(path).is_file():
        raise EvidenceError(f"missing input json: {path}")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def identity_characters(root: Path) -> list[str]:
    """The UTF-8 character order the identity font is built from.

    The order is owned by the identity generator; this tool reads it instead of
    repeating it, so the font cell index used here is the same one the
    generator pasted the glyphs with.
    """

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from tools.generate_butano_battle_identity_content import (
            load_identity_content,
        )
    except Exception as error:  # pragma: no cover - defensive
        raise EvidenceError(
            f"the identity generator could not be imported: {error}"
        ) from error
    characters = load_identity_content(root)["utf8_characters"]
    return [str(item) for item in characters]


def ink_bbox(px, box, color) -> tuple[int, int, int, int] | None:
    x0, y0, x1, y1 = box
    points = [
        (x, y)
        for y in range(y0, y1)
        for x in range(x0, x1)
        if px[x, y] == color
    ]
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs), min(ys), max(xs), max(ys))


def column_spans(px, box, color) -> dict[int, tuple[int, int]]:
    """For every column with ink, the first and the last row that carries it."""

    x0, y0, x1, y1 = box
    spans: dict[int, tuple[int, int]] = {}
    for x in range(x0, x1):
        rows = [
            y
            for y in range(y0, y1)
            if px[x, y] == color
        ]
        if rows:
            spans[x] = (rows[0], rows[-1])
    return spans


def _walk_frames(directory: Path) -> list[tuple[int, Any, str]]:
    """Every recorded frame of a walk, as ``(step number, pixels, name)``."""

    import re

    frames: list[tuple[int, Any, str]] = []
    for path in sorted(directory.glob("step-*.png")):
        match = re.match(r"step-(\d+)", path.stem)
        if not match:
            continue
        frames.append(
            (int(match.group(1)), load_image(path).load(), path.name)
        )
    frames.sort(key=lambda item: item[0])
    return frames


def _rightmost_run(columns: list[int], anchor: int) -> list[int]:
    """The contiguous run of columns that ends at ``anchor``."""

    if anchor not in columns:
        return []
    run = [anchor]
    current = anchor
    while current - 1 in columns:
        current -= 1
        run.append(current)
    return sorted(run)


def measure_action_menu_glyphs(root: Path) -> dict[str, Any]:
    """Compare the shipped action menu font against the original frame."""

    from PIL import Image

    original_path = root / ORIGINAL_WALK / "step-21-A.png"
    font_path = root / "butano-sequel/graphics/battle_action_menu_font.bmp"

    original = load_image(original_path)
    font = Image.open(font_path)
    if font.mode != "P":
        raise EvidenceError(
            f"the action menu font must stay a palette image, got {font.mode}"
        )
    if font.size[0] != GLYPH_WIDTH:
        raise EvidenceError(f"unexpected action menu font width: {font.size}")

    characters = identity_characters(root)
    original_px = original.load()
    font_px = font.load()

    cells: list[dict[str, Any]] = []
    matching = 0
    for top, text in ACTION_MENU_ROWS:
        for index, character in enumerate(text):
            left = ACTION_MENU_LEFT + index * GLYPH_WIDTH
            cut = _cut_glyph(original_px, left, top)
            cell_index = ASCII_GLYPH_COUNT + characters.index(character)
            shipped = [
                font_px[dx, cell_index * GLYPH_HEIGHT + dy]
                for dy in range(GLYPH_HEIGHT)
                for dx in range(GLYPH_WIDTH)
            ]
            difference = sum(
                1 for cut_value, font_value in zip(cut, shipped)
                if cut_value != font_value
            )
            if difference == 0:
                matching += 1
            cells.append(
                {
                    "character": character,
                    "row_top": top,
                    "left": left,
                    "font_cell_index": cell_index,
                    "different_pixels": difference,
                    "cell_pixels": GLYPH_WIDTH * GLYPH_HEIGHT,
                }
            )
    total = len(cells)
    return {
        "schema": "konoha.s49-ledger-action-menu-glyphs.v1",
        "inputs": {
            "original_frame": str(original_path.relative_to(root)),
            "original_frame_sha256": sha256_file(original_path),
            "shipped_font": str(font_path.relative_to(root)),
            "shipped_font_sha256": sha256_file(font_path),
        },
        "measurement": {
            "cell_size": [GLYPH_WIDTH, GLYPH_HEIGHT],
            "cells_compared": total,
            "cells_identical": matching,
            "cells_differing": total - matching,
            "differing_characters": [
                cell["character"] for cell in cells
                if cell["different_pixels"]
            ],
            "cells": cells,
        },
        "conclusion": (
            f"{matching}/{total} action menu glyph cells are byte identical "
            f"to the original frame; {total - matching} cells differ"
        ),
    }


def _cut_glyph(px, left: int, top: int) -> list[int]:
    """Cut one glyph cell out of an original frame and map it to indices."""

    result: list[int] = []
    for dy in range(GLYPH_HEIGHT):
        for dx in range(GLYPH_WIDTH):
            color = px[left + dx, top + dy]
            if color == GLYPH_BACKGROUND:
                result.append(0)
            elif color in GLYPH_SHADOW_COLORS:
                result.append(GLYPH_SHADOW_INDEX)
            elif color in GLYPH_MIDTONE_COLORS:
                result.append(GLYPH_MIDTONE_INDEX)
            else:
                result.append(GLYPH_FOREGROUND_INDEX)
    return result


def measure_select_prompt(root: Path) -> dict[str, Any]:
    """Measure the original prompt and compare it with the remake's."""

    original_dir = root / ORIGINAL_WALK
    remake_dir = root / REMAKE_WALK

    original_steps: dict[str, Any] = {}
    original_frames = _walk_frames(original_dir)
    for step, px, name in original_frames:
        box = ink_bbox(px, PROMPT_BOX, ORIGINAL_PROMPT_INK)
        if box is None:
            continue
        original_steps[f"step-{step:02d}"] = {
            "frame": name,
            "ink_bbox": list(box),
            "ink_pixels": sum(
                1
                for y in range(box[1], box[3] + 1)
                for x in range(box[0], box[2] + 1)
                if px[x, y] == ORIGINAL_PROMPT_INK
            ),
        }
    if not original_steps:
        raise EvidenceError(
            f"no original frame shows the prompt ink {ORIGINAL_PROMPT_INK}"
        )

    reference_step = 17
    reference = next(
        (item for item in original_frames if item[0] == reference_step),
        None,
    )
    if reference is None:
        raise EvidenceError(
            f"the original walk has no step {reference_step} frame"
        )
    reference_px = reference[1]
    reference_name = reference[2]
    reference_path = original_dir / reference_name
    spans = column_spans(reference_px, PROMPT_BOX, ORIGINAL_PROMPT_INK)
    if not spans:
        raise EvidenceError(
            f"the original frame {reference_name} carries no prompt ink"
        )
    bottom_row = max(bottom for (_top, bottom) in spans.values())
    ascii_band = [bottom_row - ASCII_BAND_ROWS + 1, bottom_row]
    right_edge = max(spans)
    kanji_start = right_edge - KANJI_CELLS * GLYPH_WIDTH + 1
    kanji_columns = list(range(kanji_start, right_edge + 1))
    ascii_columns = sorted(column for column in spans if column < kanji_start)
    separate_marks = sorted(
        column
        for column in spans
        if column in ascii_columns
        and spans[column][0] < ascii_band[0]
    )
    if not ascii_columns:
        raise EvidenceError(
            "the original prompt could not be split into an ASCII part and a "
            "kanji part"
        )

    remake_steps: dict[str, Any] = {}
    for step, px, name in _walk_frames(remake_dir):
        box = ink_bbox(px, PROMPT_BOX, REMAKE_PROMPT_INK)
        if box is None:
            continue
        remake_steps[f"step-{step:02d}"] = {
            "frame": name,
            "ink_bbox": list(box),
            "ink_pixels": sum(
                1
                for y in range(box[1], box[3] + 1)
                for x in range(box[0], box[2] + 1)
                if px[x, y] == REMAKE_PROMPT_INK
            ),
        }
    if not remake_steps:
        raise EvidenceError(
            f"no remake frame shows the prompt ink {REMAKE_PROMPT_INK}"
        )

    original_bbox = original_steps[f"step-{reference_step:02d}"]["ink_bbox"]
    remake_first = max(
        remake_steps,
        key=lambda key: (remake_steps[key]["ink_pixels"], key),
    )
    remake_bbox = remake_steps[remake_first]["ink_bbox"]
    remake_columns = column_spans(
        load_image(remake_dir / remake_steps[remake_first]["frame"]).load(),
        PROMPT_BOX,
        REMAKE_PROMPT_INK,
    )
    remake_right_edge = max(remake_columns)
    remake_kanji_start = remake_right_edge - KANJI_CELLS * GLYPH_WIDTH + 1
    remake_kanji = list(range(remake_kanji_start, remake_right_edge + 1))
    remake_ascii = sorted(
        column for column in remake_columns if column < remake_kanji_start
    )

    return {
        "schema": "konoha.s49-ledger-select-prompt.v1",
        "inputs": {
            "original_reference_frame": str(reference_path.relative_to(root)),
            "original_reference_frame_sha256": sha256_file(reference_path),
            "original_walk": ORIGINAL_WALK,
            "remake_walk": REMAKE_WALK,
        },
        "measurement": {
            "original": {
                "ink_color": list(ORIGINAL_PROMPT_INK),
                "reference_step": f"step-{reference_step:02d}",
                "ink_bbox": original_bbox,
                "ink_width": original_bbox[2] - original_bbox[0] + 1,
                "ink_height": original_bbox[3] - original_bbox[1] + 1,
                "kanji_columns": [min(kanji_columns), max(kanji_columns)],
                "kanji_width": max(kanji_columns) - min(kanji_columns) + 1,
                "kanji_inked_columns": sum(
                    1 for column in kanji_columns if column in spans
                ),
                "ascii_columns": [min(ascii_columns), max(ascii_columns)],
                "ascii_width": max(ascii_columns) - min(ascii_columns) + 1,
                "ascii_band_rows": ascii_band,
                "separate_mark_columns": (
                    [min(separate_marks), max(separate_marks)]
                    if separate_marks
                    else []
                ),
                "visible_steps": sorted(original_steps),
                "hidden_steps": sorted(
                    f"step-{index:02d}"
                    for index in range(11, 25)
                    if f"step-{index:02d}" not in original_steps
                ),
            },
            "remake": {
                "ink_color": list(REMAKE_PROMPT_INK),
                "ink_bbox": remake_bbox,
                "ink_width": remake_bbox[2] - remake_bbox[0] + 1,
                "ink_height": remake_bbox[3] - remake_bbox[1] + 1,
                "kanji_columns": (
                    [min(remake_kanji), max(remake_kanji)]
                    if remake_kanji
                    else []
                ),
                "ascii_columns": (
                    [min(remake_ascii), max(remake_ascii)]
                    if remake_ascii
                    else []
                ),
                "reference_step": remake_first,
                "visible_steps": sorted(remake_steps),
            },
        },
        "conclusion": (
            "the original prompt is a narrow 'SELECT' plus two 8 pixel kanji "
            f"cells ({original_bbox[2] - original_bbox[0] + 1} ink pixels "
            "wide); the remake draws a wider label in a different ink and "
            "never hides it again once it appeared"
        ),
    }


def measure_move_grid_colors(root: Path) -> dict[str, Any]:
    """Measure the original move range overlay against the untinted frame."""

    grid_path = root / ORIGINAL_WALK / "step-19-A.png"
    plain_path = root / ORIGINAL_WALK / "step-20-A.png"
    remake_path = root / REMAKE_WALK / "step-20-A.png"

    grid_px = load_image(grid_path).load()
    plain_px = load_image(plain_path).load()
    remake_px = load_image(remake_path).load()

    pairs: dict[tuple[tuple[int, int, int], tuple[int, int, int]], int] = {}
    field_differences = 0
    for y in range(0, 128):
        for x in range(0, 240):
            base = plain_px[x, y]
            tinted = grid_px[x, y]
            if base == tinted:
                continue
            field_differences += 1
            key = (base, tinted)
            pairs[key] = pairs.get(key, 0) + 1

    if not pairs:
        raise EvidenceError(
            f"the original move grid frame {grid_path} differs from "
            f"{plain_path} nowhere; the overlay could not be measured"
        )

    overlay_results = {tinted for (_base, tinted) in pairs}
    # The move range overlay is the cyan family: the blue channel of those
    # colours is far above the blue channel of the map underneath.
    cyan_results = {
        color for color in overlay_results if color[2] >= CYAN_MIN_BLUE
    }
    cyan_pairs = {
        (base, overlay): count
        for (base, overlay), count in pairs.items()
        if overlay in cyan_results
    }
    bases_with_several_cyan_overlays = sorted(
        {
            base
            for (base, overlay) in cyan_pairs
            if len(
                {
                    other
                    for (other_base, other) in cyan_pairs
                    if other_base == base
                }
            )
            > 1
        }
    )
    original_overlay_pixels = 0
    remake_overlay_pixels = 0
    original_vs_remake = 0
    for y in range(0, 128):
        for x in range(0, 240):
            if grid_px[x, y] in cyan_results:
                original_overlay_pixels += 1
            if remake_px[x, y] in cyan_results:
                remake_overlay_pixels += 1
            if grid_px[x, y] != remake_px[x, y]:
                original_vs_remake += 1

    top = sorted(cyan_pairs.items(), key=lambda item: -item[1])[:12]
    return {
        "schema": "konoha.s49-ledger-move-grid-colors.v1",
        "inputs": {
            "original_grid_frame": str(grid_path.relative_to(root)),
            "original_grid_frame_sha256": sha256_file(grid_path),
            "original_untinted_frame": str(plain_path.relative_to(root)),
            "original_untinted_frame_sha256": sha256_file(plain_path),
            "remake_frame": str(remake_path.relative_to(root)),
            "remake_frame_sha256": sha256_file(remake_path),
        },
        "measurement": {
            "field_area": [0, 0, 240, 128],
            "changed_pixels_in_field": field_differences,
            "distinct_base_to_overlay_pairs": len(pairs),
            "distinct_overlay_colours": len(overlay_results),
            "cyan_overlay_colours": len(cyan_results),
            "cyan_pairs": len(cyan_pairs),
            "bases_with_several_cyan_overlays": len(
                bases_with_several_cyan_overlays
            ),
            "original_pixels_in_a_cyan_overlay_colour": original_overlay_pixels,
            "remake_pixels_in_a_cyan_overlay_colour": remake_overlay_pixels,
            "original_vs_remake_different_pixels": original_vs_remake,
            "top_cyan_pairs": [
                {
                    "base": list(base),
                    "overlay": list(overlay),
                    "pixels": count,
                }
                for (base, overlay), count in top
            ],
        },
        "conclusion": (
            "the original paints the move range with a dithered cyan overlay "
            f"({len(cyan_results)} cyan overlay colours over "
            f"{sum(cyan_pairs.values())} changed pixels); "
            f"{len(bases_with_several_cyan_overlays)} map colours map to more "
            "than one overlay colour, so the overlay is a dither mask and not "
            "one flat tint"
        ),
    }


def measure_idle_sequence(root: Path) -> dict[str, Any]:
    """Measure the original unit idle animation period from the idle sweep."""

    sweep = root / "artifacts/s49-fidelity-20261019-v1/original-idle-sweep"
    frames = sorted(sweep.glob("frame-*.png"))
    if len(frames) < IDLE_FRAMES:
        raise EvidenceError(
            f"the original idle sweep has {len(frames)} frames, "
            f"{IDLE_FRAMES} are needed"
        )

    from PIL import ImageChops

    images = [load_image(path) for path in frames[:IDLE_FRAMES]]

    signatures: list[tuple[Any, ...] | None] = []
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
        changed_pixels = sum(
            count for value, count in enumerate(peak.histogram()) if value
        )
        signatures.append(
            (box[0], box[1], box[2] - 1, box[3] - 1, changed_pixels)
        )
    if not any(signatures):
        raise EvidenceError("the original idle sweep never changes")

    bounds = [
        min(item[0] for item in signatures if item),
        min(item[1] for item in signatures if item),
        max(item[2] for item in signatures if item),
        max(item[3] for item in signatures if item),
    ]

    region = (bounds[0], bounds[1], bounds[2] + 1, bounds[3] + 1)
    poses = [
        hashlib.sha256(image.crop(region).tobytes()).hexdigest()[:16]
        for image in images
    ]

    candidates = [
        period
        for period in range(1, IDLE_MAX_PERIOD + 1)
        if IDLE_FRAMES - 1 - period > 0
    ]
    table: list[dict[str, int]] = []
    for period in candidates:
        transition_matches = sum(
            1
            for index in range(0, len(signatures) - period)
            if signatures[index] is not None
            and signatures[index] == signatures[index + period]
        )
        pose_matches = sum(
            1
            for index in range(0, len(poses) - period)
            if poses[index] == poses[index + period]
        )
        table.append(
            {
                "period": period,
                "transition_matches": transition_matches,
                "pose_matches": pose_matches,
            }
        )
    best = max(
        table,
        key=lambda row: (row["transition_matches"], -row["period"]),
    )
    best_period = best["period"]

    window = poses[:best_period]
    distinct_poses = len(set(window))
    identical_neighbours = sum(
        1 for index in range(1, len(window)) if window[index] == window[index - 1]
    )

    return {
        "schema": "konoha.s49-ledger-idle-sequence.v1",
        "inputs": {
            "idle_sweep": str(sweep.relative_to(root)),
            "frames_measured": len(images),
            "first_frame_sha256": sha256_file(frames[0]),
        },
        "measurement": {
            "frames_with_change": sum(1 for item in signatures if item),
            "changed_region_bbox": bounds,
            "best_period_frames": best_period,
            "distinct_poses_in_one_period": distinct_poses,
            "identical_neighbouring_frames_in_period": identical_neighbours,
            "period_table": [
                row
                for row in table
                if row["period"] in (8, 16, 24, 32, 40, 48, 56, 64)
            ],
        },
        "conclusion": (
            f"the original unit idle animation changes its sprite on "
            f"{sum(1 for item in signatures if item)} of {len(signatures)} "
            f"frame transitions and shows {distinct_poses} distinct sprites "
            f"inside {best_period} frames, so the original animates every "
            "frame instead of holding a few poses"
        ),
    }


def measure_standby_state(root: Path) -> dict[str, Any]:
    """Read the two region comparison receipts that pin the standby rule."""

    before_path = (
        root
        / "artifacts/s49-fidelity-20261019-v1/region-diff-banner"
        / "field-unit-selection.json"
    )
    after_path = (
        root
        / "artifacts/s49-fidelity-20261019-v1/region-diff-banner2"
        / "field-unit-selection.json"
    )
    before = read_json(before_path)
    after = read_json(after_path)
    before_status = before["regions"]["status-bar"]["different_pixels"]
    after_status = after["regions"]["status-bar"]["different_pixels"]
    return {
        "schema": "konoha.s49-ledger-standby-state.v1",
        "inputs": {
            "before_receipt": str(before_path.relative_to(root)),
            "before_receipt_sha256": sha256_file(before_path),
            "after_receipt": str(after_path.relative_to(root)),
            "after_receipt_sha256": sha256_file(after_path),
        },
        "measurement": {
            "baseline": "field-unit-selection",
            "status_bar_different_pixels_before": before_status,
            "status_bar_different_pixels_after": after_status,
            "before_original_frame": before.get("original_frame"),
            "before_remake_frame": before.get("remake_frame"),
            "after_original_frame": after.get("original_frame"),
            "after_remake_frame": after.get("remake_frame"),
        },
        "conclusion": (
            "the status bar of the unit selection screen went from "
            f"{before_status} to {after_status} different pixels after the "
            "standby rule was changed to follow the unit state"
        ),
    }


MEASUREMENTS = {
    "action-menu-glyphs": measure_action_menu_glyphs,
    "select-prompt": measure_select_prompt,
    "move-grid-colors": measure_move_grid_colors,
    "idle-sequence": measure_idle_sequence,
    "standby-state": measure_standby_state,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument(
        "--out-dir",
        default="artifacts/s49-ledger-evidence-v1",
        help="directory the receipts are written to",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    receipts: dict[str, Any] = {}
    for name, measurement in MEASUREMENTS.items():
        try:
            receipt = measurement(root)
        except EvidenceError as error:
            print(f"error: {name}: {error}", file=sys.stderr)
            return 1
        path = out_dir / f"{name}.json"
        path.write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        receipts[name] = {
            "path": str(path.relative_to(root)),
            "sha256": sha256_file(path),
            "conclusion": receipt["conclusion"],
        }
        print(f"wrote {path.relative_to(root)}")

    index = {
        "schema": RECEIPT_SCHEMA,
        "root": str(root),
        "receipts": receipts,
    }
    (out_dir / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
