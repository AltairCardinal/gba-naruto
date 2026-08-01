import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import run_battle_effect_controlled_sequence_batch as batch


ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "sequel/content/battle-effect-controlled-runtime/unobserved-groups-v1.json"


class ControlledSequenceBatchTests(unittest.TestCase):
    def test_loads_exact_unobserved_denominator_and_static_mapping(self):
        spec = batch.load_spec(SPEC)

        self.assertEqual(
            [row["group_id"] for row in spec["cases"]],
            [3, 4, 6, 7, 8, 9, 10, 12, 13, 15, 16, 17, 18],
        )
        self.assertEqual(spec["scratch_before"], bytes(4))

    def test_prepares_rebuildable_rom_and_hash_bound_profile(self):
        spec = batch.load_spec(SPEC)
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as temporary:
            case = batch.prepare_case(spec, spec["cases"][7], Path(temporary))

            profile = json.loads(case["profile"].read_text(encoding="utf-8"))
            rom = case["rom"].read_bytes()
            self.assertEqual(profile["group_id"], 12)
            self.assertEqual(profile["sequence_id"], 14)
            self.assertEqual(profile["execution_mode"], "controlled-sequence-injection")
            self.assertEqual(profile["source_rom_sha256"], hashlib.sha256(rom).hexdigest())
            self.assertEqual(
                rom,
                batch.build_probe((ROOT / "rom/base.gba").read_bytes(), sequence_id=14),
            )

    def test_rejects_duplicate_group_and_wrong_sequence_mapping(self):
        payload = json.loads(SPEC.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as temporary:
            path = Path(temporary) / "spec.json"
            duplicate = copy.deepcopy(payload)
            duplicate["cases"].append(copy.deepcopy(duplicate["cases"][0]))
            path.write_text(json.dumps(duplicate), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exact unobserved group denominator"):
                batch.load_spec(path)

            wrong = copy.deepcopy(payload)
            wrong["cases"][0]["sequence_id"] = 14
            path.write_text(json.dumps(wrong), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not bind group"):
                batch.load_spec(path)

    def test_command_uses_single_guarded_phase_runner(self):
        command = batch.build_case_command(
            binary=Path("/tmp/mGBA"),
            binary_sha256="a" * 64,
            toolchain_profile=ROOT / "artifacts/rom-expansion-profile-v1/profile.json",
            case={
                "rom": Path("/tmp/group12.gba"),
                "rom_sha256": "b" * 64,
                "profile": Path("/tmp/profile.json"),
                "profile_sha256": "c" * 64,
                "case_root": Path("/tmp/group12"),
            },
            wall_timeout_s=60,
            idle_timeout_s=25,
        )

        self.assertIn("tools/run_macos_mgba_controlled_battle_effect_capture.py", " ".join(command))
        self.assertIn("--toolchain-profile", command)
        self.assertNotIn("tools/run_guarded.py", " ".join(command))


if __name__ == "__main__":
    unittest.main()
