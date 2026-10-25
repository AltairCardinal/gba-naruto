#!/usr/bin/env python3
"""Extract the original S49 battle-14 map truth (atlas + terrain + passability).

The reverse line (read only) exports every map of the original ROM as a
canvas, a tilemap and a *collision grid*:

    D:\\Shell\\gba-naruto-reverse\\artifacts\\map-canvases-v1\\
        manifest.json
        canvases/map-NN-primary.png
        tilemaps/map-NN-primary-u16le.bin
        resources/collision-grids/<sha>.u16le.bin

This script picks the battle-14 map out of that manifest, copies the small
artifacts into ``tools/s49_orig_map/artifacts/`` and writes a machine
readable truth file next to it.

The battle-14 map is **map id 14**: it is the only map whose coarse grid is
15 x 19, which is exactly the shape of the remake's battle-14 battle grid
(15 x 19 cells) -- see notes/s49-fidelity/M-original-victory-truth.md.

Grid geometry (from the manifest's ``consumer_contract``):

* the coarse (battle) cell is ``coarse_cell_size_tiles = [4, 2]`` =
  **32 x 16 px**, so the battle grid is 15 x 19 cells = 480 x 304 px
* the map is stored as 60 x 38 tiles of 8 x 8 px
* the collision grid holds one byte per coarse cell (the high byte is zero)

Usage::

    python tools/s49_orig_map/orig_map_truth.py --out tools/s49_orig_map
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil

REVERSE = pathlib.Path(r"D:\Shell\Github\gba-naruto-reverse\artifacts\map-canvases-v1")

# The collision byte -> terrain class.  The names come from the map canvas:
# 15 is the grass wall that closes the arena, 1 is the river, 7 is a rock /
# bush and 3 is a small ground patch; 0 is plain grass.
TERRAIN = {
    0: {"name": "plain", "walkable": True},
    1: {"name": "river", "walkable": False},
    3: {"name": "ground_patch", "walkable": True},
    7: {"name": "rock", "walkable": False},
    15: {"name": "wall", "walkable": False},
}

BATTLE_MAP_ID = 14
BATTLE_COARSE = (15, 19)


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest() -> dict:
    return json.loads((REVERSE / "manifest.json").read_text(encoding="utf-8"))


def find_map(manifest: dict, map_id: int) -> dict:
    for entry in manifest["entries"]:
        if entry["map_id"] == map_id:
            return entry
    raise SystemExit(f"map id {map_id} not in the manifest")


def collision_cells(entry: dict) -> list[int]:
    resource = entry["resources"]["collision_grid"]
    path = REVERSE / resource["output_bin"]
    blob = pathlib.Path(path).read_bytes()
    if len(blob) != resource["decompressed_size"]:
        raise SystemExit(f"collision grid size mismatch: {len(blob)}")
    return [blob[index * 2] for index in range(len(blob) // 2)]


def ascii_map(cells: list[int], cols: int, rows: int) -> str:
    short = {0: ".", 1: "~", 3: ",", 7: "O", 15: "#"}
    lines = []
    for y in range(rows):
        row = " ".join(short.get(cells[y * cols + x], "?") for x in range(cols))
        lines.append(f"  y{y:02d} {row}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(pathlib.Path(__file__).resolve().parent))
    parser.add_argument("--map-id", type=int, default=BATTLE_MAP_ID)
    args = parser.parse_args(argv)

    out_dir = pathlib.Path(args.out)
    art_dir = out_dir / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest()
    entry = find_map(manifest, args.map_id)
    cols, rows = entry["coarse_grid_dimensions"]
    if (cols, rows) != BATTLE_COARSE:
        print(f"!! map {args.map_id} coarse grid {entry['coarse_grid_dimensions']} "
              f"!= expected {list(BATTLE_COARSE)}")

    cells = collision_cells(entry)
    if len(cells) != cols * rows:
        raise SystemExit(f"collision grid has {len(cells)} cells, expected {cols*rows}")

    # copy the small artifacts so the truth is self contained
    copied = {}
    for variant in entry.get("variants", []):
        for key, suffix in (("canvas_png", "atlas.png"),
                            ("tilemap_bin", "tilemap-u16le.bin")):
            if key not in variant:
                continue
            source = REVERSE / variant[key]
            target = art_dir / f"map-{args.map_id:02d}-{suffix}"
            shutil.copyfile(source, target)
            copied[target.name] = {
                "source": str(source),
                "sha256": sha256(target),
                "bytes": target.stat().st_size,
            }

    classes: dict[str, int] = {}
    for value in cells:
        classes[TERRAIN.get(value, {"name": "unknown"})["name"]] = \
            classes.get(TERRAIN.get(value, {"name": "unknown"})["name"], 0) + 1

    truth = {
        "schema": "konoha.s49-orig-map.v1",
        "map_id": args.map_id,
        "source": {
            "manifest": str(REVERSE / "manifest.json"),
            "manifest_sha256": sha256(REVERSE / "manifest.json"),
            "collision_grid_sha256":
                entry["resources"]["collision_grid"]["sha256"],
        },
        "geometry": {
            "tiles": entry["dimensions_tiles"],
            "pixels": entry["dimensions_pixels"],
            "coarse_grid": [cols, rows],
            "coarse_cell_px": [32, 16],
            "coarse_cell_tiles": manifest["consumer_contract"]["coarse_cell_size_tiles"],
        },
        "terrain_classes": {
            str(value): info for value, info in sorted(TERRAIN.items())
        },
        "class_histogram": classes,
        "walkable_cells": sum(1 for value in cells
                              if TERRAIN.get(value, {}).get("walkable")),
        "blocked_cells": sum(1 for value in cells
                             if not TERRAIN.get(value, {}).get("walkable", False)),
        "collision_grid": cells,
        "copied_artifacts": copied,
    }
    (out_dir / "battle-14-map-truth.json").write_text(
        json.dumps(truth, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")

    print(f"map {args.map_id}: {cols}x{rows} battle cells of 32x16 px "
          f"({entry['dimensions_pixels'][0]}x{entry['dimensions_pixels'][1]} px)")
    print(f"  classes: {classes}")
    print(f"  walkable {truth['walkable_cells']} / blocked {truth['blocked_cells']}")
    print("  # wall  ~ river  O rock  , patch  . plain")
    print(ascii_map(cells, cols, rows))
    print("-> ", out_dir / "battle-14-map-truth.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
