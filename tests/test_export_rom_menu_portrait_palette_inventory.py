#!/usr/bin/env python3
"""TDD contract for the fixed menu/story portrait palette inventory."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import export_rom_menu_portrait_palette_inventory as exporter
from tools import verify_rom_menu_portrait_palette_inventory as verifier


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom/base.gba"
ARTIFACT = ROOT / "artifacts/rom-menu-portrait-palette-inventory-v1"
EXPECTED_RANGE_VECTOR_SHA256 = (
    "84e8b9f99a51f94e1b9e0b972d6458c883428443aa173a9f739beaf601b4e338"
)
EXPECTED_RESOURCE_VECTOR_SHA256 = (
    "aacf1dd777711ffddd46d268b419da0887002557004064c38d51e5b299521c3b"
)
EXPECTED_BUNDLE_SHA256 = (
    "d5d80e37d88000ec81501d9549b4c6038c42e6ec172614127821213d9dbcdccc"
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _rehash_manifest(artifact: Path, *names: str) -> None:
    manifest_path = artifact / "manifest.json"
    manifest = _json(manifest_path)
    for name in names:
        manifest["files"][name] = _sha((artifact / name).read_bytes())
    manifest_path.write_bytes(_canonical(manifest))


def _export_temp() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory()
    artifact = Path(temporary.name) / "artifact"
    exporter.export_artifact(ROOT, artifact)
    return temporary, artifact


def _copy_implementation_files(module: object, root: Path) -> None:
    for relative in module.IMPLEMENTATION_PATHS.values():
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)


def _copy_bound_source_files(module: object, root: Path) -> None:
    for relative in (
        module.CATALOG_MANIFEST,
        module.WRITEBACK_MANIFEST,
        module.WRITEBACK_PAYLOAD,
        module.WRITEBACK_VERIFIER,
        module.QUEUE_MANIFEST,
        module.QUEUE_PAYLOAD,
        module.QUEUE_VERIFIER,
    ):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)


class MenuPortraitPaletteInventoryTests(unittest.TestCase):
    def test_red_contract_or_repository_artifact_rebuilds_exact_denominator(self) -> None:
        payload, bundle = exporter.build_payload(ROOT)
        rebuilt, rebuilt_bundle = verifier.rebuild_payload(ROOT)
        self.assertEqual(payload, rebuilt)
        self.assertEqual(bundle, rebuilt_bundle)
        self.assertEqual(payload["schema"], "rom-menu-portrait-palette-inventory-v1")
        self.assertEqual(
            payload["summary"],
            {
                "logical_output_count": 311,
                "source_resource_count": 74,
                "unique_palette_count": 70,
                "alias_group_count": 1,
                "aliased_resource_count": 5,
                "aliased_logical_output_count": 56,
                "logical_alias_count": 311,
                "unique_palette_content_hash_count": 54,
                "palette_bytes": 8_960,
                "packed_bytes": 8_960,
                "range_overlap_bytes": 0,
                "range_vector_sha256": EXPECTED_RANGE_VECTOR_SHA256,
                "bundle_sha256": EXPECTED_BUNDLE_SHA256,
            },
        )
        self.assertEqual(
            payload["source"]["resource_vector_sha256"],
            EXPECTED_RESOURCE_VECTOR_SHA256,
        )
        self.assertEqual(
            payload["implementation_binding"],
            {
                "kind": "passed-root-files-equal-loaded-script-root",
                "loaded_root_derived_from": "__file__",
                "paths": [
                    "tests/test_export_rom_menu_portrait_palette_inventory.py",
                    "tools/export_rom_menu_portrait_palette_inventory.py",
                    "tools/verify_rom_menu_portrait_palette_inventory.py",
                ],
            },
        )
        records = payload["physical_palettes"]
        self.assertEqual(len(records), 70)
        self.assertEqual(sum(row["size"] for row in records), 8_960)
        self.assertEqual(records[0]["range"], [0x4098C4, 0x409944])
        self.assertEqual(records[-1]["range"], [0x441324, 0x4413A4])
        self.assertEqual(
            [row["packed_range"] for row in records],
            [[index * 128, (index + 1) * 128] for index in range(70)],
        )
        alias = next(row for row in records if row["range"][0] == 0x4098C4)
        self.assertEqual(alias["resource_ids"], [0, 67, 68, 69, 70])
        self.assertEqual(alias["alias_count"], 5)
        self.assertEqual(_sha(bundle), EXPECTED_BUNDLE_SHA256)

    def test_selector_semantics_are_checked_beyond_outer_slice_hash(self) -> None:
        rom = ROM.read_bytes()
        evidence = verifier.validate_selector(rom)
        self.assertEqual(evidence["function"]["range"], [0x096138, 0x096162])
        self.assertEqual(evidence["function"]["sha256"], exporter.SELECTOR_SHA256)
        self.assertEqual(evidence["formula"]["record_stride"], 40)
        self.assertEqual(evidence["formula"]["variant_stride"], 8)
        tampered = bytearray(rom)
        tampered[0x096144] ^= 0x01
        with mock.patch.object(verifier, "ROM_SHA256", _sha(bytes(tampered))):
            with mock.patch.object(verifier, "SELECTOR_SHA256", _sha(bytes(tampered[0x096138:0x096162]))):
                with self.assertRaisesRegex(ValueError, "selector.*branch|BNE"):
                    verifier.validate_selector(bytes(tampered))

        same_target_beq = bytearray(rom)
        same_target_beq[0x096144 : 0x096146] = bytes.fromhex("04d0")
        for module in (exporter, verifier):
            with self.subTest(module=module.__name__):
                with mock.patch.object(
                    module,
                    "SELECTOR_SHA256",
                    _sha(bytes(same_target_beq[0x096138:0x096162])),
                ):
                    with self.assertRaisesRegex(ValueError, "BNE.*condition"):
                        module.validate_selector(bytes(same_target_beq))

    def test_record0_special_and_partial_zero_table_mutations_fail_closed(self) -> None:
        rom = ROM.read_bytes()
        table = bytearray(rom)
        table[0x5A4DEC] = 1
        with mock.patch.object(verifier, "TABLE_SHA256", _sha(bytes(table[0x5A4DEC:0x5A4DEC + 63 * 40]))):
            with self.assertRaisesRegex(ValueError, "record 0"):
                verifier._table_evidence(bytes(table))

        special = bytearray(rom)
        special[0x5A4DE4] ^= 1
        with self.assertRaisesRegex(ValueError, "special"):
            verifier._table_evidence(bytes(special))

        deep_special = bytearray(rom)
        deep_special[0x5A4DE8 : 0x5A4DEC] = bytes(4)
        deep_special_sha = _sha(bytes(deep_special[0x5A4DE4:0x5A4DEC]))
        catalog = _json(ROOT / "artifacts/menu-portraits-v1/manifest.json")
        for module in (exporter, verifier):
            with self.subTest(module=module.__name__, mutation="deep-special"):
                with mock.patch.object(
                    module, "SPECIAL_PAIR_RAW_SHA256", deep_special_sha
                ):
                    module._table_evidence(bytes(deep_special))
                    with self.assertRaisesRegex(ValueError, "special pair"):
                        module._logical_outputs(bytes(deep_special), catalog)

        partial = bytearray(rom)
        partial[0x5A4DEC + 40] = 0
        with mock.patch.object(verifier, "TABLE_SHA256", _sha(bytes(partial[0x5A4DEC:0x5A4DEC + 63 * 40]))):
            with self.assertRaisesRegex(ValueError, "catalog is missing|pair"):
                verifier._logical_outputs(bytes(partial), _json(ROOT / "artifacts/menu-portraits-v1/manifest.json"))

    def test_representative_palette_rom_byte_tamper_fails_closed(self) -> None:
        catalog = _json(ROOT / "artifacts/menu-portraits-v1/manifest.json")
        logical, _ = verifier._logical_outputs(ROM.read_bytes(), catalog)
        tampered = bytearray(ROM.read_bytes())
        tampered[0x4098C4] ^= 1
        with self.assertRaisesRegex(ValueError, "catalog palette bytes changed"):
            verifier._physical_palettes(bytes(tampered), catalog, logical)

    def test_artifact_export_and_independent_verification(self) -> None:
        temporary, artifact = _export_temp()
        self.addCleanup(temporary.cleanup)
        self.assertEqual(
            {path.name for path in artifact.iterdir()},
            {
                "manifest.json",
                "rom-menu-portrait-palette-inventory.json",
                "rom-menu-portrait-palettes.bin",
            },
        )
        report = verifier.verify_artifact(ROOT, artifact)
        self.assertEqual(
            report,
            {
                "schema": "rom-menu-portrait-palette-inventory-verification-v1",
                "verified": True,
                "logical_output_count": 311,
                "source_resource_count": 74,
                "unique_palette_count": 70,
                "alias_group_count": 1,
                "aliased_resource_count": 5,
                "palette_bytes": 8_960,
                "packed_bytes": 8_960,
                "range_overlap_bytes": 0,
                "range_vector_sha256": EXPECTED_RANGE_VECTOR_SHA256,
                "bundle_sha256": EXPECTED_BUNDLE_SHA256,
                "errors": [],
            },
        )

    def test_payload_range_alias_scope_and_bundle_tamper_fail_closed(self) -> None:
        for mutation in ("range", "reorder", "duplicate", "alias", "scope", "bundle"):
            temporary, artifact = _export_temp()
            try:
                payload_path = artifact / "rom-menu-portrait-palette-inventory.json"
                payload = _json(payload_path)
                if mutation == "range":
                    payload["physical_palettes"] = payload["physical_palettes"][1:]
                elif mutation == "reorder":
                    payload["physical_palettes"] = list(reversed(payload["physical_palettes"]))
                elif mutation == "duplicate":
                    payload["physical_palettes"].append(payload["physical_palettes"][0])
                elif mutation == "alias":
                    payload["physical_palettes"][0]["resource_ids"] = [0]
                elif mutation == "scope":
                    payload["scope"]["fixed_palette_byte_inventory_complete"] = False
                else:
                    bundle_path = artifact / "rom-menu-portrait-palettes.bin"
                    data = bytearray(bundle_path.read_bytes())
                    data[0] ^= 1
                    bundle_path.write_bytes(data)
                if mutation != "bundle":
                    payload_path.write_bytes(_canonical(payload))
                _rehash_manifest(
                    artifact,
                    "rom-menu-portrait-palette-inventory.json"
                    if mutation != "bundle"
                    else "rom-menu-portrait-palettes.bin",
                )
                report = verifier.verify_artifact(ROOT, artifact)
                self.assertFalse(report["verified"], (mutation, report))
            finally:
                temporary.cleanup()

    def test_source_and_upstream_verifier_identity_or_report_tamper_fails_closed(self) -> None:
        temporary, artifact = _export_temp()
        self.addCleanup(temporary.cleanup)
        bad = subprocess.CompletedProcess(
            args=["upstream"],
            returncode=0,
            stdout=b'{"errors": [], "verified": true}\n',
            stderr=b"",
        )
        with mock.patch.object(verifier.subprocess, "run", return_value=bad):
            report = verifier.verify_artifact(ROOT, artifact)
        self.assertFalse(report["verified"])
        self.assertTrue(any("verifier" in error for error in report["errors"]))

        for module in (exporter, verifier):
            for mutation in ("missing-caller", "wrong-size"):
                with self.subTest(module=module.__name__, mutation=mutation):
                    with tempfile.TemporaryDirectory() as raw:
                        copied_root = Path(raw).resolve()
                        _copy_bound_source_files(module, copied_root)
                        payload_path = copied_root / module.QUEUE_PAYLOAD
                        manifest_path = copied_root / module.QUEUE_MANIFEST
                        payload = _json(payload_path)
                        routes = payload["instruction_evidence"][
                            "menu_palette_routes"
                        ]
                        if mutation == "missing-caller":
                            routes.pop()
                        else:
                            routes[0]["size_bytes"] = 64
                        payload_path.write_bytes(_canonical(payload))
                        manifest = _json(manifest_path)
                        manifest["files"][module.QUEUE_PAYLOAD.name] = _sha(
                            payload_path.read_bytes()
                        )
                        manifest_path.write_bytes(_canonical(manifest))
                        with mock.patch.object(
                            module,
                            "QUEUE_PAYLOAD_SHA256",
                            _sha(payload_path.read_bytes()),
                        ), mock.patch.object(
                            module,
                            "QUEUE_MANIFEST_SHA256",
                            _sha(manifest_path.read_bytes()),
                        ):
                            with self.assertRaisesRegex(
                                ValueError, "queue menu palette route"
                            ):
                                module._source_identity(copied_root)

    def test_loaded_implementation_must_match_passed_root(self) -> None:
        for module, label in (
            (exporter, "exporter"),
            (verifier, "verifier"),
        ):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as raw:
                    copied_root = Path(raw).resolve()
                    _copy_implementation_files(module, copied_root)
                    relative = module.IMPLEMENTATION_PATHS[label]
                    target = copied_root / relative
                    target.write_bytes(target.read_bytes() + b"\n# drift\n")
                    with self.assertRaisesRegex(
                        ValueError, "loaded implementation.*passed root"
                    ):
                        module._implementation(copied_root)

    def test_artifact_membership_and_symlink_boundaries_fail_closed(self) -> None:
        temporary, artifact = _export_temp()
        self.addCleanup(temporary.cleanup)
        (artifact / "extra.txt").write_text("foreign", encoding="utf-8")
        report = verifier.verify_artifact(ROOT, artifact)
        self.assertFalse(report["verified"])

        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw).resolve()
            real = base / "real"
            real.mkdir()
            linked = base / "linked"
            linked.symlink_to(real, target_is_directory=True)
            self.assertFalse(verifier.verify_artifact(ROOT, linked)["verified"])
            member = artifact / "rom-menu-portrait-palettes.bin"
            target = base / "foreign.bin"
            target.write_bytes(bytes(8_960))
            member.unlink()
            member.symlink_to(target)
            self.assertFalse(verifier.verify_artifact(ROOT, artifact)["verified"])

        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw).absolute()
            escaped = base / "escape"
            escaped.symlink_to(
                Path(tempfile.gettempdir()).absolute(), target_is_directory=True
            )
            escaped_path = escaped / base.name / "artifact"
            for module in (exporter, verifier):
                with self.subTest(module=module.__name__, mutation="temp-alias"):
                    with self.assertRaisesRegex(ValueError, "symlink"):
                        module._reject_symlink_components(escaped_path)

    def test_missing_and_noncanonical_members_fail_closed(self) -> None:
        temporary, artifact = _export_temp()
        self.addCleanup(temporary.cleanup)
        bundle_path = artifact / "rom-menu-portrait-palettes.bin"
        bundle = bundle_path.read_bytes()
        bundle_path.unlink()
        missing = verifier.verify_artifact(ROOT, artifact)
        self.assertFalse(missing["verified"])
        self.assertTrue(any("file inventory" in item for item in missing["errors"]))

        bundle_path.write_bytes(bundle)
        payload_path = artifact / "rom-menu-portrait-palette-inventory.json"
        payload = _json(payload_path)
        payload_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        _rehash_manifest(artifact, payload_path.name)
        noncanonical = verifier.verify_artifact(ROOT, artifact)
        self.assertFalse(noncanonical["verified"])
        self.assertTrue(
            any("payload byte reconstruction" in item for item in noncanonical["errors"])
        )

    def test_relative_root_and_output_are_resolved_once(self) -> None:
        active = ROOT / "build/experiments/active"
        active.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=active) as raw:
            base = Path(raw).resolve()
            relative_output = (base / "out").relative_to(ROOT)
            completed = subprocess.run(
                [
                    "python3",
                    str(ROOT / "tools/export_rom_menu_portrait_palette_inventory.py"),
                    "--root",
                    ROOT.name,
                    "--output-dir",
                    str(relative_output),
                ],
                cwd=ROOT.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            self.assertTrue((base / "out").exists())

    def test_verifier_does_not_import_exporter(self) -> None:
        source = (ROOT / "tools/verify_rom_menu_portrait_palette_inventory.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        self.assertFalse(any(name.endswith("export_rom_menu_portrait_palette_inventory") for name in imported))

    def test_repository_artifact_verifies_when_present(self) -> None:
        self.assertTrue(ARTIFACT.is_dir(), "accepted artifact must be installed")
        report = verifier.verify_artifact(ROOT, ARTIFACT)
        self.assertTrue(report["verified"], report)


if __name__ == "__main__":
    unittest.main()
