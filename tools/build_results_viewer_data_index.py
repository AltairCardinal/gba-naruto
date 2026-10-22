#!/usr/bin/env python3
"""Index the ROM artifact families that ship structured data rather than images.

120 of the reverse branch's ``rom-*`` families are control-flow graphs, decoder
contracts and bounded inventories -- almost none carry PNGs, so the visual
card builder skips them entirely.  Their *content* is still completed reverse
engineering (proven roots, closed denominators, dispatch summaries, scope and
limits), so this renders each manifest's summary as a browsable card.

Everything shown is read from the family manifest: schema, declared status,
scalar counters, and the scope/limits blocks that say what the family does
*not* claim.  No interpretation is added.

Usage:
    python3 tools/build_results_viewer_data_index.py [--root .]
"""
from __future__ import annotations

import argparse
import glob
import html
import json
from pathlib import Path
from typing import Any

# Blocks whose keys are worth surfacing first, in this order.
PRIORITY = ("scope", "limits", "implementation", "combined_summary",
            "static_dispatch_summary", "decoder", "summary")
MAX_LIST = 24


def esc(value: Any) -> str:
    return html.escape(str(value), quote=False)


def render_value(value: Any) -> str:
    if isinstance(value, bool):
        return '<span class="fml-bool">true</span>' if value else '<span class="fml-bool">false</span>'
    if isinstance(value, (int, float)):
        return f'<span class="fml-num">{value:,}</span>' if isinstance(value, int) and abs(value) > 9999 else f'<span class="fml-num">{value}</span>'
    text = str(value)
    if len(text) > 220:
        text = text[:220] + "…"
    return f'<span class="fml-text">{esc(text)}</span>'


def flatten(prefix: str, node: Any, out: list[tuple[str, Any]], depth: int = 0) -> None:
    if depth > 2:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, (dict, list)):
                flatten(name, value, out, depth + 1)
            else:
                out.append((name, value))
    elif isinstance(node, list):
        if node and all(not isinstance(v, (dict, list)) for v in node):
            out.append((prefix, ", ".join(str(v)[:40] for v in node[:12])))
        else:
            for index, value in enumerate(node[:MAX_LIST]):
                flatten(f"{prefix}[{index}]", value, out, depth + 1)


