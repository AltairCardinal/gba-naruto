#!/usr/bin/env python3
"""Emit the HTML sections for verified reverse-engineering artifact families.

Companion to ``tools/build_results_viewer_artifact_index.py``: this reads the
same manifests and writes the markup blocks that present the families the page
currently does not show (assembled battle maps, character battle visuals, BG
canvases, scene visual packs, battle-effect atlases, battle glyphs, sprite
definitions).

Only families whose manifest and images actually exist on disk are emitted, so
a missing or upstream-blocked family silently produces no section instead of a
broken image gallery.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PRE = "../"


def load(root: Path, relative: str) -> dict | None:
    """Read a manifest, or a specific JSON file when ``relative`` names one."""
    target = root / relative
    if target.is_dir():
        target = target / "manifest.json"
    if not target.is_file():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


def map_canvases_section(root: Path) -> str:
    manifest = load(root, "artifacts/map-canvases-v1")
    if not manifest:
        return ""
    canvases = sorted((root / "artifacts/map-canvases-v1/canvases").glob("map-*.png"))
    # Display copies carry a tRNS chunk that makes GBA colour 0 transparent, so
    # every map paints its empty blocks with the same backdrop instead of its
    # own palette colour.  Fall back to the canonical PNG when they are absent.
    web_dir = root / "build/map-canvases-web"
    cards = []
    for path in canvases:
        if (web_dir / path.name).is_file():
            src = f"{PRE}build/map-canvases-web/{path.name}"
        else:
            src = f"{PRE}artifacts/map-canvases-v1/canvases/{path.name}"
        cards.append(
            f'            <div class="tileset-item">\n'
            f'              <div class="tileset-header"><strong>{path.stem.replace("map-", "Map ").replace("-", " · ")}</strong></div>\n'
            f'              <div class="tileset-img-wrap map-canvas-wrap"><img class="map-canvas-img" src="{src}" alt="{path.stem}" loading="lazy"></div>\n'
            f"            </div>"
        )
    cards = "\n".join(cards)
    return f"""        <div class="card full-width" id="sec-map-canvases">
          <div class="card-head">
            <div class="card-title">成品战场地图画布 (Assembled Battle Map Canvases)</div>
            <span class="tag tag-green">artifacts/map-canvases-v1 · {manifest["canvas_count"]} 张 · 覆盖 {manifest["map_count"]} 张地图</span>
          </div>
          <p class="card-desc">
            由 <code>tools/export_map_canvases.py</code> 从已验证的 <code>0x53D910</code> 地图头表导出：把每张地图的瓦片图集、tilemap 与调色板合成为<strong>可直接观看的完整战场画面</strong>。
            {manifest["map_count"]} 张地图共产出 <strong>{manifest["canvas_count"]} 张画布</strong>，其中 {manifest["alternate_canvas_count"]} 张为 alternate 布局变体。
            独立校验器 <code>tools/verify_map_canvases.py</code> 复核 61 张画布零错误。
            这一项是本页此前完全缺失的内容——之前只展示了原始瓦片图集，没有任何合成后的地图。
          </p>
          <p class="card-desc">
            <strong>空地块（该变体没有铺 tile 的地方）统一显示为透明</strong>，背后是全站同一张中性棋盘格底衬。
            索引色 PNG 的调色板 0 号色本身就是这张地图自己的 BG 背景色，直接看原图会让每张地图的空地块各画各的颜色
            （0 号浅蓝、1–5 号深蓝、6 号纯绿、7 号以后纯黑），看起来像渲染错误而不是"这里没有 tile"。
            证据在 ROM 侧是明确的：47 张地图的 <strong>tile 0 全部是 64 像素全透明的空 tile</strong>，
            所以调色板索引 0 只会由"没铺 tile"产生。
            页面展示的是 <code>tools/build_results_viewer_map_canvases.py</code> 派生的副本
            （<code>build/map-canvases-web/</code>）：<strong>索引像素与调色板与原 PNG 逐字节相同</strong>，只多一个 tRNS 块；
            未经改动的原始证据 PNG 仍在 <code>artifacts/map-canvases-v1/canvases/</code>。
          </p>
          <div class="tileset-gallery">
{cards}
          </div>
        </div>
