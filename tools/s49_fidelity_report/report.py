"""Assemble the report document and render its Markdown receipt."""

from __future__ import annotations

import hashlib

from . import classify, overlay as overlay_module
from .anchors import dispcnt_variation, pairing_quality
from .paths import (BLACK_NON_BLACK_LIMIT, FLAT_SPOT_PHASES,
                    FLAT_SPOT_SHADES, OUTLINE_WAVE)
from .pixels import (block_means, block_occupancy, diff_mask, row_spread,
                     structure_match)
from .staticframes import STATIC_RULE, check_capture

SCHEMA = "s49-fidelity-report/2"


def _compact_anchor(anchor: dict | None) -> dict:
    if anchor is None:
        return {}
    out = {
        "screen": anchor.get("screen"),
        "outline_shades": anchor.get("outline_shades"),
        "palette_black": anchor.get("palette_black"),
    }
    registers = anchor.get("registers")
    if registers:
        out["dispcnt_hex"] = registers["dispcnt_hex"]
        out["bg_hofs"] = registers["bg_hofs"]
    overlay = anchor.get("overlay")
    if overlay:
        out["overlay"] = {
            "lit_cells": overlay["lit_cells"],
            "family_counts": overlay["family_counts"],
            "family_digest": overlay["family_digest"][:16],
        }
    return out


