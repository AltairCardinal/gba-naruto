#!/usr/bin/env python3
"""Render the battle-effect sprite animations as real animations.

``artifacts/battle-effect-sprite-animations-v1`` exports, per group, a set of
frame PNGs plus a keyframe timeline (``frame_id`` + ``hold_frames``).  The
generic card builder listed the 182 frames as static thumbnails, so the family
looked frozen even though the timing data is right there in the manifest.

This builds one card per group that plays the frames with the real hold
durations, and lists the frame sequence for reference.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PRE = "../"
FAMILY = "battle-effect-sprite-animations-v1"


def build(root: Path) -> str:
    directory = root / "artifacts" / FAMILY
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        return ""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    cards = []
    for group in manifest.get("groups", []):
        group_id = group.get("group_id", 0)
        stem = f"group-{group_id:02d}"
        available = {
            p.name: p for p in directory.glob(f"{stem}-frame-*.png")
        }
        # The animation timeline: frame_id -> hold_frames.
        timeline = []
        for animation in group.get("animations", []):
            for keyframe in animation.get("keyframes", []):
                name = f"{stem}-frame-{keyframe['frame_id']:02d}.png"
                if name in available:
                    timeline.append((name, int(keyframe.get("hold_frames", 1))))
        if not timeline:
            timeline = [(p.name, 1) for p in sorted(available.values())]
        if not timeline:
            continue

        frames = "|".join(f"{PRE}artifacts/{FAMILY}/{name}" for name, _ in timeline)
        holds = ",".join(str(hold) for _, hold in timeline)
        total = sum(hold for _, hold in timeline)
        # A group can define more frames than its keyframe timeline plays --
        # group 18 defines 8 frames but its only animation uses 7 of them.
        # Those frames are real artifacts, so they are shown as stills rather
        # than dropped: nothing in the family may be invisible.
        unplayed = [p.name for p in sorted(available.values())
                    if p.name not in {name for name, _ in timeline}]
        extra = ""
        if unplayed:
            extra = (
                '          <div class="pack-anim-extra">'
                f'<span class="pack-anim-extra-label">未被关键帧播放的 {len(unplayed)} 帧</span>'
                + "".join(
                    f'<img class="tile-zoom-sm" src="{PRE}artifacts/{FAMILY}/{name}" '
                    f'alt="{name}" loading="lazy">'
                    for name in unplayed
                )
                + "</div>\n"
            )
        cards.append(
            f'        <div class="tileset-item tile-item-compact">\n'
            f'          <div class="tileset-header"><strong>Group {group_id:02d}</strong>'
            f'<span class="tag tag-cyan">{group.get("frame_count", len(timeline))} 帧</span></div>\n'
            f'          <span class="pack-anim-player" data-frames="{frames}" '
            f'data-holds="{holds}" data-fps="60" '
            f'title="按 hold_frames 时序播放（{total} tick）"></span>\n'
            + extra +
            f'          <div class="tileset-meta">'
            f'{group.get("animation_count", 0)} 动画 · '
            f'{group.get("component_count", 0)} 组件 · '
            f'{group.get("keyframe_count", 0)} 关键帧</div>\n'
            f"        </div>"
        )

    if not cards:
        return ""
    summary = manifest.get("summary", {})
    return f"""        <div class="card full-width" id="sec-battle-effect-anims">
          <div class="card-head">
            <div class="card-title">战斗特效精灵动画 (Battle Effect Sprite Animations)</div>
            <span class="tag tag-rose">{len(cards)} 组 · {summary.get("frame_definition_count", 0)} 帧 ·
              {summary.get("animation_count", 0)} 动画 · {summary.get("keyframe_count", 0)} 关键帧</span>
          </div>
          <p class="card-desc">
            每组特效按该族 manifest 里的 <strong>关键帧时序</strong>（<code>frame_id</code> +
            <code>hold_frames</code>）播放，而不是把帧排成静态图。
            下方每组可点击暂停 / 继续；帧序列出处列在各自图集下载包内。
          </p>
          <div class="tileset-gallery" data-paginate="24">
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
        default=Path("build/viewer-data/fragment-battle-effect-anims.html"),
    )
    args = parser.parse_args()
    markup = build(args.root.resolve())
    if not markup:
        print("battle effect animations not available")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markup, encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
