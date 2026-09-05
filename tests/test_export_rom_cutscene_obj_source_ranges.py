#!/usr/bin/env python3
"""TDD contract for the fixed Cutscene OBJ source-range artifact."""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from tools import export_rom_cutscene_obj_source_ranges as exporter
from tools import verify_rom_cutscene_obj_source_ranges as verifier


ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = ROOT / "rom/base.gba"
RUN_DIR = ROOT / "build/experiments/active/cutscene-obj-source-ranges/r5"
ARTIFACT = Path(
    os.environ.get(
        "CUTSCENE_OBJ_SOURCE_ARTIFACT",
        ROOT / "artifacts/rom-cutscene-obj-source-ranges-v1",
    )
)

ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
VERIFY_SCHEMA = "rom-cutscene-obj-source-ranges-verification-v1"
ARTIFACT_SCHEMA = "rom-cutscene-obj-source-ranges-v1"
PAYLOAD_NAME = "rom-cutscene-obj-source-ranges.json"
BUNDLE_NAME = "rom-cutscene-obj-source-ranges.bin"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME, BUNDLE_NAME}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _copy_tree(source: Path, target: Path) -> None:
    shutil.copytree(source, target, symlinks=True)


def _copy_verifier_root(source: Path, target: Path) -> None:
    for relative in (
        "rom/base.gba",
        "artifacts/cutscene-obj-v1",
        "artifacts/cutscene-obj-bundle-relocation-v1",
        "artifacts/rom-cutscene-obj-source-ranges-v1",
        "tools/verify_cutscene_obj_export.py",
        "tools/export_rom_cutscene_obj_source_ranges.py",
        "tools/verify_rom_cutscene_obj_source_ranges.py",
        "tests/test_export_rom_cutscene_obj_source_ranges.py",
    ):
        source_path = (
            ARTIFACT
            if relative == "artifacts/rom-cutscene-obj-source-ranges-v1"
            else source / relative
        )
        target_path = target / relative
        if source_path.is_dir():
            _copy_tree(source_path, target_path)
        else:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)


class CutsceneObjSourceRangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM_PATH.read_bytes()

    def test_frozen_denominator_and_bundle(self):
        payload, bundle = exporter.build_payload(ROOT)
        report = verifier.verify_payload_from_rom(ROOT, self.rom, payload, bundle)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual((payload["summary"]["range_count"], payload["summary"]["byte_count"]), (28, 400))
        self.assertEqual(len(bundle), 400)
        self.assertEqual(payload["summary"]["kind_counts"], {
            "definition_record": {"range_count": 10, "byte_count": 240},
            "definition_pointer_table": {"range_count": 4, "byte_count": 40},
            "animation_timeline": {"range_count": 10, "byte_count": 80},
            "animation_pointer_table": {"range_count": 4, "byte_count": 40},
        })
        self.assertEqual(payload["summary"]["resource_envelopes"], [
            [0x12DEFC, 0x12DF4C],
            [0x12E444, 0x12E494],
            [0x12E960, 0x12E9B0],
            [0x12ED70, 0x12EE10],
        ])

    def test_records_are_rom_rebuilt_with_grammar_and_pointer_vectors(self):
        payload, bundle = exporter.build_payload(ROOT)
        self.assertEqual(payload["resource_count"], 4)
        self.assertEqual(payload["frame_counts"], [2, 2, 2, 4])
        records = payload["records"]
        self.assertEqual(len(records), 28)
        self.assertEqual([row["resource_id"] for row in records], sorted(row["resource_id"] for row in records))
        self.assertEqual([row["range"][0] for row in records], sorted(row["range"][0] for row in records))
        self.assertEqual(sum(row["size"] for row in records), 400)
        for row in records:
            start, end = row["range"]
            self.assertEqual(row["raw_sha256"], _sha(self.rom[start:end]))
            self.assertEqual(row["raw_hex"], self.rom[start:end].hex())
            self.assertEqual(row["gba_range"], [f"0x{0x08000000 + start:08X}", f"0x{0x08000000 + end:08X}"])
            if row["kind"] == "definition_record":
                self.assertEqual(row["size"], 24)
                self.assertEqual(row["raw_hex"][40:], "ffff0000")
                self.assertEqual(set(row["component"]) , {
                    "tile_offset", "flag_02", "flag_03",
                    "horizontal_position_input", "vertical_position_input",
                    "width", "height", "transform_factor_0c",
                    "transform_factor_0e", "unknown_10_byte",
                    "oam_attribute_byte", "unknown_12",
                })
                self.assertEqual(row["component"]["flag_02"], 0)
                self.assertEqual(row["component"]["flag_03"], 0)
                self.assertEqual(row["component"]["unknown_10_byte"], 0xFF)
                self.assertEqual(row["component"]["oam_attribute_byte"], 0)
                self.assertEqual(row["component"]["unknown_12"], 0)
            elif row["kind"] == "animation_timeline":
                self.assertEqual(row["size"], 8)
                self.assertEqual(row["raw_hex"][8:], "ffff0000")
                self.assertEqual(row["frame_id"], row["selector"]["frame_id"])
        for resource in payload["resources"]:
            self.assertEqual(resource["definition_pointer_vector"], [
                row["pointer_gba"] for row in records
                if row["resource_id"] == resource["resource_id"] and row["kind"] == "definition_record"
            ])
            self.assertEqual(resource["animation_pointer_vector"], [
                row["pointer_gba"] for row in records
                if row["resource_id"] == resource["resource_id"] and row["kind"] == "animation_timeline"
            ])
            self.assertEqual(len(resource["definition_pointer_table_raw_hex"]), resource["frame_count"] * 8)
            self.assertEqual(len(resource["animation_pointer_table_raw_hex"]), resource["frame_count"] * 8)
        self.assertEqual(bundle, b"".join(bytes.fromhex(row["raw_hex"]) for row in records))

    def test_source_identity_and_provenance_are_frozen(self):
        payload, _ = exporter.build_payload(ROOT)
        self.assertEqual(payload["rom"], {"path": "rom/base.gba", "size": len(self.rom), "sha256": ROM_SHA256})
        source = payload["source_identity"]
        self.assertEqual(source["cutscene_obj_export_manifest"]["path"], "artifacts/cutscene-obj-v1/manifest.json")
        self.assertEqual(source["cutscene_obj_export_verifier"]["path"], "tools/verify_cutscene_obj_export.py")
        self.assertEqual(source["bundle_relocation"]["artifact_path"], "artifacts/cutscene-obj-bundle-relocation-v1")
        self.assertEqual(source["roots"], ["0x0853DF70", "0x0853DF90"])
        self.assertEqual(source["consumers"], [
            "0x080625A4",
            "0x08062668",
            "0x0806298C",
            "0x080631F6",
            "0x08063256",
        ])
        parser = source["consumer_evidence"]["component_parser"]
        self.assertEqual(parser["gba_range"], ["0x080631F6", "0x08063210"])
        self.assertEqual(parser["record_stride_bytes"], 20)
        self.assertEqual(parser["terminator_field_offset"], 0)
        self.assertEqual(parser["terminator_s16"], -1)
        self.assertEqual(
            parser["semantic_halfwords"],
            ["0x2514", "0x44A8", "0x4640", "0x2200", "0x5E81", "0x2001", "0x4240", "0x4281", "0xD00B"],
        )

    def test_manifest_and_report_contract(self):
        manifest = _json(ARTIFACT / "manifest.json")
        self.assertEqual(set(manifest), {
            "schema", "artifact_schema", "artifact_status", "files",
            "producer", "verifier", "rom", "source_identity", "scope", "limitations",
        })
        self.assertEqual(manifest["schema"], "git-artifact-promotion-v1")
        self.assertEqual(manifest["artifact_schema"], ARTIFACT_SCHEMA)
        self.assertEqual(manifest["artifact_status"], "accepted")
        self.assertEqual(set(manifest["files"]), {PAYLOAD_NAME, BUNDLE_NAME})
        report = verifier.verify_artifact(ROOT, ARTIFACT)
        self.assertEqual(report["schema"], VERIFY_SCHEMA)
        self.assertTrue(report["verified"], report["errors"])

    def test_artifact_binds_the_exact_test_source_identity(self):
        test_path = Path("tests/test_export_rom_cutscene_obj_source_ranges.py")
        expected = {
            "path": test_path.as_posix(),
            "sha256": _sha((ROOT / test_path).read_bytes()),
        }
        payload = _json(ARTIFACT / PAYLOAD_NAME)
        manifest = _json(ARTIFACT / "manifest.json")
        self.assertEqual(payload["implementation"]["test"], expected)
        self.assertEqual(manifest["producer"]["test"], expected)

        with tempfile.TemporaryDirectory(dir=RUN_DIR) as raw:
            root = Path(raw) / "root"
            _copy_verifier_root(ROOT, root)
            copied_test = root / test_path
            copied_test.write_bytes(copied_test.read_bytes() + b"\n# drift\n")
            report = verifier.verify_artifact(
                root, root / "artifacts/rom-cutscene-obj-source-ranges-v1"
            )
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("payload fixed provenance changed" in error for error in report["errors"]),
                report["errors"],
            )

    def test_manifest_files_are_canonical_and_exact(self):
        for name in EXPECTED_FILES - {"manifest.json"}:
            self.assertEqual((ARTIFACT / name).read_bytes(), _canonical(_json(ARTIFACT / name)) if name.endswith(".json") else (ARTIFACT / name).read_bytes())
        manifest = _json(ARTIFACT / "manifest.json")
        self.assertEqual(manifest["files"], {
            PAYLOAD_NAME: _sha((ARTIFACT / PAYLOAD_NAME).read_bytes()),
            BUNDLE_NAME: _sha((ARTIFACT / BUNDLE_NAME).read_bytes()),
        })
        self.assertEqual({path.name for path in ARTIFACT.iterdir()}, EXPECTED_FILES)

    def test_relative_roots_outputs_and_symlinks_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=RUN_DIR) as raw:
            root = Path(raw) / "root"
            _copy_verifier_root(ROOT, root)
            artifact = root / "artifacts/rom-cutscene-obj-source-ranges-v1"
            self.assertTrue(verifier.verify_artifact(root, Path("artifacts/rom-cutscene-obj-source-ranges-v1"))["verified"])
            self.assertFalse(verifier.verify_artifact(root, Path("."))["verified"])
            outside = Path(raw) / "outside"
            outside.mkdir()
            (root / "rom/base.gba").unlink()
            (root / "rom/base.gba").symlink_to(outside / "base.gba")
            self.assertFalse(verifier.verify_artifact(root, artifact)["verified"])

    def test_missing_extra_noncanonical_and_member_symlink_fail_closed(self):
        for mode in ("missing", "extra", "noncanonical", "member-symlink"):
            with tempfile.TemporaryDirectory(dir=RUN_DIR) as raw:
                artifact = Path(raw) / "artifact"
                _copy_tree(ARTIFACT, artifact)
                if mode == "missing":
                    (artifact / BUNDLE_NAME).unlink()
                elif mode == "extra":
                    (artifact / "extra.bin").write_bytes(b"x")
                elif mode == "noncanonical":
                    payload = _json(artifact / PAYLOAD_NAME)
                    (artifact / PAYLOAD_NAME).write_text(json.dumps(payload) + "\n", encoding="utf-8")
                else:
                    (artifact / "link").symlink_to(artifact / BUNDLE_NAME)
                report = verifier.verify_artifact(ROOT, artifact)
                self.assertFalse(report["verified"], mode)

    def test_payload_bundle_manifest_and_deep_rom_tampering_fail_closed(self):
        for mode in ("payload", "bundle", "manifest", "rom-table", "rom-definition", "rom-animation"):
            with tempfile.TemporaryDirectory(dir=RUN_DIR) as raw:
                root = Path(raw) / "root"
                _copy_verifier_root(ROOT, root)
                artifact = root / "artifacts/rom-cutscene-obj-source-ranges-v1"
                if mode == "payload":
                    payload = _json(artifact / PAYLOAD_NAME)
                    payload["summary"]["byte_count"] += 1
                    (artifact / PAYLOAD_NAME).write_bytes(_canonical(payload))
                    manifest = _json(artifact / "manifest.json")
                    manifest["files"][PAYLOAD_NAME] = _sha((artifact / PAYLOAD_NAME).read_bytes())
                    (artifact / "manifest.json").write_bytes(_canonical(manifest))
                elif mode == "bundle":
                    data = bytearray((artifact / BUNDLE_NAME).read_bytes())
                    data[0] ^= 1
                    (artifact / BUNDLE_NAME).write_bytes(data)
                    manifest = _json(artifact / "manifest.json")
                    manifest["files"][BUNDLE_NAME] = _sha(bytes(data))
                    (artifact / "manifest.json").write_bytes(_canonical(manifest))
                elif mode == "manifest":
                    manifest = _json(artifact / "manifest.json")
                    manifest["scope"]["all_fixed_resources"] = True
                    (artifact / "manifest.json").write_bytes(_canonical(manifest))
                else:
                    rom = bytearray((root / "rom/base.gba").read_bytes())
                    offsets = {
                        "rom-table": 0x53DF70,
                        "rom-definition": 0x12DEFC,
                        "rom-animation": 0x12DF34,
                    }
                    rom[offsets[mode]] ^= 1
                    (root / "rom/base.gba").write_bytes(rom)
                self.assertFalse(verifier.verify_artifact(root, artifact)["verified"], mode)

    def test_each_rom_mutation_hits_deep_semantics_after_slice_resigning(self):
        for implementation in (exporter, verifier):
            with self.subTest(module=implementation.__name__, mutation="root-table"):
                tampered = bytearray(self.rom)
                tampered[0x53DF70 + 4] ^= 1
                resource_sha = _sha(bytes(tampered[0x53DF70:0x53DF90]))
                combined_sha = _sha(bytes(tampered[0x53DF70:0x53DFB0]))
                with mock.patch.object(implementation, "RESOURCE_TABLE_SHA256", resource_sha), mock.patch.object(implementation, "COMBINED_TABLE_SHA256", combined_sha):
                    with self.assertRaisesRegex(ValueError, "pointer vector"):
                        if implementation is exporter:
                            implementation._resource_tables(bytes(tampered))
                        else:
                            implementation._read_root_pairs(bytes(tampered))

            with self.subTest(module=implementation.__name__, mutation="definition"):
                tampered = bytearray(self.rom)
                tampered[0x12DEFC] ^= 1
                with self.assertRaisesRegex(ValueError, "definition component"):
                    if implementation is exporter:
                        tables = implementation._resource_tables(self.rom)
                        implementation._resource_records(bytes(tampered), tables[0])
                    else:
                        implementation._decode_component_abi(
                            bytes(tampered[0x12DEFC:0x12DF14]), 0, 0
                        )

            with self.subTest(module=implementation.__name__, mutation="animation"):
                tampered = bytearray(self.rom)
                tampered[0x12DF34 + 2] ^= 1
                with self.assertRaisesRegex(ValueError, "animation semantics"):
                    if implementation is exporter:
                        tables = implementation._resource_tables(self.rom)
                        implementation._resource_records(bytes(tampered), tables[0])
                    else:
                        implementation._decode_animation_claim(
                            bytes(tampered[0x12DF34:0x12DF3C]), 0, 0
                        )

            with self.subTest(module=implementation.__name__, mutation="consumer"):
                tampered = bytearray(self.rom)
                tampered[0x6298C] ^= 1
                original = implementation.CONSUMER_SLICES
                resigned = tuple(
                    (name, start, end, _sha(bytes(tampered[start - 0x08000000:end - 0x08000000])))
                    if name == "animation_frame_selector" else (name, start, end, digest)
                    for name, start, end, digest in original
                )
                with mock.patch.object(implementation, "CONSUMER_SLICES", resigned):
                    with self.assertRaisesRegex(ValueError, "semantic bytes"):
                        implementation._consumer_evidence(bytes(tampered))

            with self.subTest(module=implementation.__name__, mutation="component-parser"):
                tampered = bytearray(self.rom)
                tampered[0x631F6] ^= 1
                name, start, end, _ = implementation.COMPONENT_PARSER_SLICE
                resigned = (
                    name,
                    start,
                    end,
                    _sha(bytes(tampered[start - 0x08000000:end - 0x08000000])),
                )
                with mock.patch.object(
                    implementation, "COMPONENT_PARSER_SLICE", resigned
                ):
                    with self.assertRaisesRegex(ValueError, "component parser"):
                        implementation._consumer_evidence(bytes(tampered))

    def test_command_and_canonical_manifest_resigning_fail_closed(self):
        for key in ("producer", "verifier"):
            with tempfile.TemporaryDirectory(dir=RUN_DIR) as raw:
                artifact = Path(raw) / "artifact"
                _copy_tree(ARTIFACT, artifact)
                manifest = _json(artifact / "manifest.json")
                manifest[key]["command"] = list(manifest[key]["command"])
                manifest[key]["command"][-1] = "tampered"
                (artifact / "manifest.json").write_bytes(_canonical(manifest))
                self.assertFalse(verifier.verify_artifact(ROOT, artifact)["verified"], key)

    def test_verifier_does_not_import_exporter(self):
        tree = ast.parse((ROOT / "tools/verify_rom_cutscene_obj_source_ranges.py").read_text(encoding="utf-8"))
        imported = [node.module or "" for node in tree.body if isinstance(node, ast.ImportFrom)]
        imported += [alias.name for node in tree.body if isinstance(node, ast.Import) for alias in node.names]
        self.assertFalse(any("export_rom_cutscene_obj_source_ranges" in name for name in imported))

    def test_verifier_core_oracle_is_not_a_copy_of_the_exporter_builder(self):
        def fingerprints(path: Path, names: set[str]) -> set[str]:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            result: set[str] = set()
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
                    normalized = ast.parse(ast.unparse(node)).body[0]
                    normalized.name = "_normalized_core"
                    result.add(ast.dump(normalized, include_attributes=False))
            return result

        core_names = {"_resource_tables", "_component", "_resource_records", "_build_payload"}
        exporter_core = fingerprints(
            ROOT / "tools/export_rom_cutscene_obj_source_ranges.py", core_names
        )
        verifier_core = fingerprints(
            ROOT / "tools/verify_rom_cutscene_obj_source_ranges.py", core_names
        )
        self.assertTrue(exporter_core)
        self.assertTrue(
            exporter_core.isdisjoint(verifier_core),
            "independent verifier must not copy the exporter root/parser/range builder",
        )

    def test_committed_artifact_exists_and_passes(self):
        self.assertTrue(ARTIFACT.is_dir())
        report = verifier.verify_artifact(ROOT, ARTIFACT)
        self.assertTrue(report["verified"], report["errors"])


if __name__ == "__main__":
    unittest.main()