def build_report(args, captures: dict, frames_dir, anchors: dict) -> dict:
    from .pixels import load_rgb, stats

    area = tuple(args.field_area)
    full_box = (0, 0, 240, 160)

    original_dir = frames_dir / "capture-original"
    remake_dir = frames_dir / "capture-remake"

    original_paths = sorted(original_dir.glob("step-*.png"))
    remake_paths = sorted(remake_dir.glob("step-*.png"))
    if not original_paths or not remake_paths:
        raise SystemExit("ERR no captured frames found")

    original_images = {p.name: load_rgb(p) for p in original_paths}
    remake_images = {p.name: load_rgb(p) for p in remake_paths}
    original_blocks = {n: block_means(im, area) for n, im in original_images.items()}
    remake_blocks = {n: block_means(im, area) for n, im in remake_images.items()}

    # --- the remake walk's repeated frames (the "still frame" evidence) -----
    remake_field_digest = {
        name: hashlib.sha256(image.crop(area).tobytes()).hexdigest()
        for name, image in remake_images.items()
    }
    remake_repeat_count: dict[str, int] = {}
    for name in remake_images:
        remake_repeat_count[name] = sum(
            1 for other, digest in remake_field_digest.items()
            if digest == remake_field_digest[name])
    remake_repeated = {name for name, count in remake_repeat_count.items()
                       if count > 1}

    # --- did the camera move at this step?  The background scroll register is
    #     9 bits of hardware, so the masked value is the camera position; a
    #     change of that value between two steps of the same walk is a camera
    #     move.  "Did the camera move" is comparable across the two sides even
    #     though the two positions themselves are not (different maps).
    def camera_of(anchor: dict | None):
        if not anchor:
            return None
        registers = anchor.get("registers")
        if not registers:
            return None
        # ⭐ 2026-10-25 (wave 20 / E3): the corrected IO decoder reads the
        # real BGxHOFS addresses, but this headless debugger answers every
        # scroll register with a per-frame constant filler (open bus) — so the
        # three values are always identical.  When that happens the word is
        # **not** a camera reading and must not be compared as one.
        if registers.get("bg_hofs_readable") is False:
            return None
        return tuple(registers.get("bg_hofs") or ())

    remake_walk_order = [p.name for p in remake_paths]
    remake_camera_moved = {}
    previous = None
    for name in remake_walk_order:
        camera = camera_of(anchors["remake"]["frames"].get(name))
        remake_camera_moved[name] = (previous is not None and camera is not None
                                     and camera != previous)
        previous = camera

    rows = []
    for original_path in original_paths:
        name = original_path.name
        left = original_images[name]
        left_blocks = original_blocks[name]

        matrix = {}
        for remake_path in remake_paths:
            rname = remake_path.name
            count, _ = diff_mask(left, remake_images[rname], area)
            matrix[rname] = count
        ordered = sorted(matrix.items(), key=lambda kv: (kv[1], kv[0]))
        best_name, best_residual = ordered[0]
        second_name, second_residual = ordered[1] if len(ordered) > 1 else (None, None)

        best_remake = remake_images[best_name]
        full_residual, _ = diff_mask(left, best_remake, full_box)
        _, mask = diff_mask(left, best_remake, area)
        structure = structure_match(left_blocks, remake_blocks[best_name],
                                    classify.STRUCT_TOLERANCE)
        occupancy = block_occupancy(mask)
        spread = row_spread(mask)
        verdict = classify.vote(structure, occupancy, spread)

        if best_residual == 0:
            kind = "identical"
        elif verdict["same_moment"]:
            kind = "product_diff"
        else:
            kind = "pairing_diff"

        # --- the content anchors -------------------------------------------
        original_anchor = anchors["original"]["frames"].get(name)
        remake_anchor = anchors["remake"]["frames"].get(best_name)

        # --- did the remake advance between the previous original step and
        #     this one?  When both original steps are paired to the *same*
        #     remake frame, the remake's screen did not move while the
        #     original's did: the remake is showing a still frame.
        previous_best = rows[-1]["best_match"] if rows else None
        pairing_stalled = previous_best is not None and previous_best == best_name

        refinement = classify.refine_pairing_diff(
            original_anchor, remake_anchor,
            remake_repeated=best_name in remake_repeated,
            pairing_stalled=pairing_stalled)

        # --- the overlay family residual ------------------------------------
        overlay_result = None
        if original_anchor and remake_anchor:
            left_grid = original_anchor.get("_grid")
            right_grid = remake_anchor.get("_grid")
            if left_grid and right_grid:
                overlay_result = overlay_module.best_offset(left_grid, right_grid)

        # --- did the camera move on either side at this step? ---------------
        original_camera = camera_of(original_anchor)
        previous_original_camera = camera_of(
            anchors["original"]["frames"].get(rows[-1]["original"])
            if rows else None)
        camera_moved_original = (previous_original_camera is not None
                                 and original_camera is not None
                                 and original_camera != previous_original_camera)
        camera_moved_remake = remake_camera_moved.get(best_name)

        criteria = [
            f"结构同构 s={structure:.3f} (阈值 {classify.STRUCT_THRESHOLD:.2f}, "
            f"块均色差<={classify.STRUCT_TOLERANCE})",
            f"差异块占比 o={occupancy:.3f} (阈值 {classify.OCCUPANCY_THRESHOLD:.2f})",
            f"差异行占比 r={spread:.3f} (阈值 {classify.ROW_SPREAD_THRESHOLD:.2f})",
            f"投票 {verdict['votes']['same']}/3 判同 ⇒ "
            f"{'同一游戏时刻' if verdict['same_moment'] else '不同游戏时刻'} ⇒ "
            f"{classify.CLASS_NAMES[kind]}",
        ]
        if kind == "pairing_diff":
            criteria.append(
                f"配对差细分 ⇒ {refinement['subclass_label']} "
                f"`{refinement['subclass']}`（{refinement['subclass_rule']}）")

        row = {
            "original": name,
            "best_match": best_name,
            "field_residual_px": best_residual,
            "field_percent": round(100.0 * best_residual / max(1, area[2] * area[3]), 4),
            "full_residual_px": full_residual,
            "second_best": {"frame": second_name, "field_residual_px": second_residual},
            "signals": {
                "structure_match": round(structure, 6),
                "diff_block_occupancy": round(occupancy, 6),
                "diff_row_spread": round(spread, 6),
            },
            "verdict": {
                "class": kind,
                "class_label": classify.CLASS_NAMES[kind],
                "same_moment": verdict["same_moment"],
                "confidence": verdict["confidence"],
                "votes": verdict["votes"],
                "support_margin": verdict["support_margin"],
                "dissent_margin": verdict["dissent_margin"],
                "signal_detail": verdict["signals"],
                "criteria": criteria,
            },
            "anchor": {
                "original": _compact_anchor(original_anchor),
                "remake": _compact_anchor(remake_anchor),
                "camera_moved_original": camera_moved_original,
                "camera_moved_remake": camera_moved_remake,
                "camera_agrees": (camera_moved_original == camera_moved_remake
                                  if camera_moved_remake is not None else None),
            },
        }
        if kind == "pairing_diff":
            row["verdict"]["subclass"] = refinement["subclass"]
            row["verdict"]["subclass_label"] = refinement["subclass_label"]
            row["verdict"]["subclass_rule"] = refinement["subclass_rule"]
            row["verdict"]["subclass_evidence"] = refinement["evidence"]
        if overlay_result is not None:
            row["overlay_residual"] = overlay_result
        rows.append(row)

    field_values = [r["field_residual_px"] for r in rows]
    full_values = [r["full_residual_px"] for r in rows]
    attribution = {kind: sum(1 for r in rows if r["verdict"]["class"] == kind)
                   for kind in ("identical", "product_diff", "pairing_diff")}
    subclasses = {name: sum(1 for r in rows
                            if r["verdict"].get("subclass") == name)
                  for name in classify.SUBCLASS_NAMES}
    confidence_counts = {level: sum(1 for r in rows
                                    if r["verdict"]["confidence"] == level)
                         for level in ("high", "medium", "low")}
    best_matches = {r["best_match"] for r in rows}
    overlay_values = [r["overlay_residual"]["residual"] for r in rows
                      if "overlay_residual" in r]

    # --- the static frame criterion, per side -------------------------------
    static = {}
    for side, images, order in (
            ("original", original_images, [p.name for p in original_paths]),
            ("remake", remake_images, [p.name for p in remake_paths])):
        static[side] = check_capture(images, order)

    quality = pairing_quality(rows, anchors)
    variation = {
        "original": dispcnt_variation(anchors["original"]),
        "remake": dispcnt_variation(anchors["remake"]),
    }
    camera_agrees = sum(1 for row in rows
                         if row["anchor"].get("camera_agrees") is True)
    camera_total = sum(1 for row in rows
                       if row["anchor"].get("camera_agrees") is not None)
    # ⭐ 2026-10-25 (wave 20 / E3): the scroll registers read back as a
    # constant filler on this headless debugger, so bg_hofs is not a camera
    # reading.  Say so instead of publishing meaningless positions.
    camera_readable = camera_total > 0
    camera = {
        "readable": camera_readable,
        "original_positions": sorted({
            tuple(row["anchor"]["original"].get("bg_hofs") or ())
            for row in rows if row["anchor"].get("original", {}).get("bg_hofs")}),
        "remake_positions": sorted({
            tuple(row["anchor"]["remake"].get("bg_hofs") or ())
            for row in rows if row["anchor"].get("remake", {}).get("bg_hofs")}),
        "camera_move_agrees": camera_agrees,
        "camera_move_comparable": camera_total,
    }

    return {
        "schema": SCHEMA,
        "tool": {
            "path": "tools/s49_fidelity_report.py",
            "package": "tools/s49_fidelity_report",
            "version": "2.0.0",
        },
        "config": {
            "field_area": list(area),
            "classifier_calibrated_for_field_area": [0, 0, 240, 128],
            "field_area_warning": (
                None if list(area) == [0, 0, 240, 128] else
                "the classifier thresholds were calibrated on (0,0,240,128); "
                "re-check the attribution before trusting it on another area"),
            "screen_size": [240, 160],
            "bios_mode": "real" if args.bios else "hle",
            "bios_path": str(args.bios) if args.bios else None,
            "classifier": {
                "block_size": 16,
                "structure_tolerance": classify.STRUCT_TOLERANCE,
                "structure_threshold": classify.STRUCT_THRESHOLD,
                "occupancy_threshold": classify.OCCUPANCY_THRESHOLD,
                "row_spread_threshold": classify.ROW_SPREAD_THRESHOLD,
                "vote_rule": "same_moment when at least 2 of the 3 signals agree",
                "confidence_rule": {
                    "high": "unanimous and support margin >= 0.20",
                    "medium": "unanimous with margin >= 0.05, or dissent margin >= 0.10",
                    "low": "otherwise",
                },
            },
            "black_transition_rule": {
                "non_black_fraction_limit": BLACK_NON_BLACK_LIMIT,
                "corroborating_evidence": (
                    "the frames whose DISPCNT differs from the walk's usual "
                    "value (see summary.black_transition_evidence); the "
                    "palette is NOT blacked out during the fade, so it "
                    "cannot be used as the test"),
            },
            "pairing_diff_subclasses": classify.SUBCLASS_RULES,
            "static_frame_rule": STATIC_RULE,
            "outline_wave": list(OUTLINE_WAVE),
            "flat_spot_phases": [list(pair) for pair in FLAT_SPOT_PHASES],
            "flat_spot_shades": sorted(FLAT_SPOT_SHADES),
        },
        "captures": captures,
        "anchors": {
            "original": {
                "side": anchors["original"]["side"],
                "status": anchors["original"]["status"],
                "reason": anchors["original"]["reason"],
            },
            "remake": {
                "side": anchors["remake"]["side"],
                "status": anchors["remake"]["status"],
                "reason": anchors["remake"]["reason"],
            },
        },
        "frames": rows,
        "summary": {
            "original_frames": len(original_paths),
            "remake_frames": len(remake_paths),
            "distinct_remake_frames_used": len(best_matches),
            "field_residual": stats(field_values),
            "full_residual": stats(full_values),
            "overlay_residual": stats(overlay_values),
            "attribution": attribution,
            "attribution_labels": {k: classify.CLASS_NAMES[k] for k in attribution},
            "pairing_diff_subclasses": subclasses,
            "pairing_diff_subclass_labels": {
                k: classify.SUBCLASS_NAMES[k] for k in subclasses},
            "confidence": confidence_counts,
            "identical_frames": [r["original"] for r in rows
                                 if r["verdict"]["class"] == "identical"],
            "pairing_quality": {
                key: value for key, value in quality.items() if key != "details"
            },
            "black_transition_evidence": variation,
            "camera_anchor": camera,
            "black_transition_frames": [
                row["original"] for row in rows
                if row["verdict"].get("subclass") == "black_transition"],
            "static_frames": static,
        },
    }


