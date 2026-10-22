#!/usr/bin/env python3
"""Generate viewer cards for families that ship a large PNG set plus a manifest.

Most families differ only in naming and in which numbers matter, so they share
one builder: read ``manifest.json`` for the headline counts, glob the PNGs, and
render a card.  Families that need bespoke presentation (portraits, glyph strips,
map canvases) keep their own builder in
``tools/build_results_viewer_artifact_sections.py``.

Only families whose manifest and at least one PNG exist are emitted, so a family
that was not regenerated in this worktree produces no broken card.

Usage:
    python3 tools/build_results_viewer_generic_families.py [--root .]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PRE = "../"

# family dir -> (card id, card title, hub page, exporter, verifier, image glob,
#                which manifest counter to headline, counter label)
FAMILIES: tuple[tuple[str, str, str, str, str, str, str, str, str], ...] = (
    (
        "tile-assets-bg-v2", "sec-tile-assets-bg", "reverse-engineering-visuals.html",
        "tools/export_tile_asset_bg_layers.py", "tools/verify_tile_asset_bg_export.py",
        "*.png", "complete_layer_count", "完整 BG 图层",
    ),
    (
        "battle-visual-catalog-v1", "sec-battle-visual-catalog", "reverse-engineering-battle.html",
        "tools/export_battle_visual_catalog.py", "tools/verify_battle_visual_catalog.py",
        "previews/*.png", "descriptor_count", "表现描述符",
    ),
    (
        "battle-visual-runtime-timelines-v1", "sec-battle-visual-timelines",
        "reverse-engineering-battle.html",
        "tools/export_battle_visual_runtime_timelines.py",
        "tools/verify_battle_visual_runtime_timelines.py",
        "visual_*_contact.png", "playable_count", "可播放时间线",
    ),
    (
        "cutscene-obj-v1", "sec-cutscene-obj", "reverse-engineering-story.html",
        "tools/export_cutscene_obj_assets.py", "tools/verify_cutscene_obj_export.py",
        "*.png", "frame_count", "静态 OBJ 帧",
    ),
    (
        "story-visual-layers-v1", "sec-story-visual-layers", "reverse-engineering-story.html",
        "tools/export_story_visual_layers.py", "tools/verify_story_visual_layer_export.py",
        "story_visual_layer_*.png", "entry_count", "剧情视觉图层",
    ),
    (
        "story-scene-timelines-v1", "sec-story-scene-timelines", "reverse-engineering-story.html",
        "tools/export_story_scene_timelines.py", "tools/verify_story_scene_timelines.py",
        "story_*_contact.png", "entry_count", "剧情场景时间线",
    ),
    (
        "dialogue-font-v2", "sec-dialogue-font", "reverse-engineering-story.html",
        "tools/export_dialogue_font_atlases.py", "tools/verify_dialogue_font_atlases.py",
        "*-atlas.png", "glyph_count", "字形图集",
    ),
    (
        "world-map-backgrounds-v1", "sec-world-map-bg", "reverse-engineering-visuals.html",
        "tools/export_world_map_backgrounds.py", "tools/verify_world_map_backgrounds.py",
        "page-*/*.png", "background_count", "世界地图背景",
    ),
    (
        "battle-effect-affine-runtime-v1", "sec-affine-runtime",
        "reverse-engineering-battle.html",
        "tools/export_battle_effect_affine_runtime.py",
        "tools/verify_battle_effect_affine_runtime.py",
        "*.png", "artifact_file_count", "仿射运行时证据",
    ),
    (
        "scene-visual-packs-v1", "sec-scene-visual-packs", "reverse-engineering-visuals.html",
        "tools/export_scene_visual_packs.py", "tools/verify_scene_visual_packs.py",
        "pack-*/background.png", "pack_count", "场景视觉包",
    ),
    (
        "sprite-definition-animations-v1", "sec-sprite-def-anims", "reverse-engineering-data.html",
        "tools/export_sprite_definition_animations.py",
        "tools/verify_sprite_definition_animations.py",
        "sprite-id-*-contact.png", "entry_count", "精灵动画",
    ),
)


def counter(manifest: dict, key: str) -> object:
    """Look a counter up at the top level, then one level into summary/scope."""
    if key in manifest:
        return manifest[key]
    for container in ("summary", "scope", "source_table"):
        nested = manifest.get(container)
        if isinstance(nested, dict) and key in nested:
            return nested[key]
    return None


IMAGE_SUFFIXES = (".png", ".gif", ".jpg", ".jpeg", ".webp")


def first_pngs(directory: Path, pattern: str, limit: int) -> list[Path]:
    """Only real image files.

    A directory or a manifest.json must never be emitted as an <img src>:
    the world-map card used to point at page-00/ and manifest.json.
    """
    return sorted(
        p for p in directory.glob(pattern)
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )[:limit]


def build(root: Path, spec: tuple[str, ...], limit: int) -> str:
    (family, card_id, _page, exporter, verifier, pattern,
     counter_key, counter_label) = spec
    directory = root / "artifacts" / family
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        return ""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    images = first_pngs(directory, pattern, limit)
    if not images:
        return ""

    total_png = len(list(directory.glob(pattern)))
    headline = counter(manifest, counter_key)
    tail = (
        f'<p class="card-desc" style="margin-top:10px;">'
        f'本卡片展示前 <strong>{len(images)}</strong> 张，该族实际共 <strong>{total_png}</strong> 张，'
        f'全部位于 <code>artifacts/{family}/</code>。'
        f'</p>'
    ) if total_png > len(images) else ""

    cards = "\n".join(
        f'            <div class="tileset-item tile-item-compact">\n'
        f'              <div class="tileset-header"><strong>{path.stem}</strong></div>\n'
        f'              <div class="tileset-img-wrap"><img class="tile-zoom-sm" '
        f'src="{PRE}artifacts/{family}/{path.relative_to(directory).as_posix()}" '
        f'alt="{path.stem}" loading="lazy"></div>\n'
        f"            </div>"
        for path in images
    )
    schema = manifest.get("schema", family)
    return f"""        <div class="card full-width" id="{card_id}">
          <div class="card-head">
            <div class="card-title">{card_label(family)}</div>
            <span class="tag tag-cyan">artifacts/{family} · {counter_label} {headline if headline is not None else "—"}</span>
          </div>
          <p class="card-desc">
            由 <code>{exporter}</code> 导出，独立校验器 <code>{verifier}</code> 复核零错误。
            清单 schema：<code>{schema}</code>，完整字段见
            <code>artifacts/{family}/manifest.json</code>。
          </p>
          <div class="tileset-gallery">
{cards}
          </div>
{tail}
        </div>
