from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = (
    ROOT
    / "sequel/content/battle-effect-controlled-pixel-ab/"
    "group-18-sequence-07-direct-spawn.json"
)
GROUP3_PROFILE = (
    ROOT
    / "sequel/content/battle-effect-controlled-pixel-ab/"
    "group-03-sequence-03-side-0-direct-spawn.json"
)


class ControlledBattleEffectPixelAbBuilderTests(unittest.TestCase):
    def setUp(self):
        self.builder = importlib.import_module(
            "tools.build_controlled_battle_effect_pixel_ab"
        )
        self.probe = importlib.import_module(
            "tools.build_controlled_battle_effect_direct_spawn_probe"
        )

    def test_group18_builds_isolated_relocation_and_identical_direct_probe(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "pair"
            result = self.builder.build_pair(ROOT, PROFILE, output)

            self.assertEqual(
                result["schema"],
                "controlled-battle-effect-pixel-ab-build-v1",
            )
            self.assertEqual(result["case_id"], "group-18-sequence-07-direct-spawn")
            self.assertEqual(result["group_id"], 18)
            self.assertEqual(result["sequence_id"], 7)
            self.assertEqual(result["execution_mode"], "controlled-direct-spawn")
            self.assertFalse(result["natural_gameplay_route"])
            self.assertTrue(result["production_resource_relocation"])
            self.assertEqual(
                result["edit"],
                {
                    "frame_id": 0,
                    "component_index": 0,
                    "component_pixel_xy": [20, 10],
                    "graphics_byte_offset": 202,
                    "before_byte": 0x44,
                    "after_byte": 0x41,
                    "before_index": 4,
                    "after_index": 1,
                    "screen_xy": [124, 43],
                    "before_rgb": [181, 181, 181],
                    "after_rgb": [231, 231, 231],
                },
            )
            self.assertTrue(result["same_patch_topology"])
            self.assertTrue(result["same_encoded_size"])

            stubs = []
            for variant in ("baseline", "candidate"):
                row = result["variants"][variant]
                self.assertEqual(row["encoded_graphics_size"], 2002)
                self.assertEqual(row["graphics_allocation_offset"], 0xB40000)
                self.assertEqual(row["redirect_pointer_offsets"], [0x5991AC])
                rom = (output / row["rom_path"]).read_bytes()
                self.assertEqual(len(rom), 0x1000000)
                self.assertEqual(
                    rom[self.probe.HOOK_OFFSET:self.probe.HOOK_OFFSET + 4],
                    self.probe.encode_thumb_bl(self.probe.HOOK, self.probe.STUB),
                )
                stub = rom[
                    self.probe.STUB_OFFSET:
                    self.probe.STUB_OFFSET + self.probe.STUB_SIZE
                ]
                self.assertEqual(stub, self.probe.build_stub(self.probe.CASES_BY_ID[result["case_id"]]))
                stubs.append(stub)
            self.assertEqual(stubs[0], stubs[1])

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

    def test_profile_cannot_promote_the_controlled_route_to_natural(self):
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        profile["natural_gameplay_route"] = True
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as temporary:
            altered = Path(temporary) / "profile.json"
            altered.write_text(json.dumps(profile), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "natural gameplay"):
                self.builder.build_pair(ROOT, altered, Path(temporary) / "out")

    def test_group3_splits_only_its_shared_graphics_alias(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "pair"
            result = self.builder.build_pair(ROOT, GROUP3_PROFILE, output)

            self.assertEqual(result["case_id"], "group-03-sequence-03-side-0-direct-spawn")
            self.assertEqual(result["group_id"], 3)
            self.assertEqual(result["sequence_id"], 3)
            self.assertTrue(result["same_patch_topology"])
            self.assertTrue(result["same_encoded_size"])
            self.assertTrue(result["same_probe_bytes"])
            self.assertEqual(result["source_pointer_offsets"], [0x59912C, 0x599134])
            self.assertEqual(result["target_pointer_offsets"], [0x599134])

            base = (ROOT / "rom/base.gba").read_bytes()
            stubs = []
            for variant in ("baseline", "candidate"):
                row = result["variants"][variant]
                self.assertEqual(row["encoded_graphics_size"], 5294)
                self.assertEqual(row["graphics_allocation_offset"], 0xB40000)
                self.assertEqual(row["redirect_pointer_offsets"], [0x599134])
                rom = (output / row["rom_path"]).read_bytes()
                self.assertEqual(
                    rom[0x59912C:0x599130],
                    base[0x59912C:0x599130],
                )
                self.assertEqual(
                    int.from_bytes(rom[0x599134:0x599138], "little"),
                    0x08B40000,
                )
                stub = rom[
                    self.probe.STUB_OFFSET:
                    self.probe.STUB_OFFSET + self.probe.STUB_SIZE
                ]
                self.assertEqual(
                    stub,
                    self.probe.build_stub(self.probe.CASES_BY_ID[result["case_id"]]),
                )
                stubs.append(stub)
            self.assertEqual(stubs[0], stubs[1])

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


if __name__ == "__main__":
    unittest.main()
