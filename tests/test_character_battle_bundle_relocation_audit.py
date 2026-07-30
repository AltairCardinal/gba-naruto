import hashlib
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CharacterBattleBundleRelocationAuditTests(unittest.TestCase):
    def test_all_250_resources_fit_and_independent_verifier_rebuilds_output(self):
        from tools.export_character_battle_bundle_relocation_audit import (
            export_audit,
        )
        from tools.verify_character_battle_bundle_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "audit"
            payload = export_audit(ROOT, output)
            verification = verify_audit(ROOT, output)
            promotion_path = output / "manifest.json"
            promotion = json.loads(promotion_path.read_text(encoding="utf-8"))
            payload_path = output / "relocation-audit.json"
            original_payload_text = payload_path.read_text(encoding="utf-8")
            tampered_manifest = json.loads(
                original_payload_text
            )
            coincidence = next(
                item
                for resource in tampered_manifest["resources"]
                for item in resource["compressed_payload_coincidences"]
            )
            coincidence["source_offset"] += 4
            payload_path.write_text(
                json.dumps(tampered_manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            tampered_digest = hashlib.sha256(payload_path.read_bytes()).hexdigest()
            promotion["payload_sha256"] = tampered_digest
            promotion["files"]["relocation-audit.json"] = tampered_digest
            promotion_path.write_text(
                json.dumps(promotion, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            tampered_verification = verify_audit(ROOT, output)

            payload_path.write_text(original_payload_text, encoding="utf-8")
            author_spec_path = output / "full-relocation-spec.json"
            author_spec = json.loads(
                author_spec_path.read_text(encoding="utf-8")
            )
            author_spec["edits"][0]["frames"] = []
            author_spec_path.write_text(
                json.dumps(author_spec, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            semantic_manifest = json.loads(original_payload_text)
            semantic_manifest["authoring_spec"]["sha256"] = hashlib.sha256(
                author_spec_path.read_bytes()
            ).hexdigest()
            payload_path.write_text(
                json.dumps(semantic_manifest, ensure_ascii=False, indent=2)
                + "\n",
                encoding="utf-8",
            )
            semantic_payload_digest = hashlib.sha256(
                payload_path.read_bytes()
            ).hexdigest()
            promotion["payload_sha256"] = semantic_payload_digest
            promotion["files"]["relocation-audit.json"] = semantic_payload_digest
            promotion["files"]["full-relocation-spec.json"] = hashlib.sha256(
                author_spec_path.read_bytes()
            ).hexdigest()
            promotion_path.write_text(
                json.dumps(promotion, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            semantic_tampered_verification = verify_audit(ROOT, output)

        self.assertEqual("git-artifact-promotion-v1", promotion["schema"])
        self.assertEqual("accepted", promotion["artifact_status"])
        self.assertEqual("relocation-audit.json", promotion["payload_file"])
        self.assertEqual(
            {"relocation-audit.json", "full-relocation-spec.json"},
            set(promotion["files"]),
        )
        summary = payload["summary"]
        self.assertEqual(250, summary["resource_count"])
        self.assertEqual(342, summary["descriptor_slot_count"])
        self.assertEqual(2004, summary["frame_count"])
        self.assertEqual(2190, summary["component_count"])
        self.assertEqual(784, summary["animation_count"])
        self.assertEqual(3187, summary["keyframe_count"])
        self.assertEqual(60430, summary["tile_count"])
        self.assertEqual(3815, summary["reference_count"])
        self.assertEqual(1, summary["compressed_payload_coincidence_count"])
        self.assertEqual(0, summary["unexpected_external_reference_count"])
        coincidences = [
            item
            for resource in payload["resources"]
            for item in resource["compressed_payload_coincidences"]
        ]
        self.assertEqual(
            [
                {
                    "pointer": "0x08220E80",
                    "source_offset": 0x446CC8,
                    "classification": "pointed_lz77_payload_coincidence",
                    "container_start": 0x4414E4,
                    "container_end": 0x4491D8,
                    "container_pointer_sources": [0x5A8014],
                }
            ],
            coincidences,
        )
        self.assertEqual(0x600000, summary["allocation_start"])
        self.assertLessEqual(summary["allocation_end"], 0x800000)
        self.assertGreater(summary["remaining_bytes"], 0)
        self.assertEqual([], verification["errors"])
        self.assertEqual(250, verification["verified_resources"])
        self.assertEqual(342, verification["verified_descriptors"])
        self.assertEqual(
            payload["output_rom_sha256"],
            verification["rebuilt_output_rom_sha256"],
        )
        self.assertEqual(1, verification["verified_compressed_payload_coincidences"])
        self.assertTrue(tampered_verification["errors"])
        self.assertTrue(semantic_tampered_verification["errors"])


if __name__ == "__main__":
    unittest.main()