"""


TITLES = {
    "tile-assets-bg-v2": "图块资产 BG 图层 (Tile Asset BG Layers)",
    "battle-visual-catalog-v1": "79 项战斗视觉表现目录 (Battle Visual Catalog)",
    "battle-visual-runtime-timelines-v1": "战斗视觉运行时时间线 (Battle Visual Runtime Timelines)",
    "cutscene-obj-v1": "过场 OBJ 静态资源 (Cutscene OBJ Assets)",
    "story-visual-layers-v1": "剧情视觉图层 (Story Visual Layers)",
    "story-scene-timelines-v1": "剧情场景时间线 (Story Scene Timelines)",
    "sprite-definition-animations-v1": "精灵定义动画 (Sprite Definition Animations)",
    "dialogue-font-v2": "对话字体图集 (Dialogue Font Atlases)",
    "world-map-backgrounds-v1": "世界地图背景 (World Map Backgrounds)",
    "battle-effect-affine-runtime-v1": "战斗特效仿射运行时 (Affine Runtime Evidence)",
}


def card_label(family: str) -> str:
    return TITLES.get(family, family)


# Families whose generic card is not enough: the scene visual packs ship an
# animated OBJ layer next to the static background, and the generic builder
# only renders the background, so it gets a dedicated builder.
SPECIAL_BUILDERS = {
    "scene-visual-packs-v1": "build_results_viewer_scene_packs",
    "battle-effect-sprite-animations-v1": "build_results_viewer_effect_anims",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("build/viewer-data")
    )
    parser.add_argument("--limit", type=int, default=400)
    args = parser.parse_args()
    root = args.root.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    index: dict[str, tuple[str, str]] = {}
    for spec in FAMILIES:
        if spec[0] in SPECIAL_BUILDERS:
            module = __import__(SPECIAL_BUILDERS[spec[0]])
            markup = module.build(root).rstrip("\n")
        else:
            markup = build(root, spec, args.limit).rstrip("\n")
        if not markup:
            print(f"skipped {spec[0]} (no manifest or no PNG in this worktree)")
            continue
        name = f"fragment-{spec[1][4:]}.html"
        (args.output_dir / name).write_text(markup + "\n", encoding="utf-8")
        index[spec[1]] = (spec[2], name)
        print(f"wrote {args.output_dir / name} ({len(spec[6])} counter)")

    (args.output_dir / "generic-family-fragments.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
