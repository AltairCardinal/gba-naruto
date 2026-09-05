#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools.export_rom_dialogue_padding_inventory import (
    BUNDLE_NAME,
    PAYLOAD_NAME,
    ROM_SHA256,
    SCHEMA,
    SOURCE_MANIFEST_SHA256,
    _replace_output_dir,
    _validate_output_dir,
    export_rom_dialogue_padding_inventory,
)
from tools.verify_rom_dialogue_padding_inventory import (
    verify_rom_dialogue_padding_inventory,
)


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SUMMARY = {
    "source_target_count": 1_220,
    "gap_count": 1_219,
    "padding_bytes": 16_814,
    "zero_byte_count": 16_814,
    "nonzero_gap_count": 0,
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


class RomDialoguePaddingInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        base = Path(cls.temporary.name).resolve()
        cls.first = base / "first"
        cls.second = base / "second"
        export_rom_dialogue_padding_inventory(ROOT, cls.first)
        export_rom_dialogue_padding_inventory(ROOT, cls.second)
        cls.payload_raw = (cls.first / PAYLOAD_NAME).read_bytes()
        cls.payload = json.loads(cls.payload_raw)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_inventory_is_deterministic_and_independently_verified(self):
        self.assertEqual(self.payload_raw, (self.second / PAYLOAD_NAME).read_bytes())
        self.assertEqual(
            (self.first / "manifest.json").read_bytes(),
            (self.second / "manifest.json").read_bytes(),
        )
        report = verify_rom_dialogue_padding_inventory(ROOT, self.first)
        self.assertEqual(
            {
                "schema": "rom-dialogue-padding-inventory-verification-v1",
                "verified": True,
                **EXPECTED_SUMMARY,
                "errors": [],
            },
            report,
        )

    def test_inventory_binds_the_full_zero_gap_denominator(self):
        self.assertEqual(SCHEMA, self.payload["schema"])
        self.assertEqual(EXPECTED_SUMMARY, self.payload["summary"])
        self.assertEqual(ROM_SHA256, self.payload["rom"]["sha256"])
        self.assertEqual(
            SOURCE_MANIFEST_SHA256,
            self.payload["source_artifact"]["manifest_sha256"],
        )
        gaps = self.payload["gaps"]
        bundle = (self.first / BUNDLE_NAME).read_bytes()
        rom = (ROOT / "rom/base.gba").read_bytes()
        self.assertEqual(1_219, len(gaps))
        self.assertEqual(16_814, len(bundle))
        cursor = 0
        previous_end = -1
        for index, gap in enumerate(gaps):
            start, end = gap["range"]
            packed_start, packed_end = gap["packed_range"]
            raw = rom[start:end]
            self.assertEqual(index, gap["gap_id"])
            self.assertGreaterEqual(start, previous_end)
            self.assertTrue(raw)
            self.assertEqual({0}, set(raw))
            self.assertEqual(end - start, gap["size"])
            self.assertEqual(_sha(raw), gap["bytes_sha256"])
            self.assertEqual([cursor, cursor + len(raw)], gap["packed_range"])
            self.assertEqual(raw, bundle[packed_start:packed_end])
            self.assertEqual(
                gap["left_target"]["range"][1],
                start,
            )
            self.assertEqual(
                gap["right_target"]["range"][0],
                end,
            )
            cursor = packed_end
            previous_end = end
        self.assertEqual(len(bundle), cursor)
        self.assertFalse(self.payload["scope"]["safe_allocatable_space_claimed"])

    def test_verifier_rejects_semantic_tampering_after_manifest_rehash(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory).resolve() / "artifact"
            shutil.copytree(self.first, artifact)
            payload_path = artifact / PAYLOAD_NAME
            payload = json.loads(payload_path.read_bytes())
            payload["gaps"][0]["range"][1] -= 1
            raw = _canonical_json(payload)
            payload_path.write_bytes(raw)
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_bytes())
            manifest["files"][PAYLOAD_NAME] = {
                "size": len(raw),
                "sha256": _sha(raw),
            }
            manifest_path.write_bytes(_canonical_json(manifest))

            report = verify_rom_dialogue_padding_inventory(ROOT, artifact)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"], report)

    def test_output_validator_rejects_root_ancestor_and_foreign_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "repo"
            root.mkdir()
            with self.assertRaisesRegex(ValueError, "root or ancestor"):
                _validate_output_dir(root, root)
            with self.assertRaisesRegex(ValueError, "root or ancestor"):
                _validate_output_dir(root, root.parent)
            foreign = root / "foreign"
            foreign.mkdir()
            keep = foreign / "keep.txt"
            keep.write_bytes(b"keep")
            with self.assertRaisesRegex(ValueError, "replaceable dialogue padding"):
                _validate_output_dir(root, foreign)
            self.assertEqual(b"keep", keep.read_bytes())

    def test_output_validator_rejects_a_forged_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "repo"
            root.mkdir()
            forged = root / "forged"
            forged.mkdir()
            for name in ("manifest.json", PAYLOAD_NAME, BUNDLE_NAME):
                (forged / name).write_bytes(b"{}\n")
            with self.assertRaisesRegex(ValueError, "replaceable dialogue padding"):
                _validate_output_dir(root, forged)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_output_validator_rejects_leaf_and_external_parent_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "repo"
            root.mkdir()
            foreign = Path(directory).resolve() / "foreign"
            foreign.mkdir()
            leaf = root / "leaf"
            leaf.symlink_to(foreign, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                _validate_output_dir(root, leaf)
            external_parent = Path(directory).resolve() / "external-link"
            external_parent.symlink_to(foreign, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                _validate_output_dir(root, external_parent / "artifact")

    def test_real_entry_rejects_fake_repository_root_before_any_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "repo"
            root.mkdir()
            sentinel = root / "must-survive.txt"
            sentinel.write_bytes(b"unchanged")
            with self.assertRaisesRegex(ValueError, "root or ancestor"):
                export_rom_dialogue_padding_inventory(root, root)
            self.assertEqual(b"unchanged", sentinel.read_bytes())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_source_dialogue_artifact_rejects_leaf_and_parent_symlinks(self):
        required_files = (
            "rom/base.gba",
            "tools/export_rom_dialogue_padding_inventory.py",
            "tools/verify_rom_dialogue_padding_inventory.py",
            "tools/export_rom_dialogue_text_inventory.py",
            "tools/verify_rom_dialogue_text_inventory.py",
            "tests/test_export_rom_dialogue_padding_inventory.py",
            "tests/test_export_rom_dialogue_text_inventory.py",
        )

        def prepare_fake_repo(base: Path) -> Path:
            fake_root = base / "repo"
            for relative in required_files:
                source = ROOT / relative
                destination = fake_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            return fake_root

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            fake_root = prepare_fake_repo(base)
            (fake_root / "artifacts").mkdir()
            (fake_root / "artifacts/rom-dialogue-text-inventory-v1").symlink_to(
                ROOT / "artifacts/rom-dialogue-text-inventory-v1",
                target_is_directory=True,
            )
            with self.assertRaisesRegex(ValueError, "symlink"):
                export_rom_dialogue_padding_inventory(
                    fake_root, fake_root / "output"
                )

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            fake_root = prepare_fake_repo(base)
            external = base / "external-artifacts"
            external.mkdir()
            shutil.copytree(
                ROOT / "artifacts/rom-dialogue-text-inventory-v1",
                external / "rom-dialogue-text-inventory-v1",
            )
            (fake_root / "artifacts").symlink_to(
                external, target_is_directory=True
            )
            with self.assertRaisesRegex(ValueError, "symlink"):
                export_rom_dialogue_padding_inventory(
                    fake_root, fake_root / "output"
                )

    def test_atomic_replace_restores_old_artifact_when_install_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            output = base / "artifact"
            staging = base / "staging"
            output.mkdir()
            staging.mkdir()
            (output / "old.bin").write_bytes(b"old")
            (staging / "new.bin").write_bytes(b"new")
            real_replace = os.replace
            calls = 0

            def fail_second_replace(source, target):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected install failure")
                return real_replace(source, target)

            with mock.patch(
                "tools.export_rom_dialogue_padding_inventory.os.replace",
                side_effect=fail_second_replace,
            ):
                with self.assertRaisesRegex(OSError, "injected install failure"):
                    _replace_output_dir(output, staging)
            self.assertEqual(b"old", (output / "old.bin").read_bytes())
            self.assertTrue(staging.is_dir())
            self.assertEqual([], list(base.glob(".artifact.backup-*")))

    def test_cli_exports_and_verifies_a_temporary_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve() / "cli-artifact"
            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/export_rom_dialogue_padding_inventory.py",
                    "--root",
                    str(ROOT),
                    "--output-dir",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            report = verify_rom_dialogue_padding_inventory(ROOT, output)
            self.assertTrue(report["verified"], report)


if __name__ == "__main__":
    unittest.main()
