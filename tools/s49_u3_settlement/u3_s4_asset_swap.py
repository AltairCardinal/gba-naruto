#!/usr/bin/env python3
"""S4 — measure the settlement-screen art swap with the **correct** compositing.

Stream U3 (wave 10).  The repo already ships 1:1 ``scenario_41_result_*`` and
``scenario_41_level_up_1_*`` layers that the runtime never references, while
the runtime still draws the remake's own ``battle_ui_*`` panels.  S4 asks to
swap them over.

⚠️ **Two measurement facts this tool makes explicit**, because the number the
acceptance criterion compares against was produced with a different
compositing rule:

1. **The 1:1 layers are ``bpp_8`` regular BGs, where index 0 is the
   transparent colour.**  The correct composite is therefore
   *topmost non-transparent pixel wins* (what the GBA does), **not** the
   opaque paste wave 9's V4 tool uses.  With the correct rule the
   ``scenario_41_result_*`` stack is a **pixel-exact** copy of the original's
   own settlement screen (0 differing pixels).
2. **V4's counter samples every third pixel** (it builds an ``L``-mode image
   and then walks the bytes in steps of three), so its numbers are about a
   third of the true count.  This tool reports both, so the V4 number and the
   true number stay comparable.

The *runtime* only draws the **static BG layers**; the text and the numbers
are sprites on top of them, so every number here is a statement about the
**底板** (the base plate), exactly like the V4 number it replaces.

Usage::

    python tools/s49_u3_settlement/u3_s4_asset_swap.py \
        --truth build/s49-victory-capture/w4/settlement-truth
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

from PIL import Image, ImageChops

GRAPHICS = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics")

# (label, layers bottom-first, truth image, reference screen)
CASES = (
    ("结算屏",
     ("battle_ui_result_background.bmp", "battle_ui_result_panel.bmp"),
     "02-settlement-exp-power-turns.png",
     "ref-scenario-41-result"),
    ("结算屏 (S4 候选)",
     ("scenario_41_result_bottom.bmp", "scenario_41_result_middle.bmp",
      "scenario_41_result_top.bmp"),
     "02-settlement-exp-power-turns.png",
     "ref-scenario-41-result"),
    ("升级屏",
     ("battle_ui_level_up_panel.bmp",),
     "03-levelup-naruto.png",
     "ref-scenario-41-level-up-1"),
    ("升级屏 (S4 候选)",
     ("scenario_41_level_up_1_bottom.bmp",
      "scenario_41_level_up_1_middle.bmp",
      "scenario_41_level_up_1_top.bmp"),
     "03-levelup-naruto.png",
     "ref-scenario-41-level-up-1"),
)


def compose(layers, transparent_index=0, size=(240, 160)):
    """Composite the priority layers the way the GBA does.

    ``transparent_index`` is the palette index that is transparent; pass
    ``None`` for an opaque paste (what wave 9's V4 tool does).
    """
    width = height = 256
    canvas = [(0, 0, 0)] * (width * height)
    for name in layers:
        with Image.open(GRAPHICS / name) as image:
            paletted = image.convert("P")
            indices = list(paletted.getdata())
            pixels = list(paletted.convert("RGB").getdata())
        for position, index in enumerate(indices):
            if transparent_index is not None and index == transparent_index:
                continue
            canvas[position] = pixels[position]
    composed = Image.new("RGB", (width, height))
    composed.putdata(canvas)
    return composed.crop((0, 0, size[0], size[1]))


def compare(left, right):
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--truth", type=pathlib.Path, required=True)
    parser.add_argument("--reference-root", type=pathlib.Path, required=True,
                        help="the directory holding ref-scenario-41-*")
    parser.add_argument("--out", type=pathlib.Path, default=None)
    args = parser.parse_args(argv)

    rows = []
    for label, layers, truth_name, reference in CASES:
        truth_path = args.truth / truth_name
        reference_path = args.reference_root / reference / "screen.png"
        if not truth_path.is_file() or not reference_path.is_file():
            print(f"  {label}: truth or reference missing")
            continue
        with Image.open(truth_path) as image:
            truth = image.convert("RGB")
        with Image.open(reference_path) as image:
            reference_screen = image.convert("RGB")

        opaque = compose(layers, transparent_index=None)
        alpha = compose(layers, transparent_index=0)

        opaque_truth = compare(opaque, truth)
        alpha_truth = compare(alpha, truth)
        alpha_reference = compare(alpha, reference_screen)

        rows.append({
            "screen": label,
            "layers": list(layers),
            "layer_sha256": {name: sha256_file(GRAPHICS / name)
                             for name in layers},
            "truth": truth_name,
            "reference": reference,
            "opaque_paste": {
                "v4_metric": opaque_truth[0],
                "true_pixels": opaque_truth[1],
                "diff_bbox": list(opaque_truth[2]) if opaque_truth[2] else None,
            },
            "alpha_composite": {
                "v4_metric": alpha_truth[0],
                "true_pixels": alpha_truth[1],
                "diff_bbox": list(alpha_truth[2]) if alpha_truth[2] else None,
            },
            "alpha_vs_own_reference": {
                "v4_metric": alpha_reference[0],
                "true_pixels": alpha_reference[1],
                "diff_bbox": (list(alpha_reference[2])
                              if alpha_reference[2] else None),
            },
        })

        print(f"  {label}")
        print(f"    opaque paste  vs truth : v4={opaque_truth[0]:6d} "
              f"true={opaque_truth[1]:6d}")
        print(f"    alpha composite vs truth: v4={alpha_truth[0]:6d} "
              f"true={alpha_truth[1]:6d} bbox={alpha_truth[2]}")
        print(f"    alpha vs own reference : v4={alpha_reference[0]:6d} "
              f"true={alpha_reference[1]:6d} bbox={alpha_reference[2]}")

    document = {
        "schema": "konoha.s49-u3-s4-asset-swap.v1",
        "graphics": str(GRAPHICS),
        "truth_dir": str(args.truth),
        "metric_note": "v4_metric is bit-identical to wave 9's V4 tool, which "
                       "samples every third pixel; true_pixels counts every "
                       "pixel; alpha_composite treats palette index 0 as "
                       "transparent, which is what the GBA does for a bpp_8 "
                       "regular BG",
        "rows": rows,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(document, indent=1, ensure_ascii=False)
                            + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
