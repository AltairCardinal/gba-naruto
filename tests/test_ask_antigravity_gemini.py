"""Antigravity gemini-3.8-flash-high video review must stay reproducible and fail-closed."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.butano.ask_antigravity_gemini import (
    DEFAULT_MODEL,
    ReviewError,
    build_prompt,
    encode_video,
    list_frames,
    review,
    stage_frames,
)

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None
FFPROBE_AVAILABLE = shutil.which("ffprobe") is not None
AGY_AVAILABLE = (Path.home() / ".local/bin/agy").is_file()


def write_capture(path: Path, count: int, size=(240, 160)) -> Path:
    path.mkdir(parents=True)
    for index in range(count):
        Image.new("RGB", size, (index * 7 % 256, 40, 90)).save(path / f"frame-{index:03d}.png")
    return path


class ListFramesTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_empty_capture_is_rejected(self):
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaisesRegex(ReviewError, "no frames"):
            list_frames(empty)

    def test_gap_or_truncation_is_rejected_instead_of_silently_shortened(self):
        capture = write_capture(self.root / "gap", 3)
        (capture / "frame-001.png").unlink()
        with self.assertRaisesRegex(ReviewError, "frame-001"):
            list_frames(capture)

    def test_unrelated_image_is_not_treated_as_a_frame(self):
        capture = write_capture(self.root / "mixed", 2)
        Image.new("RGB", (4, 4)).save(capture / "step-00-base.png")
        with self.assertRaisesRegex(ReviewError, "step-00-base"):
            list_frames(capture)


class StageFramesTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.capture = write_capture(self.root / "capture", 3)

    def test_staged_frames_are_scaled_indexed_and_originals_untouched(self):
        before = {p.name: p.read_bytes() for p in self.capture.glob("frame-*.png")}
        staging = self.root / "staging"
        staged = stage_frames(list_frames(self.capture), staging, scale=2)
        self.assertEqual([p.name for p in staged], ["frame-000.png", "frame-001.png", "frame-002.png"])
        with Image.open(staged[0]) as image:
            self.assertEqual(image.size, (480, 320))
        self.assertEqual({p.name: p.read_bytes() for p in self.capture.glob("frame-*.png")}, before)

    def test_existing_staging_directory_is_refused(self):
        staging = self.root / "staging"
        stage_frames(list_frames(self.capture), staging, scale=1)
        with self.assertRaisesRegex(ReviewError, "already exists"):
            stage_frames(list_frames(self.capture), staging, scale=1)


class PromptTest(unittest.TestCase):
    def test_prompt_pins_frame_to_time_mapping_and_capture_contract(self):
        prompt = build_prompt(
            "What changed?",
            frame_count=120,
            fps=60,
            scale=2,
            context="original ROM capture",
        )
        self.assertIn("120", prompt)
        self.assertIn("frame 119", prompt)
        self.assertIn("n/60 seconds", prompt)
        self.assertIn("Game Boy Advance", prompt)
        self.assertIn("ffprobe", prompt)
        self.assertIn("original ROM capture", prompt)


@unittest.skipUnless(FFMPEG_AVAILABLE and FFPROBE_AVAILABLE, "ffmpeg/ffprobe are unavailable")
class EncodeVideoTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def probe_frame_count(self, video: Path) -> int:
        run = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-count_frames", "-show_entries", "stream=nb_read_frames",
             "-of", "csv=p=0", str(video)],
            text=True, capture_output=True, check=True)
        return int(run.stdout.strip())

    def test_encoding_preserves_the_exact_frame_count(self):
        capture = write_capture(self.root / "capture", 17)
        staged = stage_frames(list_frames(capture), self.root / "staging", scale=2)
        video = encode_video(staged, self.root / "capture.mp4", fps=60)
        self.assertTrue(video.is_file())
        self.assertEqual(self.probe_frame_count(video), 17)

    def test_duplicate_adjacent_frames_are_not_silently_dropped(self):
        capture = self.root / "capture"
        capture.mkdir()
        for index in range(8):
            color = (255, 0, 0) if index < 4 else (0, 0, 255)
            Image.new("RGB", (240, 160), color).save(capture / f"frame-{index:03d}.png")
        staged = stage_frames(list_frames(capture), self.root / "staging", scale=2)
        video = encode_video(staged, self.root / "capture.mp4", fps=60)
        self.assertEqual(self.probe_frame_count(video), 8)


class InvokeAgyTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.capture = write_capture(self.root / "capture", 2)

    def fake_agy(self, payload: str) -> Path:
        script = self.root / "fake-agy"
        script.write_text(
            "#!/bin/sh\nprintf '%s' \"$FAKE_AGY_PAYLOAD\"\n",
            encoding="utf-8")
        script.chmod(0o755)
        (self.root / "payload.txt").write_text(payload, encoding="utf-8")
        return script

    def review_with(self, payload: str, **kwargs):
        work = self.root / f"work-{len(list(self.root.glob('work-*')))}"
        return review(
            frames_dir=self.capture,
            question="What changed?",
            work_dir=work,
            agy=self.fake_agy(payload),
            env={"FAKE_AGY_PAYLOAD": (self.root / "payload.txt").read_text(encoding="utf-8")},
            **kwargs,
        )

    def test_denied_tool_action_fails_closed_instead_of_returning_empty_analysis(self):
        payload = json.dumps({"conversation_id": "c", "status": "SUCCESS", "response": "",
                              "denied_actions": [{"action": "command"}]})
        with self.assertRaisesRegex(ReviewError, "denied"):
            self.review_with(payload)

    def test_missing_response_fails_closed(self):
        with self.assertRaisesRegex(ReviewError, "status"):
            self.review_with(json.dumps({"conversation_id": "c", "status": "ERROR"}))

    def test_non_json_output_fails_closed(self):
        with self.assertRaisesRegex(ReviewError, "JSON"):
            self.review_with("not json at all")

    def test_successful_review_records_reproducible_evidence(self):
        payload = json.dumps({
            "conversation_id": "conv-1",
            "status": "SUCCESS",
            "response": "Frame 12 differs.",
            "usage": {"total_tokens": 1234},
        })
        receipt = self.review_with(payload)
        self.assertEqual(receipt["status"], "ok")
        self.assertEqual(receipt["model"], DEFAULT_MODEL)
        self.assertEqual(receipt["frames"], 2)
        self.assertEqual(receipt["response"], "Frame 12 differs.")
        self.assertEqual(len(receipt["video_sha256"]), 64)
        self.assertEqual(len(receipt["prompt_sha256"]), 64)
        self.assertTrue((Path(receipt["receipt_path"])).is_file())
        self.assertTrue((Path(receipt["prompt"])).is_file())


@unittest.skipUnless(AGY_AVAILABLE, "antigravity CLI (agy) is unavailable")
class RealAntigravityTest(unittest.TestCase):
    """Costs one real gemini-3.8-flash-high turn; opt-in via RUN_ANTIGRAVITY_REAL=1."""

    def setUp(self):
        if not FFMPEG_AVAILABLE:
            self.skipTest("ffmpeg is unavailable")
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_real_model_reports_the_colour_change_it_was_shown(self):
        capture = self.root / "capture"
        capture.mkdir()
        for index in range(24):
            color = (255, 0, 0) if index < 12 else (0, 0, 255)
            Image.new("RGB", (240, 160), color).save(capture / f"frame-{index:03d}.png")
        receipt = review(
            frames_dir=capture,
            question=(
                "This 24-frame GBA screen capture is 12 solid red frames followed by "
                "12 solid blue frames. Report the frame number where the colour "
                "changes and the two colours. Answer in one short paragraph."
            ),
            work_dir=self.root / "work",
        )
        self.assertEqual(receipt["status"], "ok")
        self.assertEqual(receipt["model"], "gemini-3.8-flash-high")
        self.assertIn("12", receipt["response"])


if __name__ == "__main__":
    unittest.main()
