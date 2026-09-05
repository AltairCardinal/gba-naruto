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
from unittest.mock import patch

import tools.export_rom_cfg_proven_roots_v8 as exporter_v8
import tools.verify_rom_cfg_proven_roots_v8 as verifier_v8

from tools.export_rom_cfg_proven_roots_v8 import (
    PROMOTION_WINDOW,
    SOURCE_SLICE,
    _producer_denominator,
    _source_worklist,
    build_cfg_proven_roots_v8_payload,
    export_rom_cfg_proven_roots_v8,
)
from tools.verify_rom_cfg_proven_roots_v8 import verify_rom_cfg_proven_roots_v8


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/luna-cfg-proven-roots-v8b-20260820"
PAYLOAD_NAME = "rom-cfg-proven-roots-v8.json"
RUNTIME_DEPENDENCY_PATHS = (
    "tools/export_rom_cfg_inventory.py",
    "tools/export_rom_cfg_proven_roots.py",
    "tools/export_rom_cfg_proven_roots_v2.py",
    "tools/verify_rom_cfg_inventory.py",
    "tools/verify_rom_cfg_inventory_v3.py",
    "tools/verify_rom_cfg_proven_roots.py",
    "tools/verify_rom_cfg_proven_roots_v2.py",
    "tools/verify_rom_cfg_proven_roots_v3.py",
    "tools/verify_rom_cfg_proven_roots_v7.py",
    "tools/verify_rom_cfg_seeds.py",
    "tools/verify_similar_table_candidates.py",
    "tools/verify_scene_visual_packs.py",
    "tools/_vendor/capstone/__init__.py",
    "tools/_vendor/capstone/arm.py",
    "tools/_vendor/capstone/arm64.py",
    "tools/_vendor/capstone/arm64_const.py",
    "tools/_vendor/capstone/arm_const.py",
    "tools/_vendor/capstone/bpf.py",
    "tools/_vendor/capstone/bpf_const.py",
    "tools/_vendor/capstone/evm.py",
    "tools/_vendor/capstone/evm_const.py",
    "tools/_vendor/capstone/m680x.py",
    "tools/_vendor/capstone/m680x_const.py",
    "tools/_vendor/capstone/m68k.py",
    "tools/_vendor/capstone/m68k_const.py",
    "tools/_vendor/capstone/mips.py",
    "tools/_vendor/capstone/mips_const.py",
    "tools/_vendor/capstone/mos65xx.py",
    "tools/_vendor/capstone/mos65xx_const.py",
    "tools/_vendor/capstone/ppc.py",
    "tools/_vendor/capstone/ppc_const.py",
    "tools/_vendor/capstone/riscv.py",
    "tools/_vendor/capstone/riscv_const.py",
    "tools/_vendor/capstone/sh.py",
    "tools/_vendor/capstone/sh_const.py",
    "tools/_vendor/capstone/sparc.py",
    "tools/_vendor/capstone/sparc_const.py",
    "tools/_vendor/capstone/systemz.py",
    "tools/_vendor/capstone/sysz_const.py",
    "tools/_vendor/capstone/tms320c64x.py",
    "tools/_vendor/capstone/tms320c64x_const.py",
    "tools/_vendor/capstone/tricore.py",
    "tools/_vendor/capstone/tricore_const.py",
    "tools/_vendor/capstone/wasm.py",
    "tools/_vendor/capstone/wasm_const.py",
    "tools/_vendor/capstone/x86.py",
    "tools/_vendor/capstone/x86_const.py",
    "tools/_vendor/capstone/xcore.py",
    "tools/_vendor/capstone/xcore_const.py",
    "tools/_vendor/capstone/lib/libcapstone.dylib",
)


