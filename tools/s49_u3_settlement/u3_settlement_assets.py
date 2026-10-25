#!/usr/bin/env python3
"""Asset-level comparison of the settlement screens, with V4's exact metric.

Stream U3 (wave 10).  The acceptance criterion for S4 is "the asset-level
differing-pixel count drops", measured with wave 9's V4 tool
(``tools/s49_victory_capture/v4_settlement_assets.py``).

⚠️ **Two metric facts this tool makes explicit**, because the acceptance
number has to be comparable with the one already on record:

1. **V4's counter samples every third pixel.**  It builds ``merged`` in
   ``L`` mode (one byte per pixel) and then walks ``data`` in steps of three
   while OR-ing three bytes together, so it reports roughly **one third** of
   the truly differing pixels.  This tool reports **both**: ``v4_metric``
   (bit-identical to V4's number, so the recorded 12,798 / 7,681 / 8,483
   stay comparable) and ``true_pixels`` (every pixel counted).
2. **The layer stack is data, not code.**  V4's tool hard-codes the layer
   files the remake draws.  This tool takes the stack as an argument so the
   *current* stack and the *proposed* ``scenario_41_result_*`` stack can be
   compared with one command.

Usage::

    python tools/s49_u3_settlement/u3_settlement_assets.py \
        --truth build/s49-victory-capture/w4/settlement-truth
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

REMAKE_GRAPHICS = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics")

# The stack the remake draws today (V4's table).
CURRENT_STACKS = {
    "结算屏": (("battle_ui_result_background.bmp",
                "battle_ui_result_panel.bmp"),
               "02-settlement-exp-power-turns.png"),
    "升级屏": (("battle_ui_level_up_panel.bmp",),
               "03-levelup-naruto.png"),
    "训练页": (("battle_ui_training_panel.bmp",),
               "07-ninja-tool-list.png"),
}

# The 1:1 layers the repo already ships but the runtime never references.
CANDIDATE_STACKS = {
    "结算屏": (("scenario_41_result_bottom.bmp",
                "scenario_41_result_middle.bmp"),
               "02-settlement-exp-power-turns.png"),
    "升级屏": (("scenario_41_level_up_1_bottom.bmp",
                "scenario_41_level_up_1_middle.bmp",
                "scenario_41_level_up_1_top.bmp"),
               "03-levelup-naruto.png"),
    "训练页": (("battle_ui_training_panel.bmp",),
               "07-ninja-tool-list.png"),
}


def load_rgb(path: pathlib.Path):
    from PIL import Image

    with Image.open(path) as image:
        return image.convert("RGB")


def compose(layers: tuple[str, ...], size=(240, 160)):
    """Stack the palettized BG layers the way the scene stacks them.

    V4's ``compose`` pastes each layer opaquely, so the **last** layer wins
    over the whole area it covers.  This reproduces that exactly.
    """
    from PIL import Image

    canvas = Image.new("RGB", (256, 256), (0, 0, 0))
    for name in layers:
        with Image.open(REMAKE_GRAPHICS / name) as image:
            canvas.paste(image.convert("RGB"), (0, 0))
    return canvas.crop((0, 0, size[0], size[1]))


def compare(left, right):
    """Return (v4_metric, true_pixels, bbox).

    ``v4_metric`` is bit-identical to wave 9's V4 tool; ``true_pixels``
    counts every pixel.
    """
    from PIL import ImageChops

    difference = ImageChops.difference(left, right)
    bands = difference.split()
    merged = ImageChops.lighter(
        ImageChops.lighter(bands[0], bands[1]), bands[2])
    box = merged.getbbox()
    v4_metric = 0
    true_pixels = 0
    if box is not None:
        data = merged.crop(box).tobytes()
        # V4's exact walk: step by three, OR the three bytes together.
        for index in range(0, len(data) - 2, 3):
            if data[index] or data[index + 1] or data[index + 2]:
                v4_metric += 1
        # Every pixel: the merged image is in L mode, one byte per pixel.
        true_pixels = sum(1 for value in data if value)
    return v4_metric, true_pixels, box


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure(stacks: dict, truth_dir: pathlib.Path) -> list[dict]:
    rows = []
    for title, (layers, truth_name) in stacks.items():
        truth_path = truth_dir / truth_name
        if not truth_path.is_file():
            rows.append({"screen": title, "truth": truth_name,
                         "error": "the truth image is missing"})
            continue
        composed = compose(layers)
        truth = load_rgb(truth_path)
        v4_metric, true_pixels, box = compare(composed, truth)
        rows.append({
            "screen": title,
            "layers": list(layers),
            "layer_sha256": {name: sha256_file(REMAKE_GRAPHICS / name)
                             for name in layers},
            "truth": truth_name,
            "truth_sha256": sha256_file(truth_path),
            "composite_sha256": hashlib.sha256(
                composed.tobytes()).hexdigest(),
            "v4_metric": v4_metric,
            "true_pixels": true_pixels,
            "total_pixels": composed.size[0] * composed.size[1],
            "diff_bbox": list(box) if box else None,
            "caveat": "the static BG layers only; the runtime text and "
                      "numbers are sprites on top of them",
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--truth", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    args = parser.parse_args(argv)

    current = measure(CURRENT_STACKS, args.truth)
    candidate = measure(CANDIDATE_STACKS, args.truth)

    print("current stack (what the remake draws today):")
    for row in current:
        if "error" in row:
            print(f"  {row['screen']}: {row['error']}")
            continue
        print(f"  {row['screen']:<8} v4={row['v4_metric']:6d} "
              f"true={row['true_pixels']:6d}/{row['total_pixels']} "
              f"bbox={row['diff_bbox']}")
    print("candidate stack (the 1:1 scenario_41_result_* layers):")
    for row in candidate:
        if "error" in row:
            print(f"  {row['screen']}: {row['error']}")
            continue
        print(f"  {row['screen']:<8} v4={row['v4_metric']:6d} "
              f"true={row['true_pixels']:6d}/{row['total_pixels']} "
              f"bbox={row['diff_bbox']}")

    document = {
        "schema": "konoha.s49-u3-settlement-assets.v1",
        "graphics": str(REMAKE_GRAPHICS),
        "truth_dir": str(args.truth),
        "metric_note": "v4_metric is bit-identical to wave 9's V4 tool, which "
                       "samples every third pixel; true_pixels counts every "
                       "pixel",
        "current": current,
        "candidate": candidate,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(document, indent=1, ensure_ascii=False)
                            + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
