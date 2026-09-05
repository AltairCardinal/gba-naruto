#!/usr/bin/env python3
"""TDD contract tests for the frozen event-handler table rooted CFG packet."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/event-handler-cfg-sol-20260901"
PAYLOAD_NAME = "rom-event-handler-cfg.json"
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_RANGE = [0x53E698, 0x53EE98]
TABLE_SHA256 = "20e4727cf65dca82626ffc9637cb36561d5851971500b22a282c5a8c65c7c945"
MATCHING_SLOT_VECTOR_SHA256 = "94d3dddb301608d1acd16a34b89d80e1744fe37aea9da00bae8fd6d8c9025414"
ROOT_VECTOR_SHA256 = "16e6b875243fb94fb67743a40f5065d1af7b3a7d3acd40f4958cb48c0d7767a6"
OCCURRENCE_VECTOR_SHA256 = "a095ebbba8310fb194cd9f49433086eb937dac02d02154de2cb7fcb8b64495f2"
ACCEPTED_ROOTS = [
    0x07E070,
    0x07E1C8,
    0x07E340,
    0x07E4C4,
    0x07E648,
    0x07E774,
    0x07E86C,
    0x07E8A8,
    0x07EA00,
    0x07EA7C,
    0x07EAF8,
    0x07EBA0,
    0x07EC48,
    0x07ED20,
    0x07EE50,
    0x07EF80,
    0x07EFFC,
    0x07F038,
]
REJECTED_ROOT = 0x07F064
UNKNOWN_RANGE = [0x07E070, 0x07F0FC]
OPAQUE_RANGE = [0x07F0FC, 0x07F110]
CODE_RANGES = [
    [0x07E070, 0x07E1BE],
    [0x07E1C8, 0x07E338],
    [0x07E340, 0x07E4BA],
    [0x07E4C4, 0x07E63E],
    [0x07E648, 0x07E76A],
    [0x07E774, 0x07E836],
    [0x07E848, 0x07E86A],
    [0x07E86C, 0x07E8A0],
    [0x07E8A8, 0x07E956],
    [0x07E968, 0x07E9D4],
    [0x07E9DC, 0x07E9FE],
    [0x07EA00, 0x07EA78],
    [0x07EA7C, 0x07EAF0],
    [0x07EAF8, 0x07EB98],
    [0x07EBA0, 0x07EC40],
    [0x07EC48, 0x07EC5E],
    [0x07EC64, 0x07ED18],
    [0x07ED20, 0x07EE48],
    [0x07EE50, 0x07EF78],
    [0x07EF80, 0x07EFF4],
    [0x07EFFC, 0x07F036],
    [0x07F038, 0x07F062],
]
LITERAL_RANGES = [
    [0x07E1C0, 0x07E1C8],
    [0x07E338, 0x07E340],
    [0x07E4BC, 0x07E4C4],
    [0x07E640, 0x07E648],
    [0x07E76C, 0x07E774],
    [0x07E838, 0x07E848],
    [0x07E8A0, 0x07E8A8],
    [0x07E958, 0x07E968],
    [0x07E9D4, 0x07E9DC],
    [0x07EA78, 0x07EA7C],
    [0x07EAF0, 0x07EAF8],
    [0x07EB98, 0x07EBA0],
    [0x07EC40, 0x07EC48],
    [0x07EC60, 0x07EC64],
    [0x07ED18, 0x07ED20],
    [0x07EE48, 0x07EE50],
    [0x07EF78, 0x07EF80],
    [0x07EFF4, 0x07EFFC],
]
SEMANTIC_RANGES = sorted(
    [[*row, "reachable_thumb_code"] for row in CODE_RANGES]
    + [[*row, "consumed_literal_word"] for row in LITERAL_RANGES]
)
UNION_RANGES = [
    [0x07E070, 0x07E1BE],
    [0x07E1C0, 0x07E4BA],
    [0x07E4BC, 0x07E63E],
    [0x07E640, 0x07E76A],
    [0x07E76C, 0x07E836],
    [0x07E838, 0x07E86A],
    [0x07E86C, 0x07E956],
    [0x07E958, 0x07E9FE],
    [0x07EA00, 0x07EC5E],
    [0x07EC60, 0x07F036],
    [0x07F038, 0x07F062],
]


def _products():
    try:
        from tools import export_rom_event_handler_cfg as exporter
        from tools import verify_rom_event_handler_cfg as verifier
    except (ImportError, ModuleNotFoundError) as error:
        raise AssertionError("event-handler CFG product modules are absent") from error
    return exporter, verifier


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


class EventHandlerCfgExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exporter, cls.verifier = _products()
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_payload_rebuilds_frozen_table_roots_cfg_and_current_unknown(self) -> None:
        payload = self.exporter.build_rom_event_handler_cfg_payload(ROOT)
        self.assertEqual("rom-event-handler-cfg-v1", payload["schema"])
        self.assertEqual({"path": "rom/base.gba", "size": ROM_SIZE, "sha256": ROM_SHA256}, payload["rom"])
        table = payload["producer_denominator"]
        self.assertEqual(TABLE_RANGE, table["range"])
        self.assertEqual(2048, table["bytes"])
        self.assertEqual(TABLE_SHA256, table["table_sha256"])
        self.assertEqual(512, table["u32_slot_count"])
        self.assertEqual(203, table["null_slot_count"])
        self.assertEqual(247, table["matching_slot_count"])
        self.assertEqual(62, table["other_slot_count"])
        self.assertEqual(19, table["unique_root_count"])
        self.assertEqual(MATCHING_SLOT_VECTOR_SHA256, table["matching_slot_vector_sha256"])
        self.assertEqual(ROOT_VECTOR_SHA256, table["root_vector_sha256"])
        self.assertEqual(OCCURRENCE_VECTOR_SHA256, table["occurrence_vector_sha256"])
        self.assertEqual(ACCEPTED_ROOTS, payload["accepted_roots"])
        self.assertEqual([REJECTED_ROOT], payload["rejected_roots"])
        self.assertEqual(UNKNOWN_RANGE, payload["candidate_unknown_range"])
        self.assertEqual([OPAQUE_RANGE], payload["opaque_accepted_ranges"])
        self.assertEqual(1742, payload["cfg"]["instruction_count"])
        self.assertEqual(3910, payload["cfg"]["code_bytes"])
        self.assertEqual(471, payload["cfg"]["block_count"])
        self.assertEqual(1869, payload["cfg"]["instruction_internal_edge_count"])
        self.assertEqual(598, payload["cfg"]["block_internal_edge_count"])
        self.assertEqual(213, payload["cfg"]["external_call_edge_count"])
        self.assertEqual(18, payload["cfg"]["frontier_count"])
        self.assertEqual(0, payload["cfg"]["opaque_edge_count"])
        self.assertEqual("81a570aabec618d2d17143cb45f41ff934274946eff2ae02b59bdbdaae30c269", payload["cfg"]["semantic_vector_sha256"])
        self.assertEqual("195f1d8ed4a4655d35e23e77d2fc9b285aae9a01ef701fa51571c41ec832d782", payload["cfg"]["instruction_internal_edge_vector_sha256"])
        self.assertEqual("06c7d122d9875aa4b149e21a1dab01b78d9912ee1a185dbaab72dc63a368c483", payload["cfg"]["block_range_vector_sha256"])
        self.assertEqual("eae4ba95a72342c261c7049ad7871e82d6c7c8dcd6d8791f66064b0828083c0c", payload["cfg"]["block_internal_edge_vector_sha256"])
        self.assertEqual("4444ea91b64053303004b6806bf7d65040de1163c05dcafd77b7e137015c922b", payload["cfg"]["external_call_vector_sha256"])
        self.assertEqual("6c72b89540f61a55c2bbed96c505d9e95cf2db1b55a77a59ae051e9e905fed83", payload["cfg"]["frontier_vector_sha256"])
        self.assertEqual("4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", payload["cfg"]["opaque_edge_vector_sha256"])
        self.assertEqual(CODE_RANGES, payload["promotion"]["code_ranges"])
        self.assertEqual(LITERAL_RANGES, payload["promotion"]["literal_ranges"])
        self.assertEqual(SEMANTIC_RANGES, payload["promotion"]["semantic_ranges"])
        self.assertEqual(UNION_RANGES, payload["promotion"]["union_ranges"])
        self.assertEqual(22, len(payload["promotion"]["code_ranges"]))
        self.assertEqual(18, len(payload["promotion"]["literal_ranges"]))
        self.assertEqual(40, len(payload["promotion"]["semantic_ranges"]))
        self.assertEqual(11, len(payload["promotion"]["union_ranges"]))
        self.assertEqual("3b5b308924f49575121cdd8d2d3b23aa2a1b7c8457b87cab8971ec232cf259ac", payload["promotion"]["literal_range_vector_sha256"])
        self.assertEqual("40c684f688d5e3e461d6cf7ef38f86813523f95bc86c5b87b1b6b62781a5f60f", payload["promotion"]["semantic_range_vector_sha256"])
        self.assertEqual("1fedbc2f6daf37123079a26961f08dc76f81b060616c708ee4e57b0f1d44616b", payload["promotion"]["union_range_vector_sha256"])
        self.assertEqual(4062, payload["promotion"]["bytes"])
        self.assertEqual(174, payload["promotion"]["preserved_unknown_hole_bytes"])
        self.assertEqual("1fedbc2f6daf37123079a26961f08dc76f81b060616c708ee4e57b0f1d44616b", payload["promotion"]["union_range_vector_sha256"])
        self.assertEqual("991ef71ab7a17c7a8c11e25f9f8ae6db7bc1d92a070e8851ffe151cfe43d3dba", payload["promotion"]["packed_code_sha256"])
        self.assertTrue(payload["coverage_baseline"]["current_unknown_only"])
        self.assertEqual(147_160, payload["coverage_baseline"]["unknown_bytes"])
        self.assertEqual(
            ROM_SIZE,
            payload["coverage_baseline"]["classified_bytes"]
            + payload["coverage_baseline"]["unknown_bytes"],
        )
        self.assertEqual(
            4062, payload["coverage_baseline"]["promoted_from_unknown_bytes"]
        )
        self.assertFalse(payload["scope"]["natural_runtime_reachability_proven"])
        self.assertFalse(payload["scope"]["global_handler_denominator_complete"])

    def test_runtime_source_has_no_preflight_or_experiment_dependency(self) -> None:
        for path in (
            ROOT / "tools/rom_event_handler_cfg_contract.py",
            ROOT / "tools/export_rom_event_handler_cfg.py",
            ROOT / "tools/verify_rom_event_handler_cfg.py",
        ):
            source = path.read_text(encoding="utf-8")
            for forbidden in ("event-handler-cfg-preflight", "report.json", "preflight.py"):
                self.assertNotIn(forbidden, source, (path.name, forbidden))

    def test_export_is_atomic_and_artifact_is_verified(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            output = Path(raw) / "candidate"
            manifest = self.exporter.export_rom_event_handler_cfg(ROOT, output)
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual({"manifest.json", PAYLOAD_NAME}, {p.name for p in output.iterdir()})
            self.assertTrue(self.verifier.verify_rom_event_handler_cfg(ROOT, output)["verified"])
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            with mock.patch.object(self.exporter, "_run_isolated_verifier", side_effect=ValueError("forced verifier failure")), self.assertRaisesRegex(ValueError, "forced verifier failure"):
                self.exporter.export_rom_event_handler_cfg(ROOT, output)
            self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir()})

    def test_symlink_and_foreign_output_fail_closed(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            real = parent / "real"
            real.mkdir()
            linked = parent / "linked"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                self.exporter.export_rom_event_handler_cfg(ROOT, linked / "candidate")
            foreign = parent / "foreign"
            foreign.mkdir()
            (foreign / "foreign.txt").write_text("foreign", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "foreign"):
                self.exporter.export_rom_event_handler_cfg(ROOT, foreign)

    def test_raw_table_cfg_and_rejection_edge_mutations_fail_closed(self) -> None:
        checks = [
            (0x53E698, self.exporter._producer_denominator),
            (0x07E070, self.exporter._cfg_rebuild),
            (0x07F0E8, lambda rom: self.exporter._cfg_rebuild(rom)),
        ]
        for offset, helper in checks:
            mutated = bytearray(self.rom)
            mutated[offset] ^= 1
            with self.subTest(offset=hex(offset)), self.assertRaises(ValueError):
                helper(bytes(mutated))

    def test_verifier_is_independent_and_clis_require_isolated_runtime(self) -> None:
        verifier_path = ROOT / "tools/verify_rom_event_handler_cfg.py"
        tree = ast.parse(verifier_path.read_text(encoding="utf-8"))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(any("export_rom_event_handler_cfg" in name for name in imports))
        for path in (ROOT / "tools/export_rom_event_handler_cfg.py", verifier_path):
            ordinary = subprocess.run([sys.executable, str(path), "--help"], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(0, ordinary.returncode)
            self.assertIn("requires Python -I -S", ordinary.stdout + ordinary.stderr)
            isolated = subprocess.run([sys.executable, "-I", "-S", str(path), "--help"], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(0, isolated.returncode, isolated.stdout + isolated.stderr)


if __name__ == "__main__":
    unittest.main()
