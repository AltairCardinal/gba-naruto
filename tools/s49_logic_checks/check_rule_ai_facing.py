#!/usr/bin/env python3
"""A unit that has moved faces the way it moved, not its focus point.

In the original S49 the unit the mission asks the player to protect
(木叶丸) starts on scene column 8 and ends the turn on column 10: he walked
**two cells east**, and the original draws him **facing east**.  The focus
position the mission gives him lies north east of his destination
(12, 3 against 10, 7), so "face the focus" and "face the movement
direction" disagree, which is what makes the rule observable in the pixels.

The original side is measured, not narrated:

* the original draws 木叶丸 as the **dimmed** (greyscale) non-acting unit,
  using the palette that was read out of the original's palette RAM
  (``artifacts/s49-original-gpu-20261020-v2/dimmed-palette-receipt.json``),
* the leftmost column of that art is a screen column; with the camera
  (240, 24) and the grid model of the reverse side
  (``notes/character-runtime-unit-oam-bindings-20260730.md``) it is the
  scene column,
* the art is **not** bilaterally symmetric, so the facing really is
  observable in the pixels.

How the frame is found
----------------------

The macOS measurer used a hard coded step number.  On this machine the
walk is a different traversal (the two mGBA builds walk the UI at a
slightly different pace), so the frame is located by measurement: the
**modal** leftmost column of the dimmed art over the whole walk.  On both
sides that modal column is 80 -- the AI unit's position -- while every
other column belongs to one or two unrelated frames.

The remake side is measured with an orientation test: the original's unit
region compared with the remake's has to be much closer than the
original's **mirrored** region compared with the remake's.  A remake that
faced the other way would fail that.

Usage::

    python tools/s49_logic_checks/check_rule_ai_facing.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from s49_logic_common import (  # noqa: E402
    EXIT_INPUT_ERROR,
    FAIL,
    LONG_WALK,
    MACOS_DIMMED_PALETTE,
    PASS,
    REMAKE_ROOT,
    REMAKE_WALK,
    UNDECIDED,
    Check,
    CheckInputError,
    difference_pixels,
    load_image,
    read_json,
    walk_frames,
)

#: The region of the screen the unit art lives in.
LEFT_UNIT_SPRITE = (64, 24, 150, 104)

#: The original's camera on the battlefield screens.
CAMERA_HOFS = 240
CAMERA_VOFS = 24

#: The grid model of the reverse side: the sprite origin sits at
#: ``grid_x * 32 - BG0HOFS + 16`` and the art extends 16 pixels to the
#: left of the origin.
CELL_WIDTH = 32
ART_LEFT_OF_ORIGIN = 16

#: Where the S49 battle 14 variant 0 puts 木叶丸 before he moves.
DEPLOYMENT_COLUMN = 8

#: The row of 木叶丸's cell after the move.
DESTINATION_ROW = 7

#: The focus position the S49 mission gives the AI unit.  It lies north east
#: of the destination, so "face the focus" and "face the movement
#: direction" disagree; that disagreement is what makes the facing
#: observable.
FOCUS_POSITION = (12, 3)

#: The macOS measured values, taken from the signed gate
#: ``tests/test_s49_rule_ai_facing.py``.
MACOS_ART_LEFT_COLUMN = 80
MACOS_SCENE_COLUMN = 10


def _facing(dx: int, dy: int) -> str:
    """The dominant axis, the way the remake's ``facing_toward`` reads it."""

    if dx == 0 and dy == 0:
        return "none"
    if abs(dx) >= abs(dy):
        return "east" if dx > 0 else "west"
    return "north" if dy < 0 else "south"


def _dimmed_palette() -> list[tuple[int, int, int]]:
    payload = read_json(MACOS_DIMMED_PALETTE)
    if payload.get("schema") != "konoha.s49-unit-dimmed-palette.v1":
        raise CheckInputError(f"{MACOS_DIMMED_PALETTE} is not the dimmed receipt")
    return [tuple(colour) for colour in payload["dimmed"]]


def _dimmed_art_columns(image, dimmed) -> list[int]:
    x0, y0, x1, y1 = LEFT_UNIT_SPRITE
    pixels = image.load()
    return [
        x
        for x in range(x0, x1)
        if any(pixels[x, y] in dimmed for y in range(y0, y1))
    ]


