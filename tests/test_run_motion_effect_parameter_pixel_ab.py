import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.run_motion_effect_parameter_pixel_ab import VARIANTS, prepare_variant


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RunMotionEffectParameterPixelAbTests(unittest.TestCase):
    def test_prepares_exactly_two_natural_group3_phase_runs(self):
        self.assertEqual(VARIANTS, ("baseline", "candidate"))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build_root = root / "build"
            build_root.mkdir()
            rom = build_root / "baseline.gba"
            rom.write_bytes(b"rom")
            manifest = build_root / "build-manifest.json"
            manifest.write_text("{}\n", encoding="utf-8")
            build = {
                "schema": "motion-effect-parameter-pixel-ab-build-v1",
                "group_id": 3,
                "sequence_id": 3,
                "input_mode": "zero-input-active-state",
                "inputs": [],
                "input_state": "artifacts/runtime-checkpoints/state.ss9",
                "input_state_sha256": "a" * 64,
                "input_evidence": "artifacts/runtime-checkpoints/evidence.json",
                "input_evidence_sha256": "b" * 64,
                "source_phase_artifact": "artifacts/phase",
                "source_phase_manifest_sha256": "c" * 64,
                "timeout_frames": 600,
                "edit": {"rom_offset": 1},
                "boundary": "bounded",
                "variants": {
                    "baseline": {
                        "rom_path": "baseline.gba",
                        "rom_sha256": sha256(rom),
                    }
                },
            }

            case = prepare_variant(root / "runs", build_root, build, "baseline")
            profile = json.loads(case["profile"].read_text(encoding="utf-8"))

            self.assertEqual(profile["group_id"], 3)
            self.assertEqual(profile["sequence_id"], 3)
            self.assertEqual(profile["input_mode"], "zero-input-active-state")
            self.assertEqual(profile["inputs"], [])
            self.assertTrue(profile["natural_gameplay_route"])
            self.assertEqual(profile["execution_mode"], "natural-motion-parameter-pixel-ab")
            self.assertEqual(profile["source_rom_sha256"], sha256(rom))
            self.assertEqual(profile["parameter_contract"], {"rom_offset": 1})

    def test_rejects_a_non_group3_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build_root = root / "build"
            build_root.mkdir()
            rom = build_root / "baseline.gba"
            rom.write_bytes(b"rom")
            (build_root / "build-manifest.json").write_text("{}\n", encoding="utf-8")
            build = {
                "schema": "motion-effect-parameter-pixel-ab-build-v1",
                "group_id": 13,
                "sequence_id": 3,
                "variants": {"baseline": {"rom_path": "baseline.gba", "rom_sha256": sha256(rom)}},
            }
            with self.assertRaisesRegex(ValueError, "group-3"):
                prepare_variant(root / "runs", build_root, build, "baseline")


if __name__ == "__main__":
    unittest.main()
