#!/usr/bin/env python3
"""Two decisive checks for the S1 / S4 work.

**Check A (S4) — the 1:1 layer composite.**  The ``scenario_41_*`` layers are
Butano ``bpp_8`` regular BGs, where **index 0 is the transparent colour**, so
the correct composite of the three priority layers is *topmost non-transparent
wins*, not the opaque paste wave 9's V4 tool uses.  This tool computes that
correct composite and compares it against the original's own reference screen.

**Check B (S1) — can the remake render the transcribed dialogue?**  The
remake's presentation font is indexed by **Shift-JIS codes** (the original's
own dialogue font, 862 codes).  This tool encodes the transcribed dialogue into
Shift-JIS and reports which codes the font is missing.

Usage::

    python tools/s49_u3_settlement/u3_decisive_checks.py
"""

from __future__ import annotations

import pathlib
import re

from PIL import Image, ImageChops

GRAPHICS = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics")
W4 = pathlib.Path(r"D:\Github\gba-naruto\build\s49-victory-capture\w4")
GLYPH_HEADER = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include"
    r"\konoha\generated_battle_presentation_glyph_content.h")

DIALOGUE = (
    "跟你説已經没事了吧！",
    "嗚哇！別过来呀！！",
    "没关系了啦，已经没有蜜蜂了！不要害怕了！！",
    "嗚哇！！！",
    "木叶丸！！",
    "喂，他跑到森林的深处了！",
    "不好，看样子那家伙快不行了……你们快去把他追回来。",
)

LEVEL_UP = (
    "漩涡鸣人的LV升到6级了",
    "螺旋丸的现在可以修炼了",
    "宁智波佐助的LV升到5级了",
    "动作训练班可以修炼了",
    "春野樱的LV升到6级了",
    "忍者知识现在可以修炼了",
)


def alpha_compose(names, size=(240, 160)):
    """Compose the priority layers the way the GBA does: index 0 is
    transparent, so the **topmost non-transparent** pixel wins."""
    canvas = None
    for name in names:
        with Image.open(GRAPHICS / name) as image:
            paletted = image.convert("P")
            indices = paletted.getdata()
            rgb = paletted.convert("RGB")
            pixels = list(rgb.getdata())
            opaque = [index != 0 for index in indices]
        if canvas is None:
            canvas = [(0, 0, 0)] * len(pixels)
        # The layer list is bottom-first, so later layers are in front.
        for position, is_opaque in enumerate(opaque):
            if is_opaque:
                canvas[position] = pixels[position]
    composed = Image.new("RGB", (256, 256))
    composed.putdata(canvas)
    return composed.crop((0, 0, size[0], size[1]))


def diff(left, right):
    difference = ImageChops.difference(left, right)
    bands = difference.split()
    merged = ImageChops.lighter(
        ImageChops.lighter(bands[0], bands[1]), bands[2])
    box = merged.getbbox()
    if box is None:
        return 0, 0, None
    data = merged.crop(box).tobytes()
    v4_metric = 0
    for index in range(0, len(data) - 2, 3):
        if data[index] or data[index + 1] or data[index + 2]:
            v4_metric += 1
    true_pixels = sum(1 for value in data if value)
    return v4_metric, true_pixels, box


def check_a() -> None:
    print("== Check A: the 1:1 layer composite (index 0 = transparent)")
    cases = (
        ("s41 result bottom+middle+top",
         ("scenario_41_result_bottom.bmp", "scenario_41_result_middle.bmp",
          "scenario_41_result_top.bmp"), "ref-scenario-41-result"),
        ("s41 result bottom+middle",
         ("scenario_41_result_bottom.bmp", "scenario_41_result_middle.bmp"),
         "ref-scenario-41-result"),
        ("s41 level_up_1 bottom+middle+top",
         ("scenario_41_level_up_1_bottom.bmp",
          "scenario_41_level_up_1_middle.bmp",
          "scenario_41_level_up_1_top.bmp"), "ref-scenario-41-level-up-1"),
        ("s41 level_up_1 bottom+middle",
         ("scenario_41_level_up_1_bottom.bmp",
          "scenario_41_level_up_1_middle.bmp"), "ref-scenario-41-level-up-1"),
    )
    for label, layers, reference in cases:
        truth_path = W4 / reference / "screen.png"
        if not truth_path.is_file():
            print(f"  {label}: reference missing")
            continue
        with Image.open(truth_path) as image:
            truth = image.convert("RGB")
        composed = alpha_compose(layers)
        v4_metric, true_pixels, box = diff(composed, truth)
        print(f"  {label:34} v4={v4_metric:6d} true={true_pixels:6d} "
              f"bbox={box}")


def check_b() -> None:
    print("\n== Check B: Shift-JIS coverage of the transcribed text")
    text = GLYPH_HEADER.read_text(encoding="utf-8")
    body = text.split("battle_presentation_glyph_codes = {{", 1)[1]
    body = body.split("}};", 1)[0]
    codes = {int(code, 16) for code in re.findall(r"0x([0-9A-Fa-f]{4})", body)}
    print(f"  presentation font codes: {len(codes)}")

    missing: set[int] = set()
    total = 0
    for line in (*DIALOGUE, *LEVEL_UP):
        for character in line:
            encoded = character.encode("cp932", errors="replace")
            if len(encoded) == 1:
                continue
            total += 1
            code = (encoded[0] << 8) | encoded[1]
            if code not in codes:
                missing.add(code)
    print(f"  encoded characters: {total}")
    print(f"  missing codes: {len(missing)}")
    if missing:
        sample = sorted(missing)[:12]
        print(f"  sample: {[f'0x{code:04X}' for code in sample]}")
        for code in sample:
            try:
                character = bytes([code >> 8, code & 0xFF]).decode("cp932")
            except UnicodeDecodeError:
                character = "?"
            print(f"    0x{code:04X} = {character!r}")


def main() -> int:
    check_a()
    check_b()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
