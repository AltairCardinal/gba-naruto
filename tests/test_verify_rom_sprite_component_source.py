#!/usr/bin/env python3
"""Independent-verifier TDD tests for the sprite component source packet."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-sprite-component-source-v1"
PAYLOAD_NAME = "rom-sprite-component-source.json"
BUNDLE_NAME = "rom-sprite-component-source.bin"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


class VerifyRomSpriteComponentSourceTests(unittest.TestCase):
    def test_minimal_independent_rebuild_api(self) -> None:
        from tools import verify_rom_sprite_component_source as verifier

        payload, packed = verifier.rebuild_payload(ROOT)
        self.assertEqual("rom-sprite-component-source-v1", payload["schema"])
        self.assertEqual([0x12C904, 0x12D134], payload["source"]["range"])
        self.assertEqual(2096, len(packed))

    def test_committed_artifact_is_independently_verified(self) -> None:
        from tools import export_rom_sprite_component_source as exporter
        from tools import verify_rom_sprite_component_source as verifier

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary).resolve() / SCHEMA
            exporter.export_artifact(ROOT, artifact)
            result = verifier.verify_artifact(ROOT, artifact)
            self.assertTrue(result["verified"], result["errors"])
            self.assertEqual(2096, result["source_bytes"])
            self.assertEqual(147160, result["unknown_bytes"])
            self.assertEqual(6291456, result["classified_plus_unknown"])

    def test_payload_and_bundle_mutations_fail_even_when_manifest_is_resigned(self) -> None:
        from tools import export_rom_sprite_component_source as exporter
        from tools import verify_rom_sprite_component_source as verifier

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            original = base / "original"
            exporter.export_artifact(ROOT, original)
            for filename in (PAYLOAD_NAME, BUNDLE_NAME):
                tampered = base / filename.replace(".", "-")
                shutil.copytree(original, tampered)
                path = tampered / filename
                changed = bytearray(path.read_bytes())
                changed[0] ^= 1
                path.write_bytes(changed)
                manifest_path = tampered / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["files"][filename] = _sha(bytes(changed))
                manifest_path.write_bytes(_canonical(manifest))
                result = verifier.verify_artifact(ROOT, tampered)
                self.assertFalse(result["verified"], result)

    def test_verifier_has_no_exporter_import_and_reads_no_preflight(self) -> None:
        source = (ROOT / "tools/verify_rom_sprite_component_source.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = "\n".join(ast.unparse(node) for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)))
        self.assertNotIn("export_rom_sprite_component_source", imports)
        self.assertNotIn("sprite-component-source-preflight", source)

    def test_verifier_cli_exit_status_is_fail_closed(self) -> None:
        from tools import export_rom_sprite_component_source as exporter

        verifier = ROOT / "tools/verify_rom_sprite_component_source.py"
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary).resolve() / SCHEMA
            exporter.export_artifact(ROOT, artifact)
            manifest = artifact / "manifest.json"
            value = json.loads(manifest.read_text(encoding="utf-8"))
            value["unexpected"] = True
            manifest.write_bytes(_canonical(value))
            result = subprocess.run(
                [sys.executable, "-I", "-S", str(verifier), "--root", str(ROOT), "--artifact-dir", str(artifact)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertFalse(json.loads(result.stdout)["verified"])


if __name__ == "__main__":
    unittest.main()
