import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = (
    ROOT
    / "build/experiments/active/residual-wram-tilemap-reachability"
    / "selection-post-consumer-zero-20260731"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rewrite_manifest(artifact: Path) -> None:
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


class ResidualWramTilemapRuntimeEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_residual_wram_tilemap_runtime_evidence import (
            export_artifact,
        )

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.payload = export_artifact(ROOT, RUN, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_first_direct_queue_tilemap_runtime_route(self):
        self.assertEqual(
            {
                "direct_queue_tilemap_denominator": 3,
                "runtime_verified_count": 1,
                "remaining_runtime_count": 2,
                "verified_source_pointer": "0x0834928C",
            },
            self.payload["summary"],
        )
        self.assertEqual(
            ["0x083F1C98", "0x085B67E0"],
            self.payload["remaining_direct_queue_sources"],
        )

    def test_binds_natural_checkpoint_load_queue_and_exact_flush(self):
        self.assertEqual([], self.payload["run"]["inputs"])
        self.assertEqual(0, self.payload["load_hit"]["frame"])
        self.assertEqual("0x0808AD3A", self.payload["load_hit"]["target"])
        self.assertEqual("0x0834928C", self.payload["load_hit"]["registers"]["r0"])
        self.assertEqual("0x02002B48", self.payload["load_hit"]["registers"]["r1"])
        self.assertEqual(
            {
                "slot_index": 0,
                "status": 3,
                "source": "0x02002B48",
                "destination": "0x0600001E",
                "source_stride_halfwords": 15,
                "row_count": 20,
            },
            self.payload["queue_flush"]["slot"],
        )
        self.assertEqual(2, self.payload["queue_flush"]["first_consumer_frame"])
        self.assertEqual(3, self.payload["queue_flush"]["post_consumer_frame"])
        self.assertEqual(
            0,
            self.payload["queue_flush"][
                "captured_entry_count_at_post_consumer"
            ],
        )
        self.assertTrue(
            self.payload["queue_flush"][
                "captured_entry_retired_before_post_consumer_capture"
            ]
        )
        self.assertFalse(self.payload["queue_flush"]["preflush_equals_source"])
        self.assertTrue(self.payload["queue_flush"]["final_equals_source"])
        self.assertEqual(600, self.payload["queue_flush"]["changed_byte_count"])
        self.assertEqual(
            self.payload["tilemap"]["decompressed_sha256"],
            self.payload["queue_flush"]["final_rows_sha256"],
        )

    def test_manifest_is_exact_deterministic_and_promotable(self):
        manifest = json.loads(
            (self.output / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual("git-artifact-promotion-v1", manifest["schema"])
        self.assertEqual("accepted", manifest["artifact_status"])
        self.assertEqual(
            "residual-wram-tilemap-runtime-evidence-v1",
            manifest["artifact_schema"],
        )
        self.assertEqual(
            {
                "audit.json",
                "final.png",
                "final-queue.bin",
                "final.ss9",
                "guard.json",
                "hit.ss9",
                "queue-at-consumer.bin",
                "runtime-evidence.json",
                "vram-at-consumer.bin",
                "vram-final.bin",
            },
            set(manifest["files"]),
        )
        self.assertTrue(
            {
                "tools/mgba_wram_tilemap_probe.lua",
                "tools/export_residual_wram_tilemap_runtime_evidence.py",
                "tools/verify_residual_wram_tilemap_runtime_evidence.py",
            }.issubset(manifest["implementation"])
        )
        with tempfile.TemporaryDirectory() as temporary:
            second = Path(temporary) / "artifact"
            from tools.export_residual_wram_tilemap_runtime_evidence import (
                export_artifact,
            )

            export_artifact(ROOT, RUN, second)
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

    def test_independent_verifier_accepts_and_rejects_resigned_tamper(self):
        from tools.verify_residual_wram_tilemap_runtime_evidence import (
            verify_artifact,
        )

        verifier_source = (
            ROOT / "tools/verify_residual_wram_tilemap_runtime_evidence.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "from tools.export_residual_wram_tilemap_runtime_evidence",
            verifier_source,
        )
        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(1, report["runtime_verified_count"])

        cases = (
            ("payload", "queue destination mismatch"),
            ("probe", "probe declaration mismatch"),
            ("vram", "final VRAM rows do not match ROM tilemap"),
        )
        for kind, expected_error in cases:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                artifact = Path(tmp) / "artifact"
                shutil.copytree(self.output, artifact)
                if kind == "payload":
                    path = artifact / "runtime-evidence.json"
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    payload["queue_flush"]["slot"]["destination"] = "0x06000020"
                    path.write_text(
                        json.dumps(
                            payload,
                            ensure_ascii=False,
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                elif kind == "probe":
                    path = artifact / "runtime-evidence.json"
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    payload["probe"]["path"] = "tools/another_probe.lua"
                    path.write_text(
                        json.dumps(
                            payload,
                            ensure_ascii=False,
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                else:
                    path = artifact / "vram-final.bin"
                    data = bytearray(path.read_bytes())
                    data[0x1E] ^= 1
                    path.write_bytes(data)
                _rewrite_manifest(artifact)
                rejected = verify_artifact(ROOT, artifact)
                self.assertFalse(rejected["verified"])
                self.assertTrue(
                    any(expected_error in error for error in rejected["errors"]),
                    rejected["errors"],
                )

    def test_parent_artifacts_are_semantically_bound_and_reject_resigning(self):
        from tools.verify_residual_wram_tilemap_runtime_evidence import (
            _verify_parent_artifacts,
        )

        parents = (
            "artifacts/lz77-palette-runtime-v1",
            "artifacts/residual-wram-tilemap-abi-v1",
            "artifacts/residual-wram-tilemap-resource-ownership-v1",
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in parents:
                shutil.copytree(ROOT / relative, root / relative)
            errors = []
            _verify_parent_artifacts(root, errors)
            self.assertEqual([], errors)

            evidence_path = root / parents[0] / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["entries"][1]["route"] = "resigned-fake-route"
            evidence_path.write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            manifest_path = root / parents[0] / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            new_hash = _sha256(evidence_path)
            manifest["files"]["evidence.json"] = new_hash
            manifest["payload_sha256"] = new_hash
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            errors = []
            _verify_parent_artifacts(root, errors)
            self.assertTrue(errors)
            self.assertTrue(
                any("parent runtime manifest SHA-256 mismatch" in error for error in errors),
                errors,
            )

    def test_verifier_rejects_extra_file_and_symlink(self):
        from tools.verify_residual_wram_tilemap_runtime_evidence import (
            verify_artifact,
        )

        for kind in ("extra", "symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                artifact = Path(tmp) / "artifact"
                shutil.copytree(self.output, artifact)
                if kind == "extra":
                    (artifact / "extra.bin").write_bytes(b"unexpected")
                else:
                    (artifact / "linked.bin").symlink_to("runtime-evidence.json")
                report = verify_artifact(ROOT, artifact)
                self.assertFalse(report["verified"])
                self.assertTrue(report["errors"])

    def test_exporter_cli_and_tracked_artifact_verify(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/export_residual_wram_tilemap_runtime_evidence.py",
                    "--root",
                    ".",
                    "--run",
                    str(RUN),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)

        tracked = ROOT / "artifacts/residual-wram-tilemap-runtime-v1"
        if tracked.is_dir():
            from tools.verify_residual_wram_tilemap_runtime_evidence import (
                verify_artifact,
            )

            report = verify_artifact(ROOT, tracked)
            self.assertTrue(report["verified"], report["errors"])


if __name__ == "__main__":
    unittest.main()
