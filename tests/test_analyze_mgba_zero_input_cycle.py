import hashlib
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from tools import analyze_mgba_zero_input_cycle as analyzer
from tools.inspect_mgba_savestate import png_screen_fingerprint


ROOT = Path(__file__).resolve().parents[1]
SAMPLER = ROOT / "tools" / "mgba_zero_input_cycle_sample.lua"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def _rgb8_png(
    red: int, green: int, blue: int, *, width: int = 240, height: int = 160
) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    scanline = bytes((0,)) + bytes((red, green, blue)) * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(scanline * height))
        + _png_chunk(b"IEND", b"")
    )


def _complete_hashes() -> dict[int, str]:
    return {frame: f"frame-{frame}" for frame in range(1, 601)}


class SelectExactPeriodTests(unittest.TestCase):
    def test_selects_smallest_period_with_two_exact_recurrences(self):
        hashes = _complete_hashes()
        hashes[12] = hashes[24] = "baseline"
        hashes[18] = hashes[36] = "baseline"

        self.assertEqual(analyzer.select_exact_period("baseline", hashes), 12)

    def test_requires_keys_for_frames_1_through_600_exactly(self):
        with self.assertRaisesRegex(analyzer.CycleAnalysisError, "frames 1..600"):
            analyzer.select_exact_period("baseline", {1: "baseline"})

        hashes = _complete_hashes()
        hashes[601] = "extra"
        with self.assertRaisesRegex(analyzer.CycleAnalysisError, "frames 1..600"):
            analyzer.select_exact_period("baseline", hashes)

    def test_rejects_single_late_and_absent_matches(self):
        hashes = _complete_hashes()
        hashes[40] = "baseline"
        self.assertIsNone(analyzer.select_exact_period("baseline", hashes))

        hashes = _complete_hashes()
        hashes[301] = hashes[600] = "baseline"
        self.assertIsNone(analyzer.select_exact_period("baseline", hashes))

        self.assertIsNone(
            analyzer.select_exact_period("baseline", _complete_hashes())
        )


class SamplerContractTests(unittest.TestCase):
    def test_sampler_has_fixed_bound_unique_names_progress_and_no_side_effect_api(self):
        text = SAMPLER.read_text(encoding="utf-8")

        self.assertIn('required_env("MGBA_CYCLE_OUTPUT_DIR")', text)
        self.assertIn('required_env("MGBA_CYCLE_MAX_FRAME")', text)
        self.assertIn("max_frame == 600", text)
        self.assertIn('string.format("%s/frame-%04d.png"', text)
        self.assertIn("frame % 30 == 0", text)
        self.assertEqual(text.count('callbacks:add("frame"'), 1)
        self.assertEqual(text.count("emu:screenshot"), 1)
        for forbidden in (
            "emu:addKey",
            "emu:clearKey",
            "emu:setKeys",
            "emu:loadStateFile",
            "emu:saveStateFile",
            "os.exit",
        ):
            self.assertNotIn(forbidden, text)


