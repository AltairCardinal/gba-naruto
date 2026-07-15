import hashlib
import unittest
from pathlib import Path

from tools import build_controller_path_runtime_probe as probe
from tools.published_call_observer import RECORD_SIZE, build_observer_stub
from tools.thumb_branch import decode_thumb_bl, encode_thumb_bl


ROOT = Path(__file__).resolve().parent.parent
EXPECTED = (
    (0x08073946, 0x0806F718, 0x0809E800, 0x0203F060, b"PCO1", 1),
    (0x08073A16, 0x08067158, 0x0809E880, 0x0203F080, b"AC01", 2),
    (0x08073A2E, 0x08067158, 0x0809E900, 0x0203F0A0, b"AC02", 3),
    (0x08073A3E, 0x08067158, 0x0809E980, 0x0203F0C0, b"AC03", 4),
    (0x08073A4A, 0x08067158, 0x0809EA00, 0x0203F0E0, b"AC04", 5),
)
EXPECTED_BASE_BYTES = (
    bytes.fromhex("fb f7 e7 fe"),
    bytes.fromhex("f3 f7 9f fb"),
    bytes.fromhex("f3 f7 93 fb"),
    bytes.fromhex("f3 f7 8b fb"),
    bytes.fromhex("f3 f7 85 fb"),
)


class ControllerPathRuntimeProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()

    def test_sites_match_checked_layout(self):
        self.assertEqual(
            EXPECTED,
            tuple(
                (
                    site.hook,
                    site.original,
                    site.stub,
                    site.scratch,
                    site.magic.to_bytes(4, "little"),
                    site.event_code,
                )
                for site in probe.OBSERVER_SITES
            ),
        )

    def test_base_callsite_bytes_decode_to_checked_targets(self):
        self.assertEqual(probe.BASE_SHA1, hashlib.sha1(self.base).hexdigest())
        for site, expected_bytes in zip(probe.OBSERVER_SITES, EXPECTED_BASE_BYTES):
            with self.subTest(site=site.name):
                offset = site.hook - probe.ROM_BASE
                actual = self.base[offset : offset + 4]
                self.assertEqual(expected_bytes, actual)
                first, second = int.from_bytes(actual[:2], "little"), int.from_bytes(
                    actual[2:], "little"
                )
                self.assertEqual(site.original, decode_thumb_bl(site.hook, first, second))
                self.assertEqual(expected_bytes, encode_thumb_bl(site.hook, site.original))

    def test_all_five_reserved_caves_are_zero(self):
        for site in probe.OBSERVER_SITES:
            with self.subTest(site=site.name):
                offset = site.stub - probe.ROM_BASE
                cave = self.base[offset : offset + probe.STUB_SIZE]
                self.assertEqual(probe.STUB_SIZE, len(cave))
                self.assertEqual(b"\x00" * probe.STUB_SIZE, cave)

    def test_stub_literals_and_event_codes_match_each_site(self):
        for site in probe.OBSERVER_SITES:
            with self.subTest(site=site.name):
                stub = build_observer_stub(site, probe.EVENT_COUNTER, probe.STUB_SIZE)
                self.assertIn(site.scratch.to_bytes(4, "little"), stub)
                self.assertIn(site.magic.to_bytes(4, "little"), stub)
                self.assertIn(site.event_code.to_bytes(4, "little"), stub)
                self.assertIn(probe.EVENT_COUNTER.to_bytes(4, "little"), stub)
                self.assertIn((site.original | 1).to_bytes(4, "little"), stub)

    def test_callsite_record_stub_and_counter_ranges_are_pairwise_disjoint(self):
        ranges = [(probe.EVENT_COUNTER, probe.EVENT_COUNTER + 4, "counter")]
        for site in probe.OBSERVER_SITES:
            ranges.extend(
                (
                    (site.hook, site.hook + 4, f"{site.name} callsite"),
                    (site.stub, site.stub + probe.STUB_SIZE, f"{site.name} stub"),
                    (site.scratch, site.scratch + RECORD_SIZE, f"{site.name} record"),
                )
            )
        for index, (start, end, name) in enumerate(ranges):
            for other_start, other_end, other_name in ranges[index + 1 :]:
                with self.subTest(first=name, second=other_name):
                    self.assertFalse(start < other_end and other_start < end)

    def test_patch_is_confined_to_five_callsites_and_five_stubs(self):
        built = probe.build_probe(self.base)
        allowed = []
        for site in probe.OBSERVER_SITES:
            allowed.extend(
                (
                    range(site.hook - probe.ROM_BASE, site.hook - probe.ROM_BASE + 4),
                    range(
                        site.stub - probe.ROM_BASE,
                        site.stub - probe.ROM_BASE + probe.STUB_SIZE,
                    ),
                )
            )
        changed = [index for index, pair in enumerate(zip(self.base, built)) if pair[0] != pair[1]]
        self.assertEqual(len(self.base), len(built))
        self.assertTrue(changed)
        self.assertTrue(all(any(index in region for region in allowed) for index in changed))
        for site in probe.OBSERVER_SITES:
            offset = site.hook - probe.ROM_BASE
            self.assertEqual(encode_thumb_bl(site.hook, site.stub), built[offset : offset + 4])

    def test_wrong_sha_fails_closed(self):
        corrupted = bytearray(self.base)
        corrupted[0] ^= 1
        with self.assertRaisesRegex(ValueError, "immutable base ROM"):
            probe.build_probe(bytes(corrupted))

    def test_corrupt_callsite_fails_closed(self):
        corrupted = bytearray(self.base)
        corrupted[probe.OBSERVER_SITES[2].hook - probe.ROM_BASE] ^= 1
        with self.assertRaisesRegex(ValueError, "action-2 call-site bytes"):
            probe.build_probe(bytes(corrupted), verify_sha1=False)

    def test_nonzero_cave_fails_closed(self):
        corrupted = bytearray(self.base)
        corrupted[probe.OBSERVER_SITES[4].stub - probe.ROM_BASE] = 1
        with self.assertRaisesRegex(ValueError, "action-4 stub region is not zero-filled"):
            probe.build_probe(bytes(corrupted), verify_sha1=False)


if __name__ == "__main__":
    unittest.main()
