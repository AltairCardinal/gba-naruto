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
PHASE_A = RUN_ROOT / "choice-state3-phase-a-closure-v6-20260801"
PHASE_B = RUN_ROOT / "choice-state3-phase-b-closure-v6-20260801"
UNLOCK = RUN_ROOT / "choice-completion-unlock-default-20260731-v2"
STATE3 = RUN_ROOT / "choice-state3-checkpoint-20260801"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _resign(artifact: Path) -> None:
    manifest_path = artifact / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = {
        path.relative_to(artifact).as_posix(): _sha256(path)
        for path in sorted(artifact.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    manifest["payload_sha256"] = manifest["files"]["runtime-evidence.json"]
    _write_json(manifest_path, manifest)


class ResidualWramTransformedTilemapRuntimeEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_residual_wram_transformed_tilemap_runtime_evidence import (
            export_artifact,
        )

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.payload = export_artifact(
            ROOT,
            UNLOCK,
            STATE3,
            PHASE_A,
            PHASE_B,
            cls.output,
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_all_three_transformed_sources_without_claiming_natural_entry(self):
        self.assertEqual(
            {
                "transformed_tilemap_denominator": 3,
                "controlled_runtime_verified_count": 3,
                "remaining_runtime_count": 0,
                "verified_source_pointers": [
                    "0x084634B8",
                    "0x0846356C",
                    "0x084635D8",
                ],
            },
            self.payload["summary"],
        )
        self.assertEqual("controlled", self.payload["entry_provenance"]["evidence_mode"])
        self.assertEqual(
            [{"address": "0x020240BC", "before": 0, "after": 1}],
            self.payload["entry_provenance"]["controlled_memory_patches"],
        )
        self.assertFalse(self.payload["scope"]["natural_entry_reachability_verified"])
        self.assertTrue(self.payload["scope"]["controlled_entry_base_rom_runtime_verified"])

    def test_distinguishes_shared_phase_b_submit_by_load_and_queue_correlation(self):
        records = {
            record["source_pointer"]: record
            for record in self.payload["source_closures"]
        }
        self.assertEqual(
            {"0x084634B8", "0x0846356C", "0x084635D8"}, set(records)
        )
        self.assertEqual("0x08090B5C", records["0x084634B8"]["load_event"]["address"])
        self.assertEqual("0x08090D56", records["0x0846356C"]["load_event"]["address"])
        self.assertEqual("0x08090DC4", records["0x084635D8"]["load_event"]["address"])
        self.assertEqual(142, records["0x0846356C"]["queue_correlation"]["submit_frame"])
        self.assertEqual(150, records["0x084635D8"]["queue_correlation"]["submit_frame"])
        for record in records.values():
            self.assertEqual(3, record["queue_correlation"]["pre_status"])
            self.assertEqual(2, record["queue_correlation"]["post_status"])
            self.assertEqual(
                "0x0806365C",
                record["queue_correlation"]["queue_pre_event"]["address"],
            )
            self.assertEqual(
                "0x080636CE",
                record["queue_correlation"]["queue_post_event"]["address"],
            )
            audit = json.loads(
                (self.output / f"runs/{record['run']}/audit.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn(record["queue_correlation"]["queue_pre_event"], audit["events"])
            self.assertIn(record["queue_correlation"]["queue_post_event"], audit["events"])
            self.assertTrue(record["post_vram_rows_equal_output"])

    def test_independent_verifier_rejects_resigned_semantic_and_binary_tamper(self):
        from tools.verify_residual_wram_transformed_tilemap_runtime_evidence import (
            verify_artifact,
        )

        verifier_source = (
            ROOT / "tools/verify_residual_wram_transformed_tilemap_runtime_evidence.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "from tools.export_residual_wram_transformed_tilemap_runtime_evidence",
            verifier_source,
        )
        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])

        for kind, expected_error in (
            ("natural_claim", "scope mismatch"),
            ("phase_b_identity", "queue correlation mismatch"),
            ("audit_cycle", "audit event cycle mismatch"),
            ("cross_frame_queue", "same consumer sweep mismatch"),
            ("missing_queue_transcript", "same consumer sweep mismatch"),
            ("queue_status", "queue pre slot mismatch"),
            ("post_vram", "post VRAM rows do not match transformed output"),
            ("transformed_output", "runtime transform mismatch"),
        ):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                artifact = Path(temporary) / "artifact"
                shutil.copytree(self.output, artifact)
                payload_path = artifact / "runtime-evidence.json"
                payload = json.loads(payload_path.read_text(encoding="utf-8"))
                if kind == "natural_claim":
                    payload["scope"]["natural_entry_reachability_verified"] = True
                elif kind == "phase_b_identity":
                    source = next(
                        record
                        for record in payload["source_closures"]
                        if record["source_pointer"] == "0x0846356C"
                    )
                    source["queue_correlation"]["submit_frame"] = 150
                elif kind == "audit_cycle":
                    audit_path = artifact / "runs/phase-b/audit.json"
                    audit = json.loads(audit_path.read_text(encoding="utf-8"))
                    correlation = next(
                        row
                        for row in audit["correlated_queue_hits"]
                        if row["source_pointer"] == "0x0846356C"
                    )
                    correlation["load_cycle"] = str(int(correlation["load_cycle"]) + 1)
                    _write_json(audit_path, audit)
                    (artifact / "runs/phase-b/done.marker").write_bytes(
                        audit_path.read_bytes()
                    )
                    source = next(
                        record
                        for record in payload["source_closures"]
                        if record["source_pointer"] == "0x0846356C"
                    )
                    source["queue_correlation"] = correlation
                    payload["runs"]["phase-b"]["audit_sha256"] = _sha256(audit_path)
                elif kind == "cross_frame_queue":
                    audit_path = artifact / "runs/phase-b/audit.json"
                    audit = json.loads(audit_path.read_text(encoding="utf-8"))
                    correlation = next(
                        row
                        for row in audit["correlated_queue_hits"]
                        if row["source_pointer"] == "0x0846356C"
                    )
                    correlation["queue_post_frame"] += 1
                    correlation["queue_post_event"]["frame"] += 1
                    _write_json(audit_path, audit)
                    (artifact / "runs/phase-b/done.marker").write_bytes(
                        audit_path.read_bytes()
                    )
                    source = next(
                        record
                        for record in payload["source_closures"]
                        if record["source_pointer"] == "0x0846356C"
                    )
                    source["queue_correlation"] = correlation
                    payload["runs"]["phase-b"]["audit_sha256"] = _sha256(audit_path)
                elif kind == "missing_queue_transcript":
                    audit_path = artifact / "runs/phase-b/audit.json"
                    audit = json.loads(audit_path.read_text(encoding="utf-8"))
                    correlation = next(
                        row
                        for row in audit["correlated_queue_hits"]
                        if row["source_pointer"] == "0x0846356C"
                    )
                    audit["events"].remove(correlation["queue_pre_event"])
                    _write_json(audit_path, audit)
                    (artifact / "runs/phase-b/done.marker").write_bytes(
                        audit_path.read_bytes()
                    )
                    payload["runs"]["phase-b"]["audit_sha256"] = _sha256(audit_path)
                elif kind == "queue_status":
                    path = artifact / "sources/084634B8/queue-pre.bin"
                    data = bytearray(path.read_bytes())
                    source = next(
                        record
                        for record in payload["source_closures"]
                        if record["source_pointer"] == "0x084634B8"
                    )
                    slot = source["queue_correlation"]["slot_index"]
                    data[slot * 16 : slot * 16 + 4] = (2).to_bytes(4, "little")
                    path.write_bytes(data)
                    source["files"]["queue_pre_sha256"] = _sha256(path)
                elif kind == "post_vram":
                    path = artifact / "sources/084635D8/post-vram-rows.bin"
                    data = bytearray(path.read_bytes())
                    data[64] ^= 1
                    path.write_bytes(data)
                    source = next(
                        record
                        for record in payload["source_closures"]
                        if record["source_pointer"] == "0x084635D8"
                    )
                    source["files"]["post_vram_rows_sha256"] = _sha256(path)
                else:
                    source_dir = artifact / "sources/084634B8"
                    output_path = source_dir / "output-rows.bin"
                    post_rows_path = source_dir / "post-vram-rows.bin"
                    post_vram_path = source_dir / "post-vram.bin"
                    output = bytearray(output_path.read_bytes())
                    output[0] ^= 1
                    output_path.write_bytes(output)
                    post_rows_path.write_bytes(output)
                    post_vram = bytearray(post_vram_path.read_bytes())
                    post_vram[0x806] = output[0]
                    post_vram_path.write_bytes(post_vram)
                    source = next(
                        record
                        for record in payload["source_closures"]
                        if record["source_pointer"] == "0x084634B8"
                    )
                    source["files"]["output_rows_sha256"] = _sha256(output_path)
                    source["files"]["post_vram_rows_sha256"] = _sha256(post_rows_path)
                    source["files"]["post_vram_sha256"] = _sha256(post_vram_path)
                    pre = (source_dir / "pre-vram-rows.bin").read_bytes()
                    source["changed_byte_count"] = sum(
                        left != right for left, right in zip(pre, output)
                    )
                _write_json(payload_path, payload)
                _resign(artifact)
                rejected = verify_artifact(ROOT, artifact)
                self.assertFalse(rejected["verified"])
                self.assertTrue(
                    any(expected_error in error for error in rejected["errors"]),
                    rejected["errors"],
                )


if __name__ == "__main__":
    unittest.main()