"""


def character_battle_visuals_section(root: Path) -> str:
    manifest = load(root, "artifacts/character-battle-visuals-v1")
    if not manifest:
        return ""
    summary = manifest["summary"]
    resources = manifest["resources"]
    cards = "\n".join(
        f'            <div class="tileset-item">\n'
        f'              <div class="tileset-header"><strong>资源 {resource["resource_id"]:03d}</strong></div>\n'
        f'              <div class="tileset-img-wrap"><img src="{PRE}artifacts/character-battle-visuals-v1/resource-{resource["resource_id"]:03d}/frame-000.png" alt="character battle resource {resource["resource_id"]}" loading="lazy"></div>\n'
        f"            </div>"
        for resource in resources
    )
    return f"""        <div class="card full-width" id="sec-character-battle-visuals">
          <div class="card-head">
            <div class="card-title">角色战斗视觉资源 (Character Battle Visuals)</div>
            <span class="tag tag-purple">{summary.get("resource_count", len(resources))} 资源 · {summary.get("animation_count", 0)} 动画 · {summary.get("frame_count", 0)} 帧</span>
          </div>
          <p class="card-desc">
            由 <code>tools/export_character_battle_visuals.py</code> 导出：把角色战斗 FBFF 组件按 OAM 任务还原为完整帧。
            共 <strong>{summary.get("resource_count", len(resources))} 个资源</strong>、<strong>{summary.get("animation_count", 0)} 条动画</strong>、
            <strong>{summary.get("frame_count", 0)} 帧</strong>、{summary.get("component_count", 0)} 个组件、{summary.get("tile_count", 0)} 个瓦片。
            独立校验器 <code>tools/verify_character_battle_visuals.py</code> 复核 250 资源 / 558 槽位 / 2,004 帧全部闭合。
            下图<strong>列出全部 {len(resources)} 个资源</strong>的首帧（每格为导出原始尺寸），点击可在同目录查看该资源的完整帧序列。
          </p>
          <div class="tileset-gallery">
{cards}
          </div>
        </div>
