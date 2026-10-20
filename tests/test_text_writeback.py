"""Tests for the ROM text write path.

The point of these tests is the one the old cp932 pipeline never made:
what the build writes must read back as the text the author wrote.

See notes/text-writeback-migration-20261020.md.
"""
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools import text_codec  # noqa: E402
from tools.import_dialogue import import_dialogue  # noqa: E402

BANK = REPO / "sequel" / "content" / "text" / "dialogue-bank.json"
CONTENT = REPO / "sequel" / "content" / "text" / "dialogue-patches.json"


def _rom_available():
    try:
        return text_codec.resolve_rom() is not None
    except FileNotFoundError:
        return False


@unittest.skipUnless(_rom_available(), "base ROM not available")
class FontEncodingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom_path = text_codec.resolve_rom()
        cls.rom = cls.rom_path.read_bytes()
        cls.mapping, cls.meta = text_codec.load_mapping(cls.rom_path)

    def test_mapping_covers_the_whole_font(self):
        self.assertEqual(26, self.meta["catalog_segments_total"])
        self.assertEqual(
            self.meta["catalog_segments_total"],
            self.meta["catalog_segments_matched"],
            "font segment fingerprints must all match",
        )
        self.assertGreater(len(self.mapping), 4000)

    def test_known_rom_text_decodes_to_real_chinese(self):
        text, _ = text_codec.decode_tokens(self.rom, 0x459414, self.mapping)
        self.assertEqual("把九尾妖狐封印在鸣人体内的\n是第几代火影？", text)

    def test_encode_decode_roundtrip(self):
        for text in ("漩涡鸣人", "第一章", "边境情报异常\n小队被派往警戒线", "保护运输卷轴！"):
            raw = text_codec.encode(text, "font", self.mapping)
            self.assertEqual(text, text_codec.decode(raw, self.mapping))

    def test_unencodable_character_is_rejected(self):
        # A character outside the ROM's font must fail loudly rather than be
        # written as a wrong glyph.
        with self.assertRaises(KeyError):
            text_codec.encode("龘", "font", self.mapping)

    def test_legacy_encoding_warns(self):
        with self.assertWarns(DeprecationWarning):
            text_codec.encode("abc", "cp932", self.mapping)

    def test_rom_text_reencodes_to_the_exact_original_bytes(self):
        """Independent check of the code->character table: every bank entry's
        own text must re-encode to the bytes the ROM already stores."""
        bank = json.loads(BANK.read_text(encoding="utf-8"))
        for entry in bank["entries"]:
            offset = int(entry["offset"])
            max_bytes = int(entry["max_bytes"])
            actual = self.rom[offset:offset + max_bytes]
            self.assertEqual(
                entry["expected_hex"].lower(), actual.hex(),
                f"{entry['id']}: bank expected_hex is stale",
            )
            text, _ = text_codec.decode_bounded(
                self.rom, offset, max_bytes, self.mapping
            )
            encoded = text_codec.encode(text, "font", self.mapping)
            self.assertEqual(
                actual[:len(encoded)], encoded,
                f"{entry['id']}: ROM text does not re-encode to its own bytes",
            )


@unittest.skipUnless(_rom_available(), "base ROM not available")
class DialogueWritebackTests(unittest.TestCase):
    def setUp(self):
        self.content = json.loads(CONTENT.read_text(encoding="utf-8"))
        self.authored = {e["id"]: e["text"] for e in self.content["entries"]}
        self.mapping, _ = text_codec.load_mapping()

    def test_bank_declares_the_font_encoding(self):
        bank = json.loads(BANK.read_text(encoding="utf-8"))
        for entry in bank["entries"]:
            self.assertEqual("font", entry["encoding"], entry["id"])

    def test_patches_fit_their_slots(self):
        patches = import_dialogue(BANK, CONTENT)
        bank = json.loads(BANK.read_text(encoding="utf-8"))
        bank_map = {e["id"]: e for e in bank["entries"]}
        for patch in patches:
            eid = patch["source_entry"]
            if patch.get("sub_type") == "pointer_redirect":
                continue
            max_bytes = int(bank_map[eid]["max_bytes"])
            self.assertLessEqual(len(bytes.fromhex(patch["after_hex"])), max_bytes, eid)

    def test_every_patched_slot_renders_the_authored_text(self):
        """The end-to-end guarantee: bytes written -> text the game draws."""
        patches = import_dialogue(BANK, CONTENT)
        rom = bytearray(text_codec.resolve_rom().read_bytes())
        for patch in patches:
            eid = patch["source_entry"]
            offset = int(patch["offset"])
            length = len(bytes.fromhex(patch["after_hex"]))
            rom[offset:offset + length] = bytes.fromhex(patch["after_hex"])
            rendered = text_codec.decode(bytes(rom[offset:offset + length]), self.mapping)
            self.assertEqual(self.authored[eid], rendered, eid)
            self.assertNotIn("{字", rendered, f"{eid}: unresolved glyph")

    def test_legacy_pipeline_would_have_written_garbage(self):
        """Regression guard for the bug this migration fixed: the old content
        was Japanese text cp932-encoded into a Chinese font ROM."""
        patches = import_dialogue(BANK, CONTENT)
        for patch in patches:
            eid = patch["source_entry"]
            legacy = bytes.fromhex(patch["after_hex"]).decode("cp932", errors="replace")
            self.assertNotEqual(
                self.authored[eid], legacy,
                f"{eid}: cp932 should not reproduce the authored text",
            )

    def test_variable_length_redirect_renders_the_authored_text(self):
        """The variable-length path (text into free space + pointer redirect)
        must render the authored text too.

        This path had never run: `dialogue_var` is not enabled in the patch
        manifest, and the module referenced an undefined ROM_BASE."""
        import tempfile

        from tools.import_dialogue_var import FREE_SPACE_START, import_dialogue_variable

        long_text = (
            "边境情报异常\n小队被派往南部警戒线展开搜索！"
            "目标是不明忍者部队的运输队。"
        )
        content = json.loads(CONTENT.read_text(encoding="utf-8"))
        for entry in content["entries"]:
            if entry["id"] == "group0.main":
                entry["text"] = long_text

        with tempfile.TemporaryDirectory() as tmp:
            content_path = Path(tmp) / "content.json"
            content_path.write_text(
                json.dumps(content, ensure_ascii=False), encoding="utf-8"
            )
            patches = import_dialogue_variable(
                BANK, content_path, FREE_SPACE_START
            )

        rom = bytearray(text_codec.resolve_rom().read_bytes())
        for patch in patches:
            if patch["type"] == "bytes":
                off = int(patch["offset"])
                raw = bytes.fromhex(patch["after_hex"])
                rom[off:off + len(raw)] = raw
            else:
                off = int(patch["pointer_table_offset"])
                rom[off:off + 4] = bytes.fromhex(patch["new_pointer_hex"])

        bank = json.loads(BANK.read_text(encoding="utf-8"))
        entry = next(e for e in bank["entries"] if e["id"] == "group0.main")
        table_off = int(entry["table_offset"])
        pointer = int.from_bytes(rom[table_off:table_off + 4], "little")
        text_off = pointer - 0x08000000
        rendered = text_codec.decode(
            bytes(rom[text_off:text_off + 160]), self.mapping
        )
        self.assertEqual(long_text, rendered)


if __name__ == "__main__":
    unittest.main()
