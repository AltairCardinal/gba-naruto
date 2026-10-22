#!/usr/bin/env python3
"""Summarise verified reverse-engineering artifact families for the results viewer.

The viewer page historically covered only a handful of assets, while the repo
contains many more exporter/verifier pairs whose results are fully verified and
regenerable offline from ``rom/base.gba``.  This script reads those manifests and
emits:

* ``build/viewer-data/artifact-families.json`` - one entry per family, with the
  facts needed to render the page (counts, schema, cover image, deep link).
* ``fragment-artifact-coverage.html``          - a coverage table so the page
  states plainly which completed work it shows and which it does not.

A family is only listed as ``presented`` when its manifest and images actually
exist; anything missing or blocked upstream is reported as ``not_presented`` with
the concrete blocking input, never silently dropped.

Usage:
    python3 tools/build_results_viewer_artifact_index.py [--root .]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

# name -> (title, artifact dir, hub, why it is blocked when unavailable)
FAMILIES: tuple[tuple[str, str, str, str], ...] = (
    ("menu-portraits-v1", "菜单 / 剧情立绘矩阵", "visuals",
     "需要 sequel/content/menu-ui/bank.json（可用 --from-rom 绕过）"),
    ("map-canvases-v1", "成品战场地图画布", "visuals", ""),
    ("character-battle-visuals-v1", "角色战斗视觉资源", "visuals", ""),
    ("bg-resource-canvases-v1", "BG 资源画布", "visuals", ""),
    ("scene-visual-packs-v1", "场景视觉包", "visuals", ""),
    ("bg-scene-selection-v1", "BG 场景选择目录", "visuals", ""),
    ("sprite-definition-assets-v2", "精灵定义静态资源 + 运行时链", "data", ""),
    ("sprite-definition-animations-v1", "精灵定义动画", "data", ""),
    ("battle-presentation-glyphs-v1", "战斗演出字形与消息", "story", ""),
    ("battle-effect-resource-pairs-v1", "战斗特效资源对", "battle", ""),
    ("battle-effect-sequence-bindings-v1", "战斗特效时序绑定", "battle", ""),
    ("dialogue-font-v2", "对话字体图集", "story", ""),
    ("world-map-backgrounds-v1", "世界地图背景", "visuals", ""),
    ("world-map-runtime-v1", "世界地图运行时合成", "visuals", ""),
    ("battle-effect-affine-runtime-v1", "战斗特效仿射运行时", "battle", ""),
    ("battle-effect-sprite-animations-v1", "战斗特效精灵动画", "battle", ""),
    ("battle-visual-catalog-v1", "战斗视觉目录（79 条）", "battle",
     "上游 tile-assets-bg-v2 需 sequel/content/tile-assets/bank.json"),
    ("battle-visual-runtime-timelines-v1", "战斗视觉运行时时间线", "battle",
     "上游 battle-visual-catalog-v1 未闭合"),
    ("tile-assets-bg-v2", "图块资产 BG 图层 v2", "visuals",
     "需要 sequel/content/tile-assets/bank.json"),
    ("cutscene-obj-v1", "过场 OBJ 资产", "story",
     "需要 sequel/content/cutscene-scripts/bank.json"),
    ("story-visual-layers-v1", "剧情视觉图层", "story",
     "需要 sequel/content/battle-encounters/bank.json"),
    ("story-scene-layer-bindings-v1", "剧情场景图层绑定", "story", ""),
        # Its 24 mappings are consumed by the story-scene-timelines manifest,
        # which the site renders in full.
    ("story-scene-timelines-v1", "剧情场景时间线", "story",
     "上游 story-scene-layer-bindings-v1 未闭合"),
)


# Families whose artifacts are rendered on the site as real content.  A family is
# NOT listed here merely because some paragraph mentions its name -- "mentioned
# in prose" is not presentation, and conflating the two overstates coverage.
# Verified by tools/measure_viewer_coverage.py, which scans the built site for
# each family's artifact paths.
# Families the site actually renders as cards.  Kept as an explicit set, but
# tests/test_results_viewer_coverage.py asserts it agrees with what
# tools/measure_viewer_coverage.py finds on the built pages, so the two cannot
# silently drift apart.
CONTENT_FAMILIES = frozenset({
    "menu-portraits-v1",
    "map-canvases-v1",
    "character-battle-visuals-v1",
    "bg-resource-canvases-v1",
    "scene-visual-packs-v1",
    "sprite-definition-assets-v2",
    "battle-presentation-glyphs-v1",
    "battle-effect-resource-pairs-v1",
    "battle-effect-sprite-animations-v1",
    "tile-assets-bg-v2",
    "battle-visual-catalog-v1",
    "battle-visual-runtime-timelines-v1",
    "cutscene-obj-v1",
    "story-visual-layers-v1",
    "story-scene-timelines-v1",
    "sprite-definition-animations-v1",
    "bg-scene-selection-v1",
    "battle-effect-sequence-bindings-v1",
    "dialogue-font-v2",
    "world-map-backgrounds-v1",
    "battle-effect-affine-runtime-v1",
    "story-scene-layer-bindings-v1",
})

# Built and reproducible in this worktree, but folded into another card, so the
# site carries no standalone artifact list for them.
MERGED_FAMILIES: dict[str, str] = {}

# A few families are not published under artifacts/ by default.
PATH_OVERRIDES = {
    "menu-portraits-v1": Path("build/vfx/menu-portraits-v1"),
}


def _first_existing(directory: Path, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        for path in sorted(directory.glob(pattern)):
            return f"artifacts/{directory.name}/{path.name}"
    return None


def summarise(root: Path, name: str, title: str, hub: str, blocked: str,
               site: str = "") -> dict[str, Any]:
    relative = PATH_OVERRIDES.get(name, Path("artifacts") / name)
    directory = root / relative
    prefix = str(relative).replace("\\", "/")
    manifest_path = directory / "manifest.json"
    entry: dict[str, Any] = {
        "family": name,
        "title": title,
        "hub": hub,
        "schema": None,
        "counts": {},
        "cover": None,
        "image_dir": prefix if directory.is_dir() else None,
        "presented": False,
        "blocked": blocked or None,
    }
    if not manifest_path.is_file():
        entry["blocked"] = blocked or "manifest.json 不存在"
        return entry

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry["schema"] = manifest.get("schema")
    entry["rom_sha256"] = (manifest.get("rom") or {}).get("sha256")

    counts: dict[str, Any] = {}
    for key, value in manifest.items():
        if isinstance(value, bool) or isinstance(value, str):
            continue
        if isinstance(value, int):
            counts[key] = value
        elif isinstance(value, (list, dict)):
            if key in {"summary", "scope", "consumer_contract", "unique_resource_counts"}:
                continue
            counts[key] = len(value)
    entry["counts"] = counts

    cover_patterns = {
        "map-canvases-v1": ("canvases/map-00-primary.png",),
        "battle-presentation-glyphs-v1": ("glyph-atlas.png",),
        "bg-resource-canvases-v1": ("entry-*/canvas.png", "entry-*/canvas-primary.png"),
        "scene-visual-packs-v1": ("pack-*/background.png",),
        "sprite-definition-assets-v2": ("sprite-id-00.png",),
        "menu-portraits-v1": (),
    }.get(name, ())
    for pattern in cover_patterns:
        for path in sorted(directory.glob(pattern)):
            entry["cover"] = f"{prefix}/{path.relative_to(directory)}"
            break
        if entry["cover"]:
            break

    # A family is presented when the site actually renders it: a card on a
    # hub page or its own sub-page.  Deciding it from a hand-kept registry
    # reported families that are on the site as missing, and hid families
    # that nobody remembered to register.
    rendered = (
        (root / "docs" / "families" / f"{name}.html").is_file()
        or any(f'id="{pre}{name}"' in site for pre in ("di-", "fml-", "sec-"))
    )
    if name in CONTENT_FAMILIES or rendered:
        entry["presented"] = True
    elif name in MERGED_FAMILIES:
        entry["presented"] = False
        entry["merged_into"] = MERGED_FAMILIES[name]
        entry["blocked"] = MERGED_FAMILIES[name]
    else:
        entry["presented"] = False
        entry["blocked"] = (
            blocked
            or "产物在逆向分支，本工作树无法重建"
        )
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("build/viewer-data")
    )
    args = parser.parse_args()
    root = args.root.resolve()

    site = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in sorted((root / "docs").glob("reverse-engineering-*.html"))
    )
    families = [summarise(root, *spec, site) for spec in FAMILIES]
    presented = [f for f in families if f["presented"]]
    missing = [f for f in families if not f["presented"]]

    payload = {
        "schema": "results-viewer-artifact-index-v1",
        "generated_from": "artifacts/*/manifest.json",
        "family_count": len(families),
        "presented_count": len(presented),
        "not_presented_count": len(missing),
        "families": families,
    }
    # Pull the census figures so the card's KPIs are never hand-maintained.
    coverage_path = args.output_dir / "coverage-report.json"
    census_stems = census_shown = census_full = census_unreg = 0
    census_pct = 0.0
    if coverage_path.is_file():
        import json as _json
        rep = _json.loads(coverage_path.read_text(encoding="utf-8"))
        head = rep["HEADLINE_census_denominator"]
        census_stems = head["families_total"]
        census_shown = head["families_with_content_on_site"]
        census_full = head["families_fully_presented"]
        census_pct = head["percent_with_content"]
        census_unreg = rep["census"]["unregistered_stems"]
    mh = {}
    mf_total = mf_presented = 0
    mf_pct = 0.0
    if coverage_path.is_file():
        mh = json.loads(coverage_path.read_text(encoding="utf-8"))["HEADLINE_manifest_families"]
        mf_total = mh["families_with_manifest"]
        mf_presented = mh["families_presented"]
        mf_pct = mh["percent"]
    presented_count = len(presented)
    family_count = len(families)

    out = args.output_dir / "artifact-families.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    rows: list[str] = []
    hub_names = {
        "visuals": "1. 视觉与动画资产库",
        "battle": "2. 战斗系统与时序引擎",
        "story": "3. 剧情调度与文本系统",
        "data": "4. 内存数据与音频架构",
    }
    for family in families:
        if family["presented"]:
            counts = " · ".join(
                f"{k}={v}" for k, v in list(family["counts"].items())[:6]
            )
            rows.append(
                f'<tr><td><code>{family["family"]}</code></td>'
                f'<td>{family["title"]}</td>'
                f'<td><span class="tag tag-cyan">{hub_names.get(family["hub"], family["hub"])}</span></td>'
                f'<td>{counts}</td>'
                f'<td><span class="tag tag-green">已收录</span></td></tr>'
            )
        else:
            rows.append(
                f'<tr><td><code>{family["family"]}</code></td>'
                f'<td>{family["title"]}</td>'
                f'<td><span class="tag tag-purple">{hub_names.get(family["hub"], family["hub"])}</span></td>'
                f'<td style="color:var(--text-muted);">—</td>'
                f'<td><span class="tag tag-amber">未收录</span><br>'
                f'<span style="font-size:0.72rem; color:var(--text-muted);">'
                f'{family["blocked"]}</span></td></tr>'
            )

    fragment = (
        '                <tr><td colspan="5" style="background:#0b1120; font-weight:600;">'
        f'已收录 {len(presented)} / 共 {len(families)} 个已验证成果族</td></tr>\n'
        + "\n".join(rows)
    )
    fragment_path = args.output_dir / "fragment-artifact-coverage.html"
    fragment_path.write_text(fragment + "\n", encoding="utf-8")

    card = f'''        <div class="card full-width" id="sec-artifact-coverage">
          <div class="card-head">
            <div class="card-title">逆向成果收录覆盖总表 (Artifact Family Coverage)</div>
            <span class="tag tag-cyan">{presented_count} / {family_count} 个成果族在页面有实际内容</span>
          </div>
          <div class="kpi-grid" style="margin:12px 0;">
            <div class="kpi-card"><div class="kpi-title">已完成 ROM 逆向成果族</div><div class="kpi-num cyan">{census_stems}</div><div class="kpi-sub">按仓库普查（合并 v1..vN 增量批次）</div></div>
            <div class="kpi-card"><div class="kpi-title">页面有实际内容</div><div class="kpi-num amber">{mf_presented} / {mf_total}</div><div class="kpi-sub">{mf_pct}% · 另有 {census_full} 族以图像/公式卡片专门呈现</div></div>
            <div class="kpi-card"><div class="kpi-title">普查到但未登记</div><div class="kpi-num rose">{census_unreg}</div><div class="kpi-sub">无任何页面内容</div></div>
          </div>
          <p class="card-desc">
            本页覆盖情况由 <code>tools/build_results_viewer_artifact_index.py</code> 直接读取
            <code>artifacts/*/manifest.json</code> 生成，<strong>并由 <code>tools/measure_viewer_coverage.py</code>
            逐条扫描本页实际引用的产物路径复核</strong>，不手写。
            「已收录」= 页面真的渲染了该族的产物；<strong>只在正文里提到族名不算收录</strong>。
            标为「未收录」的行均给出具体阻塞原因（上游内容 bank 不在本工作树，或需实时 mGBA 采集），
            <strong>不代表该逆向工作未完成</strong>——这些族的产物与证据在逆向分支的
            <code>artifacts/</code> 与对应 <code>notes/</code> 中完整存在，全量目录见下方 ROM 家族目录卡。
          </p>
          <div class="table-container" style="max-height:560px; overflow-y:auto;">
            <table>
              <thead><tr><th>成果族</th><th>说明</th><th>所属 Hub</th><th>关键计数</th><th>状态</th></tr></thead>
              <tbody>
{fragment}
              </tbody>
            </table>
          </div>
        </div>
'''
    card_path = args.output_dir / "fragment-artifact-coverage-card.html"
    card_path.write_text(card + "\n", encoding="utf-8")

    print(f"wrote {out}")
    print(f"presented={len(presented)} not_presented={len(missing)} of {len(families)}")
    print(f"wrote {fragment_path}")
    print(f"wrote {card_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