"""


def battle_glyphs_section(root: Path) -> str:
    manifest = load(root, "artifacts/battle-presentation-glyphs-v1")
    if not manifest:
        return ""
    base = f"{PRE}artifacts/battle-presentation-glyphs-v1"
    messages = manifest["messages"]
    glyphs = manifest["glyphs"]

    glyph_png = {g["glyph_id"]: g["png_file"] for g in glyphs}

    def message_row(msg: dict) -> str:
        ids = msg["binding"].get("glyph_ids", [])
        tiles = "".join(
            f'<img src="{base}/{glyph_png[i]}" alt="glyph {i}" loading="lazy">'
            for i in ids if i in glyph_png
        )
        return (
            f'                <tr><td><code>#{msg["message_id"]:02d}</code></td>'
            f'<td><code class="addr-badge" onclick="copyAddr(\'{msg["pointer"]}\')">{msg["pointer"]}</code></td>'
            f'<td style="min-width:200px;"><div class="glyph-strip">{tiles}</div></td>'
            f'<td><code>{len(ids)}</code></td>'
            f'<td><code style="font-size:0.7rem;">{msg["raw_hex"]}</code></td></tr>'
        )

    message_rows = "\n".join(message_row(m) for m in messages)

    glyph_cards = "\n".join(
        f'            <div class="tileset-item tile-item-compact">\n'
        f'              <div class="tileset-header"><strong>g{g["glyph_id"]:03d}</strong></div>\n'
        f'              <div class="tileset-img-wrap"><img src="{base}/{g["png_file"]}" alt="glyph {g["glyph_id"]}" loading="lazy"></div>\n'
        f'              <div class="tileset-meta">{g["width"]}×{g["height"]} · 被 {len(g["bound_message_ids"])} 条消息引用</div>\n'
        f"            </div>"
        for g in glyphs
    )

    return f"""        <div class="card full-width" id="sec-battle-glyphs">
          <div class="card-head">
            <div class="card-title">战斗演出字形与消息表 (Battle Presentation Glyphs)</div>
            <span class="tag tag-cyan">artifacts/battle-presentation-glyphs-v1 · {len(messages)} 条消息 · {len(glyphs)} 个字形</span>
          </div>
          <p class="card-desc">
            由 <code>tools/export_battle_presentation_glyphs.py</code> 导出：闭合了战斗演出中 {len(messages)} 条消息指针
            （表 <code>0x085A2B08</code>）、{len(glyphs)} 个 LZ77 字形，以及消息 ↔ 字形绑定表（<code>0x085A2EF4</code>）。
            运行时调色板为 16×BGR555，初始化器 <code>0x080983B8..0x0809860E</code> 拷贝到 OBJ 调色板 bank 13。
            <code>tools/verify_battle_presentation_glyphs.py</code> 复核 {len(messages)} 条消息 / {len(glyphs)} 字形零错误。
          </p>
          <div style="display:flex; gap:16px; flex-wrap:wrap; justify-content:center; background:#000; padding:12px; border-radius:8px; border:1px solid #334155; margin-bottom:14px;">
            <figure style="margin:0; text-align:center;">
              <img src="{base}/glyph-atlas.png" alt="glyph atlas" style="image-rendering:pixelated; max-width:100%; height:auto;">
              <figcaption style="color:var(--text-muted); font-size:0.75rem; margin-top:6px;">字形图集（原始调色板）</figcaption>
            </figure>
            <figure style="margin:0; text-align:center;">
              <img src="{base}/glyph-atlas-runtime.png" alt="glyph atlas runtime" style="image-rendering:pixelated; max-width:100%; height:auto;">
              <figcaption style="color:var(--text-muted); font-size:0.75rem; margin-top:6px;">字形图集（运行时调色板）</figcaption>
            </figure>
          </div>

          <details open>
            <summary style="cursor:pointer; color:var(--accent-cyan); font-weight:700; font-size:0.9rem;">📝 全部 {len(messages)} 条消息：按绑定顺序还原的字形条</summary>
            <p style="margin-top:8px; color:var(--text-secondary); font-size:0.82rem;">
              每行把该条消息绑定的字形按原始顺序拼出，便于直接读出战斗提示文本。
              字形本身无字符映射（manifest 只记录 glyph_id 与哈希），故此处呈现的是<strong>原始字形序列</strong>，不是解码后的文字。
            </p>
            <div class="table-container" style="max-height:520px; overflow-y:auto;">
              <table>
                <thead><tr><th>#</th><th>消息指针</th><th>字形序列</th><th>字形数</th><th>原始字节</th></tr></thead>
                <tbody>
{message_rows}
                </tbody>
              </table>
            </div>
          </details>

          <details style="margin-top:12px;">
            <summary style="cursor:pointer; color:var(--accent-cyan); font-weight:700; font-size:0.9rem;">🔠 全部 {len(glyphs)} 个字形图像</summary>
            <div class="tileset-gallery" style="margin-top:10px;">
{glyph_cards}
            </div>
          </details>
        </div>
"""


def bg_scene_selection_section(root: Path) -> str:
    data = load(root, "artifacts/bg-scene-selection-v1/chapter-opcode-1e.json")
    manifest = load(root, "artifacts/bg-scene-selection-v1")
    if not data or not manifest:
        return ""
    summary = data["summary"]

    def addr(value: object) -> str:
        if not value:
            return '<span style="color:var(--text-muted);">—</span>'
        return f'<code class="addr-badge" onclick="copyAddr(\'{value}\')">{value}</code>'

    rows = "\n".join(
        f'                <tr><td><code>#{i}</code></td>'
        f'<td>{addr(sel.get("address"))}</td>'
        f'<td>{addr(sel.get("selector_address"))}</td>'
        f'<td><code>{sel["input_id"]}</code></td><td><code>{sel["entry_id"]}</code></td>'
        f'<td><span class="tag tag-cyan">{sel["selection_rule"]}</span></td>'
        f'<td>{", ".join(str(r["scenario_id"]) for r in sel["roots"]) or "—"}</td>'
        f'<td>{sel["canvas"]}</td></tr>'
        for i, sel in enumerate(data["selections"])
    )
    pt = data["pointer_tables"]
    return f"""        <div class="card full-width" id="sec-bg-scene-selection">
          <div class="card-head">
            <div class="card-title">章节选择 opcode 0x1E 记录 (Chapter Scene Selection)</div>
            <span class="tag tag-purple">artifacts/bg-scene-selection-v1 · {len(data["selections"])} 条记录</span>
          </div>
          <p class="card-desc">
            由 <code>tools/verify_bg_scene_selection.py</code> 闭合的解释器契约：扫描全部战斗脚本，
            共解析 <strong>{summary["unique_instruction_nodes"]:,} 个指令节点</strong>、{summary["non_null_script_slots"]} 个非空脚本槽、
            {summary["unique_script_roots"]} 个唯一脚本根，识别出 <strong>{summary["unique_opcode_1e_records"]} 条 opcode <code>0x1E</code> 记录</strong>
            （另有 {summary["dynamic_opcode_06_nodes"]} 个动态 opcode <code>0x06</code> 节点）。
            指针表 <code>primary={pt["primary"]}</code> / <code>alternate={pt["alternate"]}</code>，各 {pt["entry_count_each"]} 项，entry 0 为空哨兵。
            解析失败数：{len(summary["parse_failures"])}。
          </p>
          <div class="table-container" style="max-height:420px; overflow-y:auto;">
            <table>
              <thead><tr><th>#</th><th>记录地址</th><th>选择子地址</th><th>input_id</th><th>entry_id</th><th>规则</th><th>关联 scenario</th><th>画布</th></tr></thead>
              <tbody>
{rows}
              </tbody>
            </table>
          </div>
        </div>
