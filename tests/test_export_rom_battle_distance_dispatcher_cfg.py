"""TDD contract for the seven-way battle-distance dispatcher closure."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BattleDistanceDispatcherCfgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_battle_distance_dispatcher_cfg as exporter
        from tools import verify_rom_battle_distance_dispatcher_cfg as verifier

        cls.exporter = exporter
        cls.verifier = verifier
        cls.payload = exporter.build_payload(ROOT)

    def test_exact_dispatcher_and_closure_denominators(self) -> None:
        payload = self.payload
        self.assertEqual("rom-battle-distance-dispatcher-cfg-v1", payload["schema"])
        dispatcher = payload["dispatcher_contract"]
        self.assertEqual(6, dispatcher["unsigned_max_index"])
        self.assertEqual(7, dispatcher["slot_count"])
        self.assertEqual(
            [0x083B78, 0x083BAC, 0x083C8A, 0x083D20,
             0x083DAE, 0x083E38, 0x083F0E],
            dispatcher["roots"],
        )
        closure = payload["target_closure"]
        self.assertEqual(555, closure["instruction_count"])
        self.assertEqual(126, closure["basic_block_count"])
        self.assertEqual(1110, closure["code_bytes"])
        self.assertEqual(24, closure["literal_bytes"])
        self.assertEqual(25, closure["opaque_baseline_exit_count"])
        self.assertEqual(0, closure["frontier_count"])
        self.assertEqual([[0x083F52, 0x083F54], [0x083FBE, 0x083FC0]],
                         closure["preserved_unknown_holes"])

    def test_exact_promotion_and_narrow_scope(self) -> None:
        promotion = self.payload["promotion"]
        self.assertEqual(1162, promotion["promotion_bytes"])
        self.assertEqual(14, promotion["claim_count"])
        self.assertEqual(28, promotion["dispatcher_table_bytes"])
        self.assertEqual(1110, promotion["target_code_bytes"])
        self.assertEqual(24, promotion["target_literal_bytes"])
        for key in ("natural_runtime_reachability", "distance_metric_semantics",
                    "opaque_baseline_target_semantics", "padding_or_free_space",
                    "editing_or_relocation_safety"):
            self.assertFalse(self.payload["scope"][key])

    def test_roundtrip_and_independent_verifier(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            output = Path(directory) / "candidate"
            self.exporter.export_artifact(ROOT, output)
            report = self.verifier.verify_artifact(ROOT, output)
            self.assertTrue(report["verified"], report)
            self.assertEqual(1162, report["promotion_bytes"])
            self.assertEqual(0, report["frontier_count"])

    def test_verifier_does_not_import_exporter(self) -> None:
        source = (ROOT / "tools/verify_rom_battle_distance_dispatcher_cfg.py").read_text()
        imports = [ast.unparse(node) for node in ast.walk(ast.parse(source))
                   if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("export_rom_battle_distance_dispatcher_cfg" in row
                             for row in imports))
        rebuilt = self.verifier._rebuild((ROOT / "rom/base.gba").read_bytes())
        self.assertEqual(555, rebuilt["target_closure"]["instruction_count"])

    def test_dispatcher_closure_exit_and_hole_mutations_fail_closed(self) -> None:
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        for offset, pattern in ((0x083B3C, "dispatcher"),
                                (0x083B58, "dispatcher"),
                                (0x083B5C, "table"),
                                (0x083B78, "closure"),
                                (0x083DFC, "literal"),
                                (0x083F52, "hole"),
                                (0x083FE8, "exit")):
            with self.subTest(offset=hex(offset)):
                changed = bytearray(rom)
                changed[offset] ^= 1
                with self.assertRaisesRegex(ValueError, pattern):
                    self.exporter._build_from_rom(ROOT, bytes(changed),
                                                  verify_identity=False)
                with self.assertRaisesRegex(ValueError, pattern):
                    self.verifier._rebuild(bytes(changed), verify_identity=False)

    def test_artifact_contract_and_existing_output_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            base = Path(directory)
            original = base / "original"
            self.exporter.export_artifact(ROOT, original)
            with self.assertRaises(FileExistsError):
                self.exporter.export_artifact(ROOT, original)

            for name, mutate in (
                ("payload", self._mutate_payload),
                ("status", lambda path: self._mutate_manifest(
                    path, "artifact_status", "rejected")),
                ("implementation", lambda path: self._mutate_manifest(
                    path, "implementation", {})),
                ("extra", lambda path: (path / "extra.txt").write_text("unexpected")),
            ):
                with self.subTest(name=name):
                    candidate = base / name
                    shutil.copytree(original, candidate)
                    mutate(candidate)
                    self.assertFalse(
                        self.verifier.verify_artifact(ROOT, candidate)["verified"]
                    )

    def test_symlink_and_exclusive_publish_guards(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            base = Path(directory)
            output = base / "candidate"
            self.exporter.export_artifact(ROOT, output)
            alias = base / "alias"
            alias.symlink_to(base, target_is_directory=True)
            self.assertFalse(
                self.verifier.verify_artifact(ROOT, alias / "candidate")["verified"]
            )

            source = base / "source"
            destination = base / "destination"
            source.mkdir()
            destination.mkdir()
            (source / "new").write_text("new")
            (destination / "keep").write_text("keep")
            with self.assertRaises(FileExistsError):
                self.exporter._publish_exclusive(source, destination)
            self.assertEqual("keep", (destination / "keep").read_text())

    @staticmethod
    def _mutate_manifest(path: Path, key: str, value: object) -> None:
        manifest_path = path / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest[key] = value
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False,
                                            indent=2, sort_keys=True) + "\n")

    def _mutate_payload(self, path: Path) -> None:
        payload_path = path / self.exporter.PAYLOAD_NAME
        payload = json.loads(payload_path.read_text())
        payload["promotion"]["promotion_bytes"] += 1
        raw = (json.dumps(payload, ensure_ascii=False, indent=2,
                          sort_keys=True) + "\n").encode()
        payload_path.write_bytes(raw)
        manifest_path = path / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][self.exporter.PAYLOAD_NAME] = {
            "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False,
                                            indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    unittest.main()
