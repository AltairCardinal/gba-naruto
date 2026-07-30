import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/portrait-palette-producers-v1"


class ExportPortraitPaletteProducersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_portrait_palette_producers import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.payload = export_artifact(ROOT, ARTIFACT / "raw", cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_enumerates_every_opcode_17_record_and_mode(self):
        self.assertEqual("portrait-palette-producers-v1", self.payload["schema"])
        self.assertEqual(
            {
                "non_null_script_slots": 110,
                "unique_script_roots": 98,
                "unique_instruction_nodes": 14199,
                "unique_opcode_17_records": 161,
                "opcode_17_root_references": 193,
                "mode_counts": {
                    "0": 48,
                    "1": 2,
                    "2": 29,
                    "3": 31,
                    "4": 11,
                    "5": 18,
                    "6": 4,
                    "7": 5,
                    "8": 13,
                },
                "parse_failures": [],
            },
            self.payload["chapter_denominator"]["summary"],
        )
        self.assertEqual(
            "17000001",
            next(
                row["raw_hex"]
                for row in self.payload["chapter_denominator"]["records"]
                if row["address"] == "0x08032724"
            ),
        )

    def test_binds_the_jump_table_and_mode_zero_fill(self):
        self.assertEqual(
            [
                {"mode": 0, "target": "0x08096BD4"},
                {"mode": 1, "target": "0x08096BF8"},
                {"mode": 2, "target": "0x08096C22"},
                {"mode": 3, "target": "0x08096C56"},
                {"mode": 4, "target": "0x08096C9C"},
                {"mode": 5, "target": "0x08096C9C"},
                {"mode": 6, "target": "0x08096CA8"},
                {"mode": 7, "target": "0x08096CBC"},
                {"mode": 8, "target": "0x08096CCC"},
            ],
            self.payload["transition_dispatch"]["jump_table"],
        )
        self.assertEqual(
            {
                "source": "u16 stack constant 0x001F",
                "destination": "0x02002882",
                "cpuset_control": "0x0100003F",
                "operation": "fixed-source fill of 63 halfwords",
                "preserved_entry": "0x02002880..0x02002881",
                "next_state": "0x40",
                "tick_reset": 0,
            },
            self.payload["mode_0_fill"]["static_semantics"],
        )
        self.assertEqual(
            {
                "source": "0x02002880",
                "destination": "0x05000200 + palette_bank * 32",
                "size_bytes": 128,
                "enqueue_callsite": "0x08096536",
                "enqueue_helper": "0x080635B8",
                "trigger": "state 0x40 and tick % 8 == 0",
            },
            self.payload["mode_0_fill"]["queue_semantics"],
        )

    def test_positive_and_zero_input_runtime_evidence_are_closed(self):
        runtime = self.payload["mode_0_fill"]["runtime"]
        self.assertFalse(runtime["control"]["audit"]["success"])
        self.assertEqual("timeout", runtime["control"]["audit"]["outcome"])
        self.assertEqual(0, runtime["control"]["audit"]["write_event_count"])
        self.assertEqual(105.01953125, runtime["control"]["guard"]["peak_tree_rss_mib"])

        positive = runtime["positive"]
        self.assertTrue(positive["audit"]["success"])
        self.assertTrue(positive["audit"]["arguments_match"])
        self.assertEqual(63, positive["audit"]["write_event_count"])
        self.assertEqual(8, positive["audit"]["tick"])
        self.assertEqual("0x02002880", positive["audit"]["r0"])
        self.assertEqual("0x05000200", positive["audit"]["r1"])
        self.assertEqual("0x00000080", positive["audit"]["r2"])
        self.assertEqual(
            {"0x0000": 1, "0x001F": 63},
            positive["scratch_halfword_histogram"],
        )
        self.assertEqual(
            [
                "chapter_opcode_17",
                "portrait_transition_helper",
                "portrait_mode_dispatch",
                "palette_fill_mode_0",
                "palette_fill_cpuset_wrapper",
                "palette_fill_mode_0_complete",
            ],
            positive["required_trace_prefix"],
        )
        self.assertEqual(84.015625, positive["guard"]["peak_tree_rss_mib"])

    def test_manifest_is_an_accepted_promotion_with_verifier_evidence(self):
        manifest = json.loads(
            (self.output / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual("git-artifact-promotion-v1", manifest["schema"])
        self.assertEqual("portrait-palette-producers-v1", manifest["artifact_schema"])
        self.assertEqual("accepted", manifest["artifact_status"])
        self.assertEqual(0, manifest["verifier"]["exit_code"])
        self.assertTrue(manifest["verifier"]["report"]["verified"])
        self.assertEqual([], manifest["verifier"]["report"]["errors"])

    def test_records_dim_transform_without_overclaiming_runtime(self):
        self.assertEqual(
            {
                "helper": "0x08096D4C",
                "callsite": "0x08096E3A",
                "enqueue_callsite": "0x08096E44",
                "source_destination": "0x02002880 in place",
                "color_count": 64,
                "formula": "((color & 0x7BDE) >> 1) + ((color & 0x739C) >> 2)",
            },
            self.payload["dim_transform"],
        )
        self.assertEqual(
            {
                "chapter_opcode_17_mode_denominator_complete": True,
                "mode_0_fill_static_complete": True,
                "mode_0_fill_runtime_complete": True,
                "mode_0_zero_input_control_complete": True,
                "dim_transform_static_complete": True,
                "dim_transform_runtime_complete": False,
                "all_scratch_02002880_producers_complete": False,
                "all_portrait_palette_runtime_paths_complete": False,
                "generic_palette_writeback_complete": False,
            },
            self.payload["scope"],
        )

    def test_long_term_notes_record_the_corrected_mode_and_superseded_gap(self):
        note = (ROOT / "notes/portrait-palette-producers-20260730.md").read_text(
            encoding="utf-8"
        )
        roadmap = (ROOT / "docs/sequel-roadmap.md").read_text(encoding="utf-8")
        queue_note = (
            ROOT / "notes/rom-gpu-copy-queue-inventory-20260730.md"
        ).read_text(encoding="utf-8")
        for text in (note, roadmap):
            self.assertIn("artifacts/portrait-palette-producers-v1/", text)
            self.assertIn("161", text)
            self.assertIn("48/161", text)
            self.assertIn("0x08096536", text)
            self.assertIn("mode 0", text)
        self.assertIn("已被后续成果取代", queue_note)
        self.assertIn("portrait-palette-producers-v1", queue_note)

    def test_export_is_deterministic_and_verifier_rejects_semantic_tamper(self):
        from tools.export_portrait_palette_producers import export_artifact
        from tools.verify_portrait_palette_producers import verify_artifact

        with tempfile.TemporaryDirectory() as temporary:
            second = Path(temporary) / "second"
            export_artifact(ROOT, ARTIFACT / "raw", second)
            first_hashes = {
                path.relative_to(self.output): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in self.output.rglob("*")
                if path.is_file()
            }
            second_hashes = {
                path.relative_to(second): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in second.rglob("*")
                if path.is_file()
            }
            self.assertEqual(first_hashes, second_hashes)

        source = (ROOT / "tools/verify_portrait_palette_producers.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)
        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            payload_path = tampered / "portrait-palette-producers.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["mode_0_fill"]["static_semantics"]["cpuset_control"] = "0x0100003E"
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][payload_path.name] = hashlib.sha256(
                payload_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"])
            self.assertTrue(rejected["errors"])

    def test_verifier_rejects_resigned_raw_trace_and_checkpoint_tamper(self):
        from tools.verify_portrait_palette_producers import verify_artifact

        def resign(artifact: Path, relative: str) -> None:
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            path = artifact / relative
            manifest["files"][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            relative = "raw/positive/trace.json"
            path = tampered / relative
            trace = json.loads(path.read_text(encoding="utf-8"))
            trace["events"][3]["address"] = "0x08096BD6"
            path.write_text(
                json.dumps(trace, separators=(",", ":")),
                encoding="utf-8",
            )
            resign(tampered, relative)
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"])
            self.assertTrue(rejected["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            relative = "raw/positive/hit.ss9"
            shutil.copyfile(
                tampered / "raw/control/timeout.ss9",
                tampered / relative,
            )
            resign(tampered, relative)
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"])
            self.assertTrue(rejected["errors"])


if __name__ == "__main__":
    unittest.main()