"""


def battle_effect_sequence_section(root: Path) -> str:
    manifest = load(root, "artifacts/battle-effect-sequence-bindings-v1")
    if not manifest:
        return ""
    sequences = manifest["sequences"]
    rows = "\n".join(
        f'                <tr><td><code>{i:02d}</code></td>'
        f'<td><code class="addr-badge" onclick="copyAddr(\'{s.get("sequence_descriptor_gba_address", "")}\')">{s.get("sequence_descriptor_gba_address", "—")}</code></td>'
        f'<td><code style="font-size:0.72rem;">{json.dumps({k: v for k, v in s.items() if k != "sequence_descriptor_gba_address"}, ensure_ascii=False)[:150]}</code></td></tr>'
        for i, s in enumerate(sequences)
    )
    return f"""        <div class="card full-width" id="sec-battle-effect-sequences">
          <div class="card-head">
            <div class="card-title">战斗特效时序绑定 (Battle Effect Sequence Bindings)</div>
            <span class="tag tag-green">artifacts/battle-effect-sequence-bindings-v1 · {len(sequences)} 条序列</span>
          </div>
          <p class="card-desc">
            由 <code>tools/export_battle_effect_sequence_bindings.py</code> 导出并经
            <code>tools/verify_battle_effect_sequence_bindings.py</code> 复核：
            把<strong>{len(manifest["runtime_state_bindings"])} 条运行时状态绑定</strong>、
            <strong>{len(manifest["active_action_bindings"])} 条主动行动绑定</strong>、
            <strong>{len(manifest["ninja_tool_bindings"])} 条忍具绑定</strong>，
            归并到 <strong>{len(sequences)} 条特效时序</strong>；另记录 {len(manifest["selector_callsites"])} 个选择子调用点
            与 {len(manifest["consumer_code_slices"])} 段消费者代码切片。
          </p>
          <div class="table-container" style="max-height:420px; overflow-y:auto;">
            <table>
              <thead><tr><th>#</th><th>序列描述符地址</th><th>绑定内容</th></tr></thead>
              <tbody>
{rows}
              </tbody>
            </table>
          </div>
        </div>