def build_card(family: str, manifest_path: Path) -> tuple[str, dict] | None:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    schema = (manifest.get("schema") or manifest.get("artifact_schema")
              or family)
    status = manifest.get("artifact_status")

    scalars: list[tuple[str, Any]] = []
    for key, value in manifest.items():
        if isinstance(value, (int, float, bool)):
            scalars.append((key, value))
        elif isinstance(value, str) and key in (
            "schema", "artifact_schema", "artifact_status", "rom_sha256",
        ):
            scalars.append((key, value))

    blocks: list[tuple[str, list[tuple[str, Any]]]] = []
    for name in PRIORITY:
        node = manifest.get(name)
        if isinstance(node, dict):
            rows: list[tuple[str, Any]] = []
            flatten("", node, rows)
            if rows:
                blocks.append((name, rows[:40]))

    pngs = sorted(manifest_path.parent.rglob("*.png"))

    head = (
        f'        <div class="card full-width" id="di-{family}">\n'
        f'          <div class="card-head">\n'
        f'            <div class="card-title">{esc(family)}</div>\n'
        f'            <span class="tag tag-purple">{esc(schema)}'
        + (f' · {esc(status)}' if status else "")
        + f'</span>\n'
        f"          </div>\n"
    )
    if pngs:
        imgs = "".join(
            f'            <div class="tileset-item tile-item-compact">'
            f'<div class="tileset-img-wrap"><img class="tile-zoom-sm" '
            f'src="../artifacts/{family}/{p.relative_to(manifest_path.parent).as_posix()}" '
            f'alt="{esc(p.stem)}" loading="lazy"></div></div>\n'
            for p in pngs[:8]
        )
        head += ('          <div class="tileset-gallery">\n' + imgs
                 + "          </div>\n")

    body = []
    if scalars:
        body.append(
            '<div class="di-row"><div class="di-key">标量计数</div><div class="di-val">'
            + "".join(
                f'<span class="fml-text">{esc(k)} = </span>{render_value(v)}  '
                for k, v in scalars[:12]
            )
            + "</div></div>"
        )
    for name, rows in blocks:
        body.append(
            f'<details class="fml-model"><summary><code>{esc(name)}</code>'
            f'<span class="fml-meta">{len(rows)} 项</span></summary>'
            '<div class="fml-tree">'
            + "".join(
                f'<div class="fml-row"><div class="fml-key">{esc(k)}</div>'
                f'<div class="fml-val">{render_value(v)}</div></div>'
                for k, v in rows
            )
            + "</div></details>"
        )

    return head + "".join(body) + "\n        </div>\n", {
        "family": family,
        "schema": schema,
        "status": status,
        "png_count": len(pngs),
        "scalar_count": len(scalars),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("build/viewer-data")
    )
    parser.add_argument("--max-families", type=int, default=400)
    args = parser.parse_args()
    root = args.root.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Every family that ships a manifest.  The visual card builders cover the
    # image-bearing families; this index is for everything else, so it must not
    # be limited to the rom-* prefix.
    paths = sorted(glob.glob(str(root / "artifacts/*/manifest.json")))
    cards: list[str] = []
    stats: list[dict] = []
    for path in paths[: args.max_families]:
        built = build_card(Path(path).parent.name, Path(path))
        if built is None:
            continue
        markup, stat = built
        cards.append(markup)
        stats.append(stat)

    rows = []
    for s in stats:
        link = f'<a class="tag tag-cyan" style="text-decoration:none;" href="families/{s["family"]}.html">{esc(s["family"])}</a>'
        status = ('<span class="tag tag-green">' + esc(s["status"]) + "</span>"
                  if s["status"] else "—")
        rows.append(
            "                <tr><td>" + link + "</td>"
            "<td><code>" + esc(s["schema"]) + "</code></td>"
            "<td>" + status + "</td>"
            "<td><code>" + str(s["scalar_count"]) + "</code></td>"
            "<td><code>" + str(s["png_count"]) + "</code></td></tr>"
        )
    index_rows = "\n".join(rows)

    index = (
        '        <div class="card full-width" id="sec-data-index">\n'
        '          <div class="card-head">\n'
        '            <div class="card-title">ROM 数据产物索引 (ROM Data Artifacts)</div>\n'
        f'            <span class="tag tag-purple">{len(stats)} 个成果族 · '
        f'{sum(1 for s in stats if s["png_count"])} 个含图像</span>\n'
        "          </div>\n"
        '          <p class="card-desc">\n'
        "            这些成果族以<strong>结构化数据</strong>形式闭合（控制流图、解码器契约、\n"
        "            有界清单、已证明根集合），几乎不含 PNG，因此图像卡片无法覆盖它们。\n"
        "            下表列出每个族的 schema、声明状态与关键计数，点击可展开其 scope/limits/汇总字段——\n"
        "            <strong>其中明确写出该族「不宣称什么」</strong>。\n"
        "          </p>\n"
        '          <div class="table-container" style="max-height:520px; overflow-y:auto;">\n'
        "            <table>\n"
        "              <thead><tr><th>成果族</th><th>schema</th><th>声明状态</th>"
        "<th>标量计数</th><th>图像数</th></tr></thead>\n"
        "              <tbody>\n"
        f"{index_rows}\n"
        "              </tbody>\n            </table>\n          </div>\n"
        "        </div>\n"
    )

    (args.output_dir / "fragment-data-index.html").write_text(index, encoding="utf-8")
    (args.output_dir / "fragment-data-index-page.html").write_text(
        "\n".join(cards) + "\n", encoding="utf-8"
    )
    (args.output_dir / "data-index.json").write_text(
        json.dumps({"schema": "viewer-data-index-v1",
                    "family_count": len(stats), "families": stats},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"families={len(stats)} with_png={sum(1 for s in stats if s['png_count'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
