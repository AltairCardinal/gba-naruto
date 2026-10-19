#!/usr/bin/env python3
"""Measure which step on one side corresponds to which step on the other side.

Three S49 pairing baselines were voided because the step-number-to-picture
mapping was read off a contact sheet rather than measured.  This tool removes
the guesswork: it compares every step image of the original walk against every
step image of the remake walk at the same full screen, with no masks and no
dynamic phase search, and reports the full distance matrix plus the ranking that
actually justifies any pairing.

A low distance is evidence, not proof of semantic identity: the tool records
the numbers so a claimed baseline can cite them instead of a position on a
grid.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Sequence

from PIL import Image

from tools.butano.compare_s49_prebattle import compare_full_screen_images

STEP_PATTERN = re.compile(r"^step-(\d+)-(.+)\.png$")


class AlignmentError(RuntimeError):
    """The two walks could not be compared as declared."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def collect_steps(directory: Path) -> list[dict[str, object]]:
    """List a walk's step images ordered by their numeric step index."""
    directory = Path(directory)
    steps: list[dict[str, object]] = []
    for path in sorted(directory.glob("step-*.png")):
        match = STEP_PATTERN.match(path.name)
        if match is None:
            raise AlignmentError(f"unrecognised step image name: {path.name}")
        steps.append({
            "step": int(match.group(1)),
            "key": match.group(2),
            "image": path.name,
            "path": path,
            "sha256": sha256_file(path),
        })
    if not steps:
        raise AlignmentError(f"no step images in {directory}")
    ordered = [step["step"] for step in steps]
    if ordered != sorted(ordered):
        raise AlignmentError(f"{directory}: step indices are not ordered")
    return steps


def pixel_distance(left: Path, right: Path) -> int:
    with Image.open(left) as left_image, Image.open(right) as right_image:
        if left_image.size != right_image.size:
            raise AlignmentError(
                f"screen size mismatch: {left.name} {left_image.size} vs "
                f"{right.name} {right_image.size}")
        return int(compare_full_screen_images(left_image, right_image)["different_pixels"])


def align(original_dir: Path, remake_dir: Path) -> dict[str, object]:
    original_steps = collect_steps(original_dir)
    remake_steps = collect_steps(remake_dir)
    rows = []
    for original_step in original_steps:
        cells = []
        for remake_step in remake_steps:
            cells.append({
                "remake_step": remake_step["step"],
                "different_pixels": pixel_distance(
                    original_step["path"], remake_step["path"]),
            })
        ranked = sorted(cells, key=lambda cell: cell["different_pixels"])
        rows.append({
            "original_step": original_step["step"],
            "original_key": original_step["key"],
            "original_image": original_step["image"],
            "original_sha256": original_step["sha256"],
            "best_remake_step": ranked[0]["remake_step"],
            "best_different_pixels": ranked[0]["different_pixels"],
            "second_best_remake_step": ranked[1]["remake_step"] if len(ranked) > 1 else None,
            "second_best_different_pixels": (
                ranked[1]["different_pixels"] if len(ranked) > 1 else None),
            "cells": cells,
        })
    exact = [row for row in rows if row["best_different_pixels"] == 0]
    return {
        "schema": "konoha.s49-step-alignment.v1",
        "alignment": "all-pairs-full-screen-no-mask-no-phase-search",
        "original": {
            "dir": str(original_dir),
            "steps": len(original_steps),
            "inputs_sha256": _optional_sha(original_dir / "inputs.json"),
        },
        "remake": {
            "dir": str(remake_dir),
            "steps": len(remake_steps),
            "inputs_sha256": _optional_sha(remake_dir / "inputs.json"),
        },
        "original_steps": [
            {"step": step["step"], "key": step["key"], "sha256": step["sha256"]}
            for step in original_steps
        ],
        "remake_steps": [
            {"step": step["step"], "key": step["key"], "sha256": step["sha256"]}
            for step in remake_steps
        ],
        "matched_steps": len(exact),
        "matched_step_indices": [row["original_step"] for row in exact],
        "rows": rows,
    }


def _optional_sha(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--remake", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = align(args.original, args.remake)
    except (AlignmentError, OSError, ValueError, KeyError) as error:
        print(f"s49_step_alignment: {error}")
        return 2
    # Preserve prior evidence: every run writes a new report path.
    with args.output.open("x") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(json.dumps({
        "original_steps": result["original"]["steps"],
        "remake_steps": result["remake"]["steps"],
        "matched_steps": result["matched_steps"],
        "report": str(args.output),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
