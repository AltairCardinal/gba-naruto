"""TDD contract for the boot-state dispatcher and five target closures."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BootStateDispatcherCfgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_boot_state_dispatcher_cfg as exporter
        from tools import verify_rom_boot_state_dispatcher_cfg as verifier

        cls.exporter = exporter
        cls.verifier = verifier

    def test_exact_denominators_and_structured_returns(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        self.assertEqual("rom-boot-state-dispatcher-cfg-v1", payload["schema"])
        self.assertEqual(6, payload["producer_denominator"]["match_count"])
        self.assertEqual(6, payload["dispatcher"]["slot_count"])
        closure = payload["target_closure"]
        self.assertEqual(5, closure["root_count"])
        self.assertEqual(1116, closure["instruction_count"])
        self.assertEqual(2248, closure["code_bytes"])
        self.assertEqual(188, closure["literal_bytes"])
        self.assertEqual(8, closure["opaque_call_count"])
        self.assertEqual(5, closure["structured_return_count"])
        self.assertEqual(0, closure["frontier_count"])
        self.assertTrue(closure["structured_return_contract"]["cpufastset_source_only"])
        self.assertEqual([0x063C7E], closure["structured_return_contract"]["sp_alias_sites"])
        self.assertEqual(12, len(closure["preserved_unknown_holes"]))
        self.assertEqual(24, closure["preserved_unknown_bytes"])

    def test_exact_promotion_and_narrow_scope(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        promotion = payload["promotion"]
        self.assertEqual(2532, promotion["promotion_bytes"])
        self.assertEqual(2248, promotion["target_code_bytes"])
        self.assertEqual(188, promotion["target_literal_bytes"])
        self.assertEqual(96, promotion["dispatcher_bytes"])
        self.assertEqual(45, len(promotion["claims"]))
        for key in ("natural_runtime_reachability", "ram_state_writer_denominator",
                    "opaque_callee_semantics", "padding_or_free_space",
                    "editing_or_relocation_safety"):
            self.assertFalse(payload["scope"][key])

    def test_export_roundtrip_and_independent_verifier(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            output = Path(directory) / "candidate"
            self.exporter.export_artifact(ROOT, output)
            report = self.verifier.verify_artifact(ROOT, output)
            self.assertTrue(report["verified"], report)
            self.assertEqual(2532, report["promotion_bytes"])
            self.assertEqual(0, report["frontier_count"])

    def test_verifier_is_independent(self) -> None:
        source = (ROOT / "tools/verify_rom_boot_state_dispatcher_cfg.py").read_text()
        imports = [ast.unparse(node) for node in ast.walk(ast.parse(source))
                   if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("export_rom_boot_state_dispatcher_cfg" in row for row in imports))
        rebuilt = self.verifier._rebuild((ROOT / "rom/base.gba").read_bytes())
        self.assertEqual(1116, rebuilt["target_closure"]["instruction_count"])

    def test_control_flow_and_structured_return_mutations_fail_closed(self) -> None:
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        for offset, pattern in ((0x06109A, "producer"), (0x06467A, "dispatcher"),
                                (0x064698, "dispatcher"), (0x063C2E, "return"),
                                (0x064472, "return"), (0x063B3E, "hole"),
                                (0x063C80, "CpuFastSet"), (0x063CEC, "CpuFastSet"),
                                (0x09C0DC, "CpuFastSet")):
            with self.subTest(offset=hex(offset)):
                changed = bytearray(rom); changed[offset] ^= 1
                with self.assertRaisesRegex(ValueError, pattern):
                    self.exporter._build_from_rom(ROOT, bytes(changed), verify_identity=False)

    def test_extra_b_and_bcond_producers_fail_closed(self) -> None:
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        # Both synthetic branches target root 0x063ADC.  The fixed ROM happens
        # to contain only BL matches, so these mutations protect the B/Bcond
        # branches of the advertised full direct-producer denominator.
        for offset, halfword in ((0x063AD0, 0xE004), (0x063AD4, 0xD002)):
            with self.subTest(offset=hex(offset)):
                changed = bytearray(rom)
                changed[offset:offset + 2] = halfword.to_bytes(2, "little")
                with self.assertRaisesRegex(ValueError, "producer denominator"):
                    self.exporter._scan_producers(bytes(changed))
                with self.assertRaisesRegex(ValueError, "producer denominator"):
                    self.verifier._rebuild(bytes(changed))

    def test_artifact_tamper_and_existing_output_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            output = Path(directory) / "candidate"
            self.exporter.export_artifact(ROOT, output)
            with self.assertRaises(FileExistsError):
                self.exporter.export_artifact(ROOT, output)
            path = output / self.exporter.PAYLOAD_NAME
            payload = json.loads(path.read_text())
            payload["promotion"]["promotion_bytes"] += 1
            raw = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
            path.write_bytes(raw)
            manifest_path = output / self.exporter.MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][self.exporter.PAYLOAD_NAME] = {
                "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False,
                                                indent=2, sort_keys=True) + "\n")
            self.assertFalse(self.verifier.verify_artifact(ROOT, output)["verified"])


if __name__ == "__main__":
    unittest.main()
