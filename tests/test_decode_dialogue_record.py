#!/usr/bin/env python3
"""Regression tests for the dialogue-record decoder.

2026-10-21 merge: this test used to pin the *retired* hand-made SJIS
mapping (19 entries) and the claim that the font code ``0x8B62`` was an
unresolved delimiter.  Both were falsified and are now pinned in their
corrected form:

* the ROM stores the game's own double-byte font codes, not Shift-JIS --
  see ``notes/font-encoding.md``;
* ``0x8B62`` is the font code for U+7684 ("的"), not a delimiter; splitting
  on it chopped sentences in the middle of a word;
* the mapping now comes from ``tools/text_codec.py`` (the ROM's own font
  catalogue, 4261 codes) instead of a hand-made table whose values were
  themselves double-encoded mojibake.

The decoder therefore splits on *control codes*, renders 0x0A as a newline
inside the segment, and reports font codes the ROM's font cannot draw.
"""

from __future__ import annotations

import unittest


class DialogueRecordDecoderTests(unittest.TestCase):
    def test_mapping_comes_from_the_rom_font_catalogue(self):
        from tools.text_codec import load_mapping

        mapping, meta = load_mapping()
        self.assertGreater(len(mapping), 4000)
        self.assertEqual(
            meta["catalog_segments_total"],
            meta["catalog_segments_matched"],
            "every font segment fingerprint must match",
        )
        # The retired 19-entry hand-made table is gone for good.
        self.assertNotEqual(len(mapping), 19)

    def test_8b62_is_the_character_de_not_a_delimiter(self):
        from tools.text_codec import load_mapping

        mapping, _ = load_mapping()
        self.assertEqual("的", mapping[0x8B62])

    def test_record_renders_the_rom_font_codes(self):
        from tools.decode_dialogue_record import decode_record
        from tools.text_codec import load_mapping

        mapping, _ = load_mapping()
        segments, unknown = decode_record(
            bytes.fromhex("92D78B620A95C4"),
            mapping,
        )
        # 0x92D7 = 内, 0x8B62 = 的, 0x0A = newline, 0x95C4 = 是
        self.assertEqual(["内的\n是"], [s["text"] for s in segments])
        self.assertEqual([], unknown)

    def test_ideographic_space_is_rendered(self):
        from tools.decode_dialogue_record import decode_record
        from tools.text_codec import load_mapping

        mapping, _ = load_mapping()
        segments, unknown = decode_record(bytes.fromhex("8140"), mapping)
        self.assertEqual(["　"], [s["text"] for s in segments])
        self.assertEqual([], unknown)

    def test_unknown_font_codes_are_reported_not_dropped(self):
        from tools.decode_dialogue_record import decode_record
        from tools.text_codec import load_mapping

        mapping, _ = load_mapping()
        # 0x8001 is a valid lead byte but not a code the ROM's font can draw.
        segments, unknown = decode_record(bytes.fromhex("8001"), mapping)
        self.assertEqual([0x8001], unknown)
        self.assertEqual(1, len(segments))
        self.assertIn("{字8001}", segments[0]["text"])


if __name__ == "__main__":
    unittest.main()
