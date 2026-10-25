#!/usr/bin/env python3
"""Run Butano's OWN 4bpp quantiser on a regular-BG BMP and prove it lossless.

Butano's `bpp_4_auto` sidecar mode calls `BMP.quantize()` from
`third_party/butano/butano/tools/bmp.py`.  That quantiser is **per tile**
(8x8), not global:

* it collects the distinct non-zero palette indices of every 8x8 tile,
* it raises ``There's a tile with more than 15 colors`` if a tile exceeds 15,
* it then assigns tiles to 16-colour palettes (first-fit + a merge pass),
* and it rewrites the BMP with the reduced palette.

So the conversion is **lossless** exactly when no tile exceeds 15 colours, and
the resulting palette count (in groups of 16) is the number of BG palette
slots the asset needs.

This tool drives that exact function (no re-implementation), then verifies the
result pixel-by-pixel against the source.

Usage:
    python probe_butano_bpp4_auto.py --bmp <file.bmp> [--out-dir <dir>]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

BUTANO_TOOLS = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\third_party\butano\butano\tools"
)


def load_bmp_module():
    if str(BUTANO_TOOLS) not in sys.path:
        sys.path.insert(0, str(BUTANO_TOOLS))
    import bmp  # noqa: E402  (Butano's own module)

    return bmp


def compare_images(a_path: pathlib.Path, b_path: pathlib.Path) -> dict[str, object]:
    from PIL import Image

    a = Image.open(a_path).convert("RGB")
    b = Image.open(b_path).convert("RGB")
    if a.size != b.size:
        return {"identical": False, "reason": f"size {a.size} != {b.size}"}
    pa = list(a.getdata())
    pb = list(b.getdata())
    changed = sum(1 for x, y in zip(pa, pb) if x != y)
    return {
        "identical": changed == 0,
        "pixels_total": len(pa),
        "pixels_changed": changed,
        "pixels_changed_pct": round(100.0 * changed / len(pa), 6),
    }


def run(bmp_path: pathlib.Path, out_dir: pathlib.Path) -> dict[str, object]:
    bmp_mod = load_bmp_module()
    out_dir.mkdir(parents=True, exist_ok=True)
    quantized = out_dir / (bmp_path.stem + ".bn_quantized.bmp")

    source = bmp_mod.BMP(str(bmp_path))
    entry: dict[str, object] = {
        "source": str(bmp_path),
        "source_colors_count": source.colors_count,
        "quantized_output": str(quantized),
    }

    try:
        colors_count = source.quantize(str(quantized))
    except Exception as error:  # noqa: BLE001
        entry["quantize_error"] = f"{type(error).__name__}: {error}"
        entry["lossless"] = False
        entry["palette_slots"] = None
        return entry

    entry["quantize_colors_count"] = colors_count
    entry["palette_slots"] = colors_count // 16
    entry["compare"] = compare_images(bmp_path, quantized)
    entry["lossless"] = bool(entry["compare"]["identical"])
    from PIL import Image

    entry["quantized_palette_entries"] = len(
        Image.open(quantized).getpalette() or []
    ) // 3
    return entry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bmp", nargs="+", required=True)
    parser.add_argument("--out-dir", default=r"D:\Github\gba-naruto\build\w22-d6\bpp4-auto")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out_dir)
    result = {}
    for raw in args.bmp:
        path = pathlib.Path(raw)
        result[path.name] = run(path, out_dir)

    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
