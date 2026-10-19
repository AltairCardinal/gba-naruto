#!/usr/bin/env python3
"""Compare scenario 49's post-move command menu with the original frame."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


SCREEN_SIZE = (240, 160)
COMMAND_PANEL_BOX = (8, 40, 56, 88)
COMMAND_ARROW_BOX = (8, 48, 16, 64)
COMMAND_LABEL_BOXES = (
    (16, 48, 48, 64),
    (16, 64, 48, 80),
)
COMMAND_LABELS = (
    "ability-and-tool",
    "end-action",
)


def _box_coordinates(box: tuple[int, int, int, int]):
    x0, y0, x1, y1 = box
    return (
        (x, y)
        for y in range(y0, y1)
        for x in range(x0, x1)
    )


def command_shell_coordinates() -> frozenset[tuple[int, int]]:
    """Return the static panel pixels outside dynamic labels and arrow."""

    excluded = set(_box_coordinates(COMMAND_ARROW_BOX))
    for box in COMMAND_LABEL_BOXES:
        excluded.update(_box_coordinates(box))
    return frozenset(
        coordinate
        for coordinate in _box_coordinates(COMMAND_PANEL_BOX)
        if coordinate not in excluded
    )


def _normalized_image(image: Image.Image) -> Image.Image:
    if image.size != SCREEN_SIZE:
        raise ValueError(
            f"expected command-menu image size {SCREEN_SIZE}, got {image.size}"
        )
    return image.convert("RGB")


def _difference_count(
    original: Image.Image,
    current: Image.Image,
    coordinates,
) -> int:
    return sum(
        original.getpixel(coordinate)
        != current.getpixel(coordinate)
        for coordinate in coordinates
    )


def _box_comparison(
    original: Image.Image,
    current: Image.Image,
    box: tuple[int, int, int, int],
) -> dict[str, object]:
    x0, y0, x1, y1 = box
    return {
        "box": list(box),
        "compared_pixels": (x1 - x0) * (y1 - y0),
        "different_pixels": _difference_count(
            original,
            current,
            _box_coordinates(box),
        ),
    }


def compare_command_menu_images(
    original: Image.Image,
    current: Image.Image,
) -> dict[str, object]:
    original = _normalized_image(original)
    current = _normalized_image(current)
    shell_coordinates = command_shell_coordinates()
    labels = []
    for label, box in zip(
        COMMAND_LABELS,
        COMMAND_LABEL_BOXES,
        strict=True,
    ):
        comparison = _box_comparison(original, current, box)
        comparison["label"] = label
        labels.append(comparison)
    return {
        "screen_size": list(SCREEN_SIZE),
        "shell": {
            "compared_pixels": len(shell_coordinates),
            "different_pixels": _difference_count(
                original,
                current,
                shell_coordinates,
            ),
        },
        "labels": labels,
        "selection_arrow": _box_comparison(
            original,
            current,
            COMMAND_ARROW_BOX,
        ),
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
            result = compare_command_menu_images(original, current)
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
