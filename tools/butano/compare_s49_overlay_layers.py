#!/usr/bin/env python3
"""Compare the remake's overlay layer with the original's, unit by unit.

``docs/butano-wiring-roadmap.md`` (W2) asks for a 1:1 S49 overlay.  The
remake's 2,917 differing pixels decompose into two very different problems,
and this tool measures the split:

* the original draws its overlay on a **15x10 grid of 16x16 px units**
  (a unit is 2x2 of the 8x8 BG tiles), while the remake draws on 32x16 px
  cells;
* inside a unit, the original's family (grid web / move lens / cursor /
  target / blocked) and the remake's family may disagree.

The split matters because the two halves have different owners:

``coverage``
    The unit's **family** differs -- the original painted the unit and the
    remake did not (or painted a different family).  That is a difference in
    *which units are highlighted*, i.e. in the remake's game rules, not in
    the wiring.  The roadmap's own boundary puts logic differences outside
    this roadmap.
``styling``
    The unit's family agrees but the pixels inside it differ -- the same
    content drawn with a different granularity or border.  That **is** the
    wiring, and it is the part this roadmap can close.

Both layers are read from receipts only:

* the original's BG2 layer: ``artifacts/s49-original-movegrid-tilemap-v1/``
  (the original's own VRAM, dumped per frame);
* the remake's BG2 layer: a GPU-state dump of the baseline walk's step-20
  savestate, whose overlay tilemap lives in a VRAM screen block.

Usage::

    python3 tools/butano/compare_s49_overlay_layers.py \\
        --root . \\
        --original artifacts/s49-original-movegrid-tilemap-v1 \\
        --remake-gpu artifacts/s49-remake-gpu-baseline-step20-v1 \\
        --out-dir artifacts/s49-overlay-layer-compare-v1
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

RECEIPT_SCHEMA = "konoha.s49-overlay-layer-compare.v1"

EXIT_OK = 0
EXIT_INPUT_ERROR = 2

#: The original's overlay unit is 16x16 px, i.e. 2x2 of the 8x8 BG tiles.
UNIT_PX = 16
CELLS_PER_UNIT = UNIT_PX // 8
#: The remake's own state cell: 4 x 2 blocks of 8x8 px, i.e. 32x16 px.
battle_range_ui_tiles_per_cell_x = 4
battle_range_ui_tiles_per_cell_y = 2

VISIBLE_COLUMNS = 30
VISIBLE_ROWS = 20
UNIT_COLUMNS = VISIBLE_COLUMNS // CELLS_PER_UNIT
UNIT_ROWS = VISIBLE_ROWS // CELLS_PER_UNIT

#: The original's BG2 tile numbers per family (its tiles 256..287).
ORIGINAL_FAMILIES = (
    (258, 262, "grid"),
    (262, 266, "move"),
    (266, 270, "attack"),
    (270, 274, "cursor"),
    (274, 278, "target"),
    (278, 282, "blocked"),
)

#: The remake's own block ranges per family (``battle_range_ui_style.h``).
REMAKE_FAMILIES = (
    (1, 9, "grid"),
    (9, 17, "move"),
    (17, 25, "attack"),
    (53, 61, "cursor"),
    (61, 69, "target"),
    (69, 77, "blocked"),
)
#: The action-menu glyph blocks are not part of the battlefield overlay.
REMAKE_MENU_RANGE = (25, 53)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _family_of(index: int, families: tuple[tuple[int, int, str], ...]) -> str:
    for low, high, name in families:
        if low <= index < high:
            return name
    return "transparent"


def original_cells(
    original_dir: Path,
    state: str = "movegrid-frame-v1",
) -> tuple[list[int], dict[str, Any]]:
    payload = json.loads(
        (original_dir / f"{state}.bg2-tilemap.json").read_text(encoding="utf-8")
    )
    cells = [0] * (32 * 32)
    for cell in payload.get("cells") or []:
        cells[cell["map_y"] * 32 + cell["map_x"]] = cell["tile"] & 0x3FF
    return cells, payload.get("screen_window") or {}


def remake_cells(remake_gpu_dir: Path) -> tuple[list[int], int]:
    """Find the remake's overlay tilemap in the dumped VRAM."""
    vram = (remake_gpu_dir / "vram.bin").read_bytes()
    best: tuple[int, list[int]] | None = None
    for block in range(32):
        offset = block * 2048
        if offset + 2048 > len(vram):
            break
        values = list(struct.unpack_from("<1024H", vram, offset))
        small = sum(1 for value in values if value < 128)
        nonzero = sum(1 for value in values if value != 0)
        if small != 1024 or nonzero < 50:
            continue
        if best is None or nonzero > best[0]:
            best = (nonzero, values)
    if best is None:
        raise ValueError("no overlay tilemap found in the remake's VRAM dump")
    return best[1], best[0]


