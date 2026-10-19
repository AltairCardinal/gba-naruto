import unittest
from pathlib import Path

from tools.build_training_levels_runtime_probe import (
    CALL_SITES,
    CONSUMER_HOOK,
    CONSUMER_RECORD_SIZE,
    CONSUMER_SCRATCH,
    CONSUMER_STUB,
    CONSUMER_STUB_SIZE,
    CONFIRM_HOOK,
    CONFIRM_ORIGINAL,
    CONFIRM_STUB,
    CONFIRM_STUB_SIZE,
    EVENT_COUNTER,
    ROM_BASE,
    STUB_SIZE,
    build_confirm_stub,
    build_probe,
    build_consumer_stub,
)
from tools.published_call_observer import build_observer_stub
from tools.thumb_branch import encode_thumb_bl


ROOT = Path(__file__).resolve().parents[1]


class TrainingLevelsRuntimeProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()

    def test_patches_only_checked_calls_consumer_instruction_and_zero_caves(self):
        output = build_probe(self.base)
        changed = {i for i, (before, after) in enumerate(zip(self.base, output)) if before != after}
        allowed = set()
        for site in CALL_SITES:
            allowed.update(range(site.hook - ROM_BASE, site.hook - ROM_BASE + 4))
            allowed.update(range(site.stub - ROM_BASE, site.stub - ROM_BASE + STUB_SIZE))
            self.assertEqual(
                output[site.hook - ROM_BASE : site.hook - ROM_BASE + 4],
                encode_thumb_bl(site.hook, site.stub),
            )
            self.assertEqual(
                output[site.stub - ROM_BASE : site.stub - ROM_BASE + STUB_SIZE],
                build_observer_stub(site, EVENT_COUNTER, STUB_SIZE),
            )
        allowed.update(range(CONFIRM_HOOK - ROM_BASE, CONFIRM_HOOK - ROM_BASE + 4))
        allowed.update(range(CONFIRM_STUB - ROM_BASE, CONFIRM_STUB - ROM_BASE + CONFIRM_STUB_SIZE))
        self.assertEqual(
            output[CONFIRM_HOOK - ROM_BASE : CONFIRM_HOOK - ROM_BASE + 4],
            encode_thumb_bl(CONFIRM_HOOK, CONFIRM_STUB),
        )
        self.assertEqual(
            output[CONFIRM_STUB - ROM_BASE : CONFIRM_STUB - ROM_BASE + CONFIRM_STUB_SIZE],
            build_confirm_stub(),
        )
        allowed.update(range(CONSUMER_HOOK - ROM_BASE, CONSUMER_HOOK - ROM_BASE + 4))
        allowed.update(range(CONSUMER_STUB - ROM_BASE, CONSUMER_STUB - ROM_BASE + CONSUMER_STUB_SIZE))
        self.assertTrue(changed)
        self.assertLessEqual(changed, allowed)
        self.assertEqual(
            output[CONSUMER_HOOK - ROM_BASE : CONSUMER_HOOK - ROM_BASE + 4],
            encode_thumb_bl(CONSUMER_HOOK, CONSUMER_STUB),
        )
        self.assertEqual(
            output[CONSUMER_STUB - ROM_BASE : CONSUMER_STUB - ROM_BASE + CONSUMER_STUB_SIZE],
            build_consumer_stub(),
        )

    def test_consumer_stub_replays_original_values_and_publishes_full_record(self):
        stub = build_consumer_stub()
        self.assertEqual(len(stub), CONSUMER_STUB_SIZE)
        self.assertIn((0x085459C8).to_bytes(4, "little"), stub)
        self.assertIn(CONSUMER_SCRATCH.to_bytes(4, "little"), stub)
        self.assertIn(EVENT_COUNTER.to_bytes(4, "little"), stub)
        self.assertGreaterEqual(CONSUMER_RECORD_SIZE, 48)
        self.assertEqual(stub[-4:], b"\x00" * 4)

    def test_confirm_stub_records_all_four_arguments_before_tail_call(self):
        stub = build_confirm_stub()
        self.assertEqual(len(stub), CONFIRM_STUB_SIZE)
        self.assertIn((CONFIRM_ORIGINAL | 1).to_bytes(4, "little"), stub)
        for store in (bytes.fromhex("a060"), bytes.fromhex("e060"), bytes.fromhex("2061"), bytes.fromhex("6061")):
            self.assertIn(store, stub)

    def test_rejects_tampered_call_consumer_or_cave(self):
        for offset, message in (
            (CALL_SITES[0].hook - ROM_BASE, "call-site"),
            (CONFIRM_HOOK - ROM_BASE, "confirm call-site"),
            (CONSUMER_HOOK - ROM_BASE, "consumer"),
            (CONSUMER_STUB - ROM_BASE, "consumer stub"),
        ):
            with self.subTest(offset=hex(offset)):
                tampered = bytearray(self.base)
                tampered[offset] ^= 0x01
                with self.assertRaisesRegex(ValueError, message):
                    build_probe(bytes(tampered), verify_sha1=False)


if __name__ == "__main__":
    unittest.main()
