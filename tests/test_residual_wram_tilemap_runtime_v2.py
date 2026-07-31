import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = (
    ROOT
    / "build/experiments/active/residual-wram-tilemap-reachability"
)
BRIDGE_RUN = RUN_ROOT / "scene-panel-v1-parent-b-bridge-20260731"
ZERO_RUN = RUN_ROOT / "scene-panel-v1-parent-direct-sources-zero5-20260731"


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
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


class ResidualWramTilemapRuntimeV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_residual_wram_tilemap_runtime_v2 import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.payload = export_artifact(
            ROOT,
            BRIDGE_RUN,
            ZERO_RUN,
            cls.output,
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_all_direct_queue_sources(self):
        self.assertEqual(
            {
                "direct_queue_tilemap_denominator": 3,
                "runtime_verified_count": 3,
                "remaining_runtime_count": 0,
                "verified_source_pointers": [
                    "0x0834928C",
                    "0x083F1C98",
                    "0x085B67E0",
                ],
            },
            self.payload["summary"],
        )
        self.assertEqual(
            {"0x083F1C98", "0x085B67E0"},
            {record["source_pointer"] for record in self.payload["tilemaps"]},
        )

    def test_binds_v1_checkpoint_single_b_bridge_and_zero_input(self):
        self.assertEqual(
            "artifacts/residual-wram-tilemap-runtime-v1/final.ss9",
            self.payload["bridge"]["input_checkpoint"]["path"],
        )
        self.assertEqual(
            [{"key": "B", "down_frame": 18, "up_frame": 20, "hold_frames": 2}],
            self.payload["bridge"]["inputs"],
        )
        self.assertEqual(28, self.payload["bridge"]["scene_panel_setup_hit"]["frame"])
        self.assertEqual("0x0808BAB0", self.payload["bridge"]["scene_panel_setup_hit"]["target"])
        self.assertEqual([], self.payload["zero_run"]["inputs"])
        self.assertEqual(5, self.payload["zero_run"]["capture_frames"])
        self.assertEqual(2, self.payload["zero_run"]["queue_consumer_hit_count"])

    def test_two_queue_slots_retire_and_flush_exact_rom_rows(self):
        expected = {
            "0x083F1C98": (0, "0x02002B78", "0x0600F810", 24, 12, 473),
            "0x085B67E0": (1, "0x02002DB8", "0x0600FC4E", 23, 3, 134),
        }
        for record in self.payload["tilemaps"]:
            slot_index, source, destination, width, height, changed = expected[
                record["source_pointer"]
            ]
            self.assertEqual(2, record["load_hit"]["frame"])
            self.assertEqual(source, record["load_hit"]["registers"]["r1"])
            self.assertEqual(
                {
                    "slot_index": slot_index,
                    "status": 3,
                    "source": source,
                    "destination": destination,
                    "source_stride_halfwords": width,
                    "row_count": height,
                },
                record["queue_flush"]["slot_at_first_consumer"],
            )
            self.assertEqual(2, record["queue_flush"]["status_at_final"])
            self.assertFalse(record["queue_flush"]["preflush_equals_source"])
            self.assertTrue(record["queue_flush"]["final_equals_source"])
            self.assertEqual(changed, record["queue_flush"]["changed_byte_count"])

    def test_manifest_is_deterministic_and_independent_verifier_rejects_tamper(self):
        from tools.export_residual_wram_tilemap_runtime_v2 import export_artifact
        from tools.verify_residual_wram_tilemap_runtime_v2 import verify_artifact

        verifier_source = (
            ROOT / "tools/verify_residual_wram_tilemap_runtime_v2.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools.export_residual_wram_tilemap_runtime_v2", verifier_source)
        manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual("residual-wram-tilemap-runtime-v2", manifest["artifact_id"])
        self.assertEqual("accepted", manifest["artifact_status"])
        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(3, report["runtime_verified_count"])

        with tempfile.TemporaryDirectory() as temporary:
            second = Path(temporary) / "artifact"
            export_artifact(ROOT, BRIDGE_RUN, ZERO_RUN, second)
            self.assertEqual(
                {
                    path.relative_to(self.output): _sha256(path)
                    for path in self.output.rglob("*")
                    if path.is_file()
                },
                {
                    path.relative_to(second): _sha256(path)
                    for path in second.rglob("*")
                    if path.is_file()
                },
            )

        for kind, expected_error in (
            ("bridge", "bridge setup checkpoint hash mismatch"),
            ("bridge_audit", "bridge audit total_hits mismatch"),
            ("consumer", "queue consumer address mismatch"),
            ("queue", "raw queue slot mismatch"),
            ("duplicate", "status-3 queue contract count mismatch"),
            ("vram", "final VRAM rows do not match ROM tilemap"),
        ):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                artifact = Path(temporary) / "artifact"
                shutil.copytree(self.output, artifact)
                if kind == "bridge":
                    path = artifact / "scene-panel-setup.ss9"
                    path.write_bytes(path.read_bytes() + b"tamper")
                elif kind == "bridge_audit":
                    for name in ("bridge-audit.json", "bridge-done.json"):
                        path = artifact / name
                        audit = json.loads(path.read_text(encoding="utf-8"))
                        audit["total_hits"] = 80
                        path.write_text(json.dumps(audit) + "\n", encoding="utf-8")
                    payload_path = artifact / "runtime-evidence.json"
                    payload = json.loads(payload_path.read_text(encoding="utf-8"))
                    payload["bridge"]["audit_sha256"] = _sha256(
                        artifact / "bridge-audit.json"
                    )
                    payload_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
                elif kind == "consumer":
                    for name in ("zero-audit.json", "zero-done.json"):
                        path = artifact / name
                        audit = json.loads(path.read_text(encoding="utf-8"))
                        event = next(
                            event
                            for event in audit["events"]
                            if event["target"] == "queue_consumer"
                        )
                        event["address"] = "0x08000000"
                        path.write_text(json.dumps(audit) + "\n", encoding="utf-8")
                    payload_path = artifact / "runtime-evidence.json"
                    payload = json.loads(payload_path.read_text(encoding="utf-8"))
                    payload["zero_run"]["audit_sha256"] = _sha256(
                        artifact / "zero-audit.json"
                    )
                    payload_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
                elif kind == "queue":
                    path = artifact / "queue-at-consumer.bin"
                    data = bytearray(path.read_bytes())
                    data[8] ^= 1
                    path.write_bytes(data)
                elif kind == "duplicate":
                    path = artifact / "queue-at-consumer.bin"
                    data = bytearray(path.read_bytes())
                    data[32:48] = data[0:16]
                    path.write_bytes(data)
                else:
                    path = artifact / "vram-final.bin"
                    data = bytearray(path.read_bytes())
                    data[0xF810] ^= 1
                    path.write_bytes(data)
                _resign(artifact)
                rejected = verify_artifact(ROOT, artifact)
                self.assertFalse(rejected["verified"])
                self.assertTrue(
                    any(expected_error in error for error in rejected["errors"]),
                    rejected["errors"],
                )


if __name__ == "__main__":
    unittest.main()
