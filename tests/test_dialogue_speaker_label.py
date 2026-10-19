#!/usr/bin/env python3
"""The dialogue speaker label must render the speaker the original ROM names.

S49's third dialogue line used to be the one place where the remake's speaker
label disagreed with the original: the original shows 「佐助」 and the remake
showed 「巨助」, a two-character label that appears in no name table.  Three
separate defects stacked up there:

* 佐 was missing from the preparation font's crop table, so its atlas cell
  held a stale glyph;
* `battle_ui_dialogue_speaker_palette` remapped indices 14 and 6 instead of
  the 2 and 5 that atlas actually bakes, so the label came out grey;
* the text origin was four pixels left and one pixel low.

All three are fixed; this gate keeps them from coming back.

This gate keeps it visible: it compares the label strip of all three dialogue
lines against the original and names the offenders.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "artifacts/s49-fidelity-20261019-v1"
ORIGINAL = RUN / "walk-original-a24"
REMAKE = RUN / "walk-remake-dd-a30-d6fix"
LABEL_STRIP = (8, 100, 80, 126)
# original dialogue step -> remake dialogue step -> the speaker the original names
DIALOGUES = ((11, 14, "小樱"), (12, 15, "鸣人"), (13, 16, "佐助"))


def captures_available() -> bool:
    return all(
        (ORIGINAL / f"step-{o:02d}-A.png").is_file()
        and (REMAKE / f"step-{r:02d}-A.png").is_file()
        for o, r, _ in DIALOGUES
    )


class DialogueSpeakerLabelTest(unittest.TestCase):
    def setUp(self):
        if not captures_available():
            self.skipTest("the dialogue walks are not recorded")

    def test_every_dialogue_speaker_label_matches_the_original(self):
        failures = []
        for original_step, remake_step, speaker in DIALOGUES:
            left = Image.open(
                ORIGINAL / f"step-{original_step:02d}-A.png").convert("RGB")
            right = Image.open(
                REMAKE / f"step-{remake_step:02d}-A.png").convert("RGB")
            difference = ImageChops.difference(
                left.crop(LABEL_STRIP), right.crop(LABEL_STRIP))
            pixels = sum(
                1 for value in difference.get_flattened_data() if any(value)
            )
            if pixels:
                failures.append(f"{speaker}: {pixels} label pixels differ")
        self.assertEqual(
            failures, [],
            "every dialogue speaker label must match the original: "
            + "; ".join(failures))


if __name__ == "__main__":
    unittest.main()
