#!/usr/bin/env python3
"""Classify the settlement chain's residual pixels for wave 18 / lane W4.

The lane has two full-screen residuals (post-battle dialogue and task menu).
A plain "how many pixels differ" number does not say *why* they differ, so this
tool classifies every differing pixel and can also answer the harder question:
"does the remake's own graphics folder contain the layers that would make the
original's screen exactly?"

Modes
-----
``--truth/--remake`` (default)
    Compare a truth screen with the remake's screen page by page and split the
    residual into

    * ``missing``  (缺画)  truth has content, the remake left the pixel empty
    * ``extra``    (多画)  the remake drew content where the original had none
    * ``content``  (颜色/结构差) both sides drew something, but not the same

    "Empty" is the colour the GBA clears to (black) by default; ``--empty``
    overrides it.

``--compose``
    Composite candidate layers taken from the remake's own ``graphics/``
    folder (in the given order, later layers win where they are not the
    transparent colour) and diff the result against a target PNG.  This is
    how one proves that the original's screen *is* reproducible from the
    assets the remake already ships, and therefore that a residual is a
    "not drawn yet" defect rather than a "missing asset" defect.

``--probe``
    Try every ordering / subset of a small layer list and report the best
    match, which turns "which layers does this screen need" into a search.

All output is deterministic JSON (plus an optional markdown table).
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import pathlib
import sys

from PIL import Image

WIDTH = 240
HEIGHT = 160
SCREEN_PIXELS = WIDTH * HEIGHT

# The whole chain, truth screen -> remake chain page.
# The truth frames come from build/s49-victory-capture/w4/settlement-truth
# (the original game); the remake pages come from a settlement chain capture.
CHAIN_PAIRS = [
    ("01-victory.png", "page-000-outcome.png", "outcome"),
    ("02-settlement-exp-power-turns.png", "page-001-result.png", "result"),
    ("03-levelup-naruto.png", "page-002-level_up.png", "level_up_1"),
    ("05-levelup-sasuke-jutsu-name.png", "page-003-level_up.png", "level_up_2"),
    ("04-levelup-konohamaru.png", "page-004-level_up.png", "level_up_3"),
    ("05-levelup-sasuke.png", "page-005-level_up.png", "level_up_4"),
    ("06-levelup-sakura.png", "page-006-level_up.png", "level_up_5"),
    ("07-ninja-tool-list.png", "page-007-level_up.png", "level_up_6"),
    ("08-postbattle-dialogue-1.png", "page-014-post_battle_dialogue.png",
     "post_battle_dialogue"),
    ("09-task-menu-map.png", "page-021-task_menu.png", "task_menu"),
]


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rgb(path: pathlib.Path) -> list[tuple[int, int, int]]:
    image = Image.open(path).convert("RGB")
    if image.size != (WIDTH, HEIGHT):
        raise SystemExit(f"{path} is {image.size}, expected {(WIDTH, HEIGHT)}")
    return list(image.get_flattened_data())


def row_bands(counts: list[int]) -> list[list[int]]:
    bands: list[list[int]] = []
    start = None
    for index, count in enumerate(counts):
        if count:
            if start is None:
                start = index
        elif start is not None:
            bands.append([start, index - 1])
            start = None
    if start is not None:
        bands.append([start, len(counts) - 1])
    return bands


def compare(truth: list, remake: list, empty: tuple[int, int, int]) -> dict:
    rows = [0] * HEIGHT
    columns = [0] * WIDTH
    diff = 0
    missing = 0
    extra = 0
    content = 0
    missing_rows = [0] * HEIGHT
    extra_rows = [0] * HEIGHT
    content_rows = [0] * HEIGHT
    for index, (a, b) in enumerate(zip(truth, remake)):
        if a == b:
            continue
        diff += 1
        row = index // WIDTH
        column = index % WIDTH
        rows[row] += 1
        columns[column] += 1
        if b == empty and a != empty:
            missing += 1
            missing_rows[row] += 1
        elif a == empty and b != empty:
            extra += 1
            extra_rows[row] += 1
        else:
            content += 1
            content_rows[row] += 1
    return {
        "diff_px": diff,
        "same_px": SCREEN_PIXELS - diff,
        "identical": diff == 0,
        "missing_px": missing,
        "extra_px": extra,
        "content_px": content,
        "diff_row_bands": row_bands(rows),
        "missing_row_bands": row_bands(missing_rows),
        "extra_row_bands": row_bands(extra_rows),
        "content_row_bands": row_bands(content_rows),
        "diff_columns": sum(1 for count in columns if count),
        "truth_colors": len(set(truth)),
        "remake_colors": len(set(remake)),
    }


def best_offset(truth: list, remake: list, span: int = 16) -> dict:
    """Find the (dx, dy) that makes the remake match the truth best."""
    truth_pixels = [truth[y * WIDTH + x] for y in range(HEIGHT)
                     for x in range(WIDTH)]
    best = None
    for dy in range(-span, span + 1):
        for dx in range(-span, span + 1):
            same = 0
            for y in range(HEIGHT):
                sy = y - dy
                if sy < 0 or sy >= HEIGHT:
                    continue
                row_base = y * WIDTH
                src_base = sy * WIDTH
                for x in range(WIDTH):
                    sx = x - dx
                    if sx < 0 or sx >= WIDTH:
                        continue
                    if truth_pixels[row_base + x] == remake[src_base + sx]:
                        same += 1
            if best is None or same > best["same_px"]:
                best = {"dx": dx, "dy": dy, "same_px": same}
    best["diff_px"] = SCREEN_PIXELS - best["same_px"]
    return best


def load_layer(path: pathlib.Path) -> list:
    """The visible window of a background layer: its top-left 240x160.

    The layers in ``graphics/`` are 256x256 tilemaps, so the visible screen
    is a **crop** of the top-left corner -- taking the first 38400 pixels of
    the raster instead would read the first 150 rows and shear the image.
    """
    image = Image.open(path).convert("RGB")
    if image.size[0] < WIDTH or image.size[1] < HEIGHT:
        raise SystemExit(f"{path} is too small ({image.size})")
    return list(image.crop((0, 0, WIDTH, HEIGHT)).get_flattened_data())


def compose(layers: list[list], transparent: tuple[int, int, int]) -> list:
    out = [(0, 0, 0)] * SCREEN_PIXELS
    for layer in layers:
        for index, pixel in enumerate(layer):
            if pixel != transparent:
                out[index] = pixel
    return out


def graphics_path(root: pathlib.Path, name: str) -> pathlib.Path:
    for suffix in (".bmp", ".png"):
        candidate = root / (name + suffix)
        if candidate.is_file():
            return candidate
    raise SystemExit(f"no layer named {name} under {root}")


def run_compare(args) -> int:
    truth_dir = pathlib.Path(args.truth)
    remake_dir = pathlib.Path(args.remake)
    empty = tuple(args.empty)
    rows = []
    for truth_name, remake_name, phase in CHAIN_PAIRS:
        truth_path = truth_dir / truth_name
        remake_path = remake_dir / remake_name
        if not truth_path.is_file():
            print(f"SKIP {truth_name}: missing")
            continue
        if not remake_path.is_file():
            print(f"SKIP {remake_name}: missing")
            continue
        row = compare(load_rgb(truth_path), load_rgb(remake_path), empty)
        row.update({
            "phase": phase,
            "truth": truth_name,
            "remake": remake_name,
            "truth_sha256": sha256_file(truth_path),
            "remake_sha256": sha256_file(remake_path),
        })
        if args.offset:
            row["best_offset"] = best_offset(load_rgb(truth_path),
                                              load_rgb(remake_path))
        rows.append(row)
        print(f"{phase:22s} {truth_name:34s} vs {remake_name:34s} "
              f"diff {row['diff_px']:6d}  missing {row['missing_px']:6d}  "
              f"extra {row['extra_px']:6d}  content {row['content_px']:6d}")

    document = {
        "schema": "konoha.s49-w4-settlement-classify.v1",
        "truth_dir": str(truth_dir),
        "remake_dir": str(remake_dir),
        "empty_color": list(empty),
        "screen_pixels": SCREEN_PIXELS,
        "pairs": rows,
        "total_diff_px": sum(row["diff_px"] for row in rows),
        "total_missing_px": sum(row["missing_px"] for row in rows),
        "total_extra_px": sum(row["extra_px"] for row in rows),
        "total_content_px": sum(row["content_px"] for row in rows),
    }
    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
        print("->", out)
    if args.markdown:
        lines = ["| phase | truth | remake | diff | missing | extra | content |",
                 "|---|---|---|---:|---:|---:|---:|"]
        for row in rows:
            lines.append(
                f"| {row['phase']} | `{row['truth']}` | `{row['remake']}` | "
                f"{row['diff_px']} | {row['missing_px']} | {row['extra_px']} | "
                f"{row['content_px']} |")
        pathlib.Path(args.markdown).write_text("\n".join(lines) + "\n",
                                                encoding="utf-8", newline="\n")
        print("->", args.markdown)
    return 0


def run_compose(args) -> int:
    root = pathlib.Path(args.graphics)
    target = load_rgb(pathlib.Path(args.target))
    transparent = tuple(args.transparent)
    layers = [(name, load_layer(graphics_path(root, name)))
              for name in args.layer]
    result = compose([pixels for _, pixels in layers], transparent)
    row = compare(target, result, transparent)
    row["layers"] = [name for name, _ in layers]
    row["target"] = str(args.target)
    print(f"compose {' + '.join(row['layers'])} vs {pathlib.Path(args.target).name}: "
          f"diff {row['diff_px']} px  missing {row['missing_px']}  "
          f"extra {row['extra_px']}  content {row['content_px']}")
    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(row, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
        print("->", out)
    return 0


def run_probe(args) -> int:
    """Search layer subsets / orderings for the best match to the target."""
    root = pathlib.Path(args.graphics)
    target = load_rgb(pathlib.Path(args.target))
    transparent = tuple(args.transparent)
    names = args.layer
    loaded = {name: load_layer(graphics_path(root, name)) for name in names}
    results = []
    for size in range(1, len(names) + 1):
        for subset in itertools.combinations(names, size):
            for order in itertools.permutations(subset):
                result = compose([loaded[name] for name in order], transparent)
                diff = sum(1 for a, b in zip(target, result) if a != b)
                results.append((diff, order))
    results.sort(key=lambda item: item[0])
    for diff, order in results[:12]:
        print(f"diff {diff:6d}  {' + '.join(order)}")
    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(
            [{"diff_px": diff, "layers": list(order)} for diff, order in results],
            ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        print("->", out)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--truth", default="")
    parser.add_argument("--remake", default="")
    parser.add_argument("--graphics", default="")
    parser.add_argument("--target", default="")
    parser.add_argument("--layer", action="append", default=[])
    parser.add_argument("--out", default="")
    parser.add_argument("--markdown", default="")
    parser.add_argument("--empty", type=int, nargs=3, default=[0, 0, 0],
                        help="the colour the remake leaves empty")
    parser.add_argument("--transparent", type=int, nargs=3, default=[255, 255, 255],
                        help="the colour a layer uses for 'nothing here'")
    parser.add_argument("--offset", action="store_true",
                        help="also search the best (dx, dy) alignment")
    parser.add_argument("--compose", action="store_true",
                        help="compose --layer and diff against --target")
    parser.add_argument("--probe", action="store_true",
                        help="search layer subsets/orderings against --target")
    args = parser.parse_args()

    if args.compose:
        if not args.target or not args.layer:
            parser.error("--compose needs --target and --layer")
        return run_compose(args)
    if args.probe:
        if not args.target or not args.layer:
            parser.error("--probe needs --target and --layer")
        return run_probe(args)
    if not args.truth or not args.remake:
        parser.error("--truth and --remake are required")
    return run_compare(args)


if __name__ == "__main__":
    raise SystemExit(main())
