#!/usr/bin/env python3
"""Emit the corrected map/tileset HTML fragments for the results viewer.

Reads ``build/viewer-data/map-rows.json`` (built by
``tools/build_results_viewer_assets.py``) and writes the two markup blocks the
viewer needs, so both stay regenerable from ROM-derived data instead of being
hand-typed addresses.

Outputs (default ``build/viewer-data/``):

* ``fragment-tileset-gallery.html`` - one card per map with a resolvable image
  path, corrected grid dimensions and correctly labelled pointer columns.
* ``fragment-scenario-table.html``  - the full 47-row map header table.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

COLUMNS = ("#", "场景", "瓦片图形 (LZ77 4bpp)", "背景调色板块",
           "布局 A", "布局 B", "元块属性", "网格 (宽×高)", "地图格数", "图集瓦片数")


def load_rows(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["rows"]


def badge(value: str | None) -> str:
    if value is None:
        return '<span style="color:var(--text-muted);">—</span>'
    return f'<code class="addr-badge" onclick="copyAddr(\'{value}\')">{value}</code>'


def tileset_gallery(rows: list[dict]) -> str:
    parts: list[str] = []
    tags = ("tag-cyan", "tag-green", "tag-amber", "tag-purple", "tag-rose")
    for index, row in enumerate(rows):
        png = row["tileset_png"]
        png_path = png.replace("build/", "../build/") if png else ""
        palette_note = "彩色渲染" if row["tileset_palette_source"] else "原始索引"
        parts.append(
            f"""            <div class="tileset-item">
              <div class="tileset-header"><strong>Map {row['map_id']:02d}</strong> <span class="tag {tags[index % len(tags)]}">{row['tileset_tile_count']} 瓦片</span></div>
              <div class="tileset-img-wrap"><img src="{png_path}" alt="Map {row['map_id']} tileset" loading="lazy"></div>
              <div class="tileset-meta">网格 {row['width_tiles']}×{row['height_tiles']} | 地图 {row['cell_count']} 格 | 图集 {row['tileset_tile_count']} 瓦片 | 调色板 {row['bg_palette_offset_hex']} ({palette_note})</div>
            </div>"""
        )
    return "\n".join(parts)


def scenario_table(rows: list[dict]) -> str:
    parts: list[str] = []
    for row in rows:
        parts.append(
            f"""                <tr><td><code>{row['map_id']}</code></td><td>Map {row['map_id']:02d} 战场配置</td><td>{badge(row['tile_gfx_offset_hex'])}</td><td>{badge(row['bg_palette_offset_hex'])}</td><td>{badge(row['layout_a_offset_hex'])}</td><td>{badge(row['layout_b_offset_hex'])}</td><td>{badge(row['metatile_attr_offset_hex'])}</td><td>{row['width_tiles']} × {row['height_tiles']}</td><td>{row['cell_count']}</td><td>{row['tileset_tile_count']}</td></tr>"""
        )
    return "\n".join(parts)


def portrait_matrix(manifest_path: Path) -> str:
    """One row per matrix record, one cell per (gfx, palette) variant."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records: dict[int, dict[int, dict]] = {}
    special: dict[int, dict] = {}
    for portrait in manifest["portraits"]:
        if portrait["kind"] == "matrix":
            records.setdefault(portrait["portrait_id"], {})[portrait["variant"]] = portrait
        else:
            special[portrait["variant"]] = portrait

    def cell(portrait: dict | None, caption: str, alt: str | None = None) -> str:
        if portrait is None:
            return '<td class="portrait-cell-empty">—</td>'
        reuse = portrait.get("reuse_count", 1)
        badge = (
            f' <span class="tag tag-amber">×{reuse}</span>' if reuse > 1 else ""
        )
        label = alt or (
            f"record {portrait.get('portrait_id')} variant {portrait['variant']}"
        )
        return (
            f'<td><div class="portrait-cell">'
            f'<img src="../build/vfx/menu-portraits-v1/{portrait["png"]}" '
            f'alt="{label}" '
            f'loading="lazy" style="image-rendering:pixelated;width:80px;height:80px;">'
            f'<div class="portrait-cell-cap">{caption}{badge}</div>'
            f'<div class="portrait-cell-addr"><code class="addr-badge" '
            f"onclick=\"copyAddr('{portrait['gfx_pointer']}')\">"
            f"{portrait['gfx_pointer']}</code></div></div></td>"
        )

    rows: list[str] = []
    for record_id in sorted(records):
        variants = records[record_id]
        first = variants[0]
        cells = "".join(cell(variants.get(v), f"变体 {v}") for v in range(5))
        rows.append(
            f'<tr><td><code>记录 {record_id:02d}</code></td>'
            f'<td><code class="addr-badge" '
            f"onclick=\"copyAddr('{first['pair_gba_address']}')\">"
            f"{first['pair_gba_address']}</code></td>{cells}</tr>"
        )

    global_variant = special[5]
    empty = '<td class="portrait-cell-empty">—</td>' * 4
    rows.append(
        f'<tr><td><code>全局</code></td>'
        f'<td><code class="addr-badge" '
        f"onclick=\"copyAddr('{global_variant['pair_gba_address']}')\">"
        f"{global_variant['pair_gba_address']}</code></td>{empty}"
        + cell(global_variant, "全局 variant 5", alt="global variant 5")
        + "</tr>"
    )
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rows",
        type=Path,
        default=Path("build/viewer-data/map-rows.json"),
    )
    parser.add_argument(
        "--portrait-manifest",
        type=Path,
        default=Path("build/vfx/menu-portraits-v1/manifest.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("build/viewer-data"),
    )
    args = parser.parse_args()

    rows = load_rows(args.rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    gallery_path = args.output_dir / "fragment-tileset-gallery.html"
    gallery_path.write_text(tileset_gallery(rows) + "\n", encoding="utf-8")

    table_path = args.output_dir / "fragment-scenario-table.html"
    table_path.write_text(scenario_table(rows) + "\n", encoding="utf-8")

    if args.portrait_manifest.exists():
        matrix_path = args.output_dir / "fragment-portrait-matrix.html"
        matrix_path.write_text(
            portrait_matrix(args.portrait_manifest) + "\n", encoding="utf-8"
        )
        print(f"wrote {matrix_path}")

    print(f"wrote {gallery_path} ({len(rows)} tileset cards)")
    print(f"wrote {table_path} ({len(rows)} scenario rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
