import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = (
    ROOT
    / "build/experiments/active/residual-wram-crop-tilemap-runtime"
    / "scene-panel-crop-consumer-wram-zero5-20260731"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resign(artifact: Path) -> None:
    manifest_path = artifact / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = {
        path.relative_to(artifact).as_posix(): _sha256(path)
        for path in sorted(artifact.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    manifest["payload_sha256"] = manifest["files"]["runtime-evidence.json"]
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")


class ResidualWramCropTilemapRuntimeEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_residual_wram_crop_tilemap_runtime_evidence import (
            export_artifact,
        )

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.payload = export_artifact(ROOT, RUN, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_one_of_four_derived_wram_tilemaps(self):
        self.assertEqual(
            {
                "derived_tilemap_denominator": 4,
                "runtime_verified_count": 1,
                "remaining_runtime_count": 3,
                "verified_source_pointer": "0x083F2108",
                "remaining_source_pointers": [
                    "0x084634B8",
                    "0x0846356C",
                    "0x084635D8",
                ],
            },
            self.payload["summary"],
        )

    def test_binds_load_consumer_crop_and_exact_final_vram(self):
        self.assertEqual([], self.payload["run"]["inputs"])
        self.assertEqual("0x0808BC2E", self.payload["load_hit"]["target"])
        self.assertEqual("0x083F2108", self.payload["load_hit"]["registers"]["r0"])
        self.assertEqual("0x02002880", self.payload["load_hit"]["registers"]["r1"])
        self.assertEqual("0x0808B79C", self.payload["consumer_hit"]["target"])
        self.assertEqual("0x0808BC3B", self.payload["consumer_hit"]["lr"])
        crop = self.payload["crop_flush"]
        self.assertEqual(40, crop["source_width_entries"])
        self.assertEqual(32, crop["submitted_width_entries"])
        self.assertEqual(10, crop["height_entries"])
        self.assertEqual(8, crop["discarded_right_entries_per_row"])
        self.assertFalse(crop["consumer_entry_equals_expected"])
        self.assertTrue(crop["consumer_wram_equals_source"])
        self.assertTrue(crop["final_equals_expected"])
        self.assertEqual(640, crop["changed_byte_count"])

    def test_independent_verifier_accepts_and_rejects_resigned_tamper(self):
        from tools.verify_residual_wram_crop_tilemap_runtime_evidence import (
            verify_artifact,
        )

        source = (
            ROOT / "tools/verify_residual_wram_crop_tilemap_runtime_evidence.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "from tools.export_residual_wram_crop_tilemap_runtime_evidence",
            source,
        )
        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])

        for kind, expected_error in (
            ("consumer", "consumer address mismatch"),
            ("geometry", "crop payload mismatch"),
            ("wram_discarded", "consumer WRAM does not match ROM source"),
            ("wram_next_row", "consumer WRAM does not match ROM source"),
            ("vram", "final VRAM crop does not match ROM source"),
        ):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                artifact = Path(temporary) / "artifact"
                shutil.copytree(self.output, artifact)
                payload_path = artifact / "runtime-evidence.json"
                payload = json.loads(payload_path.read_text(encoding="utf-8"))
                if kind == "consumer":
                    for name in ("audit.json", "done.json"):
                        path = artifact / name
                        audit = json.loads(path.read_text(encoding="utf-8"))
                        first = next(
                            event
                            for event in audit["events"]
                            if event["target"] == "crop_consumer"
                        )
                        first["address"] = "0x08000000"
                        path.write_text(json.dumps(audit) + "\n", encoding="utf-8")
                    payload["run"]["audit_sha256"] = _sha256(artifact / "audit.json")
                elif kind == "geometry":
                    payload["crop_flush"]["submitted_width_entries"] = 31
                elif kind in {"wram_discarded", "wram_next_row"}:
                    path = artifact / "wram-at-consumer.bin"
                    data = bytearray(path.read_bytes())
                    data[64 if kind == "wram_discarded" else 80] ^= 1
                    path.write_bytes(data)
                    payload["run"]["consumer_wram_sha256"] = _sha256(path)
                else:
                    path = artifact / "vram-final.bin"
                    data = bytearray(path.read_bytes())
                    data[0x1100] ^= 1
                    path.write_bytes(data)
                    payload["run"]["final_vram_sha256"] = _sha256(path)
                payload_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
                _resign(artifact)
                rejected = verify_artifact(ROOT, artifact)
                self.assertFalse(rejected["verified"])
                self.assertTrue(
                    any(expected_error in error for error in rejected["errors"]),
                    rejected["errors"],
                )


if __name__ == "__main__":
    unittest.main()
