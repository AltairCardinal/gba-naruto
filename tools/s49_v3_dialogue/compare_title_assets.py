#!/usr/bin/env python3
"""Compare the staged 「開始」 title items with the ones in graphics/.

The staged items come from tools/s49_v3_dialogue/regenerate_title_assets.py,
which fixes the cell bounds of the cut; the shipped ones come from
tools/s49_opening_title/make_title_assets.py, which does not.  The report
says, for every item, how many pixels carry ink in either version.

Usage::

    python tools/s49_v3_dialogue/compare_title_assets.py \\
        --staged build/s49-v3/title-assets \\
        --graphics "D:\\Shell\\Github\\gba-naruto-butano\\butano-sequel\\graphics"
"""

from __future__ import annotations

import argparse
import json
import pathlib

from PIL import Image


def load_item(path: pathlib.Path) -> tuple[list[int], int, int, list]:
    image = Image.open(path).convert("P")
    indices = list(image.getdata())
    return indices, image.size[0], image.size[1], image.getpalette()[:64]


def ink_count(indices: list[int]) -> int:
    return sum(1 for index in indices if index != 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", required=True)
    parser.add_argument("--graphics", required=True)
    args = parser.parse_args(argv)

    staged_dir = pathlib.Path(args.staged)
    graphics_dir = pathlib.Path(args.graphics)
    manifest = json.loads(
        (staged_dir / "manifest.json").read_text(encoding="utf-8"))

    report = []
    for item in manifest["items"]:
        name = item["name"]
        staged = staged_dir / f"{name}.bmp"
        shipped = graphics_dir / f"{name}.bmp"
        row = {"name": name, "cell": item["cell"]}
        if not shipped.exists():
            row["shipped"] = "missing"
            row["staged_ink"] = item["ink"]
            report.append(row)
            continue
        staged_indices, staged_w, staged_h, _ = load_item(staged)
        shipped_indices, shipped_w, shipped_h, _ = load_item(shipped)
        row["staged_size"] = [staged_w, staged_h]
        row["shipped_size"] = [shipped_w, shipped_h]
        row["staged_ink"] = ink_count(staged_indices)
        row["shipped_ink"] = ink_count(shipped_indices)
        same_size = (staged_w, staged_h) == (shipped_w, shipped_h)
        row["same_size"] = same_size
        if same_size:
            differing = sum(
                1 for left, right in zip(staged_indices, shipped_indices)
                if left != right)
            row["differing_pixels"] = differing
        report.append(row)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    out = staged_dir / "compare-shipped.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
