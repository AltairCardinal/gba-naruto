import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExportRuntimeFontTileProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_runtime_font_tile_provenance import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.artifact = export_artifact(ROOT, cls.output)
        cls.promotion = json.loads(
            (cls.output / "manifest.json").read_text(encoding="utf-8")
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_fixes_the_complete_unidentified_layer_and_cell_denominator(self):
        self.assertEqual(
            "runtime-font-tile-provenance-v1",
            self.artifact["schema"],
        )
        self.assertEqual(
            {
                "layer_count": 61,
                "cell_count": 62464,
                "exact_nonblank_font_content_cell_count": 2827,
                "ambiguous_blank_font_content_cell_count": 26,
                "no_font_content_cell_count": 59611,
                "ordered_sjis_pair_count": 1050,
                "ordered_sjis_pair_cell_count": 2100,
                "layers_with_ordered_sjis_pairs": 58,
                "distinct_sjis_code_count": 226,
                "unique_source_pair_count": 1050,
            },
            {
                key: self.artifact["summary"][key]
                for key in (
                    "layer_count",
                    "cell_count",
                    "exact_nonblank_font_content_cell_count",
                    "ambiguous_blank_font_content_cell_count",
                    "no_font_content_cell_count",
                    "ordered_sjis_pair_count",
                    "ordered_sjis_pair_cell_count",
                    "layers_with_ordered_sjis_pairs",
                    "distinct_sjis_code_count",
                    "unique_source_pair_count",
                )
            },
        )
        self.assertEqual(61, len(self.artifact["layers"]))
        self.assertEqual(
            {"0": 1, "1": 2, "3": 58},
            self.artifact["summary"]["layer_counts_by_bg_index"],
        )
        self.assertEqual(
            {"2": 996, "3": 54},
            self.artifact["summary"]["ordered_pair_counts_by_palette_group"],
        )

    def test_world_map_dialogue_and_menu_pairs_bind_exact_rom_glyphs(self):
        world = self._layer("scenario-42-postbattle-world-map.ss9", 3)
        self.assertEqual(14, world["ordered_sjis_pair_count"])
        world_pair = self._pair(world, [4, 1])
        self.assertEqual("0x92BB", world_pair["sjis_hex"])
        self.assertEqual(2, world_pair["expansion_palette_group"])
        self.assertEqual([0, 1], world_pair["runtime_tile_ids"])
        self.assertEqual(1, world_pair["candidate_count"])

        dialogue = self._layer("scenario-46-client-dialogue.ss9", 3)
        self.assertEqual(21, dialogue["ordered_sjis_pair_count"])
        dialogue_pair = self._pair(dialogue, [3, 13])
        self.assertEqual("0x9298", dialogue_pair["sjis_hex"])
        self.assertEqual([294, 295], dialogue_pair["runtime_tile_ids"])

        profile = self._layer("alternate-character-overview.ss9", 1)
        self.assertEqual(2, profile["ordered_sjis_pair_count"])
        self.assertEqual("0x9298", self._pair(profile, [14, 14])["sjis_hex"])

        skills = self._layer("skill-list-pre-controller.ss9", 1)
        self.assertEqual(2, skills["ordered_sjis_pair_count"])
        self.assertEqual("0x9298", self._pair(skills, [4, 14])["sjis_hex"])

        group3 = self._layer(
            "scenario-49-battle-14-postbattle-task-menu.ss9", 3
        )
        group3_pair = self._pair(group3, [8, 5])
        self.assertEqual("0x909D", group3_pair["sjis_hex"])
        self.assertEqual(3, group3_pair["expansion_palette_group"])
        self.assertEqual([42, 43], group3_pair["runtime_tile_ids"])

    def test_three_layers_without_nonblank_font_pairs_remain_explicit(self):
        self.assertEqual(
            [
                {
                    "checkpoint": "alternate-character-overview.ss9",
                    "bg_index": 0,
                },
                {
                    "checkpoint": "scenario-41-pre-controller-after-a.ss9",
                    "bg_index": 3,
                },
                {
                    "checkpoint": "scenario-41-victory.ss9",
                    "bg_index": 3,
                },
            ],
            self.artifact["summary"]["layers_without_ordered_sjis_pairs"],
        )
        for item in self.artifact["summary"]["layers_without_ordered_sjis_pairs"]:
            layer = self._layer(item["checkpoint"], item["bg_index"])
            self.assertEqual(0, layer["ordered_sjis_pair_count"])

    def test_every_promoted_pair_is_unique_ordered_unflipped_and_hash_bound(self):
        pairs = [
            pair
            for layer in self.artifact["layers"]
            for pair in layer["ordered_sjis_pairs"]
        ]
        self.assertEqual(1050, len(pairs))
        for pair in pairs:
            self.assertEqual(1, pair["candidate_count"])
            self.assertEqual([False, False], pair["flip_hv"])
            self.assertEqual(64, len(pair["source_record_sha256"]))
            self.assertEqual(64, len(pair["runtime_top_tile_sha256"]))
            self.assertEqual(64, len(pair["runtime_bottom_tile_sha256"]))
            self.assertEqual(2, len(pair["source_physical_half_indices"]))
            self.assertEqual([0, 1], pair["source_half_indices"])
            self.assertEqual(
                [
                    pair["position_tiles"],
                    [
                        pair["position_tiles"][0],
                        pair["position_tiles"][1] + 1,
                    ],
                ],
                pair["runtime_positions_tiles"],
            )
            self.assertEqual(2, len(pair["source_half_sha256s"]))
            self.assertIn(pair["expansion_palette_group"], (2, 3))

    def test_blank_font_content_remains_ambiguous_and_never_becomes_a_pair(self):
        layer = self._layer(
            "scenario-49-battle-14-postbattle-task-menu.ss9", 3
        )
        blank = next(
            item
            for item in layer["ambiguous_blank_font_cells"]
            if item["position_tiles"] == [14, 5]
        )
        self.assertEqual("ambiguous_blank_font_content", blank["classification"])
        self.assertEqual(54, blank["runtime_tile_id"])
        self.assertGreater(blank["candidate_count"], 1)
        pair_positions = {
            tuple(position)
            for pair in layer["ordered_sjis_pairs"]
            for position in pair["runtime_positions_tiles"]
        }
        self.assertNotIn((14, 5), pair_positions)

    def test_each_layer_retains_its_parent_unidentified_identity(self):
        parent_path = (
            ROOT
            / "artifacts/runtime-layer-static-provenance-v1/"
            "runtime-layer-static-provenance.json"
        )
        parent = json.loads(parent_path.read_text(encoding="utf-8"))
        unknown = {
            f"{item['state_id']}:bg{item['bg_index']}": item
            for item in parent["layers"]
            if item["classification"] == "unidentified_runtime_payload"
        }
        self.assertEqual(61, len(unknown))
        for layer in self.artifact["layers"]:
            key = layer["parent_layer_key"]
            self.assertIn(key, unknown)
            self.assertEqual(
                "unidentified_runtime_payload",
                layer["parent_classification"],
            )
            expected_hash = hashlib.sha256(
                (
                    json.dumps(
                        unknown[key],
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode("utf-8")
            ).hexdigest()
            self.assertEqual(expected_hash, layer["parent_layer_sha256"])
            for forbidden in (
                "classification",
                "source",
                "whole_bg_source",
                "exact_sources",
                "partial_sources",
            ):
                self.assertNotIn(forbidden, layer)

    def test_scope_does_not_promote_component_content_to_a_whole_layer_writer(self):
        self.assertEqual(
            {
                "all_parent_unidentified_layers_classified_for_font_content": True,
                "exact_nonblank_expanded_font_tile_content_complete": True,
                "ordered_sjis_vertical_pair_content_complete": True,
                "runtime_writer_identity_per_checkpoint_complete": False,
                "whole_bg_source_identity_complete": False,
                "nonfont_tile_source_identity_complete": False,
                "unicode_or_localized_character_semantics_complete": False,
                "all_game_visual_states_complete": False,
            },
            self.artifact["scope"],
        )

    def test_manifest_binds_sources_implementation_and_payload(self):
        expected = {
            "exporter_sha256": hashlib.sha256(
                (
                    ROOT / "tools/export_runtime_font_tile_provenance.py"
                ).read_bytes()
            ).hexdigest(),
            "verifier_sha256": hashlib.sha256(
                (
                    ROOT / "tools/verify_runtime_font_tile_provenance.py"
                ).read_bytes()
            ).hexdigest(),
            "test_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
        self.assertEqual(expected, self.artifact["implementation"])
        self.assertEqual(64, len(self.artifact["source"]["rom_sha256"]))
        self.assertEqual(
            64,
            len(self.artifact["source"]["parent_provenance_manifest_sha256"]),
        )
        self.assertEqual(
            64,
            len(self.artifact["source"]["dialogue_font_manifest_sha256"]),
        )
        self.assertEqual("git-artifact-promotion-v1", self.promotion["schema"])
        self.assertEqual(
            {"runtime-font-tile-provenance.json"},
            set(self.promotion["files"]),
        )
        self.assertTrue(self.promotion["verifier"]["report"]["verified"])

    def test_independent_verifier_rebuilds_and_rejects_tampering(self):
        from tools.verify_runtime_font_tile_provenance import verify_artifact

        source = (
            ROOT / "tools/verify_runtime_font_tile_provenance.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)

        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(61, report["layer_count"])
        self.assertEqual(1050, report["ordered_sjis_pair_count"])

        mutations = [
            lambda payload: payload["layers"][0]["ordered_sjis_pairs"][0].update(
                {"sjis_hex": "0xFFFF"}
            ),
            lambda payload: payload["layers"][0]["ordered_sjis_pairs"][0].update(
                {"expansion_palette_group": 0}
            ),
            lambda payload: payload["layers"][0]["ordered_sjis_pairs"][0].update(
                {"runtime_top_tile_sha256": "0" * 64}
            ),
            lambda payload: payload["source"].update(
                {"dialogue_font_manifest_sha256": "0" * 64}
            ),
            lambda payload: payload["layers"][0]["ordered_sjis_pairs"][0].update(
                {
                    "runtime_positions_tiles": [
                        payload["layers"][0]["ordered_sjis_pairs"][0][
                            "position_tiles"
                        ],
                        [
                            payload["layers"][0]["ordered_sjis_pairs"][0][
                                "position_tiles"
                            ][0]
                            + 1,
                            payload["layers"][0]["ordered_sjis_pairs"][0][
                                "position_tiles"
                            ][1],
                        ],
                    ]
                }
            ),
            lambda payload: payload["layers"][0]["ordered_sjis_pairs"][0].update(
                {
                    "runtime_tile_ids": list(
                        reversed(
                            payload["layers"][0]["ordered_sjis_pairs"][0][
                                "runtime_tile_ids"
                            ]
                        )
                    )
                }
            ),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                with tempfile.TemporaryDirectory() as temporary:
                    tampered = Path(temporary) / "artifact"
                    shutil.copytree(self.output, tampered)
                    payload_path = (
                        tampered / "runtime-font-tile-provenance.json"
                    )
                    payload = json.loads(
                        payload_path.read_text(encoding="utf-8")
                    )
                    mutate(payload)
                    payload_path.write_text(
                        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    rejected = verify_artifact(ROOT, tampered)
                    self.assertFalse(rejected["verified"])
                    self.assertTrue(rejected["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            (tampered / "unexpected.bin").write_bytes(b"unexpected")
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"])
            self.assertTrue(
                any(
                    "unexpected artifact files" in error
                    for error in rejected["errors"]
                ),
                rejected["errors"],
            )

    def _layer(self, checkpoint_name: str, bg_index: int) -> dict:
        return next(
            layer
            for layer in self.artifact["layers"]
            if layer["bg_index"] == bg_index
            and checkpoint_name
            in [Path(path).name for path in layer["checkpoint_paths"]]
        )

    @staticmethod
    def _pair(layer: dict, position: list[int]) -> dict:
        return next(
            pair
            for pair in layer["ordered_sjis_pairs"]
            if pair["position_tiles"] == position
        )


if __name__ == "__main__":
    unittest.main()
