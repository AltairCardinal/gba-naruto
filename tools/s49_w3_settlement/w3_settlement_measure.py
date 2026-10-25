#!/usr/bin/env python3
"""Measure the settlement screen's plate the way the runtime draws it.

Stream W3 (wave 11).  The settlement screen's plate is the original's own
settlement screen, cleaned of the capture's dynamic content (the scenario 41
numbers and character sprite) so that the remake can draw its own numbers and
its own sprites on top of it.

Two things are measured:

* the **capture** (the three ``scenario_41_result_*`` layers), which is the
  asset wave 10 measured; it still carries scenario 41's own numbers and
  character sprite, so it is not a reusable plate;
* the **runtime's plate** (``battle_ui_result_plate``), which is the capture
  with that dynamic content erased.

Both are composited the way the GBA does it: palette index 0 is transparent
and the topmost non-transparent pixel wins.  Two counters are reported: the
wave-9 tool's counter (which samples every third pixel) and the true pixel
count.

Usage::

    python tools/s49_w3_settlement/w3_settlement_measure.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

from PIL import Image, ImageChops

GRAPHICS = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics")
TRUTH = pathlib.Path(
    r"D:\Github\gba-naruto\build\s49-victory-capture\w4\settlement-truth"
    r"\02-settlement-exp-power-turns.png")

CAPTURE_LAYERS = (
    "scenario_41_result_bottom.bmp",
    "scenario_41_result_middle.bmp",
    "scenario_41_result_top.bmp",
)
RUNTIME_PLATE = "battle_ui_result_plate.bmp"


def compose(layers: tuple[str, ...], size=(240, 160)) -> Image.Image:
    width = height = 256
    canvas = [(0, 0, 0)] * (width * height)
    for name in layers:
        with Image.open(GRAPHICS / name) as image:
            paletted = image.convert("P")
            indices = list(paletted.getdata())
            pixels = list(paletted.convert("RGB").getdata())
        for position, index in enumerate(indices):
            if index == 0:
                continue
            canvas[position] = pixels[position]
    composed = Image.new("RGB", (width, height))
    composed.putdata(canvas)
    return composed.crop((0, 0, size[0], size[1]))


def compare(left: Image.Image, right: Image.Image):
    difference = ImageChops.difference(left, right)
    bands = difference.split()
    merged = ImageChops.lighter(
        ImageChops.lighter(bands[0], bands[1]), bands[2])
    box = merged.getbbox()
    if box is None:
        return 0, 0, None
    data = merged.crop(box).tobytes()
    v4_metric = 0
    for index in range(0, len(data) - 2, 3):
        if data[index] or data[index + 1] or data[index + 2]:
            v4_metric += 1
    true_pixels = sum(1 for value in data if value)
    return v4_metric, true_pixels, box


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    args = parser.parse_args()

    with Image.open(TRUTH) as image:
        truth = image.convert("RGB")

    rows = []
    for label, layers in (
        ("结算屏 (场景 41 抓取层, 含其自带数字与头像)",
         CAPTURE_LAYERS),
        ("结算屏 (运行时底板 battle_ui_result_plate)",
         (RUNTIME_PLATE,)),
    ):
        composed = compose(layers)
        metrics = compare(composed, truth)
        rows.append({
            "screen": label,
            "layers": list(layers),
            "layer_sha256": {
                name: sha256_file(GRAPHICS / name) for name in layers
            },
            "v4_metric": metrics[0],
            "true_pixels": metrics[1],
            "diff_bbox": list(metrics[2]) if metrics[2] else None,
        })
        print(f"  {label}")
        print(f"    v4={metrics[0]:6d} true={metrics[1]:6d} "
              f"bbox={metrics[2]}")

    document = {
        "schema": "konoha.s49-w3-settlement-measure.v1",
        "truth": str(TRUTH),
        "compositing": "alpha: palette index 0 is transparent, the topmost "
                       "non-transparent pixel wins (what the GBA does)",
        "metric_note": "v4_metric samples every third pixel like wave 9's "
                       "tool; true_pixels counts every pixel",
        "threshold_v4_metric": 2000,
        "rows": rows,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(document, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
