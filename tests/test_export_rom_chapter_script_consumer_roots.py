"""TDD contract for the frozen chapter-script consumer-root packet.

The initial RED run intentionally imports the not-yet-created exporter and
independent verifier.  Later phases extend this file without changing the
frozen contract.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/chapter-script-consumer-roots-luna-20260902"
SCHEMA = "rom-chapter-script-consumer-roots-v1"
PAYLOAD_NAME = "rom-chapter-script-consumer-roots.json"
BUNDLE_NAME = "chapter-script-consumer-roots.bin"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "3b13c811baf8f8d14af074e9c2dc9057932cfe720ad8e16e06f8f6cd17d09daf"
CONSUMERS = [
    {
        "id": "consumer-root1",
        "range": [0x08A534, 0x08A588],
        "sha256": "2eebdb3fecb96d74024180c6c3ff764d9ed0af2a25860a985f714cc9da8d57ad",
        "root": 0x05CD41,
        "literal_offset": 0x08A558,
        "load_offset": 0x08A548,
        "call_offset": 0x08A54C,
    },
    {
        "id": "consumer-root2",
        "range": [0x08A588, 0x08A638],
        "sha256": "b530a0bcb184060e1e1a576307919bc09e937bb1c2297d55b0f0ea879c978299",
        "root": 0x05D593,
        "literal_offset": 0x08A630,
        "load_offset": 0x08A5E8,
        "call_offset": 0x08A5FC,
    },
]
CLOSURES = [[0x05CD41, 0x05D593], [0x05D593, 0x060C70]]
CLOSURE_SHA256 = [
    "cab4ef4ab61ecdb4589627f9d6043291583668132020cd6f2678b0c49ced013c",
    "536e360a8006ace91135080e29981495559ff8555275fa0a505ae951cd9eee4f",
]
UNION_SHA256 = "7e506f02abfe85c21a01066ce010b40d0a43b8d528fb53b77cc3be7cb1b22907"
NODE_VECTOR_SHA256 = "60c3a271dbd095b1d922d04215ce8050d6496bbd18e39410222e217304ff6a36"
EDGE_VECTOR_SHA256 = "3cea3a0c8a891d48e73a3d4a1ad13d3043a67236506a4ea6d3e160bc8b260ea4"


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


class ChapterScriptConsumerRootsRedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # RED: this import must fail before the implementation is created.
        from tools import export_rom_chapter_script_consumer_roots as exporter
        from tools import verify_rom_chapter_script_consumer_roots as verifier

        cls.exporter = exporter
        cls.verifier = verifier
        cls.payload = exporter.build_payload(ROOT)
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def _export(self, parent: Path) -> Path:
        output = parent / SCHEMA
        self.exporter.export_artifact(ROOT, output)
        return output

    def test_frozen_consumer_bindings_and_roots(self) -> None:
        payload = self.payload
        self.assertEqual(SCHEMA, payload["schema"])
        self.assertEqual(ROM_SHA256, payload["rom"]["sha256"])
        self.assertEqual(CONSUMERS, payload["consumer_bindings"])
        self.assertEqual(CLOSURES, payload["closures"]["ranges"])
        self.assertEqual(CLOSURE_SHA256, payload["closures"]["range_sha256"])
        flow1, flow2 = payload["consumer_dataflow"]
        self.assertEqual(
            {"load_register": "r0", "argument_register": "r0", "argument_move": None},
            flow1["root_register_flow"],
        )
        self.assertEqual(
            {
                "load_register": "r5",
                "argument_register": "r0",
                "argument_move": {"offset": 0x08A5F8, "halfword": "0x1C28"},
            },
            flow2["root_register_flow"],
        )
        self.assertEqual(
            {"offset": 0x08A5FA, "halfword": "0x1C31", "register": "r1"},
            flow2["secondary_argument_move"],
        )

    def test_exact_closure_denominators_and_non_claimed_boundaries(self) -> None:
        closure = self.payload["closures"]
        self.assertEqual(
            {"root1": {"nodes": 406, "edges": 608, "terminals": 1, "bytes": 2130},
             "root2": {"nodes": 714, "edges": 714, "terminals": 101, "bytes": 14045},
             "union": {"nodes": 1120, "edges": 1322, "terminals": 102, "bytes": 16175}},
            closure["summary"],
        )
        self.assertEqual([], closure["frontiers"])
        self.assertEqual(NODE_VECTOR_SHA256, closure["node_vector_sha256"])
        self.assertEqual(EDGE_VECTOR_SHA256, closure["edge_vector_sha256"])
        self.assertEqual([], closure["root_intersection"]["node_offsets"])
        self.assertEqual([], closure["root_intersection"]["byte_offsets"])
        self.assertFalse(closure["root_intersection"]["root1_to_root2_edge"])
        self.assertEqual(
            {"left": [0x05CD40, 0x05CD41], "right": [0x060C70, 0x060C74]},
            self.payload["non_claims"]["adjacent_boundaries"],
        )
        self.assertEqual(1120, len(closure["nodes"]))
        self.assertNotIn("nodes", self.payload)

    def test_historical_coverage_is_reference_only(self) -> None:
        self.assertEqual(
            {
                "path": "sequel/rom-byte-coverage.json",
                "sha256": COVERAGE_SHA256,
                "observed_during_this_build": False,
                "projection_gate_deferred_to": "tools/audit_rom_byte_coverage.py",
            },
            self.payload["historical_coverage_reference"],
        )
        self.assertFalse("coverage_baseline" in self.payload)
        promoted = [tuple(row["range"]) for row in self.payload["promotion"]["claims"]]
        for consumer in CONSUMERS:
            start, end = consumer["range"]
            self.assertFalse(any(a < end and start < b for a, b in promoted))
        self.assertIn(
            "consumer slices are bound as evidence; only the two closures are classified and promoted",
            " ".join(self.payload["limitations"]),
        )

    def test_happy_path_and_report_receipt(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            artifact = self._export(Path(raw))
            report = self.verifier.verify_artifact(ROOT, artifact)
            self.assertTrue(report["verified"], report)
            self.assertFalse(report["current_unknown_checked"])
            self.assertTrue(report["coverage_projection_gate_deferred"])
            self.assertEqual(
                {"manifest.json", PAYLOAD_NAME, BUNDLE_NAME},
                {path.name for path in artifact.iterdir()},
            )

    def _refresh_manifest_entry(self, artifact: Path, name: str) -> None:
        manifest_path = artifact / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        path = artifact / name
        manifest["files"][name] = {
            "size": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        manifest_path.write_bytes(_canonical(manifest))

    def test_mutations_fail_closed(self) -> None:
        bad = bytearray(self.rom)
        # Exercise ROM, consumer instruction, literal, root opcode, and the
        # second consumer's bound literal independently.
        for offset in (0x060C6F, 0x08A548, 0x08A558, 0x05CD41, 0x08A630, 0x05D593):
            bad[offset] ^= 1
            with self.assertRaises(ValueError):
                self.exporter.build_payload(ROOT, rom_override=bytes(bad))
            bad[offset] ^= 1
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            artifact = self._export(Path(raw))
            payload_path = artifact / PAYLOAD_NAME
            payload = json.loads(payload_path.read_text())
            payload["scope"]["consumer_bound"] = False
            payload_path.write_bytes(_canonical(payload))
            self._refresh_manifest_entry(artifact, PAYLOAD_NAME)
            self.assertFalse(self.verifier.verify_artifact(ROOT, artifact)["verified"])

            payload = json.loads(payload_path.read_text())
            payload["limitations"] = []
            payload["closures"]["node_vector_sha256"] = "0" * 64
            payload["closures"]["frontiers"] = [0x05CD40]
            payload_path.write_bytes(_canonical(payload))
            self._refresh_manifest_entry(artifact, PAYLOAD_NAME)
            self.assertFalse(self.verifier.verify_artifact(ROOT, artifact)["verified"])

            artifact = self._export(Path(raw) / "bundle")
            bundle_path = artifact / BUNDLE_NAME
            bundle = bytearray(bundle_path.read_bytes())
            bundle[-1] ^= 1
            bundle_path.write_bytes(bundle)
            self._refresh_manifest_entry(artifact, BUNDLE_NAME)
            self.assertFalse(self.verifier.verify_artifact(ROOT, artifact)["verified"])

            artifact = self._export(Path(raw) / "manifest")
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["artifact_status"] = "accepted"
            manifest_path.write_bytes(_canonical(manifest))
            self.assertFalse(self.verifier.verify_artifact(ROOT, artifact)["verified"])

    def test_extra_file_symlink_ancestor_and_report_no_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            foreign = parent / "foreign"
            foreign.mkdir()
            (foreign / "extra").write_text("x")
            with self.assertRaises(ValueError):
                self.exporter.export_artifact(ROOT, foreign)
            target = parent / "real"
            target.mkdir()
            alias = parent / "alias"
            os.symlink(target, alias)
            with self.assertRaises(ValueError):
                self.exporter.export_artifact(ROOT, alias / SCHEMA)
            artifact = self._export(target)
            alias_artifact = parent / "artifact-alias"
            os.symlink(target, alias_artifact)
            self.assertFalse(self.verifier.verify_artifact(ROOT, alias_artifact)["verified"])
            child = artifact / PAYLOAD_NAME
            child_copy = parent / "payload-copy.json"
            child_copy.write_bytes(child.read_bytes())
            child.unlink()
            os.symlink(child_copy, child)
            self.assertFalse(self.verifier.verify_artifact(ROOT, artifact)["verified"])
            report = parent / "report.json"
            self.verifier.write_report_atomic(report, {"verified": True})
            with self.assertRaises(ValueError):
                self.verifier.write_report_atomic(report, {"verified": False})
            self.assertEqual({"verified": True}, json.loads(report.read_text()))

    def test_verifier_is_independent_and_artifact_has_regular_children(self) -> None:
        source = (ROOT / "tools/verify_rom_chapter_script_consumer_roots.py").read_text()
        imports = [node for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("export_rom_chapter_script_consumer_roots" in ast.unparse(node) for node in imports))
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            artifact = self._export(Path(raw))
            self.assertTrue(all(path.is_file() and not path.is_symlink() for path in artifact.iterdir()))

    def test_noncanonical_payload_and_manifest_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            artifact = self._export(Path(raw))
            payload_path = artifact / PAYLOAD_NAME
            payload_path.write_bytes(b" " + payload_path.read_bytes())
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            payload_raw = payload_path.read_bytes()
            manifest["files"][PAYLOAD_NAME] = {
                "size": len(payload_raw),
                "sha256": hashlib.sha256(payload_raw).hexdigest(),
            }
            manifest_path.write_bytes(_canonical(manifest))
            self.assertFalse(self.verifier.verify_artifact(ROOT, artifact)["verified"])

            artifact = self._export(Path(raw) / "manifest")
            manifest_path = artifact / "manifest.json"
            manifest_path.write_bytes(b" " + manifest_path.read_bytes())
            self.assertFalse(self.verifier.verify_artifact(ROOT, artifact)["verified"])

    def test_atomic_commit_does_not_replace_racing_targets(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            real = self.exporter._rename_noreplace_at

            def competing_directory(source_fd, source, destination_fd, destination):
                os.mkdir(destination, dir_fd=destination_fd)
                return real(source_fd, source, destination_fd, destination)

            with mock.patch.object(
                self.exporter,
                "_rename_noreplace_at",
                side_effect=competing_directory,
            ):
                with self.assertRaises(ValueError):
                    self.exporter.export_artifact(ROOT, parent / "racing-artifact")
            self.assertTrue((parent / "racing-artifact").is_dir())

            report = parent / "racing-report.json"
            real_report = self.verifier._rename_noreplace_at

            def competing_file(source_fd, source, destination_fd, destination):
                fd = os.open(
                    destination,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o644,
                    dir_fd=destination_fd,
                )
                try:
                    os.write(fd, b"keep")
                finally:
                    os.close(fd)
                return real_report(source_fd, source, destination_fd, destination)

            with mock.patch.object(
                self.verifier,
                "_rename_noreplace_at",
                side_effect=competing_file,
            ):
                with self.assertRaises(ValueError):
                    self.verifier.write_report_atomic(report, {"verified": True})
            self.assertEqual(b"keep", report.read_bytes())

    def test_published_artifact_survives_parent_fsync_failure(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            output = Path(raw) / "published-artifact"
            real_rename = self.exporter._rename_noreplace_at
            real_fsync = os.fsync
            published = False

            def track_publish(source_fd, source, destination_fd, destination):
                nonlocal published
                real_rename(source_fd, source, destination_fd, destination)
                published = True

            def fail_parent_fsync(fd):
                if published:
                    raise OSError("injected parent-directory fsync failure")
                return real_fsync(fd)

            with mock.patch.object(
                self.exporter,
                "_rename_noreplace_at",
                side_effect=track_publish,
            ), mock.patch.object(self.exporter.os, "fsync", side_effect=fail_parent_fsync):
                with self.assertRaisesRegex(OSError, "parent-directory fsync failure"):
                    self.exporter.export_artifact(ROOT, output)

            self.assertEqual(
                {"manifest.json", PAYLOAD_NAME, BUNDLE_NAME},
                {path.name for path in output.iterdir()},
            )
            self.assertTrue(self.verifier.verify_artifact(ROOT, output)["verified"])


if __name__ == "__main__":
    unittest.main()
