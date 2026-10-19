"""Full-frame comparisons must not hide input frames or truncate captures."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

from tools.butano.compare_frame_sequences import compare_sequences


class CompareFrameSequencesTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.original = self.capture("original")
        self.current = self.capture("current")

    def capture(self, name):
        path = self.root / name
        path.mkdir()
        audit = {"status": "capture-complete", "record_all": True,
                 "frame_count": 4, "key": "A", "hold_frames": 1,
                 "input_after_frame": 0, "input_state_sha256": "a" * 64}
        (path / "audit.json").write_text(json.dumps(audit))
        for index in range(4):
            Image.new("RGB", (240, 160), (index, 2, 3)).save(path / f"frame-{index:03d}.png")
        return path

    def test_compares_every_frame_and_every_pixel_without_phase_search(self):
        with Image.open(self.current / "frame-001.png") as source:
            changed = source.convert("RGB")
        changed.putpixel((239, 159), (255, 0, 0))
        changed.save(self.current / "frame-001.png")
        result = compare_sequences(self.original, self.current)
        self.assertEqual(result["status"], "different")
        self.assertEqual(result["compared_frames"], 4)
        self.assertEqual(result["different_frames"], 1)
        self.assertEqual(result["different_pixels"], 1)
        self.assertEqual(result["frames"][1]["difference_bbox"], [239, 159, 240, 160])
        self.assertEqual(result["alignment"], "same-index-no-exclusions")

    def test_missing_or_extra_frame_cannot_be_silently_truncated(self):
        (self.current / "frame-003.png").unlink()
        with self.assertRaisesRegex(ValueError, "frame set"):
            compare_sequences(self.original, self.current)
        Image.new("RGB", (240, 160)).save(self.current / "frame-004.png")
        with self.assertRaisesRegex(ValueError, "frame set"):
            compare_sequences(self.original, self.current)

    def test_legacy_skipped_input_capture_is_not_accepted(self):
        audit = json.loads((self.current / "audit.json").read_text())
        audit.pop("record_all")
        (self.current / "audit.json").write_text(json.dumps(audit))
        with self.assertRaisesRegex(ValueError, "record_all"):
            compare_sequences(self.original, self.current)

    def test_input_timing_must_match(self):
        audit = json.loads((self.current / "audit.json").read_text())
        audit["input_after_frame"] = 1
        (self.current / "audit.json").write_text(json.dumps(audit))
        with self.assertRaisesRegex(ValueError, "input timing"):
            compare_sequences(self.original, self.current)

    def test_real_cli_writes_full_report_and_returns_nonzero_for_difference(self):
        Image.new("RGB", (240, 160), "red").save(self.current / "frame-000.png")
        report = self.root / "report.json"
        run = subprocess.run([sys.executable, "-m", "tools.butano.compare_frame_sequences",
                              str(self.original), str(self.current), "--output", str(report)],
                             text=True, capture_output=True, check=False)
        self.assertEqual(run.returncode, 1, run.stderr)
        self.assertEqual(json.loads(report.read_text())["different_frames"], 1)

    def test_identical_capture_reports_exact_complete_denominator(self):
        result = compare_sequences(self.original, self.current)
        self.assertEqual(result["status"], "identical")
        self.assertEqual(result["compared_pixels"], 4 * 240 * 160)
        self.assertEqual(result["different_pixels"], 0)
