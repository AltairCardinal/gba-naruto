#!/usr/bin/env python3
"""Measure each candidate asset stack against **its own** original reference.

Stream U3 (wave 10).  S4 swaps the remake's settlement art for the 1:1
``scenario_41_*`` layers the repo already ships.  Those layers were
reconstructed from the **original's scenario 41** boundaries, so they must be
compared against the scenario-41 reference screens
(``build/s49-victory-capture/w4/ref-scenario-41-*/screen.png``) -- comparing
them with the S49 truth would mix two different battles.

This tool answers one yes/no question per candidate:

    *Is the candidate layer stack a 1:1 copy of the original's own screen?*

Usage::

    python tools/s49_u3_settlement/u3_candidate_fidelity.py
"""

from __future__ import annotations

import pathlib

from PIL import Image, ImageChops

GRAPHICS = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics")
W4 = pathlib.Path(r"D:\Github\gba-naruto\build\s49-victory-capture\w4")

CANDIDATES = (
    ("s41 result (bottom+middle)",
     ("scenario_41_result_bottom.bmp", "scenario_41_result_middle.bmp"),
     "ref-scenario-41-result"),
    ("s41 result (middle)",
     ("scenario_41_result_middle.bmp",),
     "ref-scenario-41-result"),
    ("s41 result (bottom)",
     ("scenario_41_result_bottom.bmp",),
     "ref-scenario-41-result"),
    ("s41 result (bottom+middle+top)",
     ("scenario_41_result_bottom.bmp", "scenario_41_result_middle.bmp",
      "scenario_41_result_top.bmp"),
     "ref-scenario-41-result"),
    ("s41 level_up_1 (bottom)",
     ("scenario_41_level_up_1_bottom.bmp",),
     "ref-scenario-41-level-up-1"),
    ("s41 level_up_1 (middle)",
     ("scenario_41_level_up_1_middle.bmp",),
     "ref-scenario-41-level-up-1"),
    ("s41 level_up_1 (top)",
     ("scenario_41_level_up_1_top.bmp",),
     "ref-scenario-41-level-up-1"),
    ("s41 level_up_1 (bottom+middle+top)",
     ("scenario_41_level_up_1_bottom.bmp", "scenario_41_level_up_1_middle.bmp",
      "scenario_41_level_up_1_top.bmp"),
     "ref-scenario-41-level-up-1"),
    ("remake result (bg+panel)",
     ("battle_ui_result_background.bmp", "battle_ui_result_panel.bmp"),
     "ref-scenario-41-result"),
    ("remake level_up (panel)",
     ("battle_ui_level_up_panel.bmp",),
     "ref-scenario-41-level-up-1"),
)


def compose(layers, size=(240, 160)):
    canvas = Image.new("RGB", (256, 256), (0, 0, 0))
    for name in layers:
        with Image.open(GRAPHICS / name) as image:
            canvas.paste(image.convert("RGB"), (0, 0))
    return canvas.crop((0, 0, size[0], size[1]))


def diff(left, right):
    difference = ImageChops.difference(left, right)
    bands = difference.split()
    merged = ImageChops.lighter(
        ImageChops.lighter(bands[0], bands[1]), bands[2])
    box = merged.getbbox()
    if box is None:
        return 0, None
    data = merged.crop(box).tobytes()
    v4_metric = 0
    for index in range(0, len(data) - 2, 3):
        if data[index] or data[index + 1] or data[index + 2]:
            v4_metric += 1
    true_pixels = sum(1 for value in data if value)
    return v4_metric, true_pixels, box


def main() -> int:
    for label, layers, reference in CANDIDATES:
        reference_path = W4 / reference / "screen.png"
        if not reference_path.is_file():
            print(f"{label}: reference {reference} missing")
            continue
        with Image.open(reference_path) as image:
            truth = image.convert("RGB")
        try:
            composed = compose(layers)
        except Exception as error:  # pragma: no cover - diagnostic path
            print(f"{label}: compose failed ({error})")
            continue
        v4_metric, true_pixels, box = diff(composed, truth)
        print(f"{label:34} v4={v4_metric:6d} true={true_pixels:6d} "
              f"bbox={box}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
