import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExportRuntimeLayerStaticProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_runtime_layer_static_provenance import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.artifact = export_artifact(ROOT, cls.output)
        cls.promotion = json.loads(
            (cls.output / "manifest.json").read_text(encoding="utf-8")
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_classifies_every_tracked_enabled_layer_with_a_fixed_denominator(self):
        self.assertEqual(
            "runtime-layer-static-provenance-v1",
            self.artifact["schema"],
        )
        self.assertEqual(
            {
                "checkpoint_count": 91,
                "checkpoint_enabled_layer_count": 199,
                "unique_state_count": 89,
                "unique_state_enabled_layer_count": 196,
                "exact_static_source_count": 28,
                "partial_static_source_count": 107,
                "unidentified_runtime_payload_count": 61,
            },
            {
                key: self.artifact["summary"][key]
                for key in (
                    "checkpoint_count",
                    "checkpoint_enabled_layer_count",
                    "unique_state_count",
                    "unique_state_enabled_layer_count",
                    "exact_static_source_count",
                    "partial_static_source_count",
                    "unidentified_runtime_payload_count",
                )
            },
        )
        self.assertEqual(91, len(self.artifact["checkpoints"]))
        self.assertEqual(196, len(self.artifact["layers"]))
        self.assertEqual(
            196,
            sum(
                self.artifact["summary"][key]
                for key in (
                    "exact_static_source_count",
                    "partial_static_source_count",
                    "unidentified_runtime_payload_count",
                )
            ),
        )

    def test_registry_is_explicit_and_hash_binds_all_six_static_families(self):
        self.assertEqual(345, self.artifact["summary"]["candidate_count"])
        self.assertEqual(
            {
                "bg-resource-canvases-v1": 12,
                "map-canvases-v1": 61,
                "scene-visual-packs-v1": 9,
                "story-visual-layers-v1": 24,
                "tile-assets-bg-v2": 236,
                "world-map-backgrounds-v1": 3,
            },
            self.artifact["summary"]["candidate_family_counts"],
        )
        for source in self.artifact["source_registry"]:
            self.assertEqual(64, len(source["manifest_sha256"]))
            self.assertTrue((ROOT / source["manifest"]).is_file())

    def test_exact_world_map_and_regular_bg_sources_have_three_domain_evidence(self):
        world = self._layer("scenario-42-postbattle-world-map.ss9", 0)
        self.assertEqual("exact_static_source", world["classification"])
        self.assertEqual(
            ["world-map-backgrounds-v1/page-00"],
            [item["source_key"] for item in world["exact_sources"]],
        )
        world_match = world["exact_sources"][0]
        self.assertTrue(world_match["domains"]["graphics"]["exact"])
        self.assertTrue(world_match["domains"]["tilemap"]["exact"])
        self.assertTrue(world_match["domains"]["palette"]["exact"])
        self.assertEqual([0, 0], world_match["domains"]["tilemap"]["origin_tiles"])

        regular = self._layer("scenario-41-turn-1-complete.ss9", 0)
        self.assertEqual("exact_static_source", regular["classification"])
        self.assertEqual(
            "bg-resource-canvases-v1/entry-01",
            regular["exact_sources"][0]["source_key"],
        )
        self.assertGreater(
            regular["exact_sources"][0]["domains"]["palette"][
                "compared_color_count"
            ],
            0,
        )

    def test_partial_and_unidentified_are_not_promoted_to_exact_identity(self):
        partial = self._layer("scenario-41-player-turn.ss9", 0)
        self.assertEqual("partial_static_source", partial["classification"])
        self.assertFalse(partial["exact_sources"])
        self.assertTrue(
            any(
                item["source_key"].startswith("map-canvases-v1/")
                and item["domains"]["graphics"]["exact"]
                for item in partial["partial_sources"]
            )
        )

        unidentified = self._layer("scenario-41-player-turn.ss9", 3)
        self.assertEqual(
            "unidentified_runtime_payload",
            unidentified["classification"],
        )
        self.assertFalse(unidentified["exact_sources"])
        self.assertFalse(unidentified["partial_sources"])

    def test_scope_closes_only_observed_provenance(self):
        self.assertEqual(
            {
                "observed_runtime_layer_static_provenance_complete": True,
                "all_runtime_visual_payloads_named": False,
                "camera_or_scroll_writer_schedule_complete": False,
                "cross_frame_transition_timing_complete": False,
                "final_screen_composition_complete": False,
                "dynamic_palette_transform_semantics_complete": False,
            },
            self.artifact["scope"],
        )

    def test_manifest_binds_implementation_and_promotes_only_the_payload(self):
        expected = {
            "exporter_sha256": hashlib.sha256(
                (
                    ROOT / "tools/export_runtime_layer_static_provenance.py"
                ).read_bytes()
            ).hexdigest(),
            "verifier_sha256": hashlib.sha256(
                (
                    ROOT / "tools/verify_runtime_layer_static_provenance.py"
                ).read_bytes()
            ).hexdigest(),
            "test_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
        self.assertEqual(expected, self.artifact["implementation"])
        self.assertEqual("git-artifact-promotion-v1", self.promotion["schema"])
        self.assertEqual(
            {"runtime-layer-static-provenance.json"},
            set(self.promotion["files"]),
        )
        self.assertEqual(0, self.promotion["verifier"]["exit_code"])
        self.assertTrue(self.promotion["verifier"]["report"]["verified"])

    def test_independent_verifier_rebuilds_and_rejects_classification_tampering(self):
        from tools.verify_runtime_layer_static_provenance import verify_artifact

        source = (
            ROOT / "tools/verify_runtime_layer_static_provenance.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "from tools.export_runtime_layer_static_provenance", source
        )
        self.assertNotIn(
            "import tools.export_runtime_layer_static_provenance", source
        )
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)

        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(91, report["checkpoint_count"])
        self.assertEqual(196, report["layer_count"])

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            payload_path = tampered / "runtime-layer-static-provenance.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["layers"][0]["classification"] = "exact_static_source"
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

    def test_independent_verifier_rejects_extra_artifact_files(self):
        from tools.verify_runtime_layer_static_provenance import verify_artifact

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            (tampered / "unexpected.bin").write_bytes(b"not part of the artifact")
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any(
                    "unexpected artifact files" in error
                    for error in report["errors"]
                ),
                report["errors"],
            )

    def test_independent_verifier_rejects_source_registry_hash_tampering(self):
        from tools.verify_runtime_layer_static_provenance import verify_artifact

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            payload_path = tampered / "runtime-layer-static-provenance.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["source_registry"][0]["manifest_sha256"] = "0" * 64
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

    def _layer(self, checkpoint_name: str, bg_index: int) -> dict:
        checkpoint = next(
            item
            for item in self.artifact["checkpoints"]
            if item["path"].endswith(checkpoint_name)
        )
        return next(
            item
            for item in self.artifact["layers"]
            if item["state_id"] == checkpoint["state_id"]
            and item["bg_index"] == bg_index
        )


if __name__ == "__main__":
    unittest.main()
