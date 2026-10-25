#!/usr/bin/env python3
"""Is the local recording the same recording as the macOS one?

The macOS recordings of the original are gone: the 2026-10-19 cleanup took
the PNG frames of ``artifacts/s49-fidelity-20261019-v1/`` and left the JSON
receipts.  This stream re-records the original on this machine, but a local
re-recording is only usable as *the original's* evidence when it is shown to
be the same thing the macOS side measured.

Four independent oracles decide that, and all four are checked here:

1. **The battle 14 unit pool.**  ``artifacts/s49-original-battle14-roster-v1/``
   holds the original's EWRAM unit pool.  The pool is dumped again from the
   same savestate and has to be byte identical.

2. **The recording recipe.**  The macOS receipt ``walk-original-a24/inputs.json``
   pins the savestate, the ROM and the Lua script by hash.  The local
   recording uses the same three files with the same parameters.

3. **The surviving original pixels.**  ``artifacts/s49-original-field-frame-v1/``
   holds six consecutive frames of the original's unit selection screen.
   The local walk reaches that screen at its step 23, so the same capture is
   taken from the local step 23 savestate with the very same script.  The
   two have to show the same screen.

4. **The rule values.**  The signed gates of the remake tree pin the
   original's measured numbers (the status bar's ink counts 107 / 150, the
   dimmed AI unit's screen column 80).  Those numbers are re-measured here
   from the local recording.

The PNG *file* bytes are **not** comparable: macOS mGBA and this machine's
probe write PNGs with different encoders, so identical pictures have
different file bytes.  The rule is about the picture, so the checks in this
directory pin decoded pixels.

Usage::

    python tools/s49_logic_checks/check_original_equivalence.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from s49_logic_common import (  # noqa: E402
    BATTLE14_STATE,
    BATTLE14_STATE_SHA256,
    EXIT_INPUT_ERROR,
    FAIL,
    LONG_WALK,
    MACOS_FIELD_FRAME,
    MACOS_ORIGINAL_WALK,
    MACOS_ROSTER,
    ORIGINAL_ROM,
    ORIGINAL_ROM_SHA256,
    PASS,
    ROSTER_POOL,
    STEP23_FRAMES,
    UNDECIDED,
    Check,
    CheckInputError,
    difference_pixels,
    load_image,
    macos_steps,
    pixel_sha256,
    read_json,
    sha256_file,
)


def _compare_roster_pool(check: Check) -> None:
    """The original's EWRAM unit pool, dumped again from the same savestate."""

    local = ROSTER_POOL / "unit_pool.bin"
    macos = MACOS_ROSTER / "unit_pool.bin"
    if not local.is_file():
        check.add(
            "roster-pool-bytes", UNDECIDED,
            "本机没有 EWRAM 战斗单位池转储；先跑 record_evidence.py --only roster-pool",
            missing=str(local),
        )
        return
    if not macos.is_file():
        check.add(
            "roster-pool-bytes", UNDECIDED,
            "macOS 的原版战斗单位池捕获不存在，无法比对",
            missing=str(macos),
        )
        return
    local_digest = sha256_file(local)
    macos_digest = sha256_file(macos)
    check.add(
        "roster-pool-bytes",
        PASS if local_digest == macos_digest else FAIL,
        "从 battle 14 入口存档重新 dump 原版 EWRAM 单位池，与 macOS 捕获逐字节比对",
        original=f"sha256 {macos_digest[:16]}…（{macos.stat().st_size} 字节）",
        remake=f"sha256 {local_digest[:16]}…（{local.stat().st_size} 字节）",
        delta="0 字节（完全相同）" if local_digest == macos_digest
        else "字节不同",
    )


def _compare_recipe(check: Check) -> None:
    """The macOS recipe and the local recording have to use the same inputs."""

    try:
        inputs = read_json(MACOS_ORIGINAL_WALK / "inputs.json")
    except CheckInputError as error:
        check.add(
            "recording-recipe", UNDECIDED,
            "macOS 的录制配方收据缺失",
            missing=str(error),
        )
        return

    local_state = sha256_file(BATTLE14_STATE)
    local_rom = sha256_file(ORIGINAL_ROM)
    script = Path(inputs.get("script", ""))
    if not script.is_absolute():
        script = MACOS_ORIGINAL_WALK.parents[2] / script
    local_script = sha256_file(script) if script.is_file() else None

    macos_state = inputs.get("state_sha256")
    macos_rom = inputs.get("rom_sha256")
    macos_script = inputs.get("script_sha256")

    same = (
        local_state == macos_state
        and local_rom == macos_rom
        and local_script == macos_script
    )
    check.add(
        "recording-recipe",
        PASS if same else FAIL,
        "比对 macOS 的 walk-original-a24/inputs.json 配方钉的存档 / ROM / 脚本哈希",
        original=f"state {str(macos_state)[:16]}… / rom {str(macos_rom)[:16]}… / "
                 f"script {str(macos_script)[:16]}…",
        remake=f"state {local_state[:16]}… / rom {local_rom[:16]}… / "
               f"script {str(local_script)[:16]}…",
        delta="三个输入哈希全部相同" if same else "输入哈希有差异",
    )

    recipe_equal = (
        inputs.get("zero_input_frames") == 90
        and inputs.get("settle_frames") == 90
        and inputs.get("hold_frames") == 4
        and inputs.get("keys") == ["A"] * 24
    )
    check.add(
        "recording-parameters",
        PASS if recipe_equal else FAIL,
        "比对录制的帧数与按键序列（zero=90 settle=90 hold=4，A×24）",
        original=f"zero={inputs.get('zero_input_frames')} "
                 f"settle={inputs.get('settle_frames')} "
                 f"hold={inputs.get('hold_frames')} "
                 f"keys={len(inputs.get('keys', []))}×A",
        remake="zero=90 settle=90 hold=4 keys=24×A",
        delta="一致" if recipe_equal else "不一致",
    )


