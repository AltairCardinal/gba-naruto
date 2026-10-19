import math
import tempfile
import unittest
import wave
from pathlib import Path

from tools.analyze_wav_integrity import analyze_wav


class AnalyzeWavIntegrityTest(unittest.TestCase):
    def test_reports_per_channel_adjacent_sample_jumps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "capture.wav"
            frames = (
                (0, 0),
                (10_000, -10_000),
                (30_000, -30_000),
            )
            with wave.open(str(path), "wb") as output:
                output.setnchannels(2)
                output.setsampwidth(2)
                output.setframerate(32_768)
                output.writeframes(
                    b"".join(
                        int(sample).to_bytes(
                            2, "little", signed=True)
                        for frame in frames
                        for sample in frame
                    )
                )

            report = analyze_wav(path)

        self.assertEqual(report["channels"], 2)
        self.assertEqual(report["sample_rate"], 32_768)
        self.assertEqual(report["frame_count"], 3)
        self.assertEqual(report["sample_count"], 6)
        self.assertEqual(report["nonzero_sample_count"], 4)
        self.assertEqual(report["peak_absolute_sample"], 30_000)
        self.assertEqual(report["mean"], 0)
        self.assertTrue(
            math.isclose(
                report["rms"],
                math.sqrt(2_000_000_000 / 6),
            )
        )
        self.assertEqual(
            report["adjacent_jump_counts"],
            {"8192": 4, "16384": 2},
        )
        self.assertEqual(
            report["adjacent_jump_rates"],
            {"8192": 1.0, "16384": 0.5},
        )


if __name__ == "__main__":
    unittest.main()
