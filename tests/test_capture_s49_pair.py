#!/usr/bin/env python3
"""Paired original/remake captures must pin every input and never reuse a run."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.butano.capture_s49_pair import (
    DEFAULT_MGBA,
    GUARD,
    RECORD_SCRIPT,
    CaptureError,
    guard_command,
    record_environment,
    record_pair,
    save_state_hash,
    sha256_file,
)

MGBA_AVAILABLE = DEFAULT_MGBA.is_file()
ROOT = Path(__file__).resolve().parents[1]


class PairContractTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def dummy(self, name: str) -> Path:
        path = self.root / name
        path.write_bytes(name.encode("utf-8"))
        return path

    def test_record_environment_pins_state_hash_and_input_contract(self):
        state = self.dummy("state.ss9")
        environment = record_environment(
            output_dir=self.root / "out",
            done_marker=self.root / "out/done.json",
            state=state,
            rom=self.dummy("rom.gba"),
            key="A",
            hold_frames=4,
            frame_count=90,
            pre_input_frames=12,
        )
        self.assertEqual(environment["MGBA_ORIGINAL_INPUT_SEQUENCE_RECORD_ALL"], "1")
        self.assertEqual(environment["MGBA_ORIGINAL_INPUT_SEQUENCE_KEY"], "A")
        self.assertEqual(environment["MGBA_ORIGINAL_INPUT_SEQUENCE_HOLD_FRAMES"], "4")
        self.assertEqual(environment["MGBA_ORIGINAL_INPUT_SEQUENCE_FRAME_COUNT"], "90")
        self.assertEqual(environment["MGBA_ORIGINAL_INPUT_SEQUENCE_PRE_INPUT_FRAMES"], "12")
        self.assertEqual(len(environment["MGBA_ORIGINAL_INPUT_SEQUENCE_INPUT_STATE_SHA256"]), 64)

    def test_cartridge_sram_sidecar_is_part_of_the_input_contract(self):
        rom = self.dummy("rom.gba")
        self.assertIsNone(save_state_hash(rom))
        sidecar = self.root / "rom.sav"
        sidecar.write_bytes(b"save-bytes")
        self.assertEqual(save_state_hash(rom), sha256_file(sidecar))

    def test_guard_command_routes_mgba_through_the_shared_heavy_lock(self):
        command = guard_command(
            self.root / "guard.json", self.root / "done.json", ["mgba", "rom.gba"])
        self.assertEqual(command[1], str(GUARD))
        self.assertIn("--success-marker", command)
        self.assertIn("--", command)
        self.assertEqual(command[-2:], ["mgba", "rom.gba"])

    def test_existing_pair_directory_is_refused_so_evidence_is_never_overwritten(self):
        out_dir = self.root / "pair"
        out_dir.mkdir()
        with self.assertRaisesRegex(CaptureError, "already exists"):
            record_pair(
                out_dir,
                self.dummy("a.gba"), self.dummy("a.ss9"),
                self.dummy("b.gba"), self.dummy("b.ss9"),
            )

    def test_missing_pinned_input_fails_before_any_capture(self):
        with self.assertRaisesRegex(CaptureError, "missing pinned input"):
            record_pair(
                self.root / "pair",
                self.root / "absent.gba", self.dummy("a.ss9"),
                self.dummy("b.gba"), self.dummy("b.ss9"),
                mgba=self.root / "absent-mgba",
            )


@unittest.skipUnless(MGBA_AVAILABLE, "patched mGBA build is unavailable")
class RealPairCaptureTest(unittest.TestCase):
    """Records both real ROMs; opt-in because it launches mGBA twice."""

    def test_original_and_remake_idle_frames_are_recorded_with_one_contract(self):
        if not os.environ.get("RUN_S49_PAIR_CAPTURE"):
            self.skipTest("set RUN_S49_PAIR_CAPTURE=1 to record the real pair")
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        out_dir = Path(temporary.name) / "pair"
        result = record_pair(
            out_dir,
            ROOT / "rom/base.gba",
            ROOT / "artifacts/s49-fidelity-20261019-v1/original-entry-advance/step-00-base.ss9",
            ROOT / "build/s49-boot-probe/v5.gba",
            ROOT / "artifacts/s49-fidelity-20261019-v1/butano-deploy-advance2/step-05-A.ss9",
            key="None", hold_frames=6, frame_count=24, pre_input_frames=0,
        )
        self.assertEqual(result["comparison"]["compared_frames"], 24)
        inputs = json.loads((out_dir / "inputs.json").read_text())
        self.assertNotEqual(inputs["original_state_sha256"], inputs["remake_state_sha256"])
        self.assertNotEqual(inputs["original_rom_sha256"], inputs["remake_rom_sha256"])
        for label in ("original", "remake"):
            self.assertEqual(len(list((out_dir / label).glob("frame-*.png"))), 24)


if __name__ == "__main__":
    unittest.main()