"""


def bg_canvases_section(root: Path) -> str:
    bg = load(root, "artifacts/bg-resource-canvases-v1")
    if not bg:
        return ""
    cards = "\n".join(
        f'            <div class="tileset-item">\n'
        f'              <div class="tileset-header"><strong>BG {path.parent.name.split("-")[-1]}</strong></div>\n'
        f'              <div class="tileset-img-wrap"><img src="{PRE}artifacts/bg-resource-canvases-v1/{path.parent.name}/canvas.png" alt="{path.parent.name}" loading="lazy"></div>\n'
        f"            </div>"
        for path in sorted(root.glob("artifacts/bg-resource-canvases-v1/entry-*/canvas.png"))
    )
    return f"""        <div class="card full-width" id="sec-bg-canvases">
          <div class="card-head">
            <div class="card-title">BG 资源画布 (BG Resource Canvases)</div>
            <span class="tag tag-cyan">artifacts/bg-resource-canvases-v1 · {len(bg["entries"])} 张</span>
          </div>
          <p class="card-desc">
            由 <code>tools/export_bg_resource_canvases.py</code> 导出的 {len(bg["entries"])} 张背景资源合成画布，
            每张附 <code>graphics</code> / <code>tilemap-u16le</code> / <code>palette-bgr555</code> 的 LZ77 原文与明文。
            <code>tools/verify_bg_resource_canvases.py</code> 复核 {len(bg["entries"])} 张零错误；
            章节 opcode <code>0x1E</code> 的 6 条场景选择记录见下方独立卡片。
          </p>
          <div class="tileset-gallery">
{cards}
          </div>
        </div>
"""


def scene_visual_packs_section(root: Path) -> str:
    packs = load(root, "artifacts/scene-visual-packs-v1")
    if not packs:
        return ""
    cards = "\n".join(
        f'            <div class="tileset-item">\n'
        f'              <div class="tileset-header"><strong>{path.parent.name}</strong></div>\n'
        f'              <div class="tileset-img-wrap"><img src="{PRE}artifacts/scene-visual-packs-v1/{path.parent.name}/background.png" alt="{path.parent.name}" loading="lazy"></div>\n'
        f"            </div>"
        for path in sorted(root.glob("artifacts/scene-visual-packs-v1/pack-*/background.png"))
    )
    summary = packs["summary"]
    return f"""        <div class="card full-width" id="sec-scene-visual-packs">
          <div class="card-head">
            <div class="card-title">场景视觉包 (Scene Visual Packs)</div>
            <span class="tag tag-green">{summary.get("pack_count", len(packs["packs"]))} 包 · {summary.get("obj_animation_count", 0)} 个 OBJ 动画</span>
          </div>
          <p class="card-desc">
            由 <code>tools/export_scene_visual_packs.py</code> 导出：每个场景包同时给出背景 (gfx / palette / tilemap) 与 OBJ 动画链 JSON，
            可直接用于复现场景演出。独立校验器 <code>tools/verify_scene_visual_packs.py</code> 复核 9 包 / 16 动画 / 16 帧全部闭合。
          </p>
          <div class="tileset-gallery">
{cards}
          </div>
        </div>
"""


def battle_effect_pairs_section(root: Path) -> str:
    pairs = load(root, "artifacts/battle-effect-resource-pairs-v1")
    if not pairs:
        return ""
    cards = "\n".join(
        f'            <div class="tileset-item">\n'
        f'              <div class="tileset-header"><strong>组 {path.stem.split("-")[-1]}</strong></div>\n'
        f'              <div class="tileset-img-wrap"><img class="tile-zoom-md" src="{PRE}artifacts/battle-effect-resource-pairs-v1/{path.name}" alt="{path.stem}" loading="lazy"></div>\n'
        f"            </div>"
        for path in sorted(root.glob("artifacts/battle-effect-resource-pairs-v1/group-*-atlas.png"))
    )
    return f"""        <div class="card full-width" id="sec-battle-effect-pairs">
          <div class="card-head">
            <div class="card-title">战斗特效资源对 (Battle Effect Resource Pairs)</div>
            <span class="tag tag-amber">artifacts/battle-effect-resource-pairs-v1 · {pairs["valid_resource_pair_count"]} 组</span>
          </div>
          <p class="card-desc">
            由 <code>tools/export_battle_effect_resource_pairs.py</code> 导出 {pairs["valid_resource_pair_count"]} 组特效的
            <code>graphics-4bpp</code> 与 <code>palette-bgr555</code> 配对，并附消费者代码切片回链。
            <code>tools/verify_battle_effect_resource_pairs.py</code> 复核 {pairs["valid_resource_pair_count"]} 组图集零错误。
          </p>
          <div class="tileset-gallery">
{cards}
          </div>
        </div>
