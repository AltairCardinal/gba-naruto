#!/usr/bin/env python3
"""Serially rebuild and verify every promoted image-relocation artifact."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[1]


FAMILIES = (
    (
        "character_battle_bundle",
        "character-battle-bundle-relocation-v1",
    ),
    (
        "tile_asset_resource",
        "tile-asset-resource-relocation-v1",
    ),
    (
        "map_resource",
        "map-resource-relocation-v1",
    ),
    (
        "menu_portrait",
        "menu-portrait-relocation-v1",
    ),
    (
        "bg_resource",
        "bg-resource-relocation-v1",
    ),
    (
        "battle_effect_resource",
        "battle-effect-resource-relocation-v1",
    ),
    (
        "story_visual_resource",
        "story-visual-resource-relocation-v1",
    ),
    (
        "world_map_background",
        "world-map-background-relocation-v1",
    ),
)


def build_plan(root: Path) -> list[list[str]]:
    root = Path(root).resolve()
    root_arg = str(root)
    plan = [
        [
            "python3",
            "tools/export_story_visual_resource_sources.py",
            "--root",
            root_arg,
            "--output",
            "artifacts/story-visual-resource-sources-v1",
        ]
    ]
    for stem, artifact_id in FAMILIES:
        plan.append(
            [
                "python3",
                f"tools/export_{stem}_relocation_audit.py",
                "--root",
                root_arg,
                "--output",
                f"artifacts/{artifact_id}",
            ]
        )
    for stem, artifact_id in FAMILIES:
        plan.append(
            [
                "python3",
                f"tools/verify_{stem}_relocation_audit.py",
                "--root",
                root_arg,
                "--artifact",
                f"artifacts/{artifact_id}",
            ]
        )
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print commands without executing them.",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    plan = build_plan(root)
    if args.list:
        for command in plan:
            print(" ".join(command))
        return 0
    for index, command in enumerate(plan, start=1):
        print(f"[{index}/{len(plan)}] {' '.join(command[1:3])}", flush=True)
        subprocess.run(command, cwd=root, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
