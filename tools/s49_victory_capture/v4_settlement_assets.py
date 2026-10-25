#!/usr/bin/env python3
"""Asset-level comparison of the remake's settlement screens against the
original's settlement truth.

Stream V4 (wave 9).  The runtime screens of the remake's settlement chain
could not be recorded on the ROM in this wave (the battle cannot be won --
see ``notes/s49-fidelity/V4-settlement-compare.md`` §4), so the comparison
falls back to the **static layers** the product code actually puts on the
screen:

* ``battle_ui_result_background`` (priority 2) + ``battle_ui_result_panel``
  (priority 1, in front) at scroll (0, 0)  => the settlement screen,
* ``battle_ui_level_up_panel``                     => the level-up screen,
* ``battle_ui_training_panel``                     => the training screen.

⚠️ **Caveat (must not be glossed over)**: the runtime draws the text and the
numbers as **sprites** on top of these layers (``battle_result_sprite_font``
/ ``battle_result_compact_sprite_font``), so this measurement compares the
**background structure only** -- it is the same caveat the B stream recorded
for the scenario-41 comparison (``notes/s49-fidelity/B-victory-settlement.md``
§5.2).

Usage::

    python tools/s49_victory_capture/v4_settlement_assets.py \
        --truth build/s49-victory-capture/w4/settlement-truth \
        --out build/s49-victory-capture/v4/settlement-assets.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

REMAKE_GRAPHICS = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics")

# layer stack (bottom first) -> the original truth image it should match
LAYERS = (
    ("结算屏", ("battle_ui_result_background.bmp",
                "battle_ui_result_panel.bmp"),
     "02-settlement-exp-power-turns.png"),
    ("升级屏", ("battle_ui_level_up_panel.bmp",),
     "03-levelup-naruto.png"),
    ("训练页", ("battle_ui_training_panel.bmp",),
     "07-ninja-tool-list.png"),
)


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rgb(path: pathlib.Path):
    from PIL import Image
    with Image.open(path) as image:
        return image.convert("RGB")


def compose(layers, size=(240, 160)):
    """Stack the palettized BG layers the way the scene stacks them."""
    from PIL import Image
    canvas = Image.new("RGB", (256, 256), (0, 0, 0))
    for name in layers:
        path = REMAKE_GRAPHICS / name
        if not path.is_file():
            raise SystemExit(f"ERR missing layer: {path}")
        with Image.open(path) as image:
            layer = image.convert("RGB")
            canvas.paste(layer, (0, 0))
    return canvas.crop((0, 0, size[0], size[1]))


def compare(left, right):
    from PIL import ImageChops
    difference = ImageChops.difference(left, right)
    bands = difference.split()
    merged = ImageChops.lighter(
        ImageChops.lighter(bands[0], bands[1]), bands[2])
    box = merged.getbbox()
    count = 0
    if box is not None:
        data = merged.crop(box).tobytes()
        count = sum(1 for index in range(0, len(data), 3)
                    if data[index] or data[index + 1] or data[index + 2])
    return count, box


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--truth", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    args = parser.parse_args(argv)

    rows = []
    for title, layers, truth_name in LAYERS:
        truth_path = args.truth / truth_name
        if not truth_path.is_file():
            rows.append({"screen": title, "truth": truth_name,
                         "error": "the truth image is missing"})
            continue
        composed = compose(layers)
        truth = load_rgb(truth_path)
        count, box = compare(composed, truth)
        rows.append({
            "screen": title,
            "layers": list(layers),
            "layer_sha256": {name: sha256_file(REMAKE_GRAPHICS / name)
                             for name in layers},
            "truth": truth_name,
            "truth_sha256": sha256_file(truth_path),
            "composite_sha256": hashlib.sha256(
                composed.tobytes()).hexdigest(),
            "differing_pixels": count,
            "total_pixels": composed.size[0] * composed.size[1],
            "diff_bbox": list(box) if box else None,
            "caveat": "the static BG layers only; the runtime text and "
                      "numbers are sprites on top of them",
        })

    document = {
        "schema": "konoha.s49-settlement-assets.v1",
        "graphics": str(REMAKE_GRAPHICS),
        "truth_dir": str(args.truth),
        "rows": rows,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(document, indent=1, ensure_ascii=False)
                            + "\n", encoding="utf-8", newline="\n")

    for row in rows:
        if "error" in row:
            print(f"{row['screen']}: {row['error']}")
            continue
        print(f"{row['screen']:<8} vs {row['truth']:<38} "
              f"diff={row['differing_pixels']:6d}/{row['total_pixels']} "
              f"bbox={row['diff_bbox']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