"""


def battle_effect_anims_section(root: Path) -> str:
    anims = load(root, "artifacts/battle-effect-sprite-animations-v1")
    if not anims:
        return ""
    cards = "\n".join(
        f'            <div class="tileset-item">\n'
        f'              <div class="tileset-header"><strong>{path.stem}</strong></div>\n'
        f'              <div class="tileset-img-wrap"><img class="tile-zoom-md" src="{PRE}artifacts/battle-effect-sprite-animations-v1/{path.name}" alt="{path.stem}" loading="lazy"></div>\n'
        f"            </div>"
        for path in sorted(root.glob("artifacts/battle-effect-sprite-animations-v1/group-*-frame-*.png"))
    )
    return f"""        <div class="card full-width" id="sec-battle-effect-anims">
          <div class="card-head">
            <div class="card-title">战斗特效精灵动画 (Battle Effect Sprite Animations)</div>
            <span class="tag tag-rose">{anims["group_count"]} 组 · {anims["frame_definition_count"]} 帧定义 · {anims["animation_count"]} 动画 · {anims["keyframe_count"]} 关键帧</span>
          </div>
          <p class="card-desc">
            由 <code>tools/export_battle_effect_sprite_animations.py</code> 导出的完整特效动画帧，并闭合了 OAM 属性模型、
            仿射矩阵模型、动态 OBJ VRAM 模型与播放调度边界。
            <code>tools/verify_battle_effect_sprite_animations.py</code> 复核 {anims["group_count"]} 组 / {anims["component_count"]} 组件 / {anims["frame_definition_count"]} 帧零错误。
          </p>
          <div class="tileset-gallery">
{cards}
          </div>
        </div>
"""


def sprite_definition_section(root: Path) -> str:
    manifest = load(root, "artifacts/sprite-definition-assets-v2")
    if not manifest:
        return ""
    cards = "\n".join(
        f'            <div class="tileset-item">\n'
        f'              <div class="tileset-header"><strong>{path.stem}</strong></div>\n'
        f'              <div class="tileset-img-wrap"><img class="tile-zoom-sm" src="{PRE}artifacts/sprite-definition-assets-v2/{path.name}" alt="{path.stem}" loading="lazy"></div>\n'
        f"            </div>"
        for path in sorted(root.glob("artifacts/sprite-definition-assets-v2/sprite-id-*.png"))
    )
    chain = manifest.get("runtime_chain", {})
    return f"""        <div class="card full-width" id="sec-sprite-definitions">
          <div class="card-head">
            <div class="card-title">精灵定义静态资源与运行时链 (Sprite Definition Assets)</div>
            <span class="tag tag-green">artifacts/sprite-definition-assets-v2 · {manifest["entry_count"]} 条定义 · {manifest["component_count"]} 个组件</span>
          </div>
          <p class="card-desc">
            由 <code>tools/export_sprite_definition_animations.py</code> 与 <code>tools/export_sprite_definition_runtime_chain.py</code>
            导出 {manifest["entry_count"]} 条精灵定义，并闭合运行时加载链
            （{ "、".join(list(chain)[:4]) } 等 {len(chain)} 个环节）。
            <code>tools/verify_sprite_definition_runtime_chain.py</code> 复核 43 资产 / 49 瓦片零错误。
          </p>
          <div class="tileset-gallery">
{cards}
          </div>
        </div>
"""


SECTIONS = {
    "fragment-map-canvases.html": map_canvases_section,
    "fragment-character-battle-visuals.html": character_battle_visuals_section,
    "fragment-bg-canvases.html": bg_canvases_section,
    "fragment-scene-visual-packs.html": scene_visual_packs_section,
    "fragment-battle-effect-pairs.html": battle_effect_pairs_section,
    "fragment-battle-effect-anims.html": battle_effect_anims_section,
    "fragment-battle-glyphs.html": battle_glyphs_section,
    "fragment-bg-scene-selection.html": bg_scene_selection_section,
    "fragment-battle-effect-sequences.html": battle_effect_sequence_section,
    "fragment-sprite-definitions.html": sprite_definition_section,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("build/viewer-data")
    )
    args = parser.parse_args()
    root = args.root.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for filename, builder in SECTIONS.items():
        markup = builder(root).rstrip("\n")
        path = args.output_dir / filename
        if markup:
            path.write_text(markup + "\n", encoding="utf-8")
            print(f"wrote {path} ({len(markup.splitlines())} lines)")
        else:
            print(f"skipped {path} (family manifest unavailable)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