class RomCfgProvenRootsV8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_source_worklist_is_bounded_and_proves_producer_boundary(self) -> None:
        source = _source_worklist(self.rom)
        self.assertEqual([0x08BAB0, 0x08BEDE], source["range"])
        self.assertEqual(1070, source["size"])
        self.assertEqual(380, source["accepted_instruction_count"])
        self.assertEqual(846, source["accepted_instruction_bytes"])
        self.assertIn(0x08BE5C, source["accepted_instruction_offsets"])
        self.assertEqual(0, source["unresolved_entry_count"])
        self.assertGreater(source["unreachable_byte_count"], 0)

    def test_source_evidence_fails_closed_on_reachable_and_unreachable_byte_tamper(self) -> None:
        for offset in (0x08BAB0, 0x08BE5D):
            with self.subTest(offset=offset):
                tampered = bytearray(self.rom)
                tampered[offset] ^= 1
                with self.assertRaises(ValueError):
                    _source_worklist(bytes(tampered))

    def test_full_rom_producer_denominator_is_unique(self) -> None:
        producer = _producer_denominator(self.rom)
        self.assertEqual(1, producer["scan"]["matching_producer_count"])
        self.assertEqual(
            [(0x08BE5C, 0x08B99C)],
            [
                (item["file_offset"], item["target_file_offset"])
                for item in producer["producers"]
            ],
        )

    def test_exact_root_summary_and_promotion_window(self) -> None:
        payload = build_cfg_proven_roots_v8_payload(ROOT)
        self.assertEqual("rom-cfg-proven-roots-v8", payload["schema"])
        self.assertEqual(
            {
                "decoded_basic_block_count": 20,
                "decoded_instruction_count": 113,
                "frontier_count": 1,
                "frontier_reasons": {"indirect_pc_target": 1},
                "reachable_instruction_bytes": 246,
            },
            payload["extension"]["summary"],
        )
        start, end = PROMOTION_WINDOW
        for block in payload["extension"]["blocks"]:
            self.assertGreaterEqual(block["range"][0], start)
            self.assertLessEqual(block["range"][1], end)
        self.assertEqual([start, end], payload["scope"]["promotion_window"])
        self.assertEqual([0x08BAB0, 0x08BEDE], payload["scope"]["source_slice"])

    def _tampered_artifact(self, tmp: str, mutate) -> Path:
        output = Path(tmp) / "cfg-v8"
        export_rom_cfg_proven_roots_v8(ROOT, output)
        payload_path = output / PAYLOAD_NAME
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        mutate(payload)
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        payload_path.write_bytes(raw)
        manifest_path = output / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"][PAYLOAD_NAME] = {
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        return output

    def test_exports_and_independently_verifies(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as tmp:
            output = Path(tmp) / "cfg-v8"
            export_rom_cfg_proven_roots_v8(ROOT, output)
            report = verify_rom_cfg_proven_roots_v8(ROOT, output)
            self.assertTrue(report["verified"], report)
            self.assertEqual(113, report["decoded_instruction_count"])
            self.assertEqual(20, report["decoded_basic_block_count"])
            self.assertEqual(1, report["frontier_count"])
            self.assertEqual(10, report["baseline_cross_edge_count"])

    def test_repository_artifact_independently_verifies(self) -> None:
        report = verify_rom_cfg_proven_roots_v8(
            ROOT, ROOT / "artifacts/rom-cfg-proven-roots-v8"
        )
        self.assertTrue(report["verified"], report)
        self.assertEqual(113, report["independently_rebuilt_instruction_count"])
        self.assertEqual(246, report["reachable_instruction_bytes"])

    def test_rejects_payload_tamper_even_after_manifest_rehash(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as tmp:
            output = self._tampered_artifact(
                tmp,
                lambda payload: payload["extension"].__setitem__(
                    "cross_edge_denominator_sha256", "0" * 64
                ),
            )
            self.assertFalse(verify_rom_cfg_proven_roots_v8(ROOT, output)["verified"])

    def test_traversals_reject_baseline_entry_middle_and_straddle(self) -> None:
        root_offset = 0x08B900
        roots = [{"mode": "thumb", "file_offset": root_offset}]
        implementations = (
            (
                exporter_v8,
                exporter_v8._traverse_bounded_root,
                "_decode_one",
            ),
            (verifier_v8, verifier_v8._traverse_root, "_decode"),
        )
        for module, traverse, decoder_name in implementations:
            with self.subTest(implementation=module.__name__, case="entry"):
                baseline = {
                    "synthetic": {("thumb", root_offset): {"size": 2}}
                }
                with self.assertRaisesRegex(ValueError, "root overlaps.*baseline"):
                    traverse(self.rom, roots, baseline)

            with self.subTest(implementation=module.__name__, case="middle"):
                baseline = {
                    "synthetic": {("thumb", root_offset + 4): {"size": 2}}
                }
                decoded = {
                    "accepted": True,
                    "size": 2,
                    "successors": [
                        {
                            "mode": "thumb",
                            "file_offset": root_offset + 5,
                            "kind": "branch",
                        }
                    ],
                }
                with patch.object(module, decoder_name, return_value=decoded):
                    with self.assertRaisesRegex(
                        ValueError, "successor targets baseline middle or straddle"
                    ):
                        traverse(self.rom, roots, baseline)

            with self.subTest(implementation=module.__name__, case="straddle"):
                baseline = {
                    "synthetic": {("thumb", root_offset + 2): {"size": 2}}
                }
                decoded = {"accepted": True, "size": 4, "successors": []}
                with patch.object(module, decoder_name, return_value=decoded):
                    with self.assertRaisesRegex(
                        ValueError, "instruction straddles.*baseline"
                    ):
                        traverse(self.rom, roots, baseline)

    def test_rejects_root_and_ancestor_output_paths(self) -> None:
        with self.assertRaisesRegex(ValueError, "repository root or ancestor"):
            export_rom_cfg_proven_roots_v8(ROOT, ROOT)
        with self.assertRaisesRegex(ValueError, "repository root or ancestor"):
            export_rom_cfg_proven_roots_v8(ROOT, ROOT.parent)

    def test_rejects_symlink_and_foreign_non_empty_output(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as tmp:
            base = Path(tmp)
            real = base / "real"
            real.mkdir()
            linked = base / "linked"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                export_rom_cfg_proven_roots_v8(ROOT, linked / "cfg-v8")
            foreign = base / "foreign"
            foreign.mkdir()
            (foreign / "foreign.txt").write_text("do not replace", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "foreign non-empty"):
                export_rom_cfg_proven_roots_v8(ROOT, foreign)

    def test_existing_same_schema_output_is_replaced_only_after_verification(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as tmp:
            output = Path(tmp) / "cfg-v8"
            export_rom_cfg_proven_roots_v8(ROOT, output)
            first = verify_rom_cfg_proven_roots_v8(ROOT, output)
            self.assertTrue(first["verified"], first)
            export_rom_cfg_proven_roots_v8(ROOT, output)
            self.assertTrue(verify_rom_cfg_proven_roots_v8(ROOT, output)["verified"])
            payload = json.loads((output / PAYLOAD_NAME).read_text(encoding="utf-8"))
            payload["scope"]["runtime_reachability_complete"] = True
            (output / PAYLOAD_NAME).write_text(
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                export_rom_cfg_proven_roots_v8(ROOT, output)

    def test_implementation_binding_rejects_loaded_source_mismatch(self) -> None:
        capstone_transitive_probes = (
            Path("tools/_vendor/capstone/x86.py"),
            Path("tools/_vendor/capstone/x86_const.py"),
        )
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as tmp:
            copied = Path(tmp) / "copy"
            copied.mkdir()
            for relative in (
                "tools/export_rom_cfg_proven_roots_v8.py",
                "tools/verify_rom_cfg_proven_roots_v8.py",
                "tests/test_export_rom_cfg_proven_roots_v8.py",
                *RUNTIME_DEPENDENCY_PATHS,
                *capstone_transitive_probes,
            ):
                target = copied / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)
            expected = exporter_v8._implementation(ROOT)
            self.assertEqual(expected, exporter_v8._implementation(copied))
            self.assertEqual(expected, verifier_v8._implementation(copied))

            copied_exporter = copied / "tools/export_rom_cfg_proven_roots_v8.py"
            copied_exporter.write_bytes(copied_exporter.read_bytes() + b"\n# copied-root\n")
            for implementation in (
                exporter_v8._implementation,
                verifier_v8._implementation,
            ):
                with self.subTest(implementation=implementation.__module__):
                    with self.assertRaisesRegex(ValueError, "loaded implementation"):
                        implementation(copied)

            shutil.copy2(ROOT / "tools/export_rom_cfg_proven_roots_v8.py", copied_exporter)
            copied_x86 = copied / capstone_transitive_probes[0]
            copied_x86.write_bytes(copied_x86.read_bytes() + b"\n# transitive-drift\n")
            for implementation in (
                exporter_v8._implementation,
                verifier_v8._implementation,
            ):
                with self.subTest(
                    implementation=implementation.__module__, dependency="x86.py"
                ):
                    with self.assertRaisesRegex(ValueError, "loaded implementation"):
                        implementation(copied)

    def test_implementation_binds_complete_runtime_dependency_denominator(self) -> None:
        expected_paths = set(RUNTIME_DEPENDENCY_PATHS)
        capstone_python_paths = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "tools/_vendor/capstone").glob("*.py")
        }
        self.assertEqual(37, len(capstone_python_paths))
        self.assertTrue(capstone_python_paths <= expected_paths)
        for implementation in (
            exporter_v8._implementation(ROOT),
            verifier_v8._implementation(ROOT),
        ):
            with self.subTest(binding=implementation.get("binding")):
                self.assertEqual(
                    expected_paths,
                    set(implementation["runtime_dependency_sha256"]),
                )
                for relative, digest in implementation[
                    "runtime_dependency_sha256"
                ].items():
                    self.assertEqual(
                        hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
                        digest,
                    )

    def test_isolated_cli_rejects_preloaded_capstone_even_with_vendored_metadata(self) -> None:
        environment = os.environ.copy()
        environment.pop("LIBCAPSTONE_PATH", None)
        for relative in (
            "tools/export_rom_cfg_proven_roots_v8.py",
            "tools/verify_rom_cfg_proven_roots_v8.py",
        ):
            script = ROOT / relative
            code = f"""
import runpy
import sys
sys.path[:0] = [{str(ROOT / 'tools/_vendor')!r}, {str(ROOT)!r}]
import capstone
capstone.Cs = object
sys.argv = [{str(script)!r}, '--help']
runpy.run_path({str(script)!r}, run_name='__main__')
"""
            with self.subTest(script=relative):
                result = subprocess.run(
                    [sys.executable, "-I", "-S", "-c", code],
                    cwd=ROOT,
                    env=environment,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(0, result.returncode)
                self.assertIn("preloaded Capstone", result.stdout + result.stderr)

    def test_isolated_cli_rejects_external_libcapstone_override(self) -> None:
        environment = os.environ.copy()
        environment["LIBCAPSTONE_PATH"] = "/tmp/external-capstone"
        for relative in (
            "tools/export_rom_cfg_proven_roots_v8.py",
            "tools/verify_rom_cfg_proven_roots_v8.py",
        ):
            with self.subTest(script=relative):
                result = subprocess.run(
                    [sys.executable, "-I", "-S", str(ROOT / relative), "--help"],
                    cwd=ROOT,
                    env=environment,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(0, result.returncode)
                self.assertIn("LIBCAPSTONE_PATH", result.stdout + result.stderr)

    def test_cli_requires_isolated_no_site_runtime(self) -> None:
        environment = os.environ.copy()
        environment.pop("LIBCAPSTONE_PATH", None)
        for relative in (
            "tools/export_rom_cfg_proven_roots_v8.py",
            "tools/verify_rom_cfg_proven_roots_v8.py",
        ):
            script = ROOT / relative
            with self.subTest(script=relative, isolated=False):
                result = subprocess.run(
                    [sys.executable, str(script), "--help"],
                    cwd=ROOT,
                    env=environment,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(0, result.returncode)
                self.assertIn("requires Python -I -S", result.stdout + result.stderr)
            with self.subTest(script=relative, isolated=True):
                result = subprocess.run(
                    [sys.executable, "-I", "-S", str(script), "--help"],
                    cwd=ROOT,
                    env=environment,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_source_evidence_executes_source_verifier_contract(self) -> None:
        failed = {
            "verified": False,
            "errors": ["synthetic source failure"],
            "pack_count": 0,
            "obj_frame_count": 0,
            "obj_animation_count": 0,
        }
        calls = (
            (exporter_v8.__name__, lambda: exporter_v8._source_evidence(ROOT, self.rom)),
            (verifier_v8.__name__, lambda: verifier_v8._source_evidence(ROOT)),
        )
        for implementation, call in calls:
            with self.subTest(implementation=implementation):
                with patch(
                    "tools.verify_scene_visual_packs.verify_artifact",
                    return_value=failed,
                ):
                    with self.assertRaisesRegex(
                        ValueError, "source artifact independent verification"
                    ):
                        call()

    def test_verifier_revalidates_source_evidence_from_passed_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as tmp:
            copied = Path(tmp) / "copy"
            shutil.copytree(
                ROOT / "artifacts/scene-visual-packs-v1",
                copied / "artifacts/scene-visual-packs-v1",
            )
            verifier_target = copied / exporter_v8.SOURCE_VERIFIER_PATH
            verifier_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / exporter_v8.SOURCE_VERIFIER_PATH, verifier_target)
            rom_target = copied / "rom/base.gba"
            rom_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "rom/base.gba", rom_target)
            expected = exporter_v8._source_evidence(ROOT, self.rom)
            self.assertEqual(expected, verifier_v8._source_evidence(copied))
            for relative in (
                exporter_v8.SOURCE_MANIFEST_PATH,
                exporter_v8.SOURCE_VERIFIER_PATH,
            ):
                with self.subTest(relative=relative.as_posix()):
                    target = copied / relative
                    original = target.read_bytes()
                    target.write_bytes(original + b"\n")
                    with self.assertRaisesRegex(ValueError, "source .* changed"):
                        verifier_v8._source_evidence(copied)
                    target.write_bytes(original)

            manifest_path = copied / exporter_v8.SOURCE_MANIFEST_PATH
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["consumer_evidence"]["setup_and_initial_row"]["size"] += 1
            tampered_raw = json.dumps(
                manifest, sort_keys=True, separators=(",", ":")
            ).encode()
            manifest_path.write_bytes(tampered_raw)
            with patch.object(
                verifier_v8,
                "SOURCE_MANIFEST_SHA256",
                hashlib.sha256(tampered_raw).hexdigest(),
            ):
                with self.assertRaisesRegex(ValueError, "source selector changed"):
                    verifier_v8._source_evidence(copied)

    def test_baseline_cache_key_tracks_artifact_file_identity(self) -> None:
        dependency_dirs = (
            "artifacts/rom-cfg-inventory-v2",
            "artifacts/rom-cfg-inventory-v3",
            "artifacts/rom-cfg-proven-roots-v1",
            "artifacts/rom-cfg-proven-roots-v2",
            "artifacts/rom-battle-controller-cfg-v1",
            "artifacts/rom-cfg-proven-roots-v3",
            "artifacts/rom-cfg-proven-roots-v4",
            "artifacts/rom-cfg-proven-roots-v5",
            "artifacts/rom-cfg-proven-roots-v6",
            "artifacts/rom-cfg-proven-roots-v7",
        )
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as tmp:
            copied = Path(tmp) / "copy"
            rom = b"synthetic-rom"
            (copied / "rom").mkdir(parents=True)
            (copied / "rom/base.gba").write_bytes(rom)
            sentinels = []
            for index, relative in enumerate(dependency_dirs):
                directory = copied / relative
                directory.mkdir(parents=True)
                sentinel = directory / "identity.bin"
                sentinel.write_bytes(bytes([index]))
                sentinels.append(sentinel)

            cases = (
                (
                    exporter_v8,
                    exporter_v8._baseline_contract,
                    "_baseline_contract_uncached",
                ),
                (
                    verifier_v8,
                    verifier_v8._load_baselines,
                    "_load_baselines_uncached",
                ),
            )
            for module, loader, uncached_name in cases:
                with self.subTest(implementation=module.__name__):
                    with patch.object(
                        module,
                        uncached_name,
                        return_value=({}, {}, {}),
                    ) as uncached:
                        loader(copied, rom)
                        loader(copied, rom)
                        self.assertEqual(2, uncached.call_count)
                        sentinels[-1].write_bytes(b"changed")
                        loader(copied, rom)
                        self.assertEqual(3, uncached.call_count)

    def test_independent_verifier_does_not_import_exporter(self) -> None:
        source = (ROOT / "tools/verify_rom_cfg_proven_roots_v8.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("export_rom_cfg_proven_roots_v8", source)


if __name__ == "__main__":
    unittest.main()
