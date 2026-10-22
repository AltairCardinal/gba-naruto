#!/usr/bin/env python3
"""Build the reverse-engineering formula page from artifact manifests.

The viewer showed images, counts and addresses but none of the *equations* the
project actually closed -- affine matrices, pre-OAM coordinate transforms, OAM
attribute layouts, damage/index derivations.  Those live as structured model
objects inside the family manifests, so this walks every manifest and renders
them as nested definition lists with the code range each model was derived from.

Nothing is transcribed by hand: every cell comes from a manifest, so a formula
cannot drift from the evidence it was extracted with.

Usage:
    python3 tools/build_results_viewer_formulas.py [--root .]
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any

# Keys whose values are models/derivations rather than plain data.
MODEL_HINTS = re.compile(
    r"formula|model|predicate|transform|matrix|conversion|derivation"
    r"|progression|schedule|addressing|expression|selection|contract",
    re.I,
)

# Skip bookkeeping subtrees that are data, not derivations.
# NB: no bare ``$`` here -- re.search treats it as "end of string", which
# matches every key and silently empties the whole tree.
SKIP_HINTS = re.compile(
    r"sha256|_file$|_path$|file_offset|gba_address|png_|preview|contact",
    re.I,
)

FAMILY_TITLES = {
    "battle-effect-sprite-animations-v1": "战斗特效精灵动画 · 运行时渲染模型",
    "battle-visual-catalog-v1": "战斗视觉目录 · 索引与合成公式",
    "tile-assets-bg-v2": "图块资产 BG · 图层合成公式",
    "story-scene-layer-bindings-v1": "剧情场景图层绑定 · tile_base 推导",
    "sprite-definition-assets-v2": "精灵定义 · 变换因子",
    "battle-presentation-glyphs-v1": "战斗演出字形 · 消息选择公式",
    "cutscene-obj-v1": "过场 OBJ · 帧数推导",
    "bg-resource-canvases-v1": "BG 资源画布 · 描述符索引公式",
    "character-battle-visuals-v1": "角色战斗视觉 · 描述符行公式",
    "sprite-definition-animations-v1": "精灵定义动画 · 运行时链",
    "battle-effect-sequence-bindings-v1": "战斗特效时序 · 绑定公式",
}

HUB_OF = {
    "battle-effect-sprite-animations-v1": "2. 战斗系统与时序引擎",
    "battle-visual-catalog-v1": "2. 战斗系统与时序引擎",
    "battle-effect-sequence-bindings-v1": "2. 战斗系统与时序引擎",
    "battle-presentation-glyphs-v1": "3. 剧情调度与文本系统",
    "story-scene-layer-bindings-v1": "3. 剧情调度与文本系统",
    "cutscene-obj-v1": "3. 剧情调度与文本系统",
    "tile-assets-bg-v2": "1. 视觉与动画资产库",
    "bg-resource-canvases-v1": "1. 视觉与动画资产库",
    "character-battle-visuals-v1": "1. 视觉与动画资产库",
    "sprite-definition-assets-v2": "4. 内存数据与音频架构",
    "sprite-definition-animations-v1": "4. 内存数据与音频架构",
}

MAX_LEAF_ROWS = 40


def esc(value: Any) -> str:
    return html.escape(str(value), quote=False)


def looks_like_formula(text: str) -> bool:
    """Does this leaf state an equation rather than a plain label?"""
    if not isinstance(text, str):
        return False
    if re.search(r"[=<>]=?|<<|>>|&\s*0x|\*\s*0x|/\s*0x", text):
        return True
    return bool(re.search(r"\b(s16|u8|u16|u32|s32)\b.*[-+*/]", text))


def render_value(value: Any) -> str:
    if isinstance(value, bool):
        return f'<span class="fml-bool">{"true" if value else "false"}</span>'
    if isinstance(value, int):
        return f'<span class="fml-num">{value}</span>'
    text = str(value)
    if looks_like_formula(text):
        return f'<code class="fml-expr">{esc(text)}</code>'
    return f'<span class="fml-text">{esc(text)}</span>'


def render_node(node: Any, key: str | None, depth: int = 0) -> str:
    """Render a manifest subtree as a nested definition list."""
    if isinstance(node, dict):
        rows = []
        for k, v in node.items():
            if isinstance(k, str) and SKIP_HINTS.search(k):
                continue
            rows.append(
                f'<div class="fml-row" style="--d:{depth}">'
                f'<div class="fml-key">{esc(k)}</div>'
                f'<div class="fml-val">{render_node(v, k, depth + 1)}</div>'
                f"</div>"
            )
        return "".join(rows)
    if isinstance(node, list):
        if not node:
            return '<span class="fml-text">—</span>'
        leaves = [render_value(v) for v in node[:MAX_LEAF_ROWS]]
        more = (
            f'<div class="fml-text">… 另有 {len(node) - MAX_LEAF_ROWS} 项</div>'
            if len(node) > MAX_LEAF_ROWS else ""
        )
        return '<div class="fml-list">' + "".join(f"<div>{x}</div>" for x in leaves) + more + "</div>"
    return render_value(node)


# A subtree is itself a model when it carries derivation markers, even if its
# key does not look model-ish: per-record rows nest formulas under entries[].
MODEL_MARKERS = ("formula", "expression", "code_range", "predicate",
                 "derivation", "matrix", "transform", "conversion")


def _is_model(node: Any) -> bool:
    if not isinstance(node, dict):
        return False
    for key in node:
        if isinstance(key, str) and MODEL_MARKERS in key.lower().split("_") \
                or (isinstance(key, str) and any(m in key.lower() for m in MODEL_MARKERS)):
            return True
    return False


def collect_models(manifest: dict) -> list[tuple[str, Any]]:
    """Every derivation subtree in the manifest, at any depth.

    Formulas appear both at the top level (``affine_matrix_model``) and nested
    per record (``entries[i].expression``); scanning only the top level would
    miss most of them.
    """
    out: list[tuple[str, Any]] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            if MODEL_HINTS.search(path.split(".")[-1]) or _is_model(node):
                out.append((path, node))
                return  # do not descend: the whole subtree is one model
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            if node and all(isinstance(v, dict) for v in node) and _is_model(node[0]):
                out.append((f"{path}[]", node))
                return
            for index, value in enumerate(node[:MAX_LEAF_ROWS]):
                walk(value, f"{path}[{index}]")

    for key, value in manifest.items():
        walk(value, str(key))
    return out


def count_leaves(node: Any) -> int:
    if isinstance(node, dict):
        return sum(count_leaves(v) for v in node.values())
    if isinstance(node, list):
        return sum(count_leaves(v) for v in node)
    return 1


def build_family(family: str, manifest: dict) -> tuple[str, int]:
    models = collect_models(manifest)
    if not models:
        return "", 0
    total = sum(count_leaves(m) for _, m in models)
    blocks = []
    for key, value in models:
        if not isinstance(value, dict):
            value = {"entries": value}
        code_range = ""
        if isinstance(value, dict):
            for field in ("code_range", "gba_start", "source_range"):
                if field in value:
                    code_range = f' · 代码区间 {esc(value[field])}'
                    break
        blocks.append(
            f'            <details class="fml-model"{" open" if len(models) <= 2 else ""}>\n'
            f'              <summary><code>{esc(key)}</code>'
            f'<span class="fml-meta">{count_leaves(value)} 个字段{code_range}</span></summary>\n'
            f'              <div class="fml-tree">{render_node(value, key)}</div>\n'
            f"            </details>"
        )
    title = FAMILY_TITLES.get(family, family)
    return (
        f'        <div class="card full-width" id="fml-{family}">\n'
        f'          <div class="card-head">\n'
        f'            <div class="card-title">{esc(title)}</div>\n'
        f'            <span class="tag tag-purple">{esc(HUB_OF.get(family, ""))} · '
        f"artifacts/{esc(family)}</span>\n"
        f"          </div>\n"
        f'          <p class="card-desc">\n'
        f"            下列模型由 <code>artifacts/{esc(family)}/manifest.json</code> 直接导出，"
        f"共 <strong>{total}</strong> 个字段；字段值即 ROM 中签发的表达式原文，未经改写。\n"
        f"          </p>\n"
        + "\n".join(blocks)
        + "\n        </div>\n",
        total,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("build/viewer-data")
    )
    args = parser.parse_args()
    root = args.root.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    cards: list[str] = []
    stats: list[dict] = []
    for manifest_path in sorted((root / "artifacts").glob("*/manifest.json")):
        family = manifest_path.parent.name
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        card, total = build_family(family, manifest)
        if not card:
            continue
        cards.append(card)
        stats.append({"family": family, "fields": total, "models": len(collect_models(manifest))})

    page = (
        '        <div class="card full-width" id="sec-formula-index">\n'
        '          <div class="card-head">\n'
        '            <div class="card-title">逆向公式与运行时模型总览 (Reverse Engineering Formulas)</div>\n'
        f'            <span class="tag tag-cyan">{len(cards)} 个成果族 · '
        f'{sum(s["fields"] for s in stats)} 个公式字段</span>\n'
        "          </div>\n"
        '          <p class="card-desc">\n'
        "            这些公式是逆向的<strong>结论本身</strong>，此前只以文字形式散落在 notes 与 manifest 中，"
        "网页未作展示。全部内容由 <code>tools/build_results_viewer_formulas.py</code> 从各成果族的\n"
        "            <code>manifest.json</code> 直接生成，字段值即 ROM 签发的表达式原文，不做人工改写。\n"
        "          </p>\n"
        '          <div class="table-container">\n'
        "            <table>\n"
        "              <thead><tr><th>成果族</th><th>所属 Hub</th><th>模型数</th><th>公式字段数</th><th></th></tr></thead>\n"
        "              <tbody>\n"
        + "\n".join(
            f'                <tr><td><code>{s["family"]}</code></td>'
            f'<td><span class="tag tag-cyan">{HUB_OF.get(s["family"], "—")}</span></td>'
            f'<td><code>{s["models"]}</code></td><td><code>{s["fields"]}</code></td>'
            f'<td><a class="tag tag-cyan" style="text-decoration:none;" '
            f'href="reverse-engineering-formulas.html#fml-{s["family"]}">查看 →</a></td></tr>'
            for s in stats
        )
        + "\n              </tbody>\n            </table>\n          </div>\n        </div>\n"
    )

    (args.output_dir / "fragment-formula-page.html").write_text(
        "\n".join(cards) + "\n", encoding="utf-8"
    )
    (args.output_dir / "fragment-formula-index.html").write_text(
        page, encoding="utf-8"
    )
    payload = {
        "schema": "viewer-formula-index-v1",
        "family_count": len(cards),
        "field_count": sum(s["fields"] for s in stats),
        "families": stats,
    }
    (args.output_dir / "formula-index.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"families={len(cards)} fields={payload['field_count']}")
    for s in stats:
        print(f"  {s['family']:44s} models={s['models']:2d} fields={s['fields']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
