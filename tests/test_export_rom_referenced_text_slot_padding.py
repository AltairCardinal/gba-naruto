#!/usr/bin/env python3
"""TDD contract for fixed referenced-text post-NUL zero padding."""

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

from tools import export_rom_referenced_text_slot_padding as exporter
from tools import verify_rom_referenced_text_slot_padding as verifier


ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = ROOT / "rom/base.gba"
SELECTOR_PAYLOAD_PATH = (
    ROOT / "artifacts/rom-selector-text-bindings-v1/selector-text-bindings.json"
)
CHAPTER_PAYLOAD_PATH = (
    ROOT / "artifacts/rom-chapter-script-inventory-v1/chapter-script-inventory.json"
)

EXPECTED_GROUPS = {
    "selector_direct": {
        "range_count": 46,
        "padding_bytes": 550,
        "range_denominator_sha256": (
            "647695b786a07f4c226bbad80246b0101d503eeb11912d71da500593812bb023"
        ),
        "packed_sha256": (
            "25778f162c4243167f8eaa876f1b0619e67afc158de7805600471a563ec5e8b7"
        ),
    },
    "selector_configured": {
        "range_count": 38,
        "padding_bytes": 368,
        "range_denominator_sha256": (
            "326f4c14065664e689b9c8245a931beb0a647241874a78953dfbc7dfcc2dddf3"
        ),
        "packed_sha256": (
            "71818ecc26433c32172dd9a3544657971c7078daa2257da7c3c303e08693cb23"
        ),
    },
    "chapter_speaker": {
        "range_count": 49,
        "padding_bytes": 337,
        "range_denominator_sha256": (
            "c2bdff7dad49f5446929b17b0a7fe6d5cd5a2a696c2ab091c5cebcd546912f16"
        ),
        "packed_sha256": (
            "3ad337042948f15072caf3da89730e6cc6d42657af2b2291806c4fd45ee1aae6"
        ),
    },
}
EXPECTED_RANGE_DENOMINATOR_SHA256 = (
    "0d565762f2bdfd18a6aa1f8c8cd25da5347da5184fe1c78e37de9c6334259b5a"
)
EXPECTED_BUNDLE_SHA256 = (
    "920b0cbd31dee627e4e6f4cd4d7805da10ec58ec47d4be3cb4a2dfc98a3b442b"
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _copy_file(root: Path, relative: str) -> None:
    source = ROOT / relative
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _copy_minimal_root(root: Path) -> None:
    for relative in (
        "rom/base.gba",
        "artifacts/rom-selector-text-bindings-v1/manifest.json",
        "artifacts/rom-selector-text-bindings-v1/selector-text-bindings.json",
        "artifacts/rom-selector-text-bindings-v1/selector-text-bytes.bin",
        "artifacts/rom-chapter-script-inventory-v1/manifest.json",
        "artifacts/rom-chapter-script-inventory-v1/chapter-script-inventory.json",
        "artifacts/rom-chapter-script-inventory-v1/chapter-script-bytes.bin",
        "tools/verify_rom_selector_text_bindings.py",
        "tools/verify_rom_chapter_script_inventory.py",
        "tools/export_rom_referenced_text_slot_padding.py",
        "tools/verify_rom_referenced_text_slot_padding.py",
        "tests/test_export_rom_referenced_text_slot_padding.py",
    ):
        _copy_file(root, relative)


def _rehash_declared_file(artifact: Path, name: str) -> None:
    manifest_path = artifact / "manifest.json"
    manifest = _json(manifest_path)
    manifest["files"][name] = _sha((artifact / name).read_bytes())
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


class ReferencedTextSlotPaddingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM_PATH.read_bytes()
        cls.selector = _json(SELECTOR_PAYLOAD_PATH)
        cls.chapter = _json(CHAPTER_PAYLOAD_PATH)

    def test_exporter_and_independent_verifier_rebuild_exact_denominator(self) -> None:
        export_payload, export_bundle = exporter.build_payload(ROOT)
        verify_payload, verify_bundle = verifier.rebuild_payload(ROOT)
        self.assertEqual(export_payload, verify_payload)
        self.assertEqual(export_bundle, verify_bundle)

        summary = export_payload["summary"]
        self.assertEqual(summary["padding_range_count"], 133)
        self.assertEqual(summary["padding_bytes"], 1_255)
        self.assertEqual(summary["zero_byte_count"], 1_255)
        self.assertEqual(summary["packed_bytes"], 1_255)
        self.assertEqual(summary["range_overlap_bytes"], 0)
        self.assertEqual(
            summary["range_denominator_sha256"],
            EXPECTED_RANGE_DENOMINATOR_SHA256,
        )
        self.assertEqual(summary["bundle_sha256"], EXPECTED_BUNDLE_SHA256)
        self.assertEqual(_sha(export_bundle), EXPECTED_BUNDLE_SHA256)
        self.assertEqual(export_bundle, bytes(1_255))
        self.assertEqual(export_payload["group_summaries"], EXPECTED_GROUPS)

    def test_ranges_are_exact_suffixes_and_exclude_unreferenced_slots(self) -> None:
        payload, _ = exporter.build_payload(ROOT)
        records = payload["classified_ranges"]
        self.assertEqual(len(records), 133)
        self.assertEqual(len({item["range_id"] for item in records}), 133)
        self.assertEqual(
            [item["range"] for item in records],
            sorted((item["range"] for item in records)),
        )

        direct_sources = {
            item["record_id"]: item
            for item in self.selector["direct_text_candidates"]["records"]
        }
        configured_sources = {
            item["record_id"]: item
            for item in self.selector["configured_text_table"]["referenced_records"]
        }
        speaker_sources = {
            f"speaker-label-{item['label_id']:02d}": item
            for item in self.chapter["referenced_resources"]["speaker_labels"]["records"]
        }
        expected_ids = {
            "selector_direct": set(direct_sources),
            "selector_configured": set(configured_sources),
            "chapter_speaker": set(speaker_sources),
        }
        actual_ids = {name: set() for name in expected_ids}
        previous_end = -1
        for item in records:
            start, end = item["range"]
            self.assertGreater(start, previous_end)
            previous_end = end
            self.assertEqual(end - start, item["size"])
            self.assertTrue(item["all_zero"])
            self.assertFalse(item["safe_allocatable_space_claimed"])
            self.assertEqual(self.rom[start:end], bytes(end - start))
            self.assertEqual(_sha(self.rom[start:end]), item["bytes_sha256"])
            actual_ids[item["source_kind"]].add(item["source_record_id"])
            if item["source_kind"] == "selector_direct":
                source = direct_sources[item["source_record_id"]]
                self.assertEqual(start, source["consumed_range"][1])
                self.assertEqual(end, source["physical_range"][1])
            elif item["source_kind"] == "selector_configured":
                source = configured_sources[item["source_record_id"]]
                self.assertEqual(start, source["consumed_range"][1])
                self.assertEqual(end, source["physical_range"][1])
            else:
                source = speaker_sources[item["source_record_id"]]
                self.assertEqual(start, source["renderer_range"][1])
                self.assertEqual(end, source["slot_range"][1])
        self.assertEqual(actual_ids, expected_ids)

        configured_ids = {
            item["slot_id"]
            for item in records
            if item["source_kind"] == "selector_configured"
        }
        self.assertEqual(
            configured_ids,
            set(range(1, 32)) | {39, 46, 50, 51, 52, 53, 54},
        )
        speaker_ids = {
            item["label_id"]
            for item in records
            if item["source_kind"] == "chapter_speaker"
        }
        self.assertEqual(
            speaker_ids,
            set(range(1, 32)) | {35, 36, 37, 41} | set(range(43, 55)) | {56, 61},
        )

    def test_each_padding_range_fails_closed_if_any_byte_becomes_nonzero(self) -> None:
        payload, _ = exporter.build_payload(ROOT)
        for item in payload["classified_ranges"]:
            tampered = bytearray(self.rom)
            tampered[item["range"][0]] = 1
            with self.subTest(item=item["range_id"], implementation="exporter"):
                with self.assertRaisesRegex(ValueError, "zero padding"):
                    exporter.derive_records(bytes(tampered), self.selector, self.chapter)
            with self.subTest(item=item["range_id"], implementation="verifier"):
                with self.assertRaisesRegex(ValueError, "zero padding"):
                    verifier.derive_records(bytes(tampered), self.selector, self.chapter)

    def test_export_is_deterministic_and_temp_artifact_independently_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as first_raw, tempfile.TemporaryDirectory() as second_raw:
            first = Path(first_raw).resolve() / "artifact"
            second = Path(second_raw).resolve() / "artifact"
            exporter.export_artifact(ROOT, first)
            exporter.export_artifact(ROOT, second)
            self.assertEqual(
                sorted(path.name for path in first.iterdir()),
                [
                    "manifest.json",
                    "referenced-text-slot-padding.bin",
                    "referenced-text-slot-padding.json",
                ],
            )
            self.assertEqual(
                {path.name: _sha(path.read_bytes()) for path in first.iterdir()},
                {path.name: _sha(path.read_bytes()) for path in second.iterdir()},
            )
            report = verifier.verify_artifact(ROOT, first)
            self.assertTrue(report["verified"], report)
            self.assertEqual(report["errors"], [])
            self.assertEqual(report["padding_range_count"], 133)
            self.assertEqual(report["padding_bytes"], 1_255)

    def test_rehashed_payload_or_bundle_tamper_still_fails(self) -> None:
        for target in (
            "referenced-text-slot-padding.json",
            "referenced-text-slot-padding.bin",
        ):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as raw:
                artifact = Path(raw).resolve() / "artifact"
                exporter.export_artifact(ROOT, artifact)
                path = artifact / target
                if target.endswith(".json"):
                    payload = _json(path)
                    payload["summary"]["padding_bytes"] += 1
                    path.write_text(
                        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                        + "\n",
                        encoding="utf-8",
                    )
                else:
                    data = bytearray(path.read_bytes())
                    data[0] = 1
                    path.write_bytes(data)
                _rehash_declared_file(artifact, target)
                report = verifier.verify_artifact(ROOT, artifact)
                self.assertFalse(report["verified"], report)

    def test_source_payload_boundary_drift_fails_from_passed_root(self) -> None:
        with tempfile.TemporaryDirectory() as root_raw:
            copied_root = Path(root_raw).resolve() / "root"
            _copy_minimal_root(copied_root)
            artifact = copied_root / "candidate"
            exporter.export_artifact(copied_root, artifact)
            source_path = (
                copied_root
                / "artifacts/rom-selector-text-bindings-v1/selector-text-bindings.json"
            )
            source = _json(source_path)
            source["direct_text_candidates"]["records"][0]["consumed_range"][1] += 1
            source_path.write_text(
                json.dumps(source, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            report = verifier.verify_artifact(copied_root, artifact)
            self.assertFalse(report["verified"], report)

    def test_output_and_artifact_membership_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw).resolve()
            foreign = base / "foreign"
            foreign.mkdir()
            (foreign / "sentinel").write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "replaceable"):
                exporter.export_artifact(ROOT, foreign)
            self.assertEqual((foreign / "sentinel").read_text(encoding="utf-8"), "keep")

            real = base / "real"
            real.mkdir()
            linked = base / "linked"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                exporter.export_artifact(ROOT, linked)

            artifact = base / "artifact"
            exporter.export_artifact(ROOT, artifact)
            (artifact / "extra.txt").write_text("unexpected", encoding="utf-8")
            report = verifier.verify_artifact(ROOT, artifact)
            self.assertFalse(report["verified"], report)

    def test_ancestor_and_member_symlinks_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw).resolve()
            real = base / "real/parent"
            real.mkdir(parents=True)
            linked = base / "linked"
            linked.symlink_to(base / "real", target_is_directory=True)
            through_link = linked / "parent/artifact"
            with self.assertRaisesRegex(ValueError, "symlink"):
                exporter.export_artifact(ROOT, through_link)

            artifact = real / "artifact"
            exporter.export_artifact(ROOT, artifact)
            report = verifier.verify_artifact(ROOT, through_link)
            self.assertFalse(report["verified"], report)
            self.assertRegex(report["errors"][0], "symlink")

            bundle = artifact / "referenced-text-slot-padding.bin"
            target = base / "external.bin"
            target.write_bytes(bytes(1_255))
            bundle.unlink()
            bundle.symlink_to(target)
            report = verifier.verify_artifact(ROOT, artifact)
            self.assertFalse(report["verified"], report)

    def test_export_does_not_publish_if_independent_verifier_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            artifact = Path(raw).resolve() / "artifact"
            failed = subprocess.CompletedProcess(
                args=["verifier"],
                returncode=1,
                stdout=b'{"verified": false, "errors": ["forced"]}\n',
                stderr=b"forced failure",
            )
            with mock.patch.object(exporter.subprocess, "run", return_value=failed):
                with self.assertRaisesRegex(ValueError, "independent verifier rejected"):
                    exporter.export_artifact(ROOT, artifact)
            self.assertFalse(artifact.exists())

    def test_cli_resolves_relative_output_once_against_relative_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw).resolve()
            copied_root = base / "r"
            _copy_minimal_root(copied_root)
            completed = subprocess.run(
                [
                    "python3",
                    str(ROOT / "tools/export_rom_referenced_text_slot_padding.py"),
                    "--root",
                    "r",
                    "--output-dir",
                    "out",
                ],
                cwd=base,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            self.assertTrue((copied_root / "out/manifest.json").is_file())
            self.assertFalse((copied_root / "r/out").exists())

    def test_repository_artifact_independently_verifies(self) -> None:
        artifact = ROOT / "artifacts/rom-referenced-text-slot-padding-v1"
        self.assertTrue(artifact.is_dir(), artifact)
        report = verifier.verify_artifact(ROOT, artifact)
        self.assertTrue(report["verified"], report)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["padding_range_count"], 133)
        self.assertEqual(report["padding_bytes"], 1_255)

    def test_verifier_does_not_import_exporter(self) -> None:
        source = (ROOT / "tools/verify_rom_referenced_text_slot_padding.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        self.assertFalse(
            any(name.endswith("export_rom_referenced_text_slot_padding") for name in imported),
            imported,
        )


if __name__ == "__main__":
    unittest.main()
