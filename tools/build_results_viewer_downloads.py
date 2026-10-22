#!/usr/bin/env python3
"""Package every viewer image into per-family and per-theme ZIP archives.

The viewer shows 5,395 images across 86 artifact families plus the extracted
build assets.  For offline or bulk use, the same set is offered as:

* one ZIP per artifact family (``docs/downloads/families/<family>.zip``);
* one ZIP per viewer theme (``docs/downloads/themes/<theme>.zip``), with the
  theme taken from the hub page that actually presents the family;
* an ``all-images.zip`` containing every image, for people who just want the
  whole set.

A ``manifest.json`` records what is in each archive, so the download links on
the site can state the real file count and byte size instead of guessing.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import zipfile
from pathlib import Path

ROOT = Path(".")
DOWNLOADS = Path("docs/downloads")
IMAGE_SUFFIXES = (".png", ".gif", ".jpg", ".jpeg", ".webp")


def collect(family: str, root: Path) -> list[Path]:
    out: list[Path] = []
    directory = root / "artifacts" / family
    if directory.is_dir():
        out += [p for p in directory.rglob("*")
                if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]
    return sorted(out)


def collect_build(root: Path) -> list[Path]:
    build = root / "build"
    if not build.is_dir():
        return []
    return sorted(p for p in build.rglob("*")
                  if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)


def write_zip(target: Path, items: list[tuple[Path, str]], root: Path) -> dict:
    """Write a ZIP; ``items`` are (absolute path, archive-relative name)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path, arcname in items:
            zf.write(path, arcname)
            total += path.stat().st_size
    return {
        "zip": str(target.relative_to(root)),
        "files": len(items),
        "source_bytes": total,
        "zip_bytes": target.stat().st_size,
    }


# Theme rules by family-name prefix.  Deterministic and documented, so the
# archive a user picks matches the subject matter they expect.
THEME_RULES: tuple[tuple[str, str], ...] = (
    ("character-", "角色与战斗视觉"),
    ("scene-visual-", "角色与战斗视觉"),
    ("map-", "地图与场景"),
    ("map41-", "地图与场景"),
    ("tile-", "地图与场景"),
    ("bg-", "地图与场景"),
    ("world-map-", "地图与场景"),
    ("runtime-bg-", "地图与场景"),
    ("runtime-screen-", "地图与场景"),
    ("overview-", "地图与场景"),
    ("battle-", "战斗系统"),
    ("battle-effect-", "战斗系统"),
    ("motion-effect-", "战斗系统"),
    ("sappy-", "战斗系统"),
    ("levels-", "战斗系统"),
    ("story-", "剧情与演出"),
    ("scenario-", "剧情与演出"),
    ("cutscene-", "剧情与演出"),
    ("dialogue-", "剧情与演出"),
    ("initializer-", "剧情与演出"),
    ("sprite-definition-", "数据与内存"),
    ("residual-", "数据与内存"),
    ("runtime-", "数据与内存"),
    ("lz77-", "数据与内存"),
    ("direct-", "数据与内存"),
    ("menu-portrait-", "立绘与界面"),
    ("portrait-", "立绘与界面"),
    ("portrait-palette-", "立绘与界面"),
    ("audio", "音频"),
    ("rom-dialogue-", "文本与字形"),
    ("rom-story-", "文本与字形"),
    ("rom-chapter-", "文本与字形"),
    ("rom-profile-", "文本与字形"),
    ("rom-renderer-", "文本与字形"),
    ("rom-training-", "文本与字形"),
    ("rom-fixed-", "文本与字形"),
    ("rom-value-range-", "文本与字形"),
    ("rom-battle-", "战斗系统"),
    ("rom-", "控制流与配置"),
)


def theme_of(family: str, hub_pages: dict[str, str] | None = None) -> str:
    for prefix, theme in THEME_RULES:
        if family.startswith(prefix):
            return theme
    return "其它"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    root = args.root.resolve()

    families = sorted(
        p.parent.name
        for p in (root / "artifacts").glob("*/manifest.json")
    )

    # Which hub page presents which family (used to assign a theme).
    hub_pages = {
        "visuals": (root / "docs/reverse-engineering-visuals.html").read_text(encoding="utf-8"),
        "battle": (root / "docs/reverse-engineering-battle.html").read_text(encoding="utf-8"),
        "story": (root / "docs/reverse-engineering-story.html").read_text(encoding="utf-8"),
        "data": (root / "docs/reverse-engineering-data.html").read_text(encoding="utf-8"),
        "engineering": (root / "docs/reverse-engineering-engineering.html").read_text(encoding="utf-8"),
    }

    manifest: dict[str, dict] = {"schema": "viewer-downloads-v1", "families": {},
                                  "themes": {}}
    all_items: list[tuple[Path, str]] = []

    for family in families:
        images = collect(family, root)
        if not images:
            continue
        items = [(p, f"{family}/{p.relative_to(root / 'artifacts' / family).as_posix()}")
                 for p in images]
        info = write_zip(
            root / DOWNLOADS / "families" / f"{family}.zip", items, root)
        theme = theme_of(family, hub_pages)
        info["theme"] = theme
        manifest["families"][family] = info
        all_items += items

    # Build-tree images (character sprites, tilesets, portraits) as one extra set.
    build_images = collect_build(root)
    if build_images:
        items = [(p, f"build/{p.relative_to(root / 'build').as_posix()}")
                 for p in build_images]
        info = write_zip(root / DOWNLOADS / "families" / "build-assets.zip", items, root)
        info["theme"] = "build"
        manifest["families"]["build-assets"] = info
        all_items += items

    # Theme archives: pick the items by each family's assigned theme.
    family_of: dict[str, str] = {}
    for path, name in all_items:
        family_of[name] = name.split("/", 1)[0]
    for theme in sorted({f["theme"] for f in manifest["families"].values()}):
        items = [
            (p, name) for p, name in all_items
            if manifest["families"].get(family_of[name], {}).get("theme") == theme
        ]
        if not items:
            continue
        safe = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", theme)
        info = write_zip(root / DOWNLOADS / "themes" / f"{safe}.zip", items, root)
        info["theme"] = theme
        manifest["themes"][theme] = info

    # Everything.
    info = write_zip(root / DOWNLOADS / "all-images.zip", all_items, root)
    manifest["all"] = info
    manifest["totals"] = {
        "families": len(manifest["families"]),
        "themes": len(manifest["themes"]),
        "images": len(all_items),
        "source_bytes": sum(i.stat().st_size for i, _ in all_items),
    }

    out = root / "build/viewer-data/downloads.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"families={manifest['totals']['families']} "
          f"themes={manifest['totals']['themes']} "
          f"images={manifest['totals']['images']} "
          f"src={manifest['totals']['source_bytes'] / 1048576:.1f}MiB")
    for theme, info in sorted(manifest["themes"].items()):
        print(f"  theme {theme:14s} {info['files']:5d} files  "
              f"zip={info['zip_bytes'] / 1048576:.1f}MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
