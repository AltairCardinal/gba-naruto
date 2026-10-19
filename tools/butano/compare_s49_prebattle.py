#!/usr/bin/env python3
"""Compare scenario 49's root task menu and start confirmation screens."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops


SCREEN_SIZE = (240, 160)


def _normalized_image(image: Image.Image) -> Image.Image:
    if image.size != SCREEN_SIZE:
        raise ValueError(
            f"expected prebattle image size {SCREEN_SIZE}, got {image.size}"
        )
    return image.convert("RGB")


def compare_full_screen_images(
    original: Image.Image,
    current: Image.Image,
) -> dict[str, object]:
    original = _normalized_image(original)
    current = _normalized_image(current)
    different_pixels = sum(
        original_pixel != current_pixel
        for original_pixel, current_pixel in zip(
            original.get_flattened_data(),
            current.get_flattened_data(),
            strict=True,
        )
    )
    difference_bbox = ImageChops.difference(
        original,
        current,
    ).getbbox()
    total_pixels = SCREEN_SIZE[0] * SCREEN_SIZE[1]
    return {
        "equal_pixels": total_pixels - different_pixels,
        "total_pixels": total_pixels,
        "different_pixels": different_pixels,
        "difference_bbox": (
            list(difference_bbox)
            if difference_bbox is not None
            else None
        ),
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compare_pair(
    original_path: Path,
    current_path: Path,
) -> dict[str, object]:
    with Image.open(original_path) as original:
        with Image.open(current_path) as current:
            result = compare_full_screen_images(original, current)
    result.update(
        {
            "original": str(original_path),
            "current": str(current_path),
            "original_sha256": _sha256(original_path),
            "current_sha256": _sha256(current_path),
        }
    )
    return result


def write_prebattle_comparison(
    *,
    original_root: Path,
    current_root: Path,
    original_confirmation: Path,
    current_confirmation: Path,
    output_path: Path,
) -> dict[str, object]:
    result = {
        "root": _compare_pair(
            Path(original_root),
            Path(current_root),
        ),
        "confirmation": _compare_pair(
            Path(original_confirmation),
            Path(current_confirmation),
        ),
    }
    output_path = Path(output_path)
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-root", required=True, type=Path)
    parser.add_argument("--current-root", required=True, type=Path)
    parser.add_argument(
        "--original-confirmation",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--current-confirmation",
        required=True,
        type=Path,
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = write_prebattle_comparison(
        original_root=args.original_root,
        current_root=args.current_root,
        original_confirmation=args.original_confirmation,
        current_confirmation=args.current_confirmation,
        output_path=args.output,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
