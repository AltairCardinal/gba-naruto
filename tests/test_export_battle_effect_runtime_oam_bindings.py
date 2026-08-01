import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _synthetic_source(group_id=1):
    graphics = bytes((index * 29 + 7) & 0xFF for index in range(1024))
    palette = struct.pack("<16H", *range(16))
    return {
        "group_id": group_id,
        "sequence_ids": [group_id],
        "frame_id": 2,
        "component_index": 0,
        "component_tile_index": 8,
        "component_x": -8,
        "component_y": -8,
        "width": 16,
        "height": 16,
        "horizontal_flip": False,
        "vertical_flip": False,
        "graphics_size": len(graphics),
        "graphics_sha256": hashlib.sha256(graphics).hexdigest(),
        "palette_sha256": hashlib.sha256(palette).hexdigest(),
        "_graphics": graphics,
        "_palette": palette,
    }


class BattleEffectOamMatchingTests(unittest.TestCase):
    def test_binds_full_group_graphics_before_frame_component(self):
        from tools.export_battle_effect_runtime_oam_bindings import (
            _match_oam_entry,
        )

        source = _synthetic_source()
        vram = bytearray(0x18000)
        load_tile_base = 256
        load_offset = 0x10000 + load_tile_base * 32
        vram[load_offset : load_offset + source["graphics_size"]] = source[
            "_graphics"
        ]
        pram = bytearray(0x400)
        palette_bank = 3
        palette_offset = 0x200 + palette_bank * 32
        pram[palette_offset : palette_offset + 32] = source["_palette"]

        match = _match_oam_entry(
            oam_index=7,
            attr0=0,
            attr1=1 << 14,
            attr2=(palette_bank << 12) | load_tile_base | 8,
            vram=bytes(vram),
            pram=bytes(pram),
            source_components=[source],
        )

        self.assertIsNotNone(match)
        self.assertEqual("unique_best_group", match["group_resolution"])
        self.assertEqual("unique_best_frame_component", match["frame_component_resolution"])
        candidate = match["best_candidates"][0]
        self.assertEqual(1, candidate["group_id"])
        self.assertEqual(2, candidate["frame_id"])
        self.assertEqual(0, candidate["component_index"])
        self.assertEqual(256, candidate["obj_vram_load_tile_base"])
        self.assertEqual("0x06012000", candidate["obj_vram_load_address"])
        self.assertEqual(0, candidate["palette_difference_count"])

    def test_rejects_component_collision_when_full_group_graphics_differ(self):
        from tools.export_battle_effect_runtime_oam_bindings import (
            _match_oam_entry,
        )

        source = _synthetic_source()
        vram = bytearray(0x18000)
        load_offset = 0x10000 + 256 * 32
        mutated = bytearray(source["_graphics"])
        mutated[0] ^= 0xFF
        vram[load_offset : load_offset + len(mutated)] = mutated
        pram = bytearray(0x400)
        pram[0x200 : 0x220] = source["_palette"]

        match = _match_oam_entry(
            oam_index=0,
            attr0=0,
            attr1=1 << 14,
            attr2=256 + 8,
            vram=bytes(vram),
            pram=bytes(pram),
            source_components=[source],
        )

        self.assertIsNone(match)

    def test_preserves_shared_graphics_group_ambiguity(self):
        from tools.export_battle_effect_runtime_oam_bindings import (
            _match_oam_entry,
        )

        group_2 = _synthetic_source(group_id=2)
        group_3 = dict(group_2, group_id=3, sequence_ids=[3])
        vram = bytearray(0x18000)
        load_offset = 0x10000 + 256 * 32
        vram[load_offset : load_offset + group_2["graphics_size"]] = group_2[
            "_graphics"
        ]
        pram = bytearray(0x400)
        pram[0x200 : 0x220] = group_2["_palette"]

        match = _match_oam_entry(
            oam_index=0,
            attr0=0,
            attr1=1 << 14,
            attr2=256 + 8,
            vram=bytes(vram),
            pram=bytes(pram),
            source_components=[group_2, group_3],
        )

        self.assertEqual("ambiguous_best_group", match["group_resolution"])
        self.assertEqual([2, 3], match["best_group_ids"])


class ExportBattleEffectRuntimeOamBindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_battle_effect_runtime_oam_bindings import build_bindings

        cls.bindings = build_bindings(ROOT)

    def test_scans_parent_checkpoint_denominator_without_redefining_it(self):
        result = self.bindings
        self.assertEqual("battle-effect-runtime-oam-bindings-v1", result["schema"])
        self.assertEqual(93, result["summary"]["tracked_checkpoint_count"])
        self.assertEqual(93, len(result["tracked_checkpoints"]))
        self.assertEqual(0, result["summary"]["tracked_checkpoint_parse_error_count"])
        self.assertEqual(91, result["checkpoint_parent"]["checkpoint_count"])
        self.assertEqual(
            [
                "artifacts/runtime-checkpoints/scenario-47-fire-action16-confirmation.ss9",
                "artifacts/runtime-checkpoints/scenario-50-cross-shuriken-confirmation.ss9",
            ],
            result["checkpoint_source"]["post_parent_extensions"],
        )
        parent = ROOT / "artifacts/runtime-screen-composites-v1"
        self.assertEqual(
            hashlib.sha256((parent / "manifest.json").read_bytes()).hexdigest(),
            result["checkpoint_parent"]["manifest_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(
                (parent / "runtime-screen-composites.json").read_bytes()
            ).hexdigest(),
            result["checkpoint_parent"]["payload_sha256"],
        )

    def test_keeps_existing_accepted_runtime_states_in_a_separate_supplement(self):
        result = self.bindings
        self.assertEqual(5, result["summary"]["supplemental_state_count"])
        self.assertEqual(5, len(result["supplemental_states"]))
        self.assertEqual(
            [1, 2, 5, 11, 14],
            result["summary"]["supplemental_observed_group_ids"],
        )
        self.assertTrue(
            all(item["matches"] for item in result["supplemental_states"])
        )
        self.assertFalse(result["scope"]["natural_task_and_selector_trace_complete"])
        self.assertFalse(result["scope"]["all_effect_groups_runtime_observed"])

    def test_discovers_group_1_frame_6_in_an_existing_tracked_checkpoint(self):
        checkpoint = next(
            item
            for item in self.bindings["tracked_checkpoints"]
            if item["path"].endswith(
                "scenario-50-battle-15-escort-12hp-player-turn.ss9"
            )
        )

        self.assertEqual(3, checkpoint["matched_oam_object_count"])
        self.assertEqual([17, 18, 19], [item["oam_index"] for item in checkpoint["matches"]])
        for match in checkpoint["matches"]:
            self.assertEqual("unique_best_group", match["group_resolution"])
            self.assertEqual(
                "unique_best_frame_component",
                match["frame_component_resolution"],
            )
            self.assertEqual([1], match["best_group_ids"])
            self.assertEqual(0, match["best_palette_difference_count"])
            candidate = match["best_candidates"][0]
            self.assertEqual(6, candidate["frame_id"])
            self.assertEqual(0, candidate["component_index"])
            self.assertEqual(24, candidate["component_tile_index"])
            self.assertEqual(768, candidate["obj_vram_load_tile_base"])
            self.assertEqual("0x06016000", candidate["obj_vram_load_address"])

    def test_affine_supplement_keeps_content_only_frame_ambiguity(self):
        state = next(
            item
            for item in self.bindings["supplemental_states"]
            if item["path"].endswith("battle-effect-affine-runtime-v1/raw/state-0154.ss9")
        )
        ambiguous = [
            item
            for item in state["matches"]
            if item["frame_component_resolution"]
            == "ambiguous_best_frame_component"
        ]

        self.assertEqual([1, 2], [item["oam_index"] for item in ambiguous])
        for match in ambiguous:
            self.assertEqual([2], match["best_group_ids"])
            self.assertEqual(
                [(0, 0), (1, 0)],
                [
                    (candidate["frame_id"], candidate["component_index"])
                    for candidate in match["best_candidates"]
                ],
            )


class PromotedBattleEffectRuntimeOamBindingsTests(unittest.TestCase):
    def test_promoted_artifact_is_hash_locked_and_independently_verified(self):
        from tools.verify_battle_effect_runtime_oam_bindings import verify_bindings

        directory = ROOT / "artifacts/battle-effect-runtime-oam-bindings-v1"
        bindings_path = directory / "bindings.json"
        manifest = json.loads(
            (directory / "manifest.json").read_text(encoding="utf-8")
        )

        self.assertEqual("git-artifact-promotion-v1", manifest["schema"])
        self.assertEqual("accepted", manifest["artifact_status"])
        self.assertEqual(
            "battle-effect-runtime-oam-bindings-v1",
            manifest["artifact_schema"],
        )
        self.assertEqual(
            hashlib.sha256(bindings_path.read_bytes()).hexdigest(),
            manifest["files"]["bindings.json"],
        )
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/export_battle_effect_runtime_oam_bindings.py").read_bytes()
            ).hexdigest(),
            manifest["producer"]["exporter_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/verify_battle_effect_runtime_oam_bindings.py").read_bytes()
            ).hexdigest(),
            manifest["producer"]["verifier_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(
                (
                    ROOT
                    / "artifacts/runtime-screen-composites-v1/manifest.json"
                ).read_bytes()
            ).hexdigest(),
            manifest["source"]["accepted_checkpoint_parent_manifest_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(
                (
                    ROOT
                    / "artifacts/battle-effect-sprite-animations-v1/manifest.json"
                ).read_bytes()
            ).hexdigest(),
            manifest["source"]["source_artifact_manifest_sha256"],
        )
        report = verify_bindings(ROOT, bindings_path)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(report, manifest["verifier"]["result"])


if __name__ == "__main__":
    unittest.main()
