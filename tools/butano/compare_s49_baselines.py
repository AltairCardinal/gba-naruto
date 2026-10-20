#!/usr/bin/env python3
"""Measure every S49 acceptance baseline in one run, with the pairing as data.

The S49 comparison has six baselines, and each of them was measured by hand
in an earlier round: the three dialogues, the round banner, the command menu
twice, and the action menu.  Measuring them by hand is how the pairing
drifted: when the remake's flow gained a screen, the step numbers moved and
the old receipts silently compared the wrong frames.

This tool therefore takes the pairing as a declared input -- one line per
baseline, naming the original step and the remake step -- and writes one
receipt per baseline plus a summary.  It never searches for a better
alignment, so a receipt can only ever mean "these two frames, compared
exactly".  The pairs file is copied next to the receipts so a claim can be
re-run from the artefacts alone.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.butano.compare_s49_regions import (  # noqa: E402
    RegionComparisonError,
    compare_regions,
)

STEP_PATTERN = re.compile(r"^step-(\d+)-(.+)\.png$")
DEFAULT_REGIONS = ROOT / "tools/butano/s49_regions.json"

SUMMARY_SCHEMA = "konoha.s49-baseline-summary.v1"


class BaselineError(RuntimeError):
    """The baselines could not be measured as declared."""


def step_file(walk: Path, step: int) -> Path:
    matches = sorted(walk.glob(f"step-{step:02d}-*.png"))
    if not matches:
        raise BaselineError(f"{walk} has no step {step}")
    if len(matches) > 1:
        raise BaselineError(f"{walk} has several step {step} frames: {matches}")
    return matches[0]


def load_regions(path: Path) -> dict[str, tuple[int, int, int, int]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    regions = payload.get("regions", payload)
    return {
        name: tuple(box) for name, box in regions.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--remake", type=Path, required=True)
    parser.add_argument(
        "--pairs",
        type=Path,
        required=True,
        help='JSON with a "pairs" list of {name, original_step, remake_step}',
    )
    parser.add_argument("--regions", type=Path, default=DEFAULT_REGIONS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    original = args.original.resolve()
    remake = args.remake.resolve()
    if not original.is_dir() or not remake.is_dir():
        print("error: both walks must be directories", file=sys.stderr)
        return 1
    pairs_payload = json.loads(args.pairs.read_text(encoding="utf-8"))
    pairs = pairs_payload.get("pairs", [])
    if not pairs:
        print("error: the pairs file declares no baseline", file=sys.stderr)
        return 1
    regions = load_regions(args.regions)

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "pairs.json").write_text(
        json.dumps(pairs_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    summary: list[dict[str, object]] = []
    for pair in pairs:
        name = pair["name"]
        original_frame = step_file(original, int(pair["original_step"]))
        remake_frame = step_file(remake, int(pair["remake_step"]))
        with Image.open(original_frame) as left, Image.open(remake_frame) as right:
            report = compare_regions(left, right, regions)
        receipt = {
            "schema": "konoha.s49-region-comparison.v1",
            "comparison": "declared-pair-no-alignment-search-no-mask",
            "baseline": name,
            "original_frame": original_frame.name,
            "remake_frame": remake_frame.name,
            "regions": report,
        }
        (args.output / f"{name}.json").write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        summary.append(
            {
                "baseline": name,
                "original_frame": original_frame.name,
                "remake_frame": remake_frame.name,
                "full_screen": report["full-screen"]["different_pixels"],
                "status_bar": report["status-bar"]["different_pixels"],
                "command_menu_panel": report["command-menu-panel"][
                    "different_pixels"
                ],
                "left_unit_sprite": report["left-unit-sprite"][
                    "different_pixels"
                ],
            }
        )

    (args.output / "summary.json").write_text(
        json.dumps(
            {
                "schema": SUMMARY_SCHEMA,
                "original_walk": str(original),
                "remake_walk": str(remake),
                "baselines": summary,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    width = max(len(str(item["baseline"])) for item in summary)
    for item in summary:
        print(
            f"{str(item['baseline']):<{width}}  "
            f"full={item['full_screen']:>6}  "
            f"status={item['status_bar']:>4}  "
            f"menu={item['command_menu_panel']:>4}  "
            f"units={item['left_unit_sprite']:>6}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BaselineError, RegionComparisonError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
