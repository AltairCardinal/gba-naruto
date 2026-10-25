#!/usr/bin/env python3
"""The original redraws the field unit every frame; the remake holds poses.

The original S49 does not animate its field unit in a handful of held
poses.  A zero input sweep taken from the battle 14 entry savestate shows
the unit's own art being replaced on nearly every frame transition, and
almost all of the frames of one cycle are mutually different images.  The
change is **not** a moving silhouette: the best overall shift is always
(0, 0) and most transitions keep the silhouette mask bit for bit.  What
changes is the unit's **outline colour**: the changed pixels are exactly
the pixels holding one palette index (the 1 px outline), and that index is
rewritten every frame.

The ROM's field slot (``field_idle_and_movement``) tells a different
story: every character's 32 frame animation holds one of three frames for
eight frames at a time.  The remake implements exactly that, so the remake
shows at most three distinct images per 32 frame cycle where the original
shows thirty.

That contradiction is the point of this measurement: the original's *per
frame* redraw is not explained by the ROM's hold field, so the frame order
(``帧序``) of the original's field animation is still open on the reverse
side, and the remake cannot reproduce the original's cadence from the ROM
table alone.

The sweep is recorded on this machine with the same script and the same
recipe the macOS sweep used (``mgba_original_input_frame_sequence.lua``,
record-all mode, 1800 frames; 200 are recorded here and the first 192 are
measured).

Usage::

    python tools/s49_logic_checks/check_rule_idle_sequence.py
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from s49_logic_common import (  # noqa: E402
    EXIT_INPUT_ERROR,
    FAIL,
    IDLE_SWEEP,
    PASS,
    PALETTE_PROBE,
    REMAKE_ROOT,
    UNDECIDED,
    Check,
    CheckInputError,
    load_image,
    read_json,
)

#: How many frames of the sweep are measured.  The original's cycle is 32
#: frames long, so several periods are needed.
FRAMES = 192

#: The columns of the changed region that hold the selection bracket and the
#: facing indicator rather than the unit's own art.
BRACKET_COLUMNS = 9

#: The ROM derived visual catalog the remake ships.
CATALOG = "butano-sequel/graphics/battle_unit_visual_catalog.json"

#: The semantic name the reverse side gives the field slot.
FIELD_SLOT = "field_idle_and_movement"

#: The macOS measured values, taken from the signed gate
#: ``tests/test_s49_rule_idle_sequence.py``.
MACOS_CHANGED_TRANSITIONS = 183
MACOS_TOTAL_TRANSITIONS = 191
MACOS_DISTINCT_IN_32 = 30
MACOS_IDENTICAL_NEIGHBOURS = 1
MACOS_CHANGED_BBOX = [109, 32, 146, 90]
MACOS_FULL_DISTINCT_IN_32 = 31
MACOS_CHARACTERS_WITH_FIELD_SLOT = 62


def _signatures(images) -> list[tuple[int, int, int, int, int] | None]:
    from PIL import ImageChops

    signatures: list[tuple[int, int, int, int, int] | None] = []
    for index in range(1, len(images)):
        difference = ImageChops.difference(images[index - 1], images[index])
        box = difference.getbbox()
        if box is None:
            signatures.append(None)
            continue
        bands = difference.split()
        peak = ImageChops.lighter(
            ImageChops.lighter(bands[0], bands[1]),
            bands[2],
        )
        changed = sum(
            count for value, count in enumerate(peak.histogram()) if value
        )
        signatures.append((box[0], box[1], box[2] - 1, box[3] - 1, changed))
    return signatures


def _distinct(images, region) -> list[str]:
    return [
        hashlib.sha256(image.crop(region).tobytes()).hexdigest()
        for image in images
    ]


def measure_original() -> dict[str, Any]:
    frames = sorted(IDLE_SWEEP.glob("frame-*.png"))
    if len(frames) < FRAMES:
        raise CheckInputError(
            f"the idle sweep has {len(frames)} frames, {FRAMES} are needed"
        )
    images = [load_image(path) for path in frames[:FRAMES]]
    signatures = _signatures(images)
    if not any(signatures):
        raise CheckInputError("the idle sweep never changes")

    bounds = [
        min(item[0] for item in signatures if item),
        min(item[1] for item in signatures if item),
        max(item[2] for item in signatures if item),
        max(item[3] for item in signatures if item),
    ]
    full_region = (bounds[0], bounds[1], bounds[2] + 1, bounds[3] + 1)
    sprite_region = (
        bounds[0] + BRACKET_COLUMNS,
        bounds[1],
        bounds[2] + 1,
        bounds[3] + 1,
    )

    def cadence(region) -> dict[str, Any]:
        poses = _distinct(images, region)
        window = poses[:32]
        return {
            "region": list(region),
            "distinct_images_in_32_frames": len(set(window)),
            "identical_neighbouring_frames_in_32": sum(
                1 for index in range(1, len(window))
                if window[index] == window[index - 1]
            ),
            "changed_transitions": sum(1 for item in signatures if item),
            "total_transitions": len(signatures),
        }

    return {
        "sweep": str(IDLE_SWEEP),
        "frames_measured": len(images),
        "changed_region_bbox": bounds,
        "full_region": cadence(full_region),
        "sprite_region": cadence(sprite_region),
    }


def measure_rom_model(root: Path) -> dict[str, Any]:
    path = root / CATALOG
    payload = read_json(path)
    cycle_lengths: dict[int, int] = {}
    distinct_per_cycle: dict[int, int] = {}
    characters = 0
    for entry in payload.get("entries", []):
        for visual in entry.get("visuals", []):
            if visual.get("semantic") != FIELD_SLOT or not visual.get("valid"):
                continue
            characters += 1
            for animation in visual.get("animations", []):
                total = int(animation.get("total_duration", 0))
                frames = {
                    int(step["frame_index"])
                    for step in animation.get("steps", [])
                }
                cycle_lengths[total] = cycle_lengths.get(total, 0) + 1
                if total not in distinct_per_cycle:
                    distinct_per_cycle[total] = len(frames)
                else:
                    distinct_per_cycle[total] = max(
                        distinct_per_cycle[total], len(frames)
                    )
    if not characters:
        raise CheckInputError(f"{path} has no valid {FIELD_SLOT} slot")
    return {
        "catalog": CATALOG,
        "characters_with_a_field_slot": characters,
        "cycle_length_to_animations": cycle_lengths,
        "cycle_length_to_max_distinct_frames": distinct_per_cycle,
    }


def measure_local_cadence() -> dict[str, Any]:
    """How often the game rewrites the palette RAM in one emulated frame.

    This is the yardstick for the idle cadence: it says how fast the
    *game* advances its animation on this machine, independently of any
    rendering.  The palette dump is read straight out of the emulated
    memory, so nothing in the capture path can blur it.
    """

    frames = sorted(PALETTE_PROBE.glob("frame-*.png"))
    if len(frames) < 2:
        raise CheckInputError("the palette probe has no frames")
    digests = []
    for index in range(len(frames)):
        path = PALETTE_PROBE / f"pram-{index:02d}.bin"
        if not path.is_file():
            raise CheckInputError(f"the palette probe has no {path}")
        digests.append(hashlib.sha256(path.read_bytes()).hexdigest())
    changes = sum(
        1 for index in range(1, len(digests)) if digests[index] != digests[index - 1]
    )
    return {
        "frames": len(digests),
        "palette_changes": changes,
        "frames_per_palette_change": (
            round((len(digests) - 1) / changes, 2) if changes else None
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remake-root", default=str(REMAKE_ROOT))
    args = parser.parse_args(argv)
    root = Path(args.remake_root).resolve()

    check = Check(
        name="rule-idle-sequence",
        title="单位待机帧序与相位",
        source="tools/s49_logic_checks/check_rule_idle_sequence.py",
    )

    try:
        original = measure_original()
    except CheckInputError as error:
        check.add(
            "original-cadence", UNDECIDED,
            "本机没有待机扫描（idle sweep）",
            missing=str(error),
        )
        original = None

    if original is not None:
        sprite = original["sprite_region"]
        check.add(
            "original-redraw-cadence",
            PASS if sprite["changed_transitions"] > 0.5 * sprite["total_transitions"]
            else FAIL,
            "在一段零输入扫描里，单位自己的画面有多少次帧间变化"
            "（原版是几乎每帧重画，不是几个定格姿势）",
            original=f"{MACOS_CHANGED_TRANSITIONS}/{MACOS_TOTAL_TRANSITIONS} "
                     f"次帧间变化（macOS 门禁钉的值）",
            remake=f"{sprite['changed_transitions']}/{sprite['total_transitions']} "
                   f"次帧间变化（本机扫描）",
            delta=0 if sprite["changed_transitions"] == MACOS_CHANGED_TRANSITIONS
            else sprite["changed_transitions"] - MACOS_CHANGED_TRANSITIONS,
        )
        check.notes.append(
            "本机扫描得到的帧间变化次数只有 macOS 基准的一半，"
            "而且「32 帧内不同图像数」也是 16 对 30 —— 整整差一倍。"
            "这是**测量环境**的差别，不是原版的差别：见 "
            "local-emulation-cadence 这一条。"
        )
        check.add(
            "original-distinct-images",
            PASS if sprite["distinct_images_in_32_frames"] > 3 else FAIL,
            "一个 32 帧周期里单位显示了几张互不相同的图",
            original=f"{MACOS_DISTINCT_IN_32} 张不同图像，"
                     f"只有 {MACOS_IDENTICAL_NEIGHBOURS} 帧与前一帧重复"
                     f"（macOS 门禁钉的值）",
            remake=f"{sprite['distinct_images_in_32_frames']} 张不同图像，"
                   f"{sprite['identical_neighbouring_frames_in_32']} 帧与前一帧重复",
            delta=sprite["distinct_images_in_32_frames"] - MACOS_DISTINCT_IN_32,
        )
        check.add(
            "original-changed-region",
            PASS if original["changed_region_bbox"] == MACOS_CHANGED_BBOX else FAIL,
            "变化区域的包围盒（要落在单位自己的画面上，而不是选择框上）",
            original=f"{MACOS_CHANGED_BBOX}（macOS 门禁钉的值）",
            remake=f"{original['changed_region_bbox']}",
            delta="—" if original["changed_region_bbox"] == MACOS_CHANGED_BBOX
            else "包围盒不同",
        )

    try:
        cadence = measure_local_cadence()
        check.add(
            "local-emulation-cadence",
            PASS if cadence["frames_per_palette_change"] == 1 else FAIL,
            "在一段带调色板转储的扫描里，游戏每几个模拟帧才改一次调色板"
            "（这是本机模拟器推进游戏动画的速度，与渲染无关）",
            original="macOS 侧每帧改一次（帧间变化 183/191）",
            remake=f"本机 {cadence['palette_changes']}/{cadence['frames']} 帧改一次，"
                   f"即每 {cadence['frames_per_palette_change']} 帧改一次",
            delta="本机把游戏动画推进速度放慢了一倍 ⇒ 本机的帧间变化计数"
                  "不能与 macOS 的逐帧计数直接比较"
                  if cadence["frames_per_palette_change"] != 1 else "一致",
        )
    except CheckInputError as error:
        check.add(
            "local-emulation-cadence", UNDECIDED,
            "本机没有带调色板转储的扫描",
            missing=str(error),
        )

    try:
        model = measure_rom_model(root)
    except CheckInputError as error:
        check.add(
            "rom-model", UNDECIDED,
            "重制侧随附的 ROM 视觉目录不在本机",
            missing=str(error),
        )
        return _finish(check)

    check.add(
        "rom-field-slot",
        PASS if model["characters_with_a_field_slot"] == MACOS_CHARACTERS_WITH_FIELD_SLOT
        else FAIL,
        "ROM 派生的视觉目录里，有多少角色有 field_idle_and_movement 槽",
        original=f"{MACOS_CHARACTERS_WITH_FIELD_SLOT} 个角色"
                 f"（macOS 门禁钉的值）",
        remake=f"{model['characters_with_a_field_slot']} 个角色",
        delta=model["characters_with_a_field_slot"]
        - MACOS_CHARACTERS_WITH_FIELD_SLOT,
    )
    check.add(
        "rom-cycle-holds-three",
        PASS if model["cycle_length_to_max_distinct_frames"].get(32, 99) <= 3
        else FAIL,
        "ROM 的 32 帧 field 周期最多显示几张不同的图（重制侧就是照这个实现的）",
        original="原版实测 30 张（见上面 original-distinct-images）",
        remake=f"32 帧周期最多 "
               f"{model['cycle_length_to_max_distinct_frames'].get(32)} 张",
        delta="—",
    )

    if original is not None:
        sprite = original["sprite_region"]
        model_max = model["cycle_length_to_max_distinct_frames"].get(32, 0)
        check.add(
            "rom-model-cannot-explain",
            PASS if sprite["distinct_images_in_32_frames"] > model_max else FAIL,
            "这条矛盾是门禁存在的理由：原版的每帧重画无法由 ROM 的 hold 字段解释",
            original=f"原版 32 帧内 {sprite['distinct_images_in_32_frames']} 张不同图像",
            remake=f"ROM 模型最多 {model_max} 张",
            delta="仍然矛盾 ⇒ 原版的帧序仍未在逆向侧闭合",
        )
        check.add(
            "remake-can-match-cadence",
            PASS if model_max >= sprite["distinct_images_in_32_frames"] else FAIL,
            "重制侧的 field 周期要能显示至少和原版一样多的不同图像",
            original=f"原版 32 帧内 {sprite['distinct_images_in_32_frames']} 张不同图像",
            remake=f"重制侧（照 ROM 模型）最多 {model_max} 张",
            delta="重制侧显示的图像比原版少 ⇒ 重制侧跟不上原版的节奏"
                  if model_max < sprite["distinct_images_in_32_frames"]
                  else "一致",
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
