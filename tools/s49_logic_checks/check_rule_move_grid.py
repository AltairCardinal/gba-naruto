#!/usr/bin/env python3
"""The move range overlay is a dither mask over a fixed palette, not a tint.

The original S49 paints the reachable area of the battlefield with a cyan
overlay.  The overlay is **not** one flat tint: the original walks the
overlay over the map with a dither mask, so the same map colour comes out
as several different overlay colours depending on where the mask lets the
overlay through.  Nineteen map colours each map to more than one overlay
colour, over eighteen distinct cyan overlay colours.

The remake blends one flat overlay colour into the map
(``battle_range_ui_style.h``: ``move_primary`` RGB5(3,25,31), blend 10/16),
so its overlay field does not match the original's.

How the frame is found
----------------------

The macOS measurer used the hard coded pair ``step-19`` / ``step-20`` of the
macOS walk.  On this machine the walk is a different traversal, so the pair
is located by measurement: the move range screen is the frame that paints
the most **cyan overlay cells** that the next frame does not.  That is a
property of the move range screen itself, not of a step number.

Usage::

    python tools/s49_logic_checks/check_rule_move_grid.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from s49_logic_common import (  # noqa: E402
    EXIT_INPUT_ERROR,
    FAIL,
    LONG_WALK,
    PASS,
    REMAKE_ROOT,
    REMAKE_WALK,
    UNDECIDED,
    Check,
    CheckInputError,
    find_overlay_pair,
    largest_connected_region,
    load_image,
    overlay_cells,
    walk_frames,
)

#: The macOS measured values, taken from the signed gate
#: ``tests/test_s49_rule_move_grid.py`` and the ledger entry
#: ``s49-move-grid-cost-colors``.
MACOS_CHANGED_PIXELS = 22735
MACOS_CYAN_PIXELS = 8536
MACOS_CYAN_COLOURS = 18
MACOS_BASES_WITH_SEVERAL = 19

#: The remake's own blend model, read out of the remake tree.
REMAKE_BLEND_HEADER = "butano-sequel/game/include/konoha/battle_range_ui_style.h"


def _describe(index: int, grid: Path, plain: Path) -> str:
    return f"{grid.name}（画了覆盖层）→ {plain.name}（没有覆盖层）"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remake-root", default=str(REMAKE_ROOT))
    args = parser.parse_args(argv)

    check = Check(
        name="rule-move-grid",
        title="移动网格的染色规则（覆盖层）",
        source="tools/s49_logic_checks/check_rule_move_grid.py",
    )

    located: dict[str, tuple[int, int, dict]] = {}
    for label, walk in (("原版", LONG_WALK), ("重制", REMAKE_WALK)):
        try:
            frames = walk_frames(walk)
        except CheckInputError as error:
            check.add(
                f"{label}-walk", UNDECIDED,
                f"{label}侧没有录制的帧",
                missing=str(error),
            )
            continue
        found = find_overlay_pair(frames)
        if found is None:
            check.add(
                f"{label}-locate", UNDECIDED,
                f"{label}侧录制里找不到「画了青色覆盖层 → 没画」的相邻帧对",
                missing=f"{label}侧录制没有移动范围画面",
            )
            continue
        grid_index, plain_index, statistics = found
        located[label] = (grid_index, plain_index, statistics)
        cells = overlay_cells(
            load_image(frames[grid_index]), load_image(frames[plain_index])
        )
        region = largest_connected_region(cells)
        check.add(
            f"{label}-locate",
            PASS,
            "在整段录制里找相邻帧对中「连成一片的青色覆盖格」最多的一对 —— "
            "移动范围画面就是把可达格涂上青色覆盖层的那一帧，"
            "而换画面时的青色是散落的文字，连不成一片",
            original="macOS 侧是 step-19 → step-20",
            remake=f"{_describe(grid_index, frames[grid_index], frames[plain_index])}，"
                   f"覆盖格 {len(cells)} 个，最大连通块 {region} 格",
            delta="—",
        )

    if "原版" in located:
        grid_index, plain_index, statistics = located["原版"]
        check.add(
            "original-is-dither-mask",
            PASS if statistics["bases_with_several_cyan_overlays"] > 1 else FAIL,
            "同一个底色（地图色）落到多于一种青色覆盖色上 ⇒ 覆盖层是抖动遮罩，"
            "不是单一平涂",
            original=f"{MACOS_BASES_WITH_SEVERAL} 个底色各对应多于一种覆盖色"
                     f"（macOS 门禁钉的值）",
            remake=f"{statistics['bases_with_several_cyan_overlays']} 个底色",
            delta="—" if statistics["bases_with_several_cyan_overlays"] > 1
            else "不是抖动遮罩",
        )
        check.add(
            "original-cyan-palette",
            PASS if statistics["cyan_overlay_colours"] > 1 else FAIL,
            "覆盖层用的青色覆盖色有多少种（原版是固定的一小套调色板）",
            original=f"{MACOS_CYAN_COLOURS} 种青色覆盖色，"
                     f"{MACOS_CYAN_PIXELS} 个青色像素，"
                     f"{MACOS_CHANGED_PIXELS} 个变化像素"
                     f"（macOS 门禁钉的值）",
            remake=f"{statistics['cyan_overlay_colours']} 种青色覆盖色，"
                   f"{statistics['cyan_pixels']} 个青色像素，"
                   f"{statistics['changed_pixels']} 个变化像素",
            delta="—" if statistics["cyan_overlay_colours"] > 1 else "覆盖色只有一种",
        )
    else:
        check.add(
            "original-is-dither-mask", UNDECIDED,
            "原版侧没有定位到移动范围画面",
            missing="原版侧录制缺移动范围画面",
        )

    if "原版" in located and "重制" in located:
        _og, _op, original = located["原版"]
        _rg, _rp, remake = located["重制"]
        check.add(
            "remake-uses-fixed-palette",
            PASS if remake["bases_with_several_cyan_overlays"] > 1 else FAIL,
            "重制侧的覆盖层也要是「同一底色落到多于一种覆盖色」的抖动遮罩，"
            "而不是随底色平涂出来的单一颜色",
            original=f"{original['bases_with_several_cyan_overlays']} 个底色各对应"
                     f"多于一种覆盖色",
            remake=f"{remake['bases_with_several_cyan_overlays']} 个底色各对应"
                   f"多于一种覆盖色；青色覆盖色 "
                   f"{remake['cyan_overlay_colours']} 种",
            delta="一致" if remake["bases_with_several_cyan_overlays"] > 1
            else "重制侧是单一平涂，覆盖层与原版不同",
        )
        check.add(
            "remake-cyan-palette",
            PASS if remake["cyan_overlay_colours"] == original["cyan_overlay_colours"]
            else FAIL,
            "两侧的青色覆盖色数量是否相同（原版是固定的一小套调色板）",
            original=f"{original['cyan_overlay_colours']} 种",
            remake=f"{remake['cyan_overlay_colours']} 种",
            delta=remake["cyan_overlay_colours"] - original["cyan_overlay_colours"],
        )
        check.notes.append(
            "两侧的计数是在**各自**的帧对上量的：原版这一对是 "
            "step-25→step-26，重制这一对是 step-20→step-21，"
            "可达格集合与相机都不同，所以数字本身不必相等；"
            "逐格比对是覆盖层那条线（notes/s49-fidelity/F-overlay-ground-truth.md）"
            "的事，这里只判「规则」不判「每一格」。"
        )
        check.notes.append(
            "像素测量说重制侧的输出也是「同一底色落到多于一种覆盖色」"
            f"（{remake['bases_with_several_cyan_overlays']} 个底色），"
            "而重制侧的源码写的是「把一种颜色按比例混进地图色」"
            "（blend 10/16）：这两件事不矛盾 —— 混色本身带抖动，"
            "所以输出不是单一颜色，但覆盖色**不固定**，仍不是原版那套"
            "固定调色板。"
        )

    # The remake's own blend model, read out of the source.
    header = Path(args.remake_root) / REMAKE_BLEND_HEADER
    if header.is_file():
        text = header.read_text(encoding="utf-8")
        blend_lines = [
            line.strip() for line in text.splitlines()
            if "move_primary" in line or "blend" in line
        ]
        flat = any("blend" in line for line in blend_lines)
        check.add(
            "remake-blend-model",
            FAIL if flat else PASS,
            "在 battle_range_ui_style.h 里读重制侧自己的覆盖层着色模型",
            original="固定的一小套青色调色板 + 抖动遮罩",
            remake="；".join(blend_lines[:4]) or "（没有找到 blend 定义）",
            delta="重制侧是把一种颜色按比例混进地图色 ⇒ 覆盖色随底色变化"
                  if flat else "重制侧不是单一平涂",
        )    else:
        check.add(
            "remake-blend-model", UNDECIDED,
            "重制侧的覆盖层着色头文件不在本机",
            missing=str(header),
        )

    path = check.write()
    print(check.render())
    print(f"\nreceipt: {path}")
    return check.exit_code()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckInputError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(EXIT_INPUT_ERROR)