def render_markdown(report: dict) -> str:
    config = report["config"]
    summary = report["summary"]
    lines = []
    lines.append("# S49 保真度判定报告 (fidelity report)")
    lines.append("")
    lines.append(f"- 生成时间：`{report['generated_at']}`")
    lines.append(f"- 内容摘要 `content_sha256`：`{report['content_sha256']}`"
                 "（覆盖 config/captures/anchors/frames/summary，**不含**时间戳与运行出处）")
    lines.append(f"- 工具：`{report['tool']['path']}` v{report['tool']['version']}"
                 f"（模块 `{report['tool']['package']}`）")
    lines.append(f"- 战场区：{config['field_area']}　BIOS 模式：`{config['bios_mode']}`")
    lines.append("")
    lines.append("## 1. 总览")
    lines.append("")
    lines.append("| 指标 | 最小 | 中位 | 最大 | 全 0 帧数 | 帧数 |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for label, key in (("战场区残差 px", "field_residual"),
                       ("整屏残差 px", "full_residual"),
                       ("覆盖层族名残差（格）", "overlay_residual")):
        s = summary.get(key) or {}
        if not s:
            lines.append(f"| {label} | — | — | — | — | 0 |")
            continue
        lines.append(f"| {label} | {s['min']} | {s['median']} | {s['max']} | "
                     f"{s['zero_frames']} | {s['frames']} |")
    lines.append("")
    lines.append("### 归因分类")
    lines.append("")
    lines.append("| 分类 | 帧数 | 含义 |")
    lines.append("|---|---:|---|")
    meanings = {
        "identical": "战场区 0 px —— 已完全一致",
        "product_diff": "同一游戏时刻但仍有渲染差 —— **要改产品代码**",
        "pairing_diff": "两侧处在不同游戏时刻 —— **不要改代码**，是对齐问题",
    }
    for kind in ("identical", "product_diff", "pairing_diff"):
        lines.append(f"| {classify.CLASS_NAMES[kind]} `{kind}` | "
                     f"{summary['attribution'][kind]} | {meanings[kind]} |")
    lines.append("")
    lines.append("### 「配对差」的三桶拆解")
    lines.append("")
    lines.append("| 子类 | 帧数 | 机器可读的判据 |")
    lines.append("|---|---:|---|")
    for name in classify.SUBCLASS_NAMES:
        lines.append(f"| {classify.SUBCLASS_NAMES[name]} `{name}` | "
                     f"{summary['pairing_diff_subclasses'][name]} | "
                     f"{classify.SUBCLASS_RULES[name]} |")
    lines.append("")
    lines.append("置信度分布：" + "　".join(
        f"{k}={v}" for k, v in summary["confidence"].items()))
    lines.append("")
    lines.append(f"原版 {summary['original_frames']} 帧，"
                 f"重制 {summary['remake_frames']} 帧，"
                 f"实际用到的不同重制帧 {summary['distinct_remake_frames_used']} 个。")
    lines.append("")
    lines.append("## 2. 逐帧表")
    lines.append("")
    lines.append("| 原版帧 | 最佳重制帧 | 战场区残差 px | 整屏残差 px | 覆盖层残差 | "
                 "归因 | 子类 | 置信度 | 投票 |")
    lines.append("|---|---|---:|---:|---:|---|---|---|---|")
    for row in report["frames"]:
        v = row["verdict"]
        overlay = row.get("overlay_residual", {}).get("residual", "—")
        lines.append(
            f"| `{row['original']}` | `{row['best_match']}` | "
            f"{row['field_residual_px']} | {row['full_residual_px']} | "
            f"{overlay} | {v['class_label']} | "
            f"{v.get('subclass_label', '—')} | {v['confidence']} | "
            f"{v['votes']['same']}/3 同 |")
    lines.append("")
    lines.append("## 3. 内容锚与配对质量")
    lines.append("")
    quality = summary["pairing_quality"]
    lines.append(f"- 原版锚状态：`{report['anchors']['original']['status']}`"
                 f"　重制锚状态：`{report['anchors']['remake']['status']}`")
    lines.append(f"- 找到内容锚的帧：**{quality['frames_with_anchor']} / "
                 f"{quality['frames']}**（覆盖率 {quality['coverage']:.2%}）")
    lines.append(f"- 锚支持该配对的帧（黑场状态一致且覆盖层有共同亮格）："
                 f"**{quality['anchor_supports_pairing']}**")
    lines.append(f"- 两侧黑场状态一致的帧：**{quality['blank_state_agrees']}**")
    lines.append(f"- 两侧覆盖层族名图完全一致的帧：**{quality['overlay_exact']}**")
    lines.append(f"- 配对后覆盖层共同亮格：最小 {quality['overlay_shared_cells']['min']} / "
                 f"最大 {quality['overlay_shared_cells']['max']} / "
                 f"总和 {quality['overlay_shared_cells']['sum']}")
    lines.append("")
    lines.append("锚的来源（全部来自文件，可复跑）：")
    lines.append("")
    lines.append("- `screen`：帧本身的非黑像素占比 / 均值 RGB / 唯一色数（判定黑场过渡）")
    lines.append("- `registers`：该帧存档里的 `DISPCNT`、四个 BG 控制寄存器与四个水平滚动寄存器")
    lines.append("- `overlay`：VRAM 里覆盖层 BG map 的逐格族名（覆盖层残差这一维）")
    lines.append("")
    lines.append("### 相机锚（背景水平滚动寄存器，9 bit）")
    lines.append("")
    camera = summary["camera_anchor"]
    if camera.get("readable") is False:
        lines.append("⛔ **本机读不到背景滚动寄存器** —— 这个无头调试器对 `0x10` 以上的"
                     "寄存器一律回一个**每帧恒定的填充值**（open bus），"
                     "三个 BG 的 HOFS/VOFS 读出来永远是同一个数 ⇒ **不是相机读数**。")
        lines.append("")
        lines.append("⇒ 相机语义映射**只能走像素口径**"
                     "（`notes/s49-fidelity/W20-E3-camera-mapping.md`）。")
        lines.append("⚠️ 2026-10-25 之前本节读的是 `VCOUNT/BG1CNT/BG3CNT`（**解码器地址表错了**），"
                     "那些「相机位置」数字**一律作废**。")
    else:
        lines.append(f"- 原版出现过的相机位置：`{camera['original_positions']}`")
        lines.append(f"- 重制出现过的相机位置：`{camera['remake_positions']}`")
        lines.append(f"- 「这一步相机有没有动」两侧一致的帧："
                     f"**{camera['camera_move_agrees']} / {camera['camera_move_comparable']}**")
    lines.append("")
    lines.append("### 黑场过渡的机器可读证据")
    lines.append("")
    lines.append("| 一侧 | 常用 `DISPCNT` | 出现过的 `DISPCNT` | 与常用值不同的帧 |")
    lines.append("|---|---|---|---|")
    for side in ("original", "remake"):
        evidence = summary["black_transition_evidence"][side]
        lines.append(f"| {side} | `{evidence['modal_dispcnt_hex']}` | "
                     f"{evidence['distinct_dispcnt']} | "
                     f"{evidence['deviating_frames']} |")
    lines.append("")
    lines.append("原版的两帧黑场过渡正是它的 `DISPCNT` 偏离常用值的两帧；"
                 "重制侧一帧黑场也没有，所以它的 `DISPCNT` 变化与黑场无关。")
    lines.append("")
    lines.append(f"判定台自动识别出的黑场过渡帧："
                 f"**{summary['black_transition_frames']}**")
    lines.append("")
    lines.append("## 4. 静止帧判据")
    lines.append("")
    lines.append(f"> {report['config']['static_frame_rule']}")
    lines.append("")
    lines.append("| 一侧 | 帧数 | 连续相同帧对 | 其中异常 | 观察到的描边色阶 | 描边波在动 |")
    lines.append("|---|---:|---:|---:|---|---|")
    for side in ("original", "remake"):
        s = summary["static_frames"][side]
        shades = s["distinct_outline_shades"]
        lines.append(f"| {side} | {s['frames']} | {s['consecutive_identical_pairs']} | "
                     f"{s['unexpected_pairs']} | {shades} | "
                     f"{'是' if s['outline_wave_animates'] else '否'} |")
    lines.append("")
    for side in ("original", "remake"):
        s = summary["static_frames"][side]
        for pair in s["pairs"]:
            if pair["wave_flat_spot"]:
                continue
            lines.append(f"- ⚠️ `{side}`：`{pair['previous']}` == `{pair['current']}` "
                         f"—— {pair['reason']}")
    lines.append("")
    lines.append("## 5. 归因判据（逐帧）")
    lines.append("")
    for row in report["frames"]:
        v = row["verdict"]
        lines.append(f"### `{row['original']}` → `{row['best_match']}` "
                     f"— {v['class_label']} `{v['class']}` "
                     f"({v['confidence']}，残差 {row['field_residual_px']} px)")
        lines.append("")
        for criterion in v["criteria"]:
            lines.append(f"- {criterion}")
        lines.append(f"- 支撑裕度 `{v['support_margin']}`"
                     + (f"，异议裕度 `{v['dissent_margin']}`"
                        if v["dissent_margin"] is not None else "，无异议信号"))
        anchor = row.get("anchor", {})
        if anchor.get("original"):
            lines.append(f"- 内容锚（原版）：`dispcnt={anchor['original'].get('dispcnt_hex')}`"
                         f"　`bg_hofs={anchor['original'].get('bg_hofs')}`"
                         f"　非黑占比 {anchor['original'].get('screen', {}).get('non_black_fraction')}")
        if anchor.get("remake"):
            lines.append(f"- 内容锚（重制）：`dispcnt={anchor['remake'].get('dispcnt_hex')}`"
                         f"　`bg_hofs={anchor['remake'].get('bg_hofs')}`"
                         f"　非黑占比 {anchor['remake'].get('screen', {}).get('non_black_fraction')}")
        if "overlay_residual" in row:
            o = row["overlay_residual"]
            lines.append(f"- 覆盖层族名残差：同亮 {o['both_lit']} / 原版缺 {o['original_only']} / "
                         f"多画 {o['remake_only']} / 族名不一致 {o['family_mismatches']} "
                         f"（对齐偏移 {o['offset']}）")
        lines.append("")
    if report.get("ratchet"):
        lines.extend(_render_ratchet(report["ratchet"]))
    lines.append("## 口径说明")
    lines.append("")
    lines.append(
        "本表的「战场区残差」是 **arg-min 对齐残差**：每一拍在重制侧的全部帧里"
        "取残差最小的那一帧（**不带时刻约束**），25 拍求和。")
    lines.append("")
    lines.append(
        "它**不是**任何「可证像素下界」的下界。下界是**另一种口径**"
        "（内容锚配对下的逐拍 arg-min 全帧最小值求和），两者**不许混用、"
        "不许互相换算**。写报告时禁止把另一个口径的下界写成"
        "「判定台的下界」。")
    lines.append("")
    lines.append("## 复跑")
    lines.append("")
    lines.append("```")
    lines.append("python tools/s49_fidelity_report.py --out build/s49-report/report.json")
    lines.append("```")
    lines.append("")
    lines.append("两次连跑必须给出相同的 `content_sha256`（`generated_at` 除外）。")
    lines.append("")
    return "\n".join(lines)


