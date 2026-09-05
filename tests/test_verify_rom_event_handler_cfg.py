#!/usr/bin/env python3
"""Contract tests for the independent event-handler CFG verifier."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/event-handler-cfg-sol-20260901"
ARTIFACT = ROOT / "artifacts/rom-event-handler-cfg-v1"
PAYLOAD_NAME = "rom-event-handler-cfg.json"


def _products():
    try:
        from tools import export_rom_event_handler_cfg as exporter
        from tools import verify_rom_event_handler_cfg as verifier
    except (ImportError, ModuleNotFoundError) as error:
        raise AssertionError("event-handler CFG product modules are absent") from error
    return exporter, verifier


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


class EventHandlerCfgVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exporter, cls.verifier = _products()

    def _make_artifact(self, parent: Path) -> Path:
        output = parent / "candidate"
        self.exporter.export_rom_event_handler_cfg(ROOT, output)
        return output

    def test_official_artifact_is_independently_verified(self) -> None:
        report = self.verifier.verify_rom_event_handler_cfg(ROOT, ARTIFACT)
        self.assertTrue(report["verified"])
        self.assertEqual("rom-event-handler-cfg-verification-v1", report["schema"])
        self.assertEqual(18, report["accepted_root_count"])
        self.assertEqual([0x07F064], report["rejected_roots"])
        self.assertEqual(1742, report["instruction_count"])
        self.assertEqual(3910, report["code_bytes"])
        self.assertEqual(471, report["block_count"])
        self.assertEqual(18, report["frontier_count"])
        self.assertEqual(0, report["opaque_edge_count"])
        self.assertEqual(4062, report["promotion_bytes"])
        self.assertEqual(174, report["preserved_unknown_hole_bytes"])
        self.assertTrue(all(value is False for value in report["nonclaims"].values()))

    def test_extra_member_symlink_and_tampering_fail_closed(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            artifact = self._make_artifact(parent)
            (artifact / "extra.json").write_text("{}", encoding="utf-8")
            self.assertFalse(self.verifier.verify_rom_event_handler_cfg(ROOT, artifact)["verified"])
            (artifact / "extra.json").unlink()
            linked = artifact / "linked"
            linked.symlink_to(artifact / PAYLOAD_NAME)
            self.assertFalse(self.verifier.verify_rom_event_handler_cfg(ROOT, artifact)["verified"])
            linked.unlink()
            payload_path = artifact / PAYLOAD_NAME
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["promotion"]["bytes"] = 4061
            payload_path.write_bytes(_canonical(payload))
            self.assertFalse(self.verifier.verify_rom_event_handler_cfg(ROOT, artifact)["verified"])

    def test_receipt_root_slot_range_and_rejection_mutations_fail_closed(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            artifact = self._make_artifact(parent)
            payload_path = artifact / PAYLOAD_NAME
            original = payload_path.read_bytes()
            payload = json.loads(original)
            payload["producer_denominator"]["matching_slots"][0][0] += 1
            payload_path.write_bytes(_canonical(payload))
            self.assertFalse(self.verifier.verify_rom_event_handler_cfg(ROOT, artifact)["verified"])
            payload_path.write_bytes(original)
            manifest_path = artifact / "manifest.json"
            original_manifest = manifest_path.read_bytes()
            manifest = json.loads(original_manifest)
            manifest["producer"]["command"][-1] = "artifacts/rom-event-handler-cfg-v1"
            manifest["verifier"]["command"][-1] = "artifacts/rom-event-handler-cfg-v1"
            manifest_path.write_bytes(_canonical(manifest))
            self.assertFalse(self.verifier.verify_rom_event_handler_cfg(ROOT, artifact)["verified"])
            payload_path.write_bytes(original)
            manifest_path.write_bytes(original_manifest)
            payload = json.loads(original)
            payload["rejected_roots"][0] ^= 2
            payload_path.write_bytes(_canonical(payload))
            self.assertFalse(self.verifier.verify_rom_event_handler_cfg(ROOT, artifact)["verified"])

    def test_missing_foreign_and_copied_receipt_artifacts_fail_closed(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            self.assertFalse(self.verifier.verify_rom_event_handler_cfg(ROOT, parent / "missing")["verified"])
            source = self._make_artifact(parent / "source")
            copied = parent / "copied"
            shutil.copytree(source, copied)
            self.assertFalse(self.verifier.verify_rom_event_handler_cfg(ROOT, copied)["verified"])
            foreign = parent / "foreign"
            shutil.copytree(source, foreign)
            (foreign / "foreign.txt").write_text("foreign", encoding="utf-8")
            self.assertFalse(self.verifier.verify_rom_event_handler_cfg(ROOT, foreign)["verified"])

    def test_verifier_has_no_exporter_import(self) -> None:
        source = Path(self.verifier.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(any("export_rom_event_handler_cfg" in name for name in imports))


if __name__ == "__main__":
    unittest.main()
