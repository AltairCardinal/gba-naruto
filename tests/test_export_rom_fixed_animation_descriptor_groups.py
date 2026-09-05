"""TDD contract for the fixed four-group animation descriptor inventory."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FixedAnimationDescriptorGroupsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_fixed_animation_descriptor_groups as exporter
        from tools import verify_rom_fixed_animation_descriptor_groups as verifier

        cls.exporter = exporter
        cls.verifier = verifier

    def test_exact_tables_and_consumer_denominators(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        self.assertEqual("rom-fixed-animation-descriptor-groups-v1", payload["schema"])
        tables = payload["tables"]
        self.assertEqual([0x12D574, 0x12D9E4], tables["range"])
        self.assertEqual(12, tables["descriptor_count"])
        self.assertEqual(0x54, tables["descriptor_size"])
        self.assertEqual(12, len(tables["descriptors"]))
        self.assertTrue(all(row["entry_count"] == 4 for row in tables["descriptors"]))
        self.assertTrue(all(row["terminator"] == 0xFFFF for row in tables["descriptors"]))
        self.assertEqual(12, tables["descriptor_pointer_count"])
        self.assertEqual(4, tables["group_count"])
        self.assertEqual(3, tables["records_per_group"])
        self.assertEqual(list(range(12)), tables["record_index_denominator"])
        self.assertEqual([0, 1, 2, 3], tables["group_index_denominator"])
        self.assertEqual([0xFFFF] * 4, tables["group_terminators"])

    def test_fixed_consumer_chain_and_narrow_scope(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        consumer = payload["consumer_contract"]
        self.assertEqual([0x071EC0, 0x071EC2], consumer["literal_load_sites"])
        self.assertEqual(0x0626B4, consumer["allocator_call_target"])
        self.assertEqual(0x062924, consumer["renderer_root"])
        self.assertEqual([0, 3], consumer["caller_group_domain"])
        self.assertEqual([0, 2], consumer["runtime_record_slot_domain"])
        self.assertEqual(0, consumer["out_of_range_reads"])
        self.assertEqual(1136, payload["promotion"]["promotion_bytes"])
        self.assertEqual(1, payload["promotion"]["claim_count"])
        for key in ("natural_runtime_reachability", "all_callers_share_this_input",
                    "descriptor_editing_safety", "opaque_renderer_side_effects"):
            self.assertFalse(payload["scope"][key])

    def test_roundtrip_and_independent_verifier(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            output = Path(directory) / "candidate"
            self.exporter.export_artifact(ROOT, output)
            report = self.verifier.verify_artifact(ROOT, output)
            self.assertTrue(report["verified"], report)
            self.assertEqual(1136, report["promotion_bytes"])
            self.assertEqual(12, report["descriptor_count"])

    def test_cli_export_from_repository_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            output = Path(directory) / "candidate"
            completed = subprocess.run(
                ["python3", "tools/export_rom_fixed_animation_descriptor_groups.py",
                 "--root", ".", "--output", str(output.relative_to(ROOT))],
                cwd=ROOT, text=True, capture_output=True, check=False)
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertTrue((output / self.exporter.MANIFEST_NAME).is_file())

    def test_verifier_does_not_import_exporter(self) -> None:
        source = (ROOT / "tools/verify_rom_fixed_animation_descriptor_groups.py").read_text()
        imports = [ast.unparse(node) for node in ast.walk(ast.parse(source))
                   if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("export_rom_fixed_animation_descriptor_groups" in row
                             for row in imports))

    def test_table_and_consumer_mutations_fail_closed(self) -> None:
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        for offset, pattern in ((0x12D574, "table identity"),
                                (0x12D5C4, "descriptor terminator"),
                                (0x12D964, "pointer table"),
                                (0x12D9A0, "terminator"),
                                (0x071EC0, "consumer"),
                                (0x062752, "consumer"),
                                (0x062992, "consumer"),
                                (0x0631F6, "consumer"),
                                (0x063200, "consumer"),
                                (0x06326C, "consumer")):
            with self.subTest(offset=hex(offset)):
                changed = bytearray(rom)
                changed[offset] ^= 1
                with self.assertRaisesRegex(ValueError, pattern):
                    self.exporter._build_from_rom(ROOT, bytes(changed), verify_identity=False)
                with self.assertRaisesRegex(ValueError, pattern):
                    self.verifier._rebuild(bytes(changed), verify_identity=False)

    def test_artifact_tamper_and_existing_output_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            output = Path(directory) / "candidate"
            self.exporter.export_artifact(ROOT, output)
            with self.assertRaises(FileExistsError):
                self.exporter.export_artifact(ROOT, output)
            path = output / self.exporter.PAYLOAD_NAME
            payload = json.loads(path.read_text())
            payload["promotion"]["promotion_bytes"] += 1
            raw = (json.dumps(payload, ensure_ascii=False, indent=2,
                              sort_keys=True) + "\n").encode()
            path.write_bytes(raw)
            manifest_path = output / self.exporter.MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][self.exporter.PAYLOAD_NAME] = {
                "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False,
                                                indent=2, sort_keys=True) + "\n")
            self.assertFalse(self.verifier.verify_artifact(ROOT, output)["verified"])

    def test_verifier_rejects_manifest_status_extra_file_and_noncanonical_json(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            base = Path(directory)
            original = base / "original"
            self.exporter.export_artifact(ROOT, original)
            for name, mutate in (
                ("status", lambda path: self._mutate_manifest(path, "artifact_status", "rejected")),
                ("implementation", lambda path: self._mutate_manifest(path, "implementation", {})),
                ("extra", lambda path: (path / "extra.txt").write_text("unexpected")),
                ("noncanonical", self._make_payload_noncanonical),
            ):
                with self.subTest(name=name):
                    candidate = base / name
                    shutil.copytree(original, candidate)
                    mutate(candidate)
                    self.assertFalse(self.verifier.verify_artifact(ROOT, candidate)["verified"])

    def test_verifier_rejects_symlinked_artifact_member(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            base = Path(directory)
            output = base / "candidate"
            self.exporter.export_artifact(ROOT, output)
            payload = output / self.exporter.PAYLOAD_NAME
            foreign = base / "foreign.json"
            foreign.write_bytes(payload.read_bytes())
            payload.unlink()
            payload.symlink_to(foreign)
            self.assertFalse(self.verifier.verify_artifact(ROOT, output)["verified"])

    def test_verifier_rejects_symlinked_artifact_ancestor(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            base = Path(directory)
            output = base / "candidate"
            self.exporter.export_artifact(ROOT, output)
            alias = base / "alias"
            alias.symlink_to(base, target_is_directory=True)
            self.assertFalse(
                self.verifier.verify_artifact(ROOT, alias / "candidate")["verified"]
            )

    def test_exclusive_publish_preserves_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            parent = Path(directory)
            source = parent / "source"
            destination = parent / "destination"
            source.mkdir()
            destination.mkdir()
            (source / "new").write_text("new")
            (destination / "keep").write_text("keep")
            with self.assertRaises(FileExistsError):
                self.exporter._publish_exclusive(source, destination)
            self.assertEqual("keep", (destination / "keep").read_text())
            self.assertTrue((source / "new").is_file())

    @staticmethod
    def _mutate_manifest(path: Path, key: str, value: object) -> None:
        manifest_path = path / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest[key] = value
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False,
                                            indent=2, sort_keys=True) + "\n")

    def _make_payload_noncanonical(self, path: Path) -> None:
        payload_path = path / self.exporter.PAYLOAD_NAME
        payload = json.loads(payload_path.read_text())
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        payload_path.write_bytes(raw)
        manifest_path = path / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][self.exporter.PAYLOAD_NAME] = {
            "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False,
                                            indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    unittest.main()
