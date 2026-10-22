#!/usr/bin/env python3
"""Render the scene visual packs properly: background + animated OBJ layers.

The generic card builder only picked ``pack-*/background.png`` for this family,
so the viewer showed a static backdrop and the user could not tell that the
family also contains 16 OBJ animation frames, 18 OBJ atlases and the animation
timing definitions.  This builds a dedicated section that shows all of it and
drives the OBJ frames from the family's own ``playback`` data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PRE = "../"
FAMILY = "scene-visual-packs-v1"


def collect(root: Path) -> tuple[list[dict], dict]:
    directory = root / "artifacts" / FAMILY
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        return [], {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    packs = []
    for pack in manifest.get("packs", []):
        pack_id = pack.get("pack_id", 0)
        pack_dir = f"pack-{pack_id:02d}"
        animations = []
        for anim_path in sorted(directory.glob(f"{pack_dir}/obj-animation-*.json")):
            data = json.loads(anim_path.read_text(encoding="utf-8"))
            frame_files = sorted(directory.glob(f"{pack_dir}/obj-frame-*.png"))
            # Playback order is authoritative; fall back to file order.
            order = [f"obj-frame-{p['frame_id']:02d}.png" for p in data.get("playback", [])]
            ordered = [f for f in order if (directory / pack_dir / f).is_file()]
            if not ordered:
                ordered = [p.name for p in frame_files]
            if not ordered:
                continue
            animations.append({
                "id": data.get("animation_id"),
                "frame_id": data.get("frame_id"),
                "pointer": data.get("timeline_pointer"),
                "policy": data.get("termination_policy"),
                "frames": [f"{pack_dir}/{f}" for f in ordered],
                "fps": 12,
            })
        atlases = sorted(p.name for p in directory.glob(f"{pack_dir}/obj-atlas-*.png"))
        background = directory / pack_dir / "background.png"
        if not background.is_file():
            continue
        packs.append({
            "pack_id": pack_id,
            "address": pack.get("entry_gba_address"),
            "presentation_id": pack.get("presentation_id"),
            "spawn_count": pack.get("spawn_count"),
            "background": f"{pack_dir}/background.png",
            "animations": animations,
            "atlases": [f"{pack_dir}/{a}" for a in atlases],
        })
    return packs, manifest


def build(root: Path) -> str:
    packs, manifest = collect(root)
    if not packs:
        return ""
    summary = manifest.get("summary", {})

    cards = []
    for pack in packs:
        anim_blocks = []
        for anim in pack["animations"]:
            frames = "|".join(f"{PRE}artifacts/{FAMILY}/{f}" for f in anim["frames"])
            anim_blocks.append(
                f'            <div class="pack-anim">\n'
                f'              <div class="pack-anim-label">OBJ 动画 #{anim["id"]}'
                f' · frame {anim["frame_id"]} · {anim["policy"]}</div>\n'
                f'              <span class="pack-anim-player" data-frames="{frames}" '
                f'data-fps="{anim["fps"]}" data-frame-index="{anim["frames"].index(anim["frames"][0])}">'
                f'</span>\n'
                f'              <div class="pack-anim-meta">'
                f'{" / ".join(anim["frames"])}</div>\n'
                f"            </div>"
            )
        atlas_html = "".join(
            f'<div class="pack-atlas"><img src="{PRE}artifacts/{FAMILY}/{a}" '
            f'alt="{a}" loading="lazy"></div>' for a in pack["atlases"]
        )
        cards.append(
            f'        <div class="tileset-item pack-item">\n'
            f'          <div class="tileset-header"><strong>Pack {pack["pack_id"]:02d}</strong>'
            f'<span class="tag tag-cyan">{pack["spawn_count"]} 个 OBJ</span></div>\n'
            f'          <div class="tileset-img-wrap">'
            f'<img src="{PRE}artifacts/{FAMILY}/{pack["background"]}" '
            f'alt="pack {pack["pack_id"]} background" loading="lazy"></div>\n'
            f'          <div class="pack-anims">\n' + "\n".join(anim_blocks) + "\n          </div>\n"
            f'          <div class="pack-atlases">{atlas_html}</div>\n'
            f'          <div class="tileset-meta">入口 {pack["address"]} · '
            f'presentation {pack["presentation_id"]}</div>\n'
            f"        </div>"
        )

    return f"""        <div class="card full-width" id="sec-scene-visual-packs">
          <div class="card-head">
            <div class="card-title">场景视觉包 (Scene Visual Packs)</div>
            <span class="tag tag-green">artifacts/{FAMILY} · {summary.get("pack_count", len(packs))} 包 ·
              {summary.get("obj_frame_count", 0)} 动画帧 · {summary.get("obj_animation_count", 0)} 动画</span>
          </div>
          <p class="card-desc">
            每个场景包同时包含<strong>背景画布</strong>（BG 图层）与 <strong>OBJ 动态层</strong>。
            OBJ 帧按该族自身的 <code>playback</code> 时序数据驱动播放，播放策略为
            <code>termination_policy</code>；下方同时列出 OBJ 图集（atlas）原图与帧序列出处。
            此前本页只渲染了静态背景，遗漏了 OBJ 动画层与图集。
          </p>
          <div class="tileset-gallery">
{chr(10).join(cards)}
          </div>
        </div>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/viewer-data/fragment-scene-visual-packs.html"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    markup = build(root)
    if not markup:
        print("scene visual packs not available")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markup, encoding="utf-8")
    print(f"wrote {args.output} ({markup.count('pack-item')} packs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
