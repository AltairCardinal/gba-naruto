#!/usr/bin/env python3
"""Tests for the multi-slot battle-message selector probe.

The runtime behaviour of the multi-slot stub is proved by an actual mGBA run
recorded in ``notes/evidence/d0-multi-slot-probe-20261020/``; the tests here
cover the hermetic properties (byte-level equivalence with the frozen legacy
stub, ROM isolation, slot-table placement, and the reader).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_battle_message_runtime_probe as legacy
from tools import build_battle_message_runtime_probe_slots as slots

BASE_ROM = ROOT / "rom/base.gba"
RECEIPT = Path("notes/evidence/d0-multi-slot-probe-20261020/runtime-verification.json")


class MultiSlotProbeTests(unittest.TestCase):
    def test_legacy_stub_is_byte_identical_to_the_frozen_probe(self):
        """The multi-slot tool must not drift from the frozen legacy stub."""
        self.assertEqual(slots.legacy_stub_bytes(), legacy._stub())
        self.assertEqual(len(slots.legacy_stub_bytes()), 68)

    def test_slot_stub_fits_the_measured_zero_run(self):
        stub = slots.slot_stub_bytes()
        self.assertLessEqual(len(stub), slots.STUB_ZERO_RUN)
        base = BASE_ROM.read_bytes()
        region = base[slots.STUB_OFFSET:slots.STUB_OFFSET + len(stub)]
        self.assertEqual(region, b"\x00" * len(stub))

    def test_control_rom_changes_only_the_hook_and_the_stub(self):
        base = BASE_ROM.read_bytes()
        rom = slots.build_probe(base)
        differences = {i for i, (a, b) in enumerate(zip(base, rom)) if a != b}
        hook = {slots.HOOK - slots.ROM_BASE + i for i in range(4)}
        stub = set(range(slots.STUB_OFFSET, slots.STUB_OFFSET + len(slots.slot_stub_bytes())))
        self.assertTrue(hook.issubset(differences))
        self.assertTrue(differences.issubset(hook | stub))
        self.assertEqual(
            rom[slots.STUB_OFFSET:slots.STUB_OFFSET + len(slots.slot_stub_bytes())],
            slots.slot_stub_bytes(),
        )

    def test_variant_changes_only_the_selected_message_pointer(self):
        base = BASE_ROM.read_bytes()
        control = slots.build_probe(base)
        rom = slots.build_probe(base, message_id=0, replacement_id=1)
        target = slots.MESSAGE_TABLE + 0 * 4
        differences = {i for i, (a, b) in enumerate(zip(control, rom)) if a != b}
        self.assertTrue(differences.issubset(set(range(target, target + 4))))
        self.assertTrue(differences)
        self.assertEqual(
            rom[target:target + 4], base[slots.MESSAGE_TABLE + 4:slots.MESSAGE_TABLE + 8]
        )

    def test_rejects_message_ids_outside_table(self):
        base = BASE_ROM.read_bytes()
        for message_id in (-1, slots.MESSAGE_COUNT):
            with self.assertRaisesRegex(ValueError, "message ID"):
                slots.build_probe(base, message_id=message_id, replacement_id=0)

    def test_slot_table_lives_in_the_measured_safe_region(self):
        start = slots.SLOT_TABLE
        end = start + slots.SLOT_TABLE_SIZE
        self.assertEqual(start % 4, 0, "slot table must be word aligned")
        self.assertGreaterEqual(start, slots.SAFE_REGION_START)
        self.assertLessEqual(end, slots.SAFE_REGION_END)
        self.assertLessEqual(end, slots.SCRATCH, "slot table must not reach the legacy scratch")
        self.assertEqual(slots.SLOT_COUNT, slots.MESSAGE_COUNT)
        self.assertEqual(slots.SLOT_SIZE * slots.SLOT_COUNT, 1264)

    def test_reader_reports_only_touched_slots(self):
        class FakeState:
            def __init__(self, payload: bytes) -> None:
                self.payload = payload

            def read_memory(self, address: int, size: int) -> bytes:
                if address != slots.SLOT_TABLE:
                    raise AssertionError("unexpected address")
                return self.payload[:size]

        empty = slots.read_slots(FakeState(b"\x00" * slots.SLOT_TABLE_SIZE))
        self.assertEqual(empty, [])
        payload = bytearray(b"\x00" * slots.SLOT_TABLE_SIZE)
        struct.pack_into("<II", payload, 5 * slots.SLOT_SIZE, 3, 0x085A1580)
        payload[5 * slots.SLOT_SIZE + 8:5 * slots.SLOT_SIZE + 16] = bytes.fromhex("8ddc816081608160")
        touched = slots.read_slots(FakeState(bytes(payload)))
        self.assertEqual(
            touched,
            [
                {
                    "message_id": 5,
                    "hit_count": 3,
                    "selected_pointer": 0x085A1580,
                    "target_prefix_hex": "8ddc816081608160",
                }
            ],
        )

    def test_recorded_runtime_verification_is_intact(self):
        path = ROOT / RECEIPT
        self.assertTrue(path.is_file(), f"missing runtime receipt: {RECEIPT}")
        receipt = json.loads(path.read_text())
        self.assertTrue(receipt["runtime_verified"])
        self.assertEqual(receipt["slot_table"], slots.SLOT_TABLE)
        self.assertEqual(receipt["slot_size"], slots.SLOT_SIZE)
        self.assertEqual(receipt["slot_count"], slots.SLOT_COUNT)
        self.assertEqual(receipt["stub_bytes"], len(slots.slot_stub_bytes()))
        rebuilt = slots.build_probe(BASE_ROM.read_bytes())
        self.assertEqual(
            hashlib.sha256(rebuilt).hexdigest(), receipt["probe_rom_sha256"]
        )
        self.assertTrue(receipt["screen_identical_to_archived_baseline"])
        self.assertEqual(len(receipt["touched_slots"]), 1)
        touched = receipt["touched_slots"][0]
        self.assertEqual(touched["message_id"], 0)
        self.assertEqual(touched["hit_count"], 1)
        self.assertEqual(touched["selected_pointer"], receipt["legacy_scratch"]["selected_pointer"])
        self.assertEqual(
            touched["target_prefix_hex"],
            receipt["legacy_scratch"]["target_prefix_hex"][:16],
        )


if __name__ == "__main__":
    unittest.main()