def _render_ratchet(ratchet: dict) -> list[str]:
    lines = ["## 棘轮门禁", ""]
    status = ratchet.get("status") or ("pass" if ratchet["ok"] else "fail")
    verdict = {
        "pass": "通过",
        "fail": "不通过（残差变大）",
        "incomparable": "不可比（基线 ROM 与本次 ROM 不同 ⇒ 残差数字不是同一个"
                        "测量 ⇒ **这不是通过**）",
    }[status]
    lines.append(f"结论：**{verdict}**")
    lines.append("")
    rom = ratchet.get("rom") or {}
    if rom.get("changed"):
        lines.append(f"- ⚠ 基线 ROM `{str(rom.get('baseline'))[:16]}…` → "
                     f"本次 ROM `{str(rom.get('candidate'))[:16]}…`："
                     "**ROM 变了 ⇒ 两侧残差不可比**。")
        lines.append("")
    lines.append("| 指标 | 基线 | 本次 | 方向 | 结果 |")
    lines.append("|---|---:|---:|---|---|")
    for check in ratchet["checks"]:
        direction = "越大越差" if check["direction"] == "higher" else "越小越差"
        lines.append(f"| {check['label']} | {check['baseline']} | {check['candidate']} | "
                     f"{direction} | {'✅' if check['ok'] else '❌'} |")
    frames = ratchet["frames"]
    lines.append("")
    lines.append(f"逐帧比较：{frames['compared']} 帧，"
                 f"变差 {frames['worsened']} 帧，变好 {frames['improved']} 帧。")
    lines.append("")
    return lines
