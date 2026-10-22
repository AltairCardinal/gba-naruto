#!/usr/bin/env python3
"""Emit the image-download panel for the viewer.

Reads ``build/viewer-data/downloads.json`` (produced by
``tools/build_results_viewer_downloads.py``) and writes a panel of chips that
link to the per-theme and per-family ZIP archives, with the real file count and
archive size on each chip.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

THEME_LABEL = {
    "角色与战斗视觉": "角色与战斗视觉",
    "地图与场景": "地图与场景",
    "战斗系统": "战斗系统",
    "剧情与演出": "剧情与演出",
    "文本与字形": "文本与字形",
    "控制流与配置": "控制流与配置",
    "数据与内存": "数据与内存",
    "立绘与界面": "立绘与界面",
    "音频": "音频",
    "其它": "其它",
}


def human(size: int) -> str:
    if size >= 1048576:
        return f"{size / 1048576:.1f} MiB"
    if size >= 1024:
        return f"{size / 1024:.0f} KiB"
    return f"{size} B"


def esc(text: str) -> str:
    import html
    return html.escape(text, quote=False)


def build_panel(manifest: dict, sections: dict) -> str:
    themes = manifest.get("themes", {})
    families = manifest.get("families", {})
    totals = manifest.get("totals", {})

    # 1) Section packs: one archive per viewer card -- what you see on a card
    #    is exactly what the archive contains.
    section_chips = []
    for pack in sorted(sections.get("packs", []), key=lambda x: -x["files"]):
        name = Path(pack["zip"]).name
        section_chips.append(
            f'<a class="dl-chip" href="{pack["zip"]}" download>'
            f'<strong>{esc(pack["title"])}</strong>'
            f'<span class="dl-size">{pack["files"]:,} 张</span></a>'
        )

    chips = []
    all_info = manifest.get("all")
    if all_info:
        chips.append(
            f'<a class="dl-chip" href="downloads/{Path(all_info["zip"]).name}" download>'
            f'<strong>全部图像</strong>'
            f'<span class="dl-size">{all_info["files"]:,} 张 · {human(all_info["zip_bytes"])}</span></a>'
        )
    for theme, info in sorted(themes.items()):
        name = Path(info["zip"]).name
        chips.append(
            f'<a class="dl-chip" href="downloads/themes/{name}" download>'
            f'<strong>{esc(THEME_LABEL.get(theme, theme))}</strong>'
            f'<span class="dl-size">{info["files"]:,} 张 · {human(info["zip_bytes"])}</span></a>'
        )

    family_chips = []
    for family, info in sorted(families.items()):
        if info.get("files", 0) == 0:
            continue
        family_chips.append(
            f'<a class="dl-chip" href="downloads/families/{family}.zip" download>'
            f'<strong>{esc(family)}</strong>'
            f'<span class="dl-size">{info["files"]:,} 张</span></a>'
        )

    return f"""        <div class="card full-width" id="sec-image-downloads">
          <div class="card-head">
            <div class="card-title">图像资源打包下载 (Image Download Packs)</div>
            <span class="tag tag-cyan">{totals.get("images", 0):,} 张图像 · {human(totals.get("source_bytes", 0))} 原始体积</span>
          </div>
          <p class="card-desc">
            页面上的每一张图都可以<strong>点击放大</strong>（Esc 关闭，←/→ 翻页，放大后可单独下载原图）。
            下面按<strong>页面板块</strong>打包：每个板块一个 ZIP，<strong>包内就是该板块展示的全部图像</strong>
            （例如「角色动作交互工作室」包含所有角色的动作动画 GIF 与帧条）。
          </p>
          <div class="dl-panel">
{chr(10).join("            " + c for c in section_chips)}
          </div>
          <details style="margin-top:12px;">
            <summary style="cursor:pointer; color:var(--accent-cyan); font-weight:600; font-size:0.9rem;">
              🗂 按成果族 / 主题重新分组
            </summary>
            <div class="dl-panel" style="margin-top:10px;">
{chr(10).join("              " + c for c in chips)}
            </div>
            <div class="dl-panel" style="margin-top:10px;">
{chr(10).join("              " + c for c in family_chips)}
            </div>
          </details>
        </div>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path,
        default=Path("build/viewer-data/fragment-image-downloads.html"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    manifest_path = root / "build/viewer-data/downloads.json"
    if not manifest_path.is_file():
        raise SystemExit("run tools/build_results_viewer_downloads.py first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sections_path = root / "build/viewer-data/section-packs.json"
    sections = (
        json.loads(sections_path.read_text(encoding="utf-8"))
        if sections_path.is_file() else {"packs": []}
    )
    panel = build_panel(manifest, sections)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(panel, encoding="utf-8")
    print(f"wrote {args.output} "
          f"({len(sections.get('packs', []))} 板块包 + "
          f"{len(manifest.get('themes', {}))} 主题包 + "
          f"{len(manifest.get('families', {}))} 族包)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
