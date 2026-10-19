#!/usr/bin/env python3
"""Contract tests for the S49 step-advance driver and the alignment tool."""

from __future__ import annotations

import json
import struct
import unittest
import zlib
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.butano.capture_s49_advance import (
    AdvanceError,
    BOOT_PREFIX,
    BOOT_SCRIPT,
    STATEFUL_PREFIX,
    STATEFUL_SCRIPT,
    advance,
    build_environment,
    parse_keys,
    verify_walk,
)
from tools.butano.s49_step_alignment import AlignmentError, align, collect_steps

ROOT = Path(__file__).resolve().parents[1]


def write_png(path: Path, colour: tuple[int, int, int],
              size: tuple[int, int] = (240, 160)) -> None:
    width, height = size
    row = b"\x00" + bytes(colour) * width
    raw = row * height

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b""))


class ParseKeysTest(unittest.TestCase):
    def test_single_and_list(self):
        self.assertEqual(parse_keys("A"), ["A"])
        self.assertEqual(parse_keys("A,B,Down"), ["A", "B", "Down"])

    def test_repeat_sugar(self):
        self.assertEqual(parse_keys("A*3"), ["A", "A", "A"])
        self.assertEqual(parse_keys("A,A*2, B "), ["A", "A", "A", "B"])

    def test_rejects_malformed(self):
        for spec in ("", "  ", ",", "A,", "X", "A*0", "A*-1", "A*x"):
            with self.subTest(spec=spec), self.assertRaises(AdvanceError):
                parse_keys(spec)


class BuildEnvironmentTest(unittest.TestCase):
    def test_stateful_prefix_requires_state(self):
        with self.assertRaises(AdvanceError):
            build_environment(STATEFUL_PREFIX, Path("/tmp/o"), Path("/tmp/d"),
                              ["A"], 1, 1, 1)

    def test_stateful_prefix_carries_state_hash(self):
        env = build_environment(STATEFUL_PREFIX, Path("/tmp/o"), Path("/tmp/d"),
                                ["A", "B"], 90, 90, 4, state=Path("/tmp/s.ss9"),
                                state_sha256="abc")
        self.assertEqual(env[f"{STATEFUL_PREFIX}INPUT_STATE"], "/tmp/s.ss9")
        self.assertEqual(env[f"{STATEFUL_PREFIX}INPUT_STATE_SHA256"], "abc")
        self.assertEqual(env[f"{STATEFUL_PREFIX}KEY_SEQUENCE"], "A,B")
        self.assertNotIn("ROM_SHA256", " ".join(env))

    def test_boot_prefix_carries_rom_hash(self):
        env = build_environment(BOOT_PREFIX, Path("/tmp/o"), Path("/tmp/d"),
                                parse_keys("A*2"), 240, 90, 4, rom_sha256="deadbeef")
        self.assertEqual(env[f"{BOOT_PREFIX}ROM_SHA256"], "deadbeef")
        self.assertEqual(env[f"{BOOT_PREFIX}KEY_SEQUENCE"], "A,A")
        self.assertNotIn("INPUT_STATE", " ".join(env))


class VerifyWalkTest(unittest.TestCase):
    def _make(self, root: Path, steps: int, audit_steps: int) -> Path:
        out = root / "walk"
        out.mkdir()
        write_png(out / "step-00-base.png", (1, 2, 3))
        (out / "step-00-base.ss9").write_bytes(b"state")
        for index in range(1, steps + 1):
            write_png(out / f"step-{index:02d}-A.png", (4, 5, 6))
            (out / f"step-{index:02d}-A.ss9").write_bytes(f"state{index}".encode())
        (out / "audit.json").write_text(json.dumps({
            "status": "capture-complete", "captured_steps": audit_steps}))
        return out

    def test_accepts_complete_walk(self):
        with TemporaryDirectory() as root:
            out = self._make(Path(root), steps=3, audit_steps=3)
            result = verify_walk(out, ["A", "A", "A"])
            self.assertEqual([s["step"] for s in result["steps"]], [0, 1, 2, 3])
            self.assertEqual(result["steps"][0]["key"], "none")
            self.assertEqual(len(result["steps"][0]["image_sha256"]), 64)

    def test_rejects_truncated_walk(self):
        with TemporaryDirectory() as root:
            out = self._make(Path(root), steps=3, audit_steps=2)
            with self.assertRaises(AdvanceError):
                verify_walk(out, ["A", "A", "A"])

    def test_rejects_missing_step_image(self):
        with TemporaryDirectory() as root:
            out = self._make(Path(root), steps=3, audit_steps=3)
            (out / "step-02-A.png").unlink()
            with self.assertRaises(AdvanceError):
                verify_walk(out, ["A", "A", "A"])

    def test_rejects_missing_savestate(self):
        with TemporaryDirectory() as root:
            out = self._make(Path(root), steps=3, audit_steps=3)
            (out / "step-02-A.ss9").unlink()
            with self.assertRaises(AdvanceError):
                verify_walk(out, ["A", "A", "A"])

    def test_rejects_missing_audit(self):
        with TemporaryDirectory() as root:
            out = self._make(Path(root), steps=1, audit_steps=1)
            (out / "audit.json").unlink()
            with self.assertRaises(AdvanceError):
                verify_walk(out, ["A"])