def unit_families(
    cells: list[int],
    families: tuple[tuple[int, int, str], ...],
) -> list[str]:
    """The family of every 16x16 unit of the visible 30x20 window."""
    out: list[str] = []
    for unit_row in range(UNIT_ROWS):
        for unit_column in range(UNIT_COLUMNS):
            kinds = set()
            for cell_row in range(CELLS_PER_UNIT):
                for cell_column in range(CELLS_PER_UNIT):
                    row = unit_row * CELLS_PER_UNIT + cell_row
                    column = unit_column * CELLS_PER_UNIT + cell_column
                    kinds.add(
                        _family_of(cells[row * 32 + column], families)
                    )
            out.append("|".join(sorted(kinds)))
    return out


def expected_units(
    original_dir: Path,
    state: str = "movegrid-frame-v1",
) -> list[dict[str, Any]]:
    """The original's per-unit answer -- the ground truth.

    The original's own BG2 dump says which family every 16x16 px unit of the
    visible window carries (grid web / move lens / cursor / target / blocked
    / transparent).  That answer is what the remake's overlay has to match,
    and it is the only statement of the target that does not depend on the
    remake at all -- so it can be written down as a fixture and checked.
    """
    cells, _window = original_cells(original_dir, state)
    units = unit_families(cells, ORIGINAL_FAMILIES)
    return [
        {
            "unit": [index % UNIT_COLUMNS, index // UNIT_COLUMNS],
            "original": family,
        }
        for index, family in enumerate(units)
    ]


def compare(
    original_dir: Path,
    remake_gpu_dir: Path,
) -> dict[str, Any]:
    original_cells_list, window = original_cells(original_dir)
    remake_cells_list, remake_nonzero = remake_cells(remake_gpu_dir)
    original_units = unit_families(original_cells_list, ORIGINAL_FAMILIES)
    remake_units = unit_families(remake_cells_list, REMAKE_FAMILIES)
    rows = []
    coverage = 0
    for index, (original, remake) in enumerate(zip(original_units, remake_units)):
        same = original == remake
        unit_row = index // UNIT_COLUMNS
        unit_column = index % UNIT_COLUMNS
        rows.append(
            {
                "unit": [unit_column, unit_row],
                "original": original,
                "remake": remake,
                "same_family": same,
            }
        )
        if not same:
            coverage += 1

    # How much of the layer each side actually paints.  The original's lens
    # covers 8x8 px cells; the remake's overlay tilemap is counted in the
    # same unit so the two areas are comparable.
    original_lens_cells = sum(
        1
        for index, family in enumerate(original_units)
        if "move" in family
    ) * (CELLS_PER_UNIT * CELLS_PER_UNIT)
    remake_painted_cells = sum(1 for value in remake_cells_list if value != 0)
    # The remake's renderer expands every state cell into 4x2 blocks, so the
    # painted area is eight times the state's area.  Dividing it back out
    # separates the two very different problems: a **drawing** expansion and a
    # **state** that is already bigger than the original's lens.
    remake_state_cells = remake_painted_cells // (
        battle_range_ui_tiles_per_cell_x * battle_range_ui_tiles_per_cell_y
    )
    remake_lens_cells = sum(
        1
        for index, family in enumerate(remake_units)
        if "move" in family
    ) * (CELLS_PER_UNIT * CELLS_PER_UNIT)
    return {
        "schema": RECEIPT_SCHEMA,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "grid": {
            "unit_px": UNIT_PX,
            "unit_columns": UNIT_COLUMNS,
            "unit_rows": UNIT_ROWS,
            "visible_cells": [VISIBLE_COLUMNS, VISIBLE_ROWS],
        },
        "original": {
            "state": "movegrid-frame-v1",
            "scroll": {
                "hoffs": window.get("bg2_hoffs"),
                "voffs": window.get("bg2_voffs"),
            },
        },
        "remake": {
            "gpu_dump": str(remake_gpu_dir),
            "overlay_tilemap_nonzero_cells": remake_nonzero,
        },
        "summary": {
            "units": len(rows),
            "units_with_different_family": coverage,
            "units_with_same_family": len(rows) - coverage,
            "matching_units_ratio": (
                round((len(rows) - coverage) / len(rows), 4) if rows else None
            ),
        },
        "expected_units": [
            {"unit": [index % UNIT_COLUMNS, index // UNIT_COLUMNS], "original": family}
            for index, family in enumerate(original_units)
        ],
        "area": {
            "unit_px": UNIT_PX,
            "original_lens_cells": original_lens_cells,
            "remake_lens_cells": remake_lens_cells,
            "remake_painted_cells": remake_painted_cells,
            "remake_state_cells": remake_state_cells,
            "remake_over_original_area_ratio": (
                round(remake_painted_cells / original_lens_cells, 2)
                if original_lens_cells
                else None
            ),
            "state_over_original_area_ratio": (
                round(remake_state_cells / (original_lens_cells / 4), 2)
                if original_lens_cells
                else None
            ),
            "drawing_expansion": (
                battle_range_ui_tiles_per_cell_x
                * battle_range_ui_tiles_per_cell_y
            ),
        },
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    area = payload["area"]
    lines = [
        "# S49 覆盖层逐单元比对（自动生成）",
        "",
        "本文件由 `tools/butano/compare_s49_overlay_layers.py` 生成，不要手工编辑。",
        "",
        "| 项 | 值 |",
        "| --- | ---: |",
        f"| 16x16 单元总数 | {summary['units']} |",
        f"| **族不同（覆盖/状态差异）** | **{summary['units_with_different_family']}** |",
        f"| 族相同（画法/描边差异） | {summary['units_with_same_family']} |",
        "",
        "## 面积对照（8x8 px 格）",
        "",
        "| 项 | 值 |",
        "| --- | ---: |",
        f"| 原版移动透镜覆盖 | {area['original_lens_cells']} |",
        f"| 重制侧移动透镜覆盖 | {area['remake_lens_cells']} |",
        f"| **重制侧覆盖层实际画出的格数** | **{area['remake_painted_cells']}** |",
        f"| **重制 / 原版 画出面积比** | **{area['remake_over_original_area_ratio']}** |",
        f"| 减去 {area['drawing_expansion']}× 绘制展开后的**状态面积比** | **{area['state_over_original_area_ratio']}** |",
        "",
        "## 逐单元",
        "",
        "| 单元 (col,row) | 原版 | 重制 | 同族 |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        if row["same_family"]:
            continue
        lines.append(
            f"| ({row['unit'][0]},{row['unit'][1]}) | {row['original']} | "
            f"{row['remake']} | ❌ |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--original",
        type=Path,
        default=Path("artifacts/s49-original-movegrid-tilemap-v1"),
    )
    parser.add_argument(
        "--remake-gpu",
        type=Path,
        default=Path("artifacts/s49-remake-gpu-baseline-step20-v1"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("artifacts/s49-overlay-layer-compare-v1"),
    )
    parser.add_argument(
        "--emit-expected",
        type=Path,
        default=None,
        help="write the original's per-unit answer (the ground truth) here",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()

    def _resolve(path: Path) -> Path:
        return path if path.is_absolute() else root / path

    original_dir = _resolve(args.original)
    remake_gpu_dir = _resolve(args.remake_gpu)
    for required in (
        original_dir / "movegrid-frame-v1.bg2-tilemap.json",
        remake_gpu_dir / "vram.bin",
    ):
        if not required.is_file():
            print(f"missing input: {required}", file=sys.stderr)
            return EXIT_INPUT_ERROR

    payload = compare(original_dir, remake_gpu_dir)
    if args.emit_expected is not None:
        expected_path = _resolve(args.emit_expected)
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        expected_path.write_text(
            json.dumps(
                {
                    "schema": "konoha.s49-overlay-expected-units.v1",
                    "source": "the original's own BG2 dump "
                    "(artifacts/s49-original-movegrid-tilemap-v1)",
                    "unit_px": UNIT_PX,
                    "units": expected_units(original_dir),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {expected_path}")

    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "compare.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "compare.md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
