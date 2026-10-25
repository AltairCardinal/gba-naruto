#!/usr/bin/env python3
"""The status bar's 結束 / 待機 word follows the unit, not the screen phase.

The original S49 status bar carries a two kanji state word next to the unit
name:

* red ``結束``  (ink 231, 24, 0)  when the unit has already finished its
  action,
* blue ``待機`` (ink 115, 33, 255) when it is still waiting.

The criterion is the **unit's** state, not the screen's phase.

How the word is found
---------------------

The state word is drawn in a fixed slot of the status bar -- the measured
columns are 104..118 on both sides -- and the unit name is drawn to its left
*in the unit's own colour*, which is sometimes the same colour as the word.
So the word is read out of its slot, not out of the whole bar: the
``结束`` **button** of the technique menu lives at columns 216..230 and is
not a state word.

What is measured
----------------

1. the two inks exist and carry the original's pixel values (107 / 150),
2. the word is drawn in the same columns on both sides,
3. **the discriminating measurement**: on the same status bar layout, the
   red ``結束`` and the blue ``待機`` are shown, and the unit name area (the
   columns left of the word) differs between them.  A word that followed the
   screen phase could not do that: the layout is the same, only the
   displayed unit differs.

The macOS walk is not index comparable with the local one (the two mGBA
builds walk the UI at a slightly different pace), so every frame is located
by measurement, not by step number.

Usage::

    python tools/s49_logic_checks/check_rule_standby_state.py
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from s49_logic_common import (  # noqa: E402
    END_INK,
    EXIT_INPUT_ERROR,
    FAIL,
    LONG_WALK,
    PASS,
    REMAKE_ROOT,
    REMAKE_WALK,
    STANDBY_INK,
    STATUS_BAR,
    UNDECIDED,
    Check,
    CheckInputError,
    classify_status_bar,
    load_image,
    walk_frames,
)

#: The macOS measured values of the two state inks, taken from the signed
#: gate ``tests/test_s49_rule_standby_state.py`` of the remake tree.
MACOS_END_INK_PIXELS = 107
MACOS_STANDBY_INK_PIXELS = 150

#: The slot of the status bar the state word is drawn in.  Measured on both
#: sides: the word covers columns 104..118.
WORD_SLOT = (96, 128)


def _ink_groups(image, colour) -> list[tuple[int, int]]:
    """The contiguous screen columns that carry one ink."""

    x0, y0, x1, y1 = STATUS_BAR
    pixels = image.load()
    groups: list[tuple[int, int]] = []
    current: list[int] = []
    for x in range(x0, x1):
        if any(pixels[x, y] == colour for y in range(y0, y1)):
            current.append(x)
        elif current:
            groups.append((current[0], current[-1]))
            current = []
    if current:
        groups.append((current[0], current[-1]))
    return groups


def _slot_state(image) -> tuple[str, tuple[int, int] | None, int]:
    """The state word inside its slot: ``("end"|"standby"|"none", span, px)``.

    Only the ink inside ``WORD_SLOT`` counts, so the ``结束`` button of the
    technique menu (columns 216..230) is not mistaken for a state word.
    """

    x0, y0, x1, y1 = STATUS_BAR
    pixels = image.load()
    counts = {END_INK: 0, STANDBY_INK: 0}
    columns = {END_INK: [], STANDBY_INK: []}
    for x in range(WORD_SLOT[0], WORD_SLOT[1]):
        for y in range(y0, y1):
            colour = pixels[x, y]
            if colour in counts:
                counts[colour] += 1
                columns[colour].append(x)
    end = counts[END_INK]
    standby = counts[STANDBY_INK]
    if end and standby:
        return ("both", None, end + standby)
    if end:
        return ("end", (min(columns[END_INK]), max(columns[END_INK])), end)
    if standby:
        return (
            "standby",
            (min(columns[STANDBY_INK]), max(columns[STANDBY_INK])),
            standby,
        )
    return ("none", None, 0)


def _name_region_difference(red, blue, word_left: int) -> int:
    """How much the status bar's *name* area differs between two frames.

    The state word sits at a fixed place in the status bar, to the right of
    the unit name.  Everything to the left of the word is the name area: if
    it differs, the status bar is showing a **different unit**.
    """

    x0, y0, x1, y1 = STATUS_BAR
    red_px = red.load()
    blue_px = blue.load()
    differences = 0
    for y in range(y0, y1):
        for x in range(x0, word_left):
            if red_px[x, y] != blue_px[x, y]:
                differences += 1
    return differences


def _status_panel_function(scene: Path) -> str | None:
    """The body of ``render_status_panel_text``, braces balanced.

    The criterion has to be read out of the function that draws the status
    panel, not out of the whole file: the file mentions the screen phases
    in many other places.
    """

    if not scene.is_file():
        return None
    source = scene.read_text(encoding="utf-8")
    match = re.search(r"void render_status_panel_text\([^)]*\)\s*\{", source)
    if not match:
        return None
    start = match.end() - 1
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remake-root", default=str(REMAKE_ROOT))
    args = parser.parse_args(argv)

    check = Check(
        name="rule-standby-state",
        title="状态栏 結束 / 待機 切换时机",
        source="tools/s49_logic_checks/check_rule_standby_state.py",
    )

    measured: dict[str, dict] = {}
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

        states = []
        for path in frames:
            state, span, pixels = _slot_state(load_image(path))
            bar = classify_status_bar(load_image(path), STATUS_BAR)
            states.append((path, state, span, pixels, bar))
        reds = [item for item in states if item[1] == "end"]
        blues = [item for item in states if item[1] == "standby"]
        switches = [item for item in states if item[1] == "both"]
        measured[label] = {"reds": reds, "blues": blues}

        if reds and blues:
            two_inks_status = PASS
            two_inks_delta = "两种状态都出现"
        else:
            two_inks_status = UNDECIDED
            two_inks_delta = (
                "录制里只出现了"
                + ("红 結束" if reds else "蓝 待機")
                + "，另一种状态没被录到"
            )
        check.add(
            f"{label}-two-inks",
            two_inks_status,
            f"{label}侧录制的每一帧都按状态字所在的槽（列 "
            f"{WORD_SLOT[0]}..{WORD_SLOT[1]}）分类",
            original="红 結束 (231,24,0) / 蓝 待機 (115,33,255)",
            remake=f"红 {len(reds)} 帧 / 蓝 {len(blues)} 帧 / 切换中 {len(switches)} 帧",
            delta=two_inks_delta,
        )

        # The macOS reference counts the ink over the whole status bar, so
        # the comparison uses the whole bar too.
        max_red = max((item[4]["end_ink_pixels"] for item in reds), default=0)
        max_blue = max(
            (item[4]["standby_ink_pixels"] for item in blues), default=0
        )
        values = sorted({value for value in (max_red, max_blue) if value})
        if not reds or not blues:
            values_status = UNDECIDED
            values_delta = "另一种状态没被录到，无法比对像素数"
        elif (max_red, max_blue) == (
            MACOS_END_INK_PIXELS, MACOS_STANDBY_INK_PIXELS
        ):
            values_status = PASS
            values_delta = "与原版逐值相同"
        else:
            values_status = FAIL
            values_delta = "与原版不同"
        check.add(
            f"{label}-ink-values",
            values_status,
            f"{label}侧状态字在整个状态栏里的墨色像素数（取该状态最稳的一帧）",
            original=f"結束 {MACOS_END_INK_PIXELS} px / 待機 "
                     f"{MACOS_STANDBY_INK_PIXELS} px（macOS 门禁钉的值）",
            remake=f"結束 {max_red} px / 待機 {max_blue} px",
            delta=values_delta,
        )

        spans = sorted({
            item[2] for item in reds + blues if item[2] is not None
        })
        check.add(
            f"{label}-word-columns",
            PASS if spans and spans == [(104, 118)] else FAIL,
            f"{label}侧状态字画在状态栏的哪几列",
            original="列 104..118（macOS 侧同一套状态栏版式）",
            remake=f"列 {spans}" if spans else "没有取到状态字",
            delta="与原版同一位置" if spans and spans == [(104, 118)]
            else ("与原版不同" if spans else "—"),
        )

        if not reds or not blues:
            check.add(
                f"{label}-follows-unit", UNDECIDED,
                f"{label}侧录制里没有同时出现红 結束 与 蓝 待機 的帧，"
                "无法在同一版式下比较「状态字变了的同时显示的单位也变了」",
                missing=f"{label}侧录制缺"
                        + ("红 結束 帧" if not reds else "蓝 待機 帧"),
            )
            continue

        # The steady frames: the word at full opacity, not the switch.
        red_frame = max(reds, key=lambda item: item[4]["end_ink_pixels"])
        blue_frame = max(
            blues, key=lambda item: item[4]["standby_ink_pixels"]
        )
        word_left = min(red_frame[2][0], blue_frame[2][0])
        differences = _name_region_difference(
            load_image(red_frame[0]), load_image(blue_frame[0]), word_left
        )
        check.add(
            f"{label}-follows-unit",
            PASS if differences > 0 else FAIL,
            "状态字固定画在状态栏的同一个位置；把它所占的列排除后，"
            "剩下的单位名区域在「红 結束 帧」与「蓝 待機 帧」之间不同 "
            "⇒ 状态字跟着显示出来的那个单位走，而不是跟着画面阶段走",
            original="macOS 侧同样成立（门禁 tests/test_s49_rule_standby_state.py）",
            remake=f"{red_frame[0].name}（紅，結束）vs {blue_frame[0].name}"
                   f"（藍，待機）：状态字列 {red_frame[2]} / {blue_frame[2]}，"
                   f"单位名区域（列 0..{word_left}）差异 {differences} px",
            delta="状态字不同的同时显示的单位也不同 ⇒ 判据是单位状态"
                  if differences > 0 else "单位名区域相同 ⇒ 判据可能是画面阶段",
        )

    # The remake's own source decides the word; read the criterion out of the
    # function that draws it, the way the signed gate does.
    scene = Path(args.remake_root) / (
        "butano-sequel/game/src/battle_runtime_scene.cpp"
    )
    body = _status_panel_function(scene)
    if body is None:
        check.add(
            "remake-source-criterion", UNDECIDED,
            "重制侧的状态栏源码不在本机，或找不到 render_status_panel_text",
            missing=str(scene),
        )
    else:
        uses_unit_state = "unit->completed" in body
        uses_phase = "battle_scene_phase::unit_selection" in body
        check.add(
            "remake-source-criterion",
            PASS if uses_unit_state and not uses_phase else FAIL,
            "在 battle_runtime_scene.cpp 的 render_status_panel_text 函数体里"
            "找状态字的判据",
            original="判据＝单位是否已行动",
            remake=("按 unit->completed 判" if uses_unit_state
                    else "未找到单位状态判据")
                   + " / "
                   + ("按画面阶段判" if uses_phase else "未按画面阶段判"),
            delta="一致" if uses_unit_state and not uses_phase else "不一致",
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
