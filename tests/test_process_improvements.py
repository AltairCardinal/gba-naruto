"""Tests for the process improvements absorbed from the third-party package.

Covered here:
  M1  synthetic fixture round-trip  (write known content -> read it back)
  M2  a build must only change bytes inside declared patch ranges
  M3  change-radius report
  M4  table bases come from the registry, not from editable content files
  M5  negative tests: the tools must refuse bad input
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import build_mod  # noqa: E402
import synthetic_fixture  # noqa: E402
import table_registry  # noqa: E402
from tools import text_codec  # noqa: E402


def _rom_available():
    try:
        text_codec.resolve_rom()
        return True
    except FileNotFoundError:
        return False


@unittest.skipUnless(_rom_available(), "base ROM not available")
class SyntheticFixtureTests(unittest.TestCase):
    """M1 - a table's format can be proven without the game."""

    @classmethod
    def setUpClass(cls):
        cls.rom_path = text_codec.resolve_rom()
        cls.mapping, _ = text_codec.load_mapping(cls.rom_path)

    def test_every_fixture_reads_back_what_was_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in sorted(synthetic_fixture.FIXTURES):
                result = synthetic_fixture.run_fixture(
                    name, self.rom_path, self.mapping, Path(tmp))
                failed = [c for c in result["checks"] if not c["pass"]]
                self.assertEqual(
                    [], failed,
                    f"fixture {name} failed:\n" + json.dumps(
                        failed, ensure_ascii=False, indent=2))

    def test_fixture_roms_do_not_touch_the_base_rom(self):
        """The fixture must never write to the real ROM."""
        before = self.rom_path.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            synthetic_fixture.run_fixture(
                "story_before", self.rom_path, self.mapping, Path(tmp))
        self.assertEqual(before, self.rom_path.read_bytes())

    def test_free_space_is_really_free(self):
        rom = bytearray(self.rom_path.read_bytes())
        with self.assertRaises(AssertionError):
            # A claim that runs past the end of the ROM must be rejected
            # rather than silently wrapping around.
            synthetic_fixture.free_space_claim(rom, 0x30000)

    def test_bad_opcode_is_reported_not_swallowed(self):
        """M5 - a malformed script must be reported, not silently accepted."""
        import decode_story_script as ds

        rom = bytearray(self.rom_path.read_bytes())
        # 0x7F is not in the opcode table.
        script = bytes([0x7F, 0x00])
        off = synthetic_fixture.free_space_claim(rom, len(script))
        rom[off:off + len(script)] = script
        nodes, issues = ds.walk(rom, [off], self.mapping)
        self.assertTrue(issues, "an unknown opcode must produce an issue")
        self.assertIn("unknown opcode", issues[0])


@unittest.skipUnless(_rom_available(), "base ROM not available")
class ChangeRadiusTests(unittest.TestCase):
    """M2 + M3 - the build may only change what it declared."""

    def test_changed_ranges_finds_only_real_differences(self):
        a = bytes(range(64))
        b = bytearray(a)
        b[10] = 0xFF
        b[20:24] = b"\x01\x02\x03\x04"
        ranges = build_mod.changed_ranges(a, bytes(b))
        self.assertIn((10, 11), ranges)
        self.assertIn((20, 24), ranges)
        # 1 byte at 10 plus 4 bytes at 20..24
        self.assertEqual(5, sum(e - s for s, e in ranges))

    def test_identical_buffers_have_no_changed_ranges(self):
        a = bytes(range(256)) * 40
        self.assertEqual([], build_mod.changed_ranges(a, a))

    def test_merge_and_subtract(self):
        self.assertEqual(
            [(0, 10), (20, 30)],
            build_mod.merge_ranges([(0, 5), (4, 10), (20, 30)]))
        self.assertEqual(
            [(5, 8)],
            build_mod.subtract_ranges([(0, 10)], [(0, 5), (8, 12)]))

    def test_undeclared_change_is_detected(self):
        """A byte that changed outside every declared range must show up."""
        declared = build_mod.merge_ranges([(0, 4)])
        diff = build_mod.merge_ranges([(0, 4), (100, 102)])
        undeclared = build_mod.subtract_ranges(diff, declared)
        self.assertEqual([(100, 102)], undeclared)


class TableRegistryTests(unittest.TestCase):
    """M4 - base pointers come from the registry, not from content files."""

    def test_content_banks_agree_with_the_registry(self):
        report = table_registry.verify_table_bases()
        strict = [r for r in report["rows"]
                  if not r["match"] and r["authoritative_verified"]]
        self.assertEqual(
            [], strict,
            "content bank base offsets disagree with the registry:\n"
            + "\n".join(f"  {r['bank']}: {r['declared_hex']} != "
                        f"{r['authoritative_hex']}" for r in strict))

    def test_poisoned_bank_offset_is_rejected(self):
        """The invariant must actually bite: move a bank and it has to fail."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = REPO / "sequel" / "content" / "maps" / "bank.json"
            dst = root / "maps"
            dst.mkdir(parents=True)
            data = json.loads(src.read_text(encoding="utf-8"))
            data["table_offset"] = 0x123456
            data["table_offset_hex"] = "0x123456"
            (dst / "bank.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

            report = table_registry.verify_table_bases(content_root=root)
            mismatches = [r for r in report["rows"] if not r["match"]]
            self.assertEqual(1, len(mismatches))
            self.assertEqual("maps", mismatches[0]["bank"])
            self.assertTrue(mismatches[0]["authoritative_verified"])
            self.assertEqual(0x53D910, mismatches[0]["authoritative"])

    def test_alias_conflicts_are_reported(self):
        """Known collisions (audio/palettes, items/skills, ...) must stay visible."""
        report = table_registry.verify_table_bases()
        by_address = {a["address"]: a["banks"] for a in report["alias_conflicts"]}
        self.assertIn("0x53f138", by_address)
        self.assertIn("audio", by_address["0x53f138"])
        self.assertIn("palettes", by_address["0x53f138"])

    def test_registry_covers_every_content_bank(self):
        declared = table_registry.load_bank_offsets()
        for bank in declared:
            self.assertIn(bank, table_registry.BANK_TO_REGISTRY,
                          f"{bank} has no registry entry")


class NegativeTestTests(unittest.TestCase):
    """M5 - the tools must refuse bad input, and refuse loudly."""

    def test_registry_rejects_unknown_bank_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "nonexistent").mkdir()
            report = table_registry.verify_table_bases(content_root=root)
            self.assertEqual([], report["mismatches"])

    def test_malformed_bank_json_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "maps").mkdir()
            (root / "maps" / "bank.json").write_text("{not json", encoding="utf-8")
            offsets = table_registry.load_bank_offsets(root)
            self.assertIn("maps", offsets)
            self.assertIsNone(offsets["maps"])


if __name__ == "__main__":
    unittest.main()