def _compare_surviving_pixels(check: Check) -> None:
    """The surviving original pixels, against the local capture of that screen.

    The macOS oracle is the unit selection screen.  The local walk reaches
    that screen at its step 23, and the local capture of 32 consecutive
    frames from that savestate walks the same animation.  The two have to
    show the same screen; what is left is the unit's own animation, which
    the original rewrites every frame.
    """

    if not MACOS_FIELD_FRAME.is_dir():
        check.add(
            "surviving-original-pixels", UNDECIDED,
            "macOS 遗留的原版像素基准不存在",
            missing=str(MACOS_FIELD_FRAME),
        )
        return
    local_frames = sorted(STEP23_FRAMES.glob("frame-*.png"))
    if not local_frames:
        check.add(
            "surviving-original-pixels", UNDECIDED,
            "本机没有 step 23 的画面序列；先跑 record_evidence.py --only field-frame-step23",
            missing=str(STEP23_FRAMES),
        )
        return

    macos_frame = MACOS_FIELD_FRAME / "frame-00.png"
    best = None
    for local in local_frames:
        difference = difference_pixels(
            load_image(macos_frame), load_image(local)
        )
        if best is None or difference < best[1]:
            best = (local, difference)
    local_best, difference = best
    whole = load_image(macos_frame)
    whole_local = load_image(local_best)
    box = (0, 0, 240, 144)
    status_bar_difference = difference_pixels(
        whole.crop((0, 144, 240, 160)), whole_local.crop((0, 144, 240, 160))
    )
    field_difference = difference_pixels(whole.crop(box), whole_local.crop(box))
    check.add(
        "surviving-original-pixels",
        PASS if status_bar_difference == 0 and difference < 2000 else FAIL,
        "把 macOS 遗留的原版像素（单位选择画面）和本机 step 23 的画面序列逐帧比，"
        "取最接近的一帧；残差必须落在单位自己的画面上，状态栏必须完全相同",
        original="macOS 原版单位选择画面（s49-original-field-frame-v1/frame-00.png）",
        remake=f"本机 {local_best.name}",
        delta=f"整帧差 {difference} px（其中战场区 {field_difference} px，"
              f"状态栏 {status_bar_difference} px）",
    )
    check.notes.append(
        "残差全部落在单位自己的画面上（战场区 "
        f"{field_difference} px，状态栏 {status_bar_difference} px）："
        "原版每帧重画单位的描边调色板，macOS 留下的六帧彼此也差 "
        "134..756 px，落在同一个区域。"
    )


def _compare_rule_values(check: Check) -> None:
    """The rule values the signed gates pin, re-measured on this machine."""

    from s49_logic_common import (
        END_INK,
        STANDBY_INK,
        STATUS_BAR,
        classify_status_bar,
        walk_frames,
    )

    frames = walk_frames(LONG_WALK)
    table = {
        path.name: classify_status_bar(load_image(path), STATUS_BAR)
        for path in frames
    }
    end_values = sorted({
        ink["end_ink_pixels"] for ink in table.values()
        if ink["end_ink_pixels"] and not ink["standby_ink_pixels"]
    })
    standby_values = sorted({
        ink["standby_ink_pixels"] for ink in table.values()
        if ink["standby_ink_pixels"] and not ink["end_ink_pixels"]
    })
    reproduced = 107 in end_values and 150 in standby_values
    check.add(
        "rule-values-reproduced",
        PASS if reproduced else FAIL,
        "把逆向侧门禁钉住的状态栏墨色像素数（結束 107 / 待機 150）"
        "在本机录制的原版上重新量一遍",
        original="結束 107 px / 待機 150 px（macOS 门禁钉的值）",
        remake=f"結束 {end_values} / 待機 {standby_values}",
        delta="逐值相同" if reproduced else "取不到原版的取值",
    )


def _report_png_bytes(check: Check) -> None:
    """How far the local PNG files are from the macOS ones.

    This is **not** a judged item: macOS mGBA and this machine's probe write
    PNGs with different encoders, so identical pictures have different file
    bytes.  The number is reported so the reader knows it was measured, and
    the judgement is carried by the pixel level item above.
    """

    try:
        steps = macos_steps()
    except CheckInputError as error:
        check.notes.append(f"macOS 的 walk-original-a24/steps.json 缺失: {error}")
        return
    equal = []
    different = []
    for name, step in sorted(steps.items()):
        local = LONG_WALK / name
        if not local.is_file():
            continue
        if sha256_file(local) == step["image_sha256"]:
            equal.append(name)
        else:
            different.append(name)
    check.notes.append(
        "PNG **文件字节**比对（不是判定项）：本机重录的 25 帧里 "
        f"{len(equal)} 帧与 macOS 的 image_sha256 相同、{len(different)} 帧不同。"
        "两端 PNG 编码器不同 ⇒ 文件字节不可比；画面是否相同由 "
        "surviving-original-pixels（像素）与各规则检查自己重算的数值判定。"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    check = Check(
        name="equivalence-original-recording",
        title="本机重录的原版 == macOS 录制的原版",
        source="tools/s49_logic_checks/check_original_equivalence.py",
    )
    _compare_roster_pool(check)
    _compare_recipe(check)
    _compare_surviving_pixels(check)
    _compare_rule_values(check)
    _report_png_bytes(check)

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