class FrameDirectoryTests(unittest.TestCase):
    @staticmethod
    def _write_frames(frame_dir: Path, payload: bytes = b"not-decoded") -> None:
        frame_dir.mkdir()
        for frame in range(1, 601):
            (frame_dir / f"frame-{frame:04d}.png").write_bytes(payload)

    def test_analyzer_reuses_strict_png_fingerprint_for_all_600_frames(self):
        self.assertIs(analyzer.png_screen_fingerprint, png_screen_fingerprint)
        with tempfile.TemporaryDirectory() as tmp:
            frame_dir = Path(tmp) / "frames"
            self._write_frames(frame_dir)
            fingerprint = {
                "width": 240,
                "height": 160,
                "rgb_pixels_sha256": "a" * 64,
            }
            with mock.patch.object(
                analyzer, "png_screen_fingerprint", return_value=fingerprint
            ) as decode:
                hashes = analyzer.analyze_frame_directory(frame_dir)

        self.assertEqual(hashes, {frame: "a" * 64 for frame in range(1, 601)})
        self.assertEqual(decode.call_count, 600)

    def test_rejects_frame_that_is_not_a_240_by_160_gba_screen(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame_dir = Path(tmp) / "frames"
            self._write_frames(frame_dir)
            fingerprint = {
                "width": 1,
                "height": 1,
                "rgb_pixels_sha256": "a" * 64,
            }
            with mock.patch.object(
                analyzer, "png_screen_fingerprint", return_value=fingerprint
            ):
                with self.assertRaisesRegex(
                    analyzer.CycleAnalysisError, "240x160"
                ):
                    analyzer.analyze_frame_directory(frame_dir)

    def test_rejects_missing_extra_and_symlinked_frame_pngs(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame_dir = Path(tmp) / "frames"
            self._write_frames(frame_dir)
            frame_600 = frame_dir / "frame-0600.png"
            frame_600.unlink()
            with self.assertRaisesRegex(analyzer.CycleAnalysisError, "frames 1..600"):
                analyzer.analyze_frame_directory(frame_dir)

            frame_600.write_bytes(b"frame")
            extra = frame_dir / "frame-0601.png"
            extra.write_bytes(b"extra")
            with self.assertRaisesRegex(analyzer.CycleAnalysisError, "frames 1..600"):
                analyzer.analyze_frame_directory(frame_dir)

            extra.unlink()
            first = frame_dir / "frame-0001.png"
            first.unlink()
            first.symlink_to(frame_600)
            with self.assertRaisesRegex(analyzer.CycleAnalysisError, "symlink"):
                analyzer.analyze_frame_directory(frame_dir)

    def test_rejects_symlinked_frame_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            actual = root / "actual"
            actual.mkdir()
            linked = root / "linked"
            linked.symlink_to(actual, target_is_directory=True)
            with self.assertRaisesRegex(analyzer.CycleAnalysisError, "symlink"):
                analyzer.analyze_frame_directory(linked)


class CliTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[list[str], dict[str, Path]]:
        baseline = root / "baseline.png"
        baseline.write_bytes(_rgb8_png(1, 2, 3))
        frame_dir = root / "frames"
        FrameDirectoryTests._write_frames(frame_dir, baseline.read_bytes())
        sampler = root / "sampler.lua"
        sampler.write_bytes(SAMPLER.read_bytes())
        audit = root / "audit.json"
        output = root / "analysis.json"
        audit.write_text(
            json.dumps(
                {
                    "evidence_mode": "script-order-diagnostic",
                    "zero_input_verified": False,
                    "inputs": [],
                    "capture_frame": 600,
                    "pre_scripts": [
                        {
                            "path": str(sampler.resolve()),
                            "sha256": _sha256(sampler),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        paths = {
            "baseline": baseline,
            "frame_dir": frame_dir,
            "audit": audit,
            "sampler": sampler,
            "output": output,
        }
        argv = [
            "--baseline-png",
            str(baseline),
            "--expected-baseline-png-sha256",
            _sha256(baseline),
            "--frame-dir",
            str(frame_dir),
            "--audit",
            str(audit),
            "--sampler",
            str(sampler),
            "--expected-sampler-sha256",
            _sha256(sampler),
            "--output",
            str(output),
        ]
        return argv, paths

    def test_cli_validates_provenance_and_writes_complete_cycle_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            argv, paths = self._fixture(Path(tmp))
            baseline_file_sha256 = _sha256(paths["baseline"])
            audit_sha256 = _sha256(paths["audit"])
            sampler_sha256 = _sha256(paths["sampler"])
            expected_rgb = hashlib.sha256(
                bytes((1, 2, 3)) * 240 * 160
            ).hexdigest()
            with mock.patch.object(
                analyzer,
                "analyze_frame_directory",
                return_value={frame: expected_rgb for frame in range(1, 601)},
            ):
                self.assertEqual(analyzer.main(argv), 0)
            report = json.loads(paths["output"].read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "cycle-found")
        self.assertEqual(report["period"], 1)
        self.assertEqual(report["match_frames"], [0, 1, 2])
        self.assertEqual(report["baseline"]["file_sha256"], baseline_file_sha256)
        self.assertEqual(report["baseline"]["rgb_sha256"], expected_rgb)
        self.assertEqual(report["sampler"]["sha256"], sampler_sha256)
        self.assertEqual(report["audit"]["sha256"], audit_sha256)
        self.assertEqual(len(report["frame_rgb_sha256"]), 600)
        self.assertEqual(report["frame_rgb_sha256"]["600"], expected_rgb)

    def test_cli_fails_closed_on_baseline_or_sampler_hash_drift(self):
        for option in (
            "--expected-baseline-png-sha256",
            "--expected-sampler-sha256",
        ):
            with self.subTest(option=option), tempfile.TemporaryDirectory() as tmp:
                argv, paths = self._fixture(Path(tmp))
                argv[argv.index(option) + 1] = "0" * 64
                with self.assertRaisesRegex(analyzer.CycleAnalysisError, "SHA-256"):
                    analyzer.main(argv)
                self.assertFalse(paths["output"].exists())

    def test_cli_fails_closed_on_invalid_diagnostic_audit(self):
        mutations = {
            "mode": {"evidence_mode": "zero-input"},
            "inputs": {"inputs": ["A"]},
            "zero-input-claim": {"zero_input_verified": True},
            "capture": {"capture_frame": 599},
            "missing-pre-script": {"pre_scripts": []},
            "wrong-pre-script": {
                "pre_scripts": [{"path": "/wrong.lua", "sha256": "0" * 64}]
            },
        }
        for label, mutation in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                argv, paths = self._fixture(Path(tmp))
                audit = json.loads(paths["audit"].read_text(encoding="utf-8"))
                audit.update(mutation)
                paths["audit"].write_text(json.dumps(audit), encoding="utf-8")
                with self.assertRaises(analyzer.CycleAnalysisError):
                    analyzer.main(argv)
                self.assertFalse(paths["output"].exists())

    def test_cli_rejects_baseline_that_is_not_a_240_by_160_gba_screen(self):
        with tempfile.TemporaryDirectory() as tmp:
            argv, paths = self._fixture(Path(tmp))
            paths["baseline"].write_bytes(_rgb8_png(1, 2, 3, width=1, height=1))
            argv[argv.index("--expected-baseline-png-sha256") + 1] = _sha256(
                paths["baseline"]
            )

            with self.assertRaisesRegex(analyzer.CycleAnalysisError, "240x160"):
                analyzer.main(argv)

            self.assertFalse(paths["output"].exists())

    def test_cli_rejects_output_that_overlaps_an_input_without_changing_it(self):
        for label in ("baseline", "sampler", "audit"):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                argv, paths = self._fixture(Path(tmp))
                protected = paths[label]
                before = protected.read_bytes()
                argv[argv.index("--output") + 1] = str(protected)

                with self.assertRaisesRegex(
                    analyzer.CycleAnalysisError, "output"
                ):
                    analyzer.main(argv)

                self.assertEqual(protected.read_bytes(), before)

    def test_cli_rejects_symlink_existing_and_frame_directory_outputs(self):
        cases = ("symlink", "existing", "frame-directory")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                argv, paths = self._fixture(root)
                if case == "symlink":
                    output = root / "linked-output.json"
                    output.symlink_to(root / "symlink-target.json")
                elif case == "existing":
                    output = paths["output"]
                    output.write_bytes(b"existing evidence")
                else:
                    output = paths["frame_dir"] / "analysis.json"
                before = {
                    label: paths[label].read_bytes()
                    for label in ("baseline", "sampler", "audit")
                }
                argv[argv.index("--output") + 1] = str(output)

                with self.assertRaisesRegex(
                    analyzer.CycleAnalysisError, "output"
                ):
                    analyzer.main(argv)

                for label, payload in before.items():
                    self.assertEqual(paths[label].read_bytes(), payload)

    def test_cli_fails_closed_when_critical_input_drifts_during_analysis(self):
        for label in ("baseline", "sampler", "audit", "frame"):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                argv, paths = self._fixture(Path(tmp))
                target = (
                    paths["frame_dir"] / "frame-0001.png"
                    if label == "frame"
                    else paths[label]
                )
                drift = f"{label}-drift".encode("ascii")

                def mutate_then_return_hashes(_frame_dir: Path) -> dict[int, str]:
                    target.write_bytes(drift)
                    return {
                        frame: f"{frame:064x}" for frame in range(1, 601)
                    }

                with mock.patch.object(
                    analyzer,
                    "analyze_frame_directory",
                    side_effect=mutate_then_return_hashes,
                ):
                    with self.assertRaisesRegex(
                        analyzer.CycleAnalysisError, "changed|SHA-256"
                    ):
                        analyzer.main(argv)

                self.assertEqual(target.read_bytes(), drift)
                self.assertFalse(paths["output"].exists())

    def test_atomic_publish_never_clobbers_a_target_that_already_appeared(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            temporary = root / ".analysis.tmp"
            temporary.write_bytes(b"new report")
            output = root / "analysis.json"
            output.write_bytes(b"concurrent evidence")

            with self.assertRaises(analyzer.CycleAnalysisError):
                analyzer._publish_no_clobber(temporary, output)

            self.assertEqual(output.read_bytes(), b"concurrent evidence")
            self.assertEqual(temporary.read_bytes(), b"new report")

    def test_cli_writes_not_proven_with_empty_matches_when_no_period_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            argv, paths = self._fixture(Path(tmp))
            unique_hashes = {
                frame: f"{frame:064x}" for frame in range(1, 601)
            }
            with mock.patch.object(
                analyzer, "analyze_frame_directory", return_value=unique_hashes
            ):
                self.assertEqual(analyzer.main(argv), 0)
            report = json.loads(paths["output"].read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "not-proven")
        self.assertIsNone(report["period"])
        self.assertEqual(report["match_frames"], [])


if __name__ == "__main__":
    unittest.main()
