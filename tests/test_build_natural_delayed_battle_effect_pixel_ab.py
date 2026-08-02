from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = (
    ROOT
    / "sequel/content/battle-effect-natural-pixel-ab/"
    "group-03-tool67-expiry.json"
)
PROFILE_GROUP18 = (
    ROOT
    / "sequel/content/battle-effect-natural-pixel-ab/"
    "group-18-tool67-zero-event-expiry.json"
)


class NaturalDelayedBattleEffectPixelAbBuilderTests(unittest.TestCase):
    def test_builds_probe_free_group18_natural_pair(self):
        builder = importlib.import_module(
            "tools.build_natural_delayed_battle_effect_pixel_ab"
        )
        probe = importlib.import_module(
            "tools.build_controlled_battle_effect_direct_spawn_probe"
        )
        base = (ROOT / "rom/base.gba").read_bytes()

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "pair"
            result = builder.build_pair(ROOT, PROFILE_GROUP18, output)

            self.assertEqual(result["group_id"], 18)
            self.assertEqual(result["sequence_id"], 7)
            self.assertEqual(result["input_mode"], "explicit-input-sequence")
            self.assertEqual(len(result["inputs"]), 17)
            self.assertEqual(result["inputs"][0], "A:18:20")
            self.assertEqual(result["inputs"][-1], "A:3440:3442")
            self.assertEqual(result["capture_frame"], 4520)
            self.assertEqual(result["timeout_frames"], 5000)
            self.assertEqual(
                result["input_state"],
                "artifacts/battle-effect-group18-natural-checkpoint-v1/raw/object-created.ss9",
            )
            self.assertEqual(result["delayed_object"]["remaining_turns"], 2)
            self.assertEqual(result["source_pointer_offsets"], [0x5991AC])
            self.assertEqual(result["target_pointer_offsets"], [0x5991AC])
            self.assertTrue(result["same_patch_topology"])
            self.assertTrue(result["same_encoded_size"])
            for variant in ("baseline", "candidate"):
                row = result["variants"][variant]
                rom = (output / row["rom_path"]).read_bytes()
                self.assertEqual(
                    rom[probe.HOOK_OFFSET:probe.HOOK_OFFSET + 4],
                    base[probe.HOOK_OFFSET:probe.HOOK_OFFSET + 4],
                )
                self.assertEqual(
                    int.from_bytes(rom[0x5991AC:0x5991B0], "little"),
                    0x08B40000,
                )
            baseline = (
                output / result["variants"]["baseline"]["graphics_path"]
            ).read_bytes()
            candidate = (
                output / result["variants"]["candidate"]["graphics_path"]
            ).read_bytes()
            self.assertEqual(
                [
                    index
                    for index, pair in enumerate(zip(baseline, candidate, strict=True))
                    if pair[0] != pair[1]
                ],
                [202],
            )
            self.assertEqual((baseline[202], candidate[202]), (0x44, 0x41))

    def test_builds_probe_free_group3_alias_split_pair(self):
        builder = importlib.import_module(
            "tools.build_natural_delayed_battle_effect_pixel_ab"
        )
        probe = importlib.import_module(
            "tools.build_controlled_battle_effect_direct_spawn_probe"
        )
        base = (ROOT / "rom/base.gba").read_bytes()

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "pair"
            result = builder.build_pair(ROOT, PROFILE, output)

            self.assertEqual(
                result["schema"],
                "natural-delayed-battle-effect-pixel-ab-build-v1",
            )
            self.assertTrue(result["natural_gameplay_route"])
            self.assertEqual(result["input_mode"], "zero-input-active-state")
            self.assertTrue(result["probe_free"])
            self.assertEqual(result["group_id"], 3)
            self.assertEqual(result["sequence_id"], 3)
            self.assertEqual(result["source_pointer_offsets"], [0x59912C, 0x599134])
            self.assertEqual(result["target_pointer_offsets"], [0x599134])
            self.assertTrue(result["same_patch_topology"])
            self.assertTrue(result["same_encoded_size"])

            for variant in ("baseline", "candidate"):
                row = result["variants"][variant]
                rom = (output / row["rom_path"]).read_bytes()
                self.assertEqual(len(rom), 0x1000000)
                self.assertEqual(
                    rom[probe.HOOK_OFFSET:probe.HOOK_OFFSET + 4],
                    base[probe.HOOK_OFFSET:probe.HOOK_OFFSET + 4],
                )
                self.assertEqual(
                    rom[probe.STUB_OFFSET:probe.STUB_OFFSET + probe.STUB_SIZE],
                    base[probe.STUB_OFFSET:probe.STUB_OFFSET + probe.STUB_SIZE],
                )
                self.assertEqual(
                    rom[0x59912C:0x599130],
                    base[0x59912C:0x599130],
                )
                self.assertEqual(
                    int.from_bytes(rom[0x599134:0x599138], "little"),
                    0x08B40000,
                )

            baseline = (
                output / result["variants"]["baseline"]["graphics_path"]
            ).read_bytes()
            candidate = (
                output / result["variants"]["candidate"]["graphics_path"]
            ).read_bytes()
            self.assertEqual(
                [
                    index
                    for index, pair in enumerate(zip(baseline, candidate, strict=True))
                    if pair[0] != pair[1]
                ],
                [207],
            )
            self.assertEqual((baseline[207], candidate[207]), (0x03, 0x0E))

    def test_rejects_promoting_an_unverified_source_phase(self):
        builder = importlib.import_module(
            "tools.build_natural_delayed_battle_effect_pixel_ab"
        )
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as temporary:
            altered = Path(temporary) / "profile.json"
            payload = json.loads(PROFILE.read_text(encoding="utf-8"))
            payload["source_natural_phase_manifest_sha256"] = "0" * 64
            altered.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "source phase"):
                builder.build_pair(ROOT, altered, Path(temporary) / "out")


if __name__ == "__main__":
    unittest.main()
