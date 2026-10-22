#!/usr/bin/env python3
"""Item-level coverage of completed reverse engineering on the results site.

Family-level counting answers "how many deliverables are on the site", but it
hides partial presentation: a card may show 60 of a family's 250 resources and
still count as one "presented family".  This script therefore counts, for each
completed family, how many of its individual artifacts the site actually
references, and reports three states: full / partial / none.

Counts come from each family's own manifest (or its evidence note when the
manifest only exists on the reverse branch).  Nothing is hand-typed into the
page; the site is scanned for the artifact paths it references.

Run:
    python3 tools/measure_viewer_coverage.py [--root .] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

ROOT = Path(".")


def site_text(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((root / "docs").glob("reverse-engineering-*.html"))
    )


def count_site(site: str, pattern: str) -> int:
    """Count DISTINCT artifacts matched, not raw references.

    A glyph PNG is referenced twice by design (once inside a message strip,
    once in the glyph grid); counting occurrences would report >100%.
    """
    return len(set(re.findall(pattern, site)))


def count_site_names(site: str, pattern: str) -> int:
    """Count distinct captured names.

    Some families are published under two paths at once -- the battle-map
    canvases are rendered from the transparent display copies but the raw
    evidence is linked as well.  Counting full matches would report the same
    canvas twice, so the file name is what gets counted.
    """
    return len({m.group(1) for m in re.finditer(pattern, site)})


# family, title, total_items, site_pattern (None => site carries no content for it)
# total_items is taken from the family's own manifest / evidence note.
FAMILIES: tuple[tuple[str, str, int | None, str | None, str], ...] = (
    ("menu-portraits-v1", "菜单/剧情立绘矩阵", 311,
     r"build/vfx/menu-portraits-v1/(?:portrait_\d+_variant_\d+|special_variant_5)\.png",
     "manifest"),
    # Published twice: the display copies carry the transparent background
    # and the raw evidence is linked from the family page, so the canvas is
    # counted by name.
    ("map-canvases-v1", "成品战场地图画布", 61,
     r"(?:artifacts/map-canvases-v1/canvases|build/map-canvases-web)/(map-[^\"]+\.png)",
     "manifest", "name"),
    ("character-battle-visuals-v1", "角色战斗视觉资源", 250,
     r"artifacts/character-battle-visuals-v1/resource-\d+/frame-\d+\.png", "manifest"),
    ("bg-resource-canvases-v1", "BG 资源画布", 12,
     r"artifacts/bg-resource-canvases-v1/entry-\d+/canvas\.png", "manifest"),
    ("scene-visual-packs-v1", "场景视觉包", 9,
     r"artifacts/scene-visual-packs-v1/pack-\d+/background\.png", "manifest"),
    ("sprite-definition-assets-v2", "精灵定义资源 + 运行时链", 43,
     r"artifacts/sprite-definition-assets-v2/sprite-id-\d+\.png", "manifest"),
    # 79 messages are presented as rendered glyph strips + table rows rather
    # than as .bin links, so the probe matches the message rows in the table.
    ("battle-presentation-glyphs-v1", "战斗演出字形与消息", 251,
     r"artifacts/battle-presentation-glyphs-v1/glyphs/glyph-\d+\.png|"
     r"<td><code>#\d{2}</code></td><td><code class=\"addr-badge\"[^>]*>0x085A2",
     "manifest"),
    ("battle-effect-resource-pairs-v1", "战斗特效资源对", 18,
     r"artifacts/battle-effect-resource-pairs-v1/group-\d+-atlas\.png", "manifest"),
    ("battle-effect-sprite-animations-v1", "战斗特效精灵动画", 178,
     r"artifacts/battle-effect-sprite-animations-v1/group-\d+-frame-\d+\.png", "manifest"),
    # Unblocked in this worktree by adding --from-rom paths to the leaf banks.
    ("tile-assets-bg-v2", "图块资产 BG 图层", 344,
     r"artifacts/tile-assets-bg-v2/[^\"]+\.png", "manifest"),
    ("battle-visual-catalog-v1", "79 项战斗视觉表现目录", 79,
     r"artifacts/battle-visual-catalog-v1/previews/[^\"]+\.png", "manifest"),
    ("battle-visual-runtime-timelines-v1", "战斗视觉运行时时间线", 75,
     r"artifacts/battle-visual-runtime-timelines-v1/visual_\d+_contact\.png", "manifest"),
    ("cutscene-obj-v1", "过场 OBJ 静态资源", 14,
     r"artifacts/cutscene-obj-v1/resource_\d+_(?:atlas|frame_\d+)\.png", "manifest"),
    ("story-visual-layers-v1", "剧情视觉图层", 24,
     r"artifacts/story-visual-layers-v1/story_visual_layer_[^\"]+\.png", "manifest"),
    ("story-scene-timelines-v1", "剧情场景时间线", 24,
     "artifacts/story-scene-timelines-v1/story_\\d\\d_config_\\d\\d_contact\\.png", "manifest"),
    ("sprite-definition-animations-v1", "精灵定义动画", 43,
     r"artifacts/sprite-definition-animations-v1/sprite-id-\d+-contact\.png", "manifest"),
    # Unblocked by importing the committed reverse-branch inputs (bank.json,
    # sjis-to-tile-mapping.json, the affine runtime capture, GPU captures).
    ("dialogue-font-v2", "对话字体图集", 1,
     r"artifacts/dialogue-font-v2/manifest\.json", "manifest"),
    ("world-map-backgrounds-v1", "世界地图背景", 1,
     r"artifacts/world-map-backgrounds-v1/[^\"]+\.png", "manifest"),
    ("battle-effect-affine-runtime-v1", "特效仿射运行时模型", 2,
     r"artifacts/battle-effect-affine-runtime-v1/[^\"]+\.png", "manifest"),
    # Completed, but the artifacts live on the reverse branch.
    ("bg-scene-selection-v1", "BG 场景选择目录", 6,
     "0x0804[0-9A-Fa-f]{4}", "note"),
    ("battle-effect-sequence-bindings-v1", "战斗特效时序绑定", 22,
     "<tr><td><code>\\d{2}</code></td><td><code class=\"addr-badge\"", "note"),
    ("battle-effect-affine-runtime-v1", "特效仿射运行时模型", 2,
     r"artifacts/battle-effect-affine-runtime-v1/[^\"]+\.png", "manifest"),
    
    ("story-scene-layer-bindings-v1", "剧情场景图层绑定", 24,
     r"artifacts/story-scene-timelines-v1/story_\d+_config_\d+_contact\.png", "manifest"),
)


def census_repo_families(root: Path) -> set[str]:
    """Discover every ``artifacts/<family>`` referenced anywhere in the repo.

    A hand-written registry is a blind spot by construction: any completed
    family nobody remembered to register is invisible to it.  The reverse-branch
    work is additionally mirrored under ``notes/evidence/**/source-snapshots/``,
    so a notes-only scan is not enough either -- this walks the whole tree.
    """
    found: set[str] = set()
    pattern = re.compile(r"artifacts/([A-Za-z0-9][\w.\-]+)")
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules"}]
        for name in filenames:
            if not name.endswith((".md", ".py", ".json", ".html", ".txt")):
                continue
            try:
                text = (Path(dirpath) / name).read_text(
                    encoding="utf-8", errors="ignore"
                )
            except OSError:
                continue
            found.update(m.rstrip("/") for m in pattern.findall(text))
    return {
        name for name in found
        if re.fullmatch(r"[a-z0-9][a-z0-9._-]*-v\d+", name)
    }


def is_remake_evidence(name: str) -> bool:
    """Butano remake A/B baselines are a different workstream, not ROM RE."""
    return name.startswith(
        ("butano-", "scenario-", "s49-", "original-", "type2-")
    )


def family_stem(name: str) -> str:
    """Collapse incremental batches: rom-cfg-proven-roots-v1..v15 -> one family."""
    return re.sub(r"-v\d+$", "", name)




def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    site = site_text(root)
    families_dir = root / "docs" / "families"

    def has_card(name: str) -> bool:
        """A family counts as presented if it has a card on a hub page or its
        own sub-page under docs/families/."""
        if any(f'id="{pre}{name}"' in site
               for pre in ("di-", "fml-", "sec-")):
            return True
        return (families_dir / f"{name}.html").is_file()

    discovered = census_repo_families(root)
    rom_names = sorted(n for n in discovered if not is_remake_evidence(n))
    remake_names = sorted(n for n in discovered if is_remake_evidence(n))
    rom_stems = sorted({family_stem(n) for n in rom_names})

    registered = {family_stem(f[0]) for f in FAMILIES}
    unregistered = [s for s in rom_stems if s not in registered]

    rows = []
    for spec in FAMILIES:
        family, title, total, pattern, source = spec[:5]
        by_name = len(spec) > 5 and spec[5] == "name"
        shown = (count_site_names(site, pattern) if by_name
                 else count_site(site, pattern)) if pattern else 0
        if pattern is None:
            state = "not-presentable" if shown == 0 else "present"
        elif total is None:
            state = "unknown-total"
        elif shown >= total:
            state = "full"
        elif shown > 0:
            state = "partial"
        else:
            state = "none"
        rows.append({
            "family": family, "title": title, "total_items": total,
            "site_items": shown, "state": state, "count_source": source,
            "percent": round(shown / total * 100, 1) if total else None,
        })

    known = [r for r in rows if r["total_items"]]
    full = [r for r in known if r["state"] == "full"]
    partial = [r for r in known if r["state"] == "partial"]
    none = [r for r in known if r["state"] == "none"]

    total_items = sum(r["total_items"] for r in known)
    shown_items = sum(r["site_items"] for r in known)

    # Excluding dialogue-font-v2: its unit is an 8x8 glyph, which is not
    # comparable in weight to a 736x512 map canvas.  Reported separately.
    weighted = [r for r in known if r["family"] != "dialogue-font-v2"]
    w_total = sum(r["total_items"] for r in weighted)
    w_shown = sum(r["site_items"] for r in weighted)

    # Family-level view: the repo's own unit for "completed reverse engineering"
    # is one exporter/verifier-backed deliverable, so this is the headline.
    with_content = [r for r in rows if r["site_items"] > 0]
    fully = [r for r in rows if r["state"] == "full"]
    family_total = len(rows)

    # Families presented as structured data (not images) on the data-index page.
    # A family counts as presented if the site renders a card for it under any
    # of the owning builders, regardless of whether it ships PNGs.
    data_presented = [
        stem for stem in rom_stems
        if has_card(stem) or any(
            has_card(v) for v in rom_names if family_stem(v) == stem
        )
    ]
    total_presented = sorted(set(data_presented) | {
        re.sub(r"-v\d+$", "", r["family"]) for r in with_content
    })

    # The census groups by stem and drops remake-baseline prefixes, so it can
    # report families the site renders cards for without counting them.  Add a
    # direct manifest-to-card ratio, which counts every family that ships one.
    data_presented = [
        stem for stem in rom_stems
        if has_card(stem) or any(
            has_card(v) for v in rom_names if family_stem(v) == stem
        )
    ]
    total_presented = sorted(set(data_presented) | {
        re.sub(r"-v\d+$", "", r["family"]) for r in with_content
    })

    # The census groups by stem and drops remake-baseline prefixes, so it can
    # report families the site renders cards for without counting them.  Add a
    # direct manifest-to-card ratio, which counts every family that ships one.
    manifest_families = {
        Path(p).parent.name for p in Path(root / "artifacts").glob("*/manifest.json")
    }
    with_manifest_card = {
        f for f in manifest_families
        if has_card(f) or any(
            has_card(v) for v in rom_names if family_stem(v) == f
        )
    }

    report = {
        "schema": "viewer-coverage-v2",
        "HEADLINE_manifest_families": {
            "families_with_manifest": len(manifest_families),
            "families_presented": len(with_manifest_card),
            "families_missing": len(manifest_families - with_manifest_card),
            "percent": round(
                len(with_manifest_card) / len(manifest_families) * 100, 1
            ) if manifest_families else 0.0,
            "missing_families": sorted(manifest_families - with_manifest_card),
        },
        # The headline denominator is the repo-wide census, NOT the hand-kept
        # registry: a registry cannot see families nobody remembered to add.
        "HEADLINE_family_level": {
            "families_total": family_total,
            "families_with_content_on_site": len(with_content),
            "families_fully_presented": len(fully),
            "percent_with_content": round(len(with_content) / family_total * 100, 1),
            "percent_fully_presented": round(len(fully) / family_total * 100, 1),
        },
        "HEADLINE_census_denominator": {
            "families_total": len(rom_stems),
            "families_with_content_on_site": len(total_presented),
            "families_fully_presented": len(fully),
            "percent_with_content": round(len(total_presented) / len(rom_stems) * 100, 1),
            "percent_fully_presented": round(len(fully) / len(rom_stems) * 100, 1),
            "presented_as_data_families": len(data_presented),
        },
        "families_total": family_total,
        "families_with_known_size": len(known),
        "families_full": len(full),
        "families_partial": len(partial),
        "families_absent": len(none),
        "items_total": total_items,
        "items_shown": shown_items,
        "items_percent": round(shown_items / total_items * 100, 1),
        "items_percent_excluding_glyphs": round(w_shown / w_total * 100, 1),
        "items_shown_excluding_glyphs": w_shown,
        "items_total_excluding_glyphs": w_total,
        "rows": rows,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")

    # Unregistered-but-completed families: discovered by walking the repo, never
    # on the site.  These are invisible to any hand-kept registry.
    unregistered_rows = []
    for stem in unregistered:
        variants = [n for n in rom_names if family_stem(n) == stem]
        unregistered_rows.append({
            "family_stem": stem,
            "versions": variants,
            # Count references to real artifact *files*, not the bare path:
            # the toolbox names scripts, and conclusion notes quote artifact
            # paths as historical evidence.  Neither presents the family.
            "site_items": sum(
                count_site(
                    site,
                    r"artifacts/" + re.escape(v) + r"/[^\"\s]+\.(?:png|gif|json|bin|bmp)",
                )
                for v in variants
            ),
        })
    report["census"] = {
        "rom_family_names": len(rom_names),
        "rom_family_stems": len(rom_stems),
        "remake_evidence_names": len(remake_names),
        "registered_stems": len(registered),
        "unregistered_stems": len(unregistered),
        "unregistered_with_site_content": sum(
            1 for r in unregistered_rows if r["site_items"] > 0
        ),
    }
    report["unregistered_families"] = unregistered_rows
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")

    mh = report["HEADLINE_manifest_families"]
    print(f"HEADLINE (families shipping a manifest): "
          f"{mh['families_presented']}/{mh['families_with_manifest']} = "
          f"{mh['percent']}%  (missing {mh['families_missing']})")
    print(f"CENSUS: {len(rom_names)} ROM family names -> {len(rom_stems)} stems; "
          f"registered {len(registered)}; UNREGISTERED {len(unregistered)} "
          f"(site content: {report['census']['unregistered_with_site_content']})")
    head = report["HEADLINE_family_level"]
    cen = report["HEADLINE_census_denominator"]
    print(f"HEADLINE (census denominator, all completed ROM families): "
          f"{cen['families_with_content_on_site']}/{cen['families_total']} = "
          f"{cen['percent_with_content']}%  (fully presented {cen['families_fully_presented']} = {cen['percent_fully_presented']}%)")
    print(f"  (hand-kept registry only would have said "
          f"{len(with_content)}/{family_total} = {head['percent_with_content']}% -- inflated by omission)")
    print(f"items: {shown_items}/{total_items} = {report['items_percent']}%")
    print(f"items excluding dialogue-font-v2 glyphs: "
          f"{w_shown}/{w_total} = {report['items_percent_excluding_glyphs']}%")
    print()
    for row in rows:
        pct = f"{row['percent']}%" if row["percent"] is not None else "  -  "
        print(f"  {row['family']:40s} {str(row['site_items']):>5s}/"
              f"{str(row['total_items'] or '?'):>5s}  {pct:>7s}  {row['state']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
