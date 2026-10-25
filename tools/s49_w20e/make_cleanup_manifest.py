#!/usr/bin/env python3
"""E4 task 2: build the deletion manifest for the 33 unreferenced dialogue assets.

Produces a manifest with size / sha256 / estimated ROM cost, and (with
--apply) deletes the files from the E4 lane copy only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

SHARED_GRAPHICS = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics"
)
LANE_GRAPHICS = pathlib.Path(
    r"D:\Github\gba-naruto\build\w20-e4\butano-sequel\graphics"
)
REPORT = pathlib.Path(r"D:\Github\gba-naruto\build\w20-e4\unused-dialogue-assets.json")
MANIFEST = pathlib.Path(
    r"D:\Github\gba-naruto\build\w20-e4\dialogue-asset-cleanup-manifest.json"
)

# A 256x256 8bpp source becomes 4bpp tiles in the ROM (32768 B) plus a
# 256 colour palette (512 B).
TILE_BYTES = 256 * 256 // 2
PALETTE_BYTES = 512
ROM_BYTES_PER_ASSET = TILE_BYTES + PALETTE_BYTES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="delete the unreferenced assets from the lane copy",
    )
    args = parser.parse_args()

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    stems = report["unreferenced_stems"]

    entries = []
    for stem in stems:
        for suffix in (".bmp", ".json"):
            path = SHARED_GRAPHICS / f"{stem}{suffix}"
            if not path.is_file():
                raise SystemExit(f"missing {path}")
            data = path.read_bytes()
            entries.append(
                {
                    "name": path.name,
                    "stem": stem,
                    "suffix": suffix,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "shared_path": str(path),
                    "lane_path": str(LANE_GRAPHICS / path.name),
                    "lane_exists": (LANE_GRAPHICS / path.name).is_file(),
                }
            )

    bmp_count = sum(1 for e in entries if e["suffix"] == ".bmp")
    manifest = {
        "schema": "konoha.s49-dialogue-asset-cleanup.v1",
        "reason": (
            "zero references in the whole remake tree (product code, tests, "
            "build scripts, third_party); the wave 19 settlement tail ships "
            "scenario_41_postbattle_dialogue_page_1..7 instead"
        ),
        "shared_tree_untouched": True,
        "lane_graphics_dir": str(LANE_GRAPHICS),
        "unreferenced_stem_count": len(stems),
        "unreferenced_bmp_count": bmp_count,
        "file_count": len(entries),
        "source_bytes_total": sum(e["bytes"] for e in entries),
        "estimated_rom_bytes_per_asset": ROM_BYTES_PER_ASSET,
        "estimated_rom_bytes_total": ROM_BYTES_PER_ASSET * bmp_count,
        "entries": entries,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"stems={len(stems)} files={len(entries)}")
    print(f"source bytes = {manifest['source_bytes_total']}")
    print(
        f"estimated ROM bytes = {bmp_count} x {ROM_BYTES_PER_ASSET} "
        f"= {manifest['estimated_rom_bytes_total']}"
    )
    print(f"wrote {MANIFEST}")

    if args.apply:
        missing = [e for e in entries if not e["lane_exists"]]
        if missing:
            raise SystemExit(
                f"{len(missing)} lane files missing, e.g. {missing[0]['lane_path']}"
            )
        for entry in entries:
            pathlib.Path(entry["lane_path"]).unlink()
        left = [
            p.name for p in LANE_GRAPHICS.glob("scenario_41_postbattle_dialogue_*")
        ]
        print(f"deleted {len(entries)} lane files; "
              f"{len(left)} scenario_41_postbattle_dialogue_* files remain")
        remaining_stems = sorted({p.rsplit(".", 1)[0] for p in left})
        print("remaining stems: " + ", ".join(remaining_stems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
