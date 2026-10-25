"""The original's dialogue timeline at one frame per capture.

Reads the fine recording produced by ``record_fine_original.py`` (one capture
per GBA frame) and reports the events of the dialogue:

* the first frame a line's first glyph is on screen,
* the frame the line stops growing,
* the frame the advance icon appears and disappears,
* the frame the confirm key goes down (the semantic walk presses it every
  ``hold + settle`` frames).

Every number is a GBA frame of the original's own timeline.
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image

INK = (57, 66, 57)
TEXT_BAND = (116, 140)
ICON_BOX = (180, 136, 240, 160)
ICON_DARK_LIMIT = 160

ZERO_INPUT_FRAMES = 90
HOLD_FRAMES = 4
SETTLE_FRAMES = 90
BEAT_FRAMES = HOLD_FRAMES + SETTLE_FRAMES


def press_frame(beat: int) -> int:
    return ZERO_INPUT_FRAMES + BEAT_FRAMES * (beat - 1)


def load(src: pathlib.Path, index: int):
    png = src / f"step-{index:05d}-in.png"
    if not png.exists():
        return None
    with Image.open(png) as handle:
        return handle.convert("RGB")


def text_signature(image: Image.Image) -> tuple[int, int, int]:
    """(ink pixels, first ink column, last ink column) of the text band."""
    pixels = image.load()
    count = 0
    first = -1
    last = -1
    for y in range(TEXT_BAND[0], min(TEXT_BAND[1], image.height)):
        for x in range(image.width):
            if pixels[x, y] == INK:
                count += 1
                if first < 0:
                    first = x
                last = x
    return count, first, last


def icon_dark(image: Image.Image) -> int:
    pixels = image.load()
    count = 0
    for y in range(ICON_BOX[1], min(ICON_BOX[3], image.height)):
        for x in range(ICON_BOX[0], ICON_BOX[2]):
            if max(pixels[x, y]) < ICON_DARK_LIMIT:
                count += 1
    return count


def main() -> int:
    src = pathlib.Path(sys.argv[1])
    base = int(sys.argv[2])
    presses = {press_frame(beat): beat for beat in range(1, 64)}
    previous = None
    for index in range(0, 2000):
        image = load(src, index)
        if image is None:
            break
        frame = base + index
        count, first, last = text_signature(image)
        icon = icon_dark(image)
        mark = ""
        if frame in presses:
            mark = f" PRESS(beat {presses[frame]})"
        if previous is None:
            print(f"f={frame:5d} ink={count:5d} x{first:4d}..{last:4d} "
                  f"icon={icon:4d}{mark}")
        else:
            old_count, old_first, old_last, old_icon = previous
            if count != old_count or icon != old_icon or first != old_first:
                print(f"f={frame:5d} ink={count:5d} x{first:4d}..{last:4d} "
                      f"icon={icon:4d}{mark}"
                      f"   d_ink={count - old_count:+5d} "
                      f"d_icon={icon - old_icon:+5d}")
        previous = (count, first, last, icon)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
