#!/usr/bin/env python3
"""Compare scenario 49's opaque target-confirmation box."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


SCREEN_SIZE = (240, 160)
CONFIRMATION_BOX = (80, 24, 160, 88)


def _normalized_image(image: Image.Image) -> Image.Image:
    if image.size != SCREEN_SIZE:
        raise ValueError(
            f"expected confirmation image size {SCREEN_SIZE}, "
            f"got {image.size}"
        )
    return image.convert("RGB")


def compare_target_confirmation_images(
    original: Image.Image,
    current: Image.Image,
) -> dict[str, object]:
    original = _normalized_image(original)
    current = _normalized_image(current)
    x0, y0, x1, y1 = CONFIRMATION_BOX
    different_pixels = sum(
        original.getpixel((x, y)) != current.getpixel((x, y))
        for y in range(y0, y1)
        for x in range(x0, x1)
    )
    return {
        "screen_size": list(SCREEN_SIZE),
        "box": list(CONFIRMATION_BOX),
        "compared_pixels": (x1 - x0) * (y1 - y0),
        "different_pixels": different_pixels,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_comparison(
    original_path: Path,
    current_path: Path,
    output_path: Path,
) -> dict[str, object]:
    original_path = Path(original_path)
    current_path = Path(current_path)
    output_path = Path(output_path)
    with Image.open(original_path) as original:
        with Image.open(current_path) as current:
            result = compare_target_confirmation_images(
                original,
                current,
            )
    result["original"] = {
        "path": str(original_path),
        "sha256": _sha256(original_path),
    }
    result["current"] = {
        "path": str(current_path),
        "sha256": _sha256(current_path),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", required=True, type=Path)
    parser.add_argument("--current", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = write_comparison(
        args.original,
        args.current,
        args.output,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
