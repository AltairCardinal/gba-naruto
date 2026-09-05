from __future__ import annotations

import ast
import copy
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPORTER_PATH = ROOT / "tools/export_rom_soundmain_relocated_cfg.py"
VERIFIER_PATH = ROOT / "tools/verify_rom_soundmain_relocated_cfg.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SoundMainRelocatedCfgIndependentVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exporter = _load(
            EXPORTER_PATH, "export_rom_soundmain_relocated_cfg_for_verifier_test"
        )
        cls.verifier = _load(VERIFIER_PATH, "verify_rom_soundmain_relocated_cfg")
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.payload = cls.exporter.build_preflight_from_rom(ROOT, cls.rom)

    def test_verifier_rebuilds_raw_contract_without_importing_exporter_or_capstone(self):
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        imports: list[str] = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(
            any(
                name.endswith("export_rom_soundmain_relocated_cfg")
                or name == "capstone"
                or name.startswith("capstone.")
                for name in imports
            ),
            imports,
        )

        report = self.verifier.verify_preflight(ROOT, self.payload)

        self.assertEqual(
            report["schema"],
            "rom-soundmain-relocated-cfg-preflight-verification-v1",
        )
        self.assertTrue(report["verified"], report)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["copy_operation_verified"])
        self.assertTrue(report["producer_denominator_verified"])
        self.assertTrue(report["runtime_mapping_verified"])
        self.assertTrue(report["cfg_verified"])
        self.assertTrue(report["coverage_baseline_verified"])
        self.assertTrue(report["promotion_verified"])
        self.assertEqual(report["summary"], {
            "instruction_count": 315,
            "instruction_bytes": 916,
            "thumb_instruction_count": 172,
            "thumb_instruction_bytes": 344,
            "arm_instruction_count": 143,
            "arm_instruction_bytes": 572,
            "block_count": 73,
            "internal_block_edge_count": 112,
            "external_block_edge_count": 1,
            "mode_switch_count": 4,
            "literal_bytes": 8,
            "alignment_gap_bytes": 6,
            "semantic_promotion_bytes": 924,
            "deferred_gap_bytes": 6,
            "opaque_return_count": 1,
            "unresolved_frontier_count": 0,
        })
        self.assertEqual(
            report["semantic_packed_sha256"],
            "2e94dbb5f876de3420d1317db7ad646991b9778e15a3699659d7786d65de8331",
        )
        self.assertEqual(
            report["instruction_vector_sha256"],
            "7f18b67eb2b9d93eb09d01c73e31cd89ca639464c888aa5e7b01ecc5d404fc88",
        )

    def test_structured_contract_tampering_fails_closed(self):
        mutations = (
            ("copy-control", lambda p: p["copy_operation"].__setitem__("control", "0x040000FF")),
            ("producer", lambda p: p["producer_denominator"]["cpuset_callsites"].pop()),
            ("runtime-map", lambda p: p["cfg"]["runtime_mapping"]["runtime_range"].__setitem__(1, 0x03007B68)),
            ("code-range", lambda p: p["cfg"]["code_ranges"][0].__setitem__(1, 0x099E1C)),
            ("mode-switch", lambda p: p["cfg"]["mode_switches"][1].__setitem__("target_mode", "arm")),
            ("literal", lambda p: p["cfg"]["literal_bindings"][0].__setitem__("value", "0x00000000")),
            ("gap", lambda p: p["cfg"]["alignment_gap_ranges"].pop()),
            ("owner", lambda p: p["cfg"]["external_edges"][0].__setitem__("owner_claim_id", "wrong")),
            ("instruction-extra-key", lambda p: p["cfg"]["instructions"][0].__setitem__("attacker", True)),
            ("block-extra-key", lambda p: p["cfg"]["blocks"][0].__setitem__("attacker", True)),
            ("terminator-extra-key", lambda p: p["cfg"]["blocks"][0]["terminator"].__setitem__("attacker", True)),
            ("coverage", lambda p: p["coverage_baseline"].__setitem__("sha256", "0" * 64)),
            ("promotion", lambda p: p["promotion"]["projected_totals"].__setitem__("unknown_bytes", 168_042)),
        )
        for label, mutate in mutations:
            candidate = copy.deepcopy(self.payload)
            mutate(candidate)
            with self.subTest(label=label):
                report = self.verifier.verify_preflight(ROOT, candidate)
                self.assertFalse(report["verified"], report)
                self.assertTrue(report["errors"], report)

    def test_raw_rom_mutation_fails_closed_before_candidate_can_self_attest(self):
        changed = bytearray(self.rom)
        changed[0x099E18] ^= 1
        report = self.verifier.verify_preflight(ROOT, self.payload, rom=bytes(changed))
        self.assertFalse(report["verified"], report)
        self.assertTrue(report["errors"], report)


if __name__ == "__main__":
    unittest.main()
