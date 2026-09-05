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

from tools.export_rom_cfg_inventory import (
    ROM_BASE,
    ROM_SHA256,
    SCHEMA,
    SEED_MANIFEST_SHA256,
    _decode_one,
    _replace_output_dir,
    _validate_output_dir,
    export_rom_cfg_inventory,
)
from tools.verify_rom_cfg_inventory import (
    _raw_control_flow,
    verify_rom_cfg_inventory,
)


ROOT = Path(__file__).resolve().parents[1]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


class RomCfgInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        base = Path(cls.temporary.name).resolve()
        cls.first = base / "first"
        cls.second = base / "second"
        cls.manifest = export_rom_cfg_inventory(ROOT, cls.first)
        export_rom_cfg_inventory(ROOT, cls.second)
        cls.payload_raw = (cls.first / "rom-cfg-inventory.json").read_bytes()
        cls.payload = json.loads(cls.payload_raw)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_decodes_armv4t_direct_control_flow(self):
        fixtures = (
            ("arm", "000000ea" + "00000000" * 3, "unconditional_branch", 8),
            ("arm", "000000eb" + "00000000" * 3, "call", 8),
            ("arm", "0000001a" + "00000000" * 3, "conditional_branch", 8),
            ("thumb", "00e0000000000000", "unconditional_branch", 4),
            ("thumb", "00d1000000000000", "conditional_branch", 4),
            ("thumb", "00f000f800000000", "call", 4),
        )
        for mode, raw_hex, flow_kind, target in fixtures:
            with self.subTest(mode=mode, raw_hex=raw_hex):
                decoded = _decode_one(bytes.fromhex(raw_hex), 0, mode)
                self.assertTrue(decoded["accepted"])
                self.assertEqual(flow_kind, decoded["flow_kind"])
                branch_targets = [
                    edge["file_offset"]
                    for edge in decoded["successors"]
                    if edge["kind"] in {"branch_target", "call_target"}
                ]
                self.assertEqual([target], branch_targets)

    def test_return_and_indirect_terminals_do_not_fall_through(self):
        cases = (
            ("arm", "1eff2fe1", "return", None),
            ("thumb", "7047", "return", None),
            ("arm", "10ff2fe1", "indirect_branch", "indirect_pc_target"),
            ("thumb", "0047", "indirect_branch", "indirect_pc_target"),
            ("thumb", "00bd", "return", None),
            ("arm", "0ef0a0e1", "return", None),
            ("thumb", "f746", "return", None),
            ("arm", "04f01fe5", "indirect_branch", "indirect_pc_target"),
        )
        for mode, raw_hex, flow_kind, frontier_reason in cases:
            with self.subTest(mode=mode, raw_hex=raw_hex):
                decoded = _decode_one(bytes.fromhex(raw_hex), 0, mode)
                self.assertTrue(decoded["accepted"])
                self.assertEqual(flow_kind, decoded["flow_kind"])
                self.assertEqual([], decoded["successors"])
                self.assertEqual(
                    [] if frontier_reason is None else [{"reason": frontier_reason}],
                    decoded["frontiers"],
                )

    def test_fails_closed_on_invalid_and_post_armv4t_encodings(self):
        cases = (
            ("arm", "ffffffff", "decode_failure"),
            ("thumb", "ffff", "decode_failure"),
            ("thumb", "00", "decode_failure"),
            ("thumb", "00f0", "decode_failure"),
            ("arm", "000000fa", "unsupported_armv4t_instruction"),
            ("thumb", "8047", "unsupported_armv4t_instruction"),
            ("thumb", "40f20000", "unsupported_armv4t_instruction"),
        )
        for mode, raw_hex, reason in cases:
            with self.subTest(mode=mode, raw_hex=raw_hex):
                decoded = _decode_one(bytes.fromhex(raw_hex), 0, mode)
                self.assertFalse(decoded["accepted"])
                self.assertEqual(reason, decoded["frontier_reason"])

    def test_supervisor_calls_preserve_fallthrough_and_open_a_bios_frontier(self):
        for mode, raw_hex, immediate, size in (
            ("arm", "010000ef00000000", 1, 4),
            ("thumb", "0adf0000", 10, 2),
        ):
            with self.subTest(mode=mode):
                decoded = _decode_one(bytes.fromhex(raw_hex), 0, mode)
                self.assertTrue(decoded["accepted"])
                self.assertEqual("supervisor_call", decoded["flow_kind"])
                self.assertEqual(
                    [{"kind": "fallthrough", "mode": mode, "file_offset": size}],
                    decoded["successors"],
                )
                self.assertEqual(
                    [
                        {
                            "reason": "bios_swi_external",
                            "swi_immediate": immediate,
                            "target": {
                                "address_space": "bios",
                                "gba_address": "0x00000008",
                            },
                        }
                    ],
                    decoded["frontiers"],
                )

    def test_verifier_uses_raw_armv4t_control_flow_oracles(self):
        cases = (
            ("arm", "000000ea", "unconditional_branch", 8),
            ("arm", "000000eb", "call", 8),
            ("thumb", "00d1", "conditional_branch", 4),
            ("thumb", "00f000f8", "call", 4),
            ("thumb", "7047", "return", None),
            ("thumb", "0adf", "supervisor_call", None),
        )
        for mode, raw_hex, kind, target in cases:
            with self.subTest(mode=mode, raw_hex=raw_hex):
                flow = _raw_control_flow(mode, bytes.fromhex(raw_hex), 0)
                self.assertEqual(kind, flow["flow_kind"])
                self.assertEqual(target, flow.get("target_file_offset"))

    def test_repository_inventory_is_deterministic_and_independently_verified(self):
        self.assertEqual(self.payload_raw, (self.second / "rom-cfg-inventory.json").read_bytes())
        self.assertEqual(
            (self.first / "manifest.json").read_bytes(),
            (self.second / "manifest.json").read_bytes(),
        )
        report = verify_rom_cfg_inventory(ROOT, self.first)
        self.assertTrue(report["verified"], report)
        self.assertEqual("armv4t-raw-encoding", report["control_flow_oracle"])
        self.assertEqual(
            report["decoded_instruction_count"],
            report["independently_rebuilt_instruction_count"],
        )
        self.assertEqual(263, report["root_count"])
        self.assertGreater(report["decoded_instruction_count"], 0)
        self.assertGreater(report["reachable_instruction_bytes"], 0)
        self.assertFalse(report["budget_exhausted"])

    def test_inventory_preserves_the_fixed_seed_denominator(self):
        self.assertEqual(SCHEMA, self.payload["schema"])
        self.assertEqual(
            "f461fda5659657f3dd3dc0690966edb854e26dcc09e868cd8f62e8cbdae62672",
            self.payload["seed_artifact"]["seed_denominator_sha256"],
        )
        roots = self.payload["roots"]
        self.assertEqual(263, len(roots))
        self.assertEqual(2, sum(root["mode"] == "arm" for root in roots))
        self.assertEqual(261, sum(root["mode"] == "thumb" for root in roots))
        self.assertEqual(
            [("arm", 0), ("arm", 0x104)],
            [(root["mode"], root["file_offset"]) for root in roots[:2]],
        )
        self.assertEqual(
            263,
            len({(root["mode"], root["file_offset"]) for root in roots}),
        )
        self.assertEqual(
            {
                "arm_instruction_bytes": 948,
                "arm_instruction_count": 237,
                "arm_root_count": 2,
                "budget_exhausted": False,
                "closed_root_count": 4,
                "cross_mode_overlap_bytes": 0,
                "decoded_basic_block_count": 7_725,
                "decoded_instruction_count": 40_872,
                "frontier_count": 366,
                "frontier_open_root_count": 259,
                "frontier_reasons": {
                    "bios_swi_external": 7,
                    "indirect_pc_target": 357,
                    "unsupported_armv4t_instruction": 2,
                },
                "reachable_instruction_bytes": 86_184,
                "root_count": 263,
                "thumb_instruction_bytes": 85_236,
                "thumb_instruction_count": 40_635,
                "thumb_root_count": 261,
            },
            self.payload["summary"],
        )
        self.assertEqual(
            "e3f6c04ea459dbec397a9d71d6f32591ec03ed076ff8aad227277cb2b3534ba3",
            self.payload["graph_denominator_sha256"],
        )

    def test_blocks_are_hash_bound_and_nonoverlapping_within_each_mode(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        previous_end = {"arm": -1, "thumb": -1}
        for block in sorted(
            self.payload["blocks"], key=lambda item: (item["mode"], item["range"])
        ):
            start, end = block["range"]
            self.assertGreaterEqual(start, previous_end[block["mode"]])
            self.assertEqual(block["bytes_sha256"], _sha(rom[start:end]))
            self.assertGreater(block["instruction_count"], 0)
            previous_end[block["mode"]] = end

    def test_verifier_rejects_semantic_tampering_after_manifest_rehash(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory).resolve() / "artifact"
            shutil.copytree(self.first, artifact)
            payload_path = artifact / "rom-cfg-inventory.json"
            payload = json.loads(payload_path.read_bytes())
            payload["blocks"][0]["bytes_sha256"] = "0" * 64
            raw = _canonical_json(payload)
            payload_path.write_bytes(raw)
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_bytes())
            manifest["files"][payload_path.name] = {
                "size": len(raw),
                "sha256": _sha(raw),
            }
            manifest_path.write_bytes(_canonical_json(manifest))

            report = verify_rom_cfg_inventory(ROOT, artifact)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("block" in error.lower() for error in report["errors"]), report
            )

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
            with self.assertRaisesRegex(ValueError, "replaceable CFG inventory"):
                _validate_output_dir(root, foreign)
            self.assertEqual(b"keep", keep.read_bytes())

    def test_output_validator_rejects_a_forged_two_file_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "repo"
            root.mkdir()
            forged = root / "forged"
            forged.mkdir()
            payload = {
                "schema": SCHEMA,
                "rom": {"sha256": ROM_SHA256},
            }
            payload_raw = _canonical_json(payload)
            (forged / "rom-cfg-inventory.json").write_bytes(payload_raw)
            manifest = {
                "artifact_schema": SCHEMA,
                "rom": {"sha256": ROM_SHA256},
                "seed_artifact": {"manifest_sha256": SEED_MANIFEST_SHA256},
                "files": {
                    "rom-cfg-inventory.json": {
                        "size": len(payload_raw),
                        "sha256": _sha(payload_raw),
                    }
                },
            }
            (forged / "manifest.json").write_bytes(_canonical_json(manifest))

            with self.assertRaisesRegex(ValueError, "replaceable CFG inventory"):
                _validate_output_dir(root, forged)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_output_validator_rejects_leaf_and_parent_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "repo"
            root.mkdir()
            foreign = Path(directory).resolve() / "foreign"
            foreign.mkdir()
            leaf = root / "leaf"
            leaf.symlink_to(foreign, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                _validate_output_dir(root, leaf)
            parent = root / "linked-parent"
            parent.symlink_to(foreign, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                _validate_output_dir(root, parent / "artifact")
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
                export_rom_cfg_inventory(root, root)
            self.assertEqual(b"unchanged", sentinel.read_bytes())

    def test_atomic_replace_restores_the_old_artifact_when_install_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            output = base / "artifact"
            staging = base / "staging"
            output.mkdir()
            staging.mkdir()
            (output / "old.bin").write_bytes(b"old")
            (staging / "new.bin").write_bytes(b"new")
            real_replace = os.replace
            call_count = 0

            def fail_second_replace(source, target):
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise OSError("injected install failure")
                return real_replace(source, target)

            with mock.patch(
                "tools.export_rom_cfg_inventory.os.replace",
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
                    "tools/export_rom_cfg_inventory.py",
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
            report = verify_rom_cfg_inventory(ROOT, output)
            self.assertTrue(report["verified"], report)


if __name__ == "__main__":
    unittest.main()