class AdvanceFailsClosedTest(unittest.TestCase):
    def setUp(self):
        self._root = TemporaryDirectory()
        self.root = Path(self._root.name)
        self.rom = self.root / "r.gba"
        self.rom.write_bytes(b"rom")

    def tearDown(self):
        self._root.cleanup()

    def test_refuses_to_overwrite(self):
        out = self.root / "walk"
        out.mkdir()
        with self.assertRaises(AdvanceError):
            advance(out, self.rom, None, ["A"], 0, 30, 4, run=False)

    def test_dry_run_pins_every_input(self):
        result = advance(self.root / "walk", self.rom, None, ["A", "A"],
                         240, 90, 4, label="remake", run=False)
        inputs = result["inputs"]
        self.assertEqual(inputs["start"], "power-on")
        self.assertEqual(inputs["script"], str(BOOT_SCRIPT.relative_to(ROOT)))
        self.assertEqual(len(inputs["rom_sha256"]), 64)
        self.assertEqual(inputs["keys"], ["A", "A"])
        self.assertEqual(inputs["settle_frames"], 90)

    def test_dry_run_stateful_pins_state(self):
        state = self.root / "s.ss9"
        state.write_bytes(b"state")
        result = advance(self.root / "walk", self.rom, state, ["A"],
                         90, 90, 4, run=False)
        self.assertEqual(result["inputs"]["start"], "savestate")
        self.assertEqual(result["inputs"]["script"],
                         str(STATEFUL_SCRIPT.relative_to(ROOT)))
        self.assertEqual(len(result["inputs"]["state_sha256"]), 64)

    def test_rejects_missing_state_file(self):
        with self.assertRaises(AdvanceError):
            advance(self.root / "walk", self.rom, self.root / "absent.ss9", ["A"],
                    90, 90, 4, run=False)

    def test_rejects_bad_frame_budgets(self):
        for zero, settle, hold in ((-1, 30, 4), (0, 0, 4), (0, 30, 0)):
            with self.subTest(budget=(zero, settle, hold)), self.assertRaises(AdvanceError):
                advance(self.root / "walk", self.rom, None, ["A"], zero,
                        settle, hold, run=False)


class CollectStepsTest(unittest.TestCase):
    def test_orders_numerically(self):
        with TemporaryDirectory() as root:
            for index in (0, 1, 2, 10):
                write_png(Path(root) / f"step-{index:02d}-A.png", (0, 0, 0))
            steps = collect_steps(Path(root))
            self.assertEqual([s["step"] for s in steps], [0, 1, 2, 10])

    def test_rejects_foreign_names(self):
        with TemporaryDirectory() as root:
            write_png(Path(root) / "frame-000.png", (0, 0, 0))
            with self.assertRaises(AlignmentError):
                collect_steps(Path(root))

    def test_rejects_empty_directory(self):
        with TemporaryDirectory() as root:
            with self.assertRaises(AlignmentError):
                collect_steps(Path(root))


class AlignTest(unittest.TestCase):
    def _walk(self, directory: Path, colours):
        directory.mkdir(parents=True)
        for index, colour in enumerate(colours):
            name = "step-00-base.png" if index == 0 else f"step-{index:02d}-A.png"
            write_png(directory / name, colour)

    def test_finds_the_measured_match(self):
        with TemporaryDirectory() as root:
            original = Path(root) / "original"
            remake = Path(root) / "remake"
            self._walk(original, [(0, 0, 0), (10, 10, 10), (20, 20, 20)])
            self._walk(remake, [(90, 90, 90), (10, 10, 10), (20, 20, 20)])
            result = align(original, remake)
            self.assertEqual(result["matched_steps"], 2)
            self.assertEqual(result["matched_step_indices"], [1, 2])
            self.assertEqual(result["rows"][1]["best_remake_step"], 1)
            self.assertEqual(result["rows"][1]["best_different_pixels"], 0)

    def test_records_all_pairs_without_masking(self):
        with TemporaryDirectory() as root:
            original = Path(root) / "original"
            remake = Path(root) / "remake"
            self._walk(original, [(0, 0, 0), (10, 10, 10)])
            self._walk(remake, [(90, 90, 90), (50, 50, 50), (10, 10, 10)])
            result = align(original, remake)
            self.assertEqual(len(result["rows"]), 2)
            self.assertTrue(all(len(row["cells"]) == 3 for row in result["rows"]))
            self.assertTrue(all(cell["different_pixels"] == 240 * 160
                                for cell in result["rows"][0]["cells"]))
            self.assertEqual(result["alignment"],
                             "all-pairs-full-screen-no-mask-no-phase-search")

    def test_rejects_size_mismatch(self):
        with TemporaryDirectory() as root:
            original = Path(root) / "original"
            remake = Path(root) / "remake"
            original.mkdir()
            remake.mkdir()
            write_png(original / "step-00-base.png", (0, 0, 0))
            write_png(remake / "step-00-base.png", (0, 0, 0), size=(8, 8))
            with self.assertRaises(AlignmentError):
                align(original, remake)


if __name__ == "__main__":
    unittest.main()