def _locate_command_frame(frames: list[Path], dimmed):
    """The frame whose dimmed art sits at the walk's modal column.

    The modal column is the AI unit's own position: it repeats over many
    frames, while every other column belongs to one or two unrelated
    frames.
    """

    histogram: Counter[int] = Counter()
    per_frame: dict[str, list[int]] = {}
    for path in frames:
        columns = _dimmed_art_columns(load_image(path), dimmed)
        if not columns:
            continue
        per_frame[path.name] = columns
        histogram[min(columns)] += 1
    if not histogram:
        return None, None, {}
    modal = histogram.most_common(1)[0][0]
    frame = next(
        path for path in frames
        if per_frame.get(path.name) and min(per_frame[path.name]) == modal
    )
    return modal, frame, per_frame


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remake-root", default=str(REMAKE_ROOT))
    args = parser.parse_args(argv)

    check = Check(
        name="rule-ai-facing",
        title="AI 移动后的朝向",
        source="tools/s49_logic_checks/check_rule_ai_facing.py",
    )

    try:
        dimmed = _dimmed_palette()
    except CheckInputError as error:
        check.add(
            "dimmed-palette", UNDECIDED,
            "原版的暗色调色板收据缺失",
            missing=str(error),
        )
        return _finish(check)

    located: dict[str, tuple[int, Path]] = {}
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
        modal, frame, per_frame = _locate_command_frame(frames, dimmed)
        if modal is None:
            check.add(
                f"{label}-locate", UNDECIDED,
                f"{label}侧录制里找不到暗色化的非行动单位",
                missing=f"{label}侧录制没有暗色化单位",
            )
            continue
        located[label] = (modal, frame)
        check.add(
            f"{label}-locate",
            PASS,
            "在整段录制里统计暗色化单位最左列的众数，取众数所在的那一帧"
            "（众数是 AI 单位自己的位置，其余列只在一两帧里出现）",
            original=f"众数列 {MACOS_ART_LEFT_COLUMN}（macOS 门禁钉的值）",
            remake=f"众数列 {modal}，取帧 {frame.name}",
            delta="与原版同一位置" if modal == MACOS_ART_LEFT_COLUMN
            else "与原版不同",
        )

    if "原版" in located:
        modal, frame = located["原版"]
        scene_column = (modal + CAMERA_HOFS) // CELL_WIDTH
        walked = scene_column - DEPLOYMENT_COLUMN
        facing_movement = _facing(walked, 0)
        facing_focus = _facing(
            FOCUS_POSITION[0] - scene_column,
            FOCUS_POSITION[1] - DESTINATION_ROW,
        )
        check.add(
            "original-cell",
            PASS if scene_column == MACOS_SCENE_COLUMN else FAIL,
            "用网格公式（origin = grid_x * 32 - BG0HOFS + 16，画向左 16 px）"
            "把暗色化单位的屏幕列换算成场景列",
            original=f"场景列 {MACOS_SCENE_COLUMN}（macOS 门禁钉的值）",
            remake=f"场景列 {scene_column}（由列 {modal} 与相机 "
                   f"({CAMERA_HOFS}, {CAMERA_VOFS}) 算出）",
            delta=0 if scene_column == MACOS_SCENE_COLUMN else "场景列不同",
        )
        check.add(
            "original-walked-east",
            PASS if (walked, facing_movement) == (2, "east") else FAIL,
            "部署列 8 → 走过的格数与走的方向",
            original="走了 2 格向东，朝向 east",
            remake=f"走了 {walked} 格，方向 {facing_movement}",
            delta="一致" if walked == 2 and facing_movement == "east" else "不同",
        )
        check.add(
            "focus-would-differ",
            PASS if facing_focus != facing_movement else FAIL,
            "把焦点位置 (12, 3) 当成朝向依据会给出什么",
            original="面向焦点 ⇒ north，与面向移动方向不同 ⇒ 朝向可判定",
            remake=f"面向焦点 ⇒ {facing_focus}",
            delta="可判定" if facing_focus != facing_movement
            else "两者相同 ⇒ 朝向无法从像素判定",
        )
        crop = load_image(frame).crop(LEFT_UNIT_SPRITE)
        from PIL import ImageOps

        mirrored = ImageOps.mirror(crop)
        check.add(
            "original-art-is-asymmetric",
            PASS if difference_pixels(crop, mirrored) > 0 else FAIL,
            "把暗色化单位的画面左右翻转后逐像素比，看朝向是否真的可读",
            original="非双侧对称（macOS 门禁钉的值）",
            remake=f"翻转前后差异 {difference_pixels(crop, mirrored)} px",
            delta="可判定" if difference_pixels(crop, mirrored) > 0 else "对称 ⇒ 不可判定",
        )
        original_frame = frame
    else:
        original_frame = None

    if "重制" in located and original_frame is not None:
        _modal, remake_frame = located["重制"]
        box = LEFT_UNIT_SPRITE
        original_crop = load_image(original_frame).crop(box)
        remake_crop = load_image(remake_frame).crop(box)
        from PIL import ImageOps

        direct = difference_pixels(original_crop, remake_crop)
        mirrored = difference_pixels(ImageOps.mirror(original_crop), remake_crop)
        check.add(
            "remake-orientation",
            PASS if direct < mirrored // 2 else FAIL,
            "朝向测试：原版单位区 vs 重制单位区的直接差，必须远小于"
            "「原版镜像区 vs 重制单位区」的差（否则重制画反了朝向）",
            original=f"直接差 {direct} px / 镜像差 {mirrored} px",
            remake=f"{remake_frame.name}",
            delta="直接差 < 镜像差的一半 ⇒ 朝向一致"
                  if direct < mirrored // 2 else "直接差不小 ⇒ 朝向不一致",
        )
        check.add(
            "remake-orientation-residual",
            PASS if direct < 2000 else FAIL,
            "朝向差异不能大到「整个单位都换了」的程度（那说明是画反了，"
            "而不是动画相位差）",
            original="原版单位区与重制单位区的差 < 2000 px（macOS 门禁钉的值）",
            remake=f"直接差 {direct} px",
            delta="在相位差范围内" if direct < 2000 else "超出相位差范围",
        )

    # The remake's own source decides the facing; read the criterion out of it.
    source_files = list(
        (Path(args.remake_root) / "butano-sequel/game").rglob("*.cpp")
    ) + list(
        (Path(args.remake_root) / "butano-sequel/game").rglob("*.h")
    )
    facing_files = []
    focus_files = []
    for path in source_files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "facing_toward" in text:
            facing_files.append(path.name)
        if "focus_position" in text:
            focus_files.append(path.name)
    check.add(
        "remake-source-criterion",
        PASS if facing_files else UNDECIDED,
        "在重制侧源码里找朝向的判据（facing_toward / focus_position）",
        original="朝向＝移动方向，不是焦点",
        remake=f"facing_toward 出现在 {sorted(set(facing_files))[:3]}；"
               f"focus_position 出现在 {sorted(set(focus_files))[:3]}",
        delta="—" if facing_files else "源码里没有朝向判据",
    )

    return _finish(check)


def _finish(check: Check) -> int:
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
