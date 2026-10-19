#!/usr/bin/env python3
"""Compare the static shell and action icons of scenario 49's action menu."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


SCREEN_SIZE = (240, 160)
ACTION_ICON_BOXES = (
    (80, 40, 96, 56),
    (96, 40, 112, 56),
    (80, 56, 96, 72),
    (96, 56, 112, 72),
    (80, 72, 96, 88),
    (96, 72, 112, 88),
    (80, 88, 96, 104),
    (96, 88, 112, 104),
)
ACTION_ICON_LABELS = (
    "row-1-category",
    "row-1-effect",
    "row-2-category",
    "row-2-effect",
    "row-3-category",
    "row-3-effect",
    "row-4-category",
    "row-4-effect",
)
ACTION_HOMOLOGOUS_REGION_LABELS = (
    "actor-name",
    "actor-stat-labels",
    "action-entries",
    "cost-label",
    "distance-label",
    "range-label",
    "success-label",
    "selected-action",
    "description",
    "start-hint",
    "attack-command",
    "back-hint",
    "return",
    "action-cursor",
)
ACTION_HOMOLOGOUS_REGION_BOXES = (
    (16, 8, 48, 24),
    (80, 8, 104, 24),
    (8, 40, 80, 104),
    (160, 8, 208, 24),
    (160, 40, 176, 56),
    (160, 56, 176, 72),
    (160, 88, 184, 104),
    (8, 120, 40, 136),
    (8, 136, 128, 152),
    (152, 120, 176, 136),
    (176, 120, 208, 136),
    (200, 136, 216, 152),
    (216, 136, 240, 152),
    (0, 40, 8, 56),
)
ACTION_STATE_VALUE_BOXES = {
    "actor-hp": (120, 8, 144, 16),
}


def action_shell_coordinates() -> frozenset[tuple[int, int]]:
    """Return pixels owned by the original static panel shell.

    The four content interiors are excluded because their text and values are
    state-dependent.  The selection arrow, right-aligned actor values and the
    bottom B-button control can overlap border tiles, so those areas are
    excluded as dynamic overlays too.
    """

    coordinates: set[tuple[int, int]] = set()
    for y in range(SCREEN_SIZE[1]):
        for x in range(SCREEN_SIZE[0]):
            in_actor = 8 <= x < 136 and 8 <= y < 24
            in_stats = 152 <= x < 232 and 8 <= y < 104
            in_actions = 8 <= x < 136 and 40 <= y < 104
            in_detail = 8 <= x < 232 and 120 <= y < 152
            under_selection_arrow = x < 8 and 40 <= y < 56
            under_actor_values = (
                136 <= x < 144 and 8 <= y < 24
            )
            under_back_control = (
                232 <= x < 240 and 136 <= y < 144
            )
            if not (
                in_actor
                or in_stats
                or in_actions
                or in_detail
                or under_selection_arrow
                or under_actor_values
                or under_back_control
            ):
                coordinates.add((x, y))
    return frozenset(coordinates)


def _normalized_image(image: Image.Image) -> Image.Image:
    if image.size != SCREEN_SIZE:
        raise ValueError(
            f"expected action-menu image size {SCREEN_SIZE}, got {image.size}"
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


def compare_action_menu_images(
    original: Image.Image,
    current: Image.Image,
) -> dict[str, object]:
    original = _normalized_image(original)
    current = _normalized_image(current)
    shell_coordinates = action_shell_coordinates()
    icons = []
    for label, box in zip(
        ACTION_ICON_LABELS,
        ACTION_ICON_BOXES,
        strict=True,
    ):
        x0, y0, x1, y1 = box
        coordinates = (
            (x, y)
            for y in range(y0, y1)
            for x in range(x0, x1)
        )
        icons.append(
            {
                "label": label,
                "box": list(box),
                "compared_pixels": (x1 - x0) * (y1 - y0),
                "different_pixels": _difference_count(
                    original,
                    current,
                    coordinates,
                ),
            }
        )
    homologous_regions = []
    for label, box in zip(
        ACTION_HOMOLOGOUS_REGION_LABELS,
        ACTION_HOMOLOGOUS_REGION_BOXES,
        strict=True,
    ):
        x0, y0, x1, y1 = box
        coordinates = (
            (x, y)
            for y in range(y0, y1)
            for x in range(x0, x1)
        )
        homologous_regions.append(
            {
                "label": label,
                "box": list(box),
                "compared_pixels": (x1 - x0) * (y1 - y0),
                "different_pixels": _difference_count(
                    original,
                    current,
                    coordinates,
                ),
            }
        )
    excluded_coordinates: set[tuple[int, int]] = set()
    for x0, y0, x1, y1 in ACTION_STATE_VALUE_BOXES.values():
        excluded_coordinates.update(
            (x, y)
            for y in range(y0, y1)
            for x in range(x0, x1)
        )
    normalized_coordinates = (
        (x, y)
        for y in range(SCREEN_SIZE[1])
        for x in range(SCREEN_SIZE[0])
        if (x, y) not in excluded_coordinates
    )
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
        "icons": icons,
        "homologous_regions": homologous_regions,
        "state_normalized_screen": {
            "excluded_regions": {
                label: list(box)
                for label, box in
                ACTION_STATE_VALUE_BOXES.items()
            },
            "compared_pixels": (
                SCREEN_SIZE[0] * SCREEN_SIZE[1]
                - len(excluded_coordinates)
            ),
            "different_pixels": _difference_count(
                original,
                current,
                normalized_coordinates,
            ),
        },
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
            result = compare_action_menu_images(
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
