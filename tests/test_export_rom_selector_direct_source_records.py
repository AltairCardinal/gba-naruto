#!/usr/bin/env python3
"""TDD contract for the fixed selector direct-source record table."""

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

from tools import export_rom_selector_direct_source_records as exporter
from tools import verify_rom_selector_direct_source_records as verifier


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom/base.gba"
TABLE_START = 0x59F5F0
TABLE_END = 0x59F988
EXPECTED_SLOTS = [
    1, 2, 3, 7, 44, 43, 4, 5, 6, 45, 8, 9, 10, 46, 11, 12, 13, 47,
    48, 30, 51, 52, 14, 15, 16, 17, 18, 19, 22, 23, 24, 29, 61, 20,
    21, 31, 49, 56, 50, 25, 26, 27, 28, 53, 54, 62,
]
EXPECTED_REPORT = {
    "schema": "rom-selector-direct-source-records-verification-v1",
    "artifact_schema": "rom-selector-direct-source-records-v1",
    "verified": True,
    "record_count": 46,
    "record_bytes": 920,
    "bundle_sha256": "a11475d1eea2ce15968ac2dc52addabcfa59354ccf80b702f922e2af548a4b56",
    "record_vector_sha256": "065fca6237d166557a03cf30ddd309f695b825f5c850356a3c736e396d9478db",
    "errors": [],
}


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
        "tools/export_rom_selector_text_bindings.py",
        "tools/verify_rom_selector_text_bindings.py",
        "tests/test_export_rom_selector_text_bindings.py",
        "tools/export_rom_selector_direct_source_records.py",
        "tools/verify_rom_selector_direct_source_records.py",
        "tests/test_export_rom_selector_direct_source_records.py",
    ):
        _copy_file(root, relative)


def _rehash(artifact: Path, name: str) -> None:
    manifest_path = artifact / "manifest.json"
    manifest = _json(manifest_path)
    manifest["files"][name] = _sha((artifact / name).read_bytes())
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _thumb_bl(site: int, target: int) -> bytes:
    delta = target - (site + 4)
    if delta % 2 or not -(1 << 22) <= delta < (1 << 22):
        raise ValueError("Thumb BL target is out of range")
    first = 0xF000 | ((delta >> 12) & 0x7FF)
    second = 0xF800 | ((delta >> 1) & 0x7FF)
    return first.to_bytes(2, "little") + second.to_bytes(2, "little")


class SelectorDirectSourceRecordsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM.read_bytes()
        cls.old_payload = _json(
            ROOT / "artifacts/rom-selector-text-bindings-v1/selector-text-bindings.json"
        )

    def test_exporter_and_verifier_rebuild_the_same_fixed_contract(self) -> None:
        exported, bundle = exporter.build_payload(ROOT)
        rebuilt, rebuilt_bundle = verifier.rebuild_payload(ROOT)
        self.assertEqual(exported, rebuilt)
        self.assertEqual(bundle, rebuilt_bundle)
        source = exported["source_table"]
        self.assertEqual(source["range"], [TABLE_START, TABLE_END])
        self.assertEqual(source["record_count"], 46)
        self.assertEqual(source["record_size"], 20)
        self.assertEqual(source["size"], 920)
        self.assertEqual(source["sha256"], "a11475d1eea2ce15968ac2dc52addabcfa59354ccf80b702f922e2af548a4b56")
        self.assertEqual(source["record_vector_sha256"], EXPECTED_REPORT["record_vector_sha256"])
        self.assertEqual(source["name_slot_vector_sha256"], "d429cca720c928593b80289794395d0c6d266268af5da567bbe76a22c5b65ba2")
        self.assertEqual(source["sorted_slot_vector_sha256"], "42aaddfc56e36df6be859279c4a64aff4ae006e416895817c200d733eeae64a2")
        self.assertEqual(source["row_range_vector_sha256"], "a4fb31202d48f65f839217585495c2dc40d29cc63b25ff7a3d5594673056e608")
        self.assertEqual([row["source_id"] for row in source["records"]], list(range(46)))
        self.assertEqual([row["name_slot_id"] for row in source["records"]], EXPECTED_SLOTS)
        self.assertEqual(len(bundle), 920)
        self.assertEqual(_sha(bundle), EXPECTED_REPORT["bundle_sha256"])
        self.assertEqual(bundle, self.rom[TABLE_START:TABLE_END])

    def test_rows_are_contiguous_and_pack_source_id_order(self) -> None:
        payload, bundle = exporter.build_payload(ROOT)
        rows = payload["source_table"]["records"]
        previous = TABLE_START
        for index, row in enumerate(rows):
            start, end = row["range"]
            self.assertEqual((start, end), (TABLE_START + index * 20, TABLE_START + (index + 1) * 20))
            self.assertEqual(start, previous)
            previous = end
            self.assertEqual(row["size"], 20)
            self.assertEqual(row["source_id"], index)
            self.assertEqual(row["raw_hex"], self.rom[start:end].hex())
            self.assertEqual(row["raw_sha256"], _sha(self.rom[start:end]))
            self.assertEqual(row["packed_range"], [index * 20, (index + 1) * 20])
        self.assertEqual(previous, TABLE_END)
        self.assertEqual(payload["summary"], {"record_count": 46, "record_bytes": 920, "range_overlap_bytes": 0, "bundle_sha256": EXPECTED_REPORT["bundle_sha256"]})
        self.assertEqual(bundle, b"".join(self.rom[row["range"][0]:row["range"][1]] for row in rows))

    def test_producer_and_consumer_contracts_bind_full_slices_and_key_bytes(self) -> None:
        payload, _ = exporter.build_payload(ROOT)
        producer = payload["producer_evidence"]
        consumer = payload["consumer_evidence"]
        expected = {
            "enumerator": (0x0808A6AC, 0x0808A700, "68e8b80905466def5f6c4cae6fb6977336c129e7560577a77f6acac7222ca665"),
            "lifecycle": (0x0808B58C, 0x0808B65A, "3b6050a3df82957c8804b86a06eb6c5b5efb8a7eca3da082dc999f74b78c7637"),
            "menu": (0x0808B2C8, 0x0808B580, "fe12c74a937dae0e60f0ba1e566788cd4dc842596d168632c9c45809f88dd07e"),
            "direct_consumer": (0x0808AFE0, 0x0808B07C, "9ec877cbef2c9aa100a825509cd41be605e3d20ff0304279572d7986c1865ac4"),
            "bridge": (0x08066758, 0x08066790, "75de35c89077d45929f63af9f7b1aeddd6ad8bbcc7f4f1982f7d596b5140dd8c"),
            "parser": (0x0806626C, 0x08066736, "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"),
        }
        for name, (start, end, digest) in expected.items():
            evidence = (producer if name in {"enumerator", "lifecycle", "menu"} else consumer)[name]
            raw = self.rom[start - 0x08000000:end - 0x08000000]
            self.assertEqual(evidence["gba_range"], [f"0x{start:08X}", f"0x{end:08X}"])
            self.assertEqual(evidence["range"], [start - 0x08000000, end - 0x08000000])
            self.assertEqual(evidence["size"], len(raw))
            self.assertEqual(evidence["sha256"], digest)
            self.assertEqual(evidence["raw_hex"], raw.hex())
        self.assertEqual(producer["literal_word_0x0808A700"]["raw_hex"], "f0f55908")
        self.assertEqual(producer["literal_word_0x0808A700"]["value"], 0x0859F5F0)
        self.assertEqual(producer["enumerator_loop"]["cmp_immediate"], 0x2D)
        self.assertEqual(producer["enumerator_loop"]["bhi_target"], 0x0808A6AC)
        self.assertEqual(producer["callsites"], [0x0808B5FE, 0x0808B640])
        self.assertEqual(consumer["direct_consumer_callsites"], [0x0808B420, 0x0808B51A])
        self.assertEqual(consumer["record_stride_bytes"], 19)
        self.assertEqual(
            consumer["record_stride_derivation"]["coefficients"], [1, 4, 5, 20, 19]
        )
        self.assertEqual(
            consumer["record_stride_derivation"]["literal_address"], 0x0808B084
        )
        self.assertEqual(consumer["literal_word_0x080B084"]["value"], 0x085A5AB8)
        self.assertEqual(
            consumer["bridge_callsites"],
            [0x0808B010, 0x0808B028, 0x0808B044, 0x0808B054, 0x0808B062, 0x0808B076],
        )
        self.assertEqual(consumer["bridge_target"], 0x08066758)
        self.assertEqual(consumer["bridge_parser_callsite"], 0x0806678A)
        self.assertEqual(consumer["bridge_parser_target"], 0x0806626C)
        self.assertEqual(consumer["parser_range"], [0x06626C, 0x066736])

    def test_old_verifier_and_legacy_rows_are_bound_but_not_used_as_ranges(self) -> None:
        payload, _ = exporter.build_payload(ROOT)
        self.assertEqual(payload["upstream"]["verifier_report"], exporter.EXPECTED_UPSTREAM_REPORT)
        old_rows = self.old_payload["direct_source_table"]["records"]
        new_rows = payload["source_table"]["records"]
        for old, new in zip(old_rows, new_rows, strict=True):
            self.assertEqual(old["source_id"], new["source_id"])
            self.assertEqual(old["name_slot"], new["name_slot_id"])
            self.assertEqual(old["range"], new["range"])
            self.assertEqual(old["sha256"], new["raw_sha256"])
            self.assertEqual(self.rom[new["range"][0]:new["range"][1]], bytes.fromhex(new["raw_hex"]))
        self.assertEqual(payload["scope"]["byte_2_to_19_semantics_proven"], False)
        self.assertFalse(payload["scope"]["complete_63_slot_text_table"])
        self.assertFalse(payload["scope"]["natural_gameplay_all_rows_reached"])

    def test_source_and_producer_semantics_fail_beyond_outer_hashes(self) -> None:
        for implementation in (exporter, verifier):
            with self.subTest(implementation=implementation.__name__, contract="source-vector"):
                tampered = bytearray(self.rom)
                tampered[TABLE_START + 1] ^= 1
                table_sha = _sha(bytes(tampered[TABLE_START:TABLE_END]))
                with mock.patch.object(implementation, "SOURCE_SHA256", table_sha):
                    with self.assertRaisesRegex(ValueError, "slot/domain vector"):
                        implementation._source_records(bytes(tampered))

            with self.subTest(implementation=implementation.__name__, contract="producer-loop"):
                tampered = bytearray(self.rom)
                offset = 0x0808A6F6 - 0x08000000
                tampered[offset] ^= 1
                start, end = implementation.ENUMERATOR_RANGE
                enumerator_sha = _sha(
                    bytes(tampered[start - 0x08000000:end - 0x08000000])
                )
                with mock.patch.object(implementation, "ENUMERATOR_SHA256", enumerator_sha):
                    with self.assertRaisesRegex(ValueError, "producer|loop"):
                        implementation._producer_evidence(bytes(tampered))

    def test_consumer_semantics_fail_beyond_outer_slice_hashes(self) -> None:
        cases = (
            (0x0808B02E, ("DIRECT_CONSUMER_SHA256", "STRIDE_FORMULA_SHA256"), "stride"),
            (0x0808B012, ("DIRECT_CONSUMER_SHA256",), "bridge callsite"),
            (0x0806678C, ("BRIDGE_SHA256",), "bridge parser"),
        )
        ranges = {
            "DIRECT_CONSUMER_SHA256": exporter.DIRECT_CONSUMER_RANGE,
            "STRIDE_FORMULA_SHA256": exporter.STRIDE_FORMULA_RANGE,
            "BRIDGE_SHA256": exporter.BRIDGE_RANGE,
        }
        for implementation in (exporter, verifier):
            for gba, digest_names, error in cases:
                with self.subTest(implementation=implementation.__name__, gba=hex(gba)):
                    tampered = bytearray(self.rom)
                    tampered[gba - 0x08000000] ^= 1
                    patches = []
                    for digest_name in digest_names:
                        start, end = ranges[digest_name]
                        patches.append(
                            mock.patch.object(
                                implementation,
                                digest_name,
                                _sha(bytes(tampered[start - 0x08000000:end - 0x08000000])),
                            )
                        )
                    for patcher in patches:
                        patcher.start()
                    try:
                        with self.assertRaisesRegex(ValueError, error):
                            implementation._consumer_evidence(bytes(tampered))
                    finally:
                        for patcher in reversed(patches):
                            patcher.stop()

    def test_full_rom_bl_denominator_rejects_an_extra_direct_consumer_callsite(self) -> None:
        site = 0x08000100
        tampered = bytearray(self.rom)
        offset = site - 0x08000000
        tampered[offset:offset + 4] = _thumb_bl(site, 0x0808AFE0)
        for implementation in (exporter, verifier):
            with self.subTest(implementation=implementation.__name__):
                with mock.patch.object(implementation, "ROM_SHA256", _sha(bytes(tampered))):
                    with self.assertRaisesRegex(ValueError, "BL denominator"):
                        implementation.rebuild_from_rom(ROOT, bytes(tampered))

    def test_artifact_rehash_tamper_member_and_ancestor_symlinks_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw).resolve()
            artifact = base / "artifact"
            exporter.export_artifact(ROOT, artifact)
            for name in ("rom-selector-direct-source-records.json", "rom-selector-direct-source-records.bin"):
                with self.subTest(name=name):
                    tampered = base / (name + "-tampered")
                    shutil.copytree(artifact, tampered)
                    path = tampered / name
                    data = bytearray(path.read_bytes())
                    data[0] ^= 1
                    path.write_bytes(data)
                    _rehash(tampered, name)
                    self.assertFalse(verifier.verify_artifact(ROOT, tampered)["verified"])

            real = base / "real/parent"
            real.mkdir(parents=True)
            linked = base / "linked"
            linked.symlink_to(base / "real", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                exporter.export_artifact(ROOT, linked / "parent/new-artifact")
            linked_artifact = real / "linked-artifact"
            shutil.copytree(artifact, linked_artifact)
            member = linked_artifact / "rom-selector-direct-source-records.bin"
            target = base / "external.bin"
            target.write_bytes(member.read_bytes())
            member.unlink()
            member.symlink_to(target)
            self.assertFalse(verifier.verify_artifact(ROOT, linked_artifact)["verified"])

    def test_export_does_not_publish_if_new_verifier_is_forced_to_fail(self) -> None:
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
            copied = base / "r"
            _copy_minimal_root(copied)
            completed = subprocess.run(
                ["python3", str(ROOT / "tools/export_rom_selector_direct_source_records.py"), "--root", "r", "--output-dir", "out"],
                cwd=base,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            self.assertTrue((copied / "out/manifest.json").is_file())
            self.assertFalse((copied / "r/out").exists())

    def test_repository_artifact_and_verifier_import_guard(self) -> None:
        artifact = ROOT / "artifacts/rom-selector-direct-source-records-v1"
        self.assertTrue(artifact.is_dir(), artifact)
        report = verifier.verify_artifact(ROOT, artifact)
        self.assertEqual(report, EXPECTED_REPORT)
        tree = ast.parse((ROOT / "tools/verify_rom_selector_direct_source_records.py").read_text(encoding="utf-8"))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        self.assertFalse(any(name.endswith("export_rom_selector_direct_source_records") for name in imported), imported)


if __name__ == "__main__":
    unittest.main()
