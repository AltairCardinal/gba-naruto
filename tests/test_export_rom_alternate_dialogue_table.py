from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "tools/export_rom_alternate_dialogue_table.py"
VERIFIER = ROOT / "tools/verify_rom_alternate_dialogue_table.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AlternateDialogueTableTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        (self.root / "rom").mkdir(parents=True)
        (self.root / "tools").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "sequel").mkdir()
        shutil.copy2(ROOT / "rom/base.gba", self.root / "rom/base.gba")
        shutil.copy2(ROOT / "sequel/rom-byte-coverage.json", self.root / "sequel/rom-byte-coverage.json")
        shutil.copy2(EXPORTER, self.root / "tools/export_rom_alternate_dialogue_table.py")
        shutil.copy2(VERIFIER, self.root / "tools/verify_rom_alternate_dialogue_table.py")
        shutil.copy2(Path(__file__), self.root / "tests/test_export_rom_alternate_dialogue_table.py")

    def tearDown(self):
        self.tmp.cleanup()

    def _export(self, output: Path | None = None, ok: bool = True):
        output = output or self.root / "artifacts/rom-alternate-dialogue-table-v1"
        result = subprocess.run(
            ["python3", str(self.root / "tools/export_rom_alternate_dialogue_table.py"), "--root", str(self.root), "--output-dir", str(output)],
            text=True, capture_output=True,
        )
        self.assertEqual(0 if ok else 1, result.returncode, result.stderr)
        return output, result

    def _verify(self, artifact: Path, ok: bool = True):
        result = subprocess.run(
            ["python3", str(self.root / "tools/verify_rom_alternate_dialogue_table.py"), "--root", str(self.root), "--artifact-dir", str(artifact)],
            text=True, capture_output=True,
        )
        self.assertEqual(0 if ok else 1, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def test_exports_exact_denominators_and_independent_verifier_accepts(self):
        artifact, _ = self._export()
        payload = json.loads((artifact / "alternate-dialogue-table.json").read_text())
        self.assertEqual({"manifest.json", "alternate-dialogue-table.json", "alternate-dialogue-text.bin"}, {p.name for p in artifact.iterdir()})
        self.assertEqual(20, payload["summary"]["row_count"])
        self.assertEqual(80, payload["summary"]["target_count"])
        self.assertEqual(80, payload["summary"]["gap_count"])
        self.assertEqual(400, payload["summary"]["table_bytes"])
        self.assertEqual(1214, payload["summary"]["text_bytes"])
        self.assertEqual(1586, payload["summary"]["gap_bytes"])
        self.assertEqual(3200, payload["summary"]["promoted_bytes"])
        self.assertEqual(3200, payload["promotion"]["promotion_bytes"])
        self.assertEqual(161, len(payload["promotion"]["claims"]))
        self.assertFalse(
            payload["historical_coverage_reference"]["observed_during_this_build"]
        )
        self.assertEqual(
            "deferred_to_coverage_auditor",
            payload["upstream_owner_gate"]["status"],
        )
        for claim in payload["promotion"]["claims"]:
            self.assertRegex(claim["bytes_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(claim["claim_kind"])
        self.assertTrue(self._verify(artifact)["verified"])

    def test_rom_identity_rejects_unrelated_mutation(self):
        rom = self.root / "rom/base.gba"
        raw = bytearray(rom.read_bytes()); raw[0x200000] ^= 1; rom.write_bytes(raw)
        self._export(ok=False)

    def test_consumer_table_pointer_target_and_gap_mutations_fail(self):
        mutations = [0x091E52, 0x0918EC, 0x459284, 0x459288, 0x458794, 0x4587AD]
        original = (self.root / "rom/base.gba").read_bytes()
        for offset in mutations:
            with self.subTest(offset=hex(offset)):
                raw = bytearray(original); raw[offset] ^= 1
                (self.root / "rom/base.gba").write_bytes(raw)
                self._export(output=self.root / f"artifacts/candidate-{offset:x}", ok=False)
        (self.root / "rom/base.gba").write_bytes(original)

    def test_publication_is_exclusive_and_does_not_clobber(self):
        output = self.root / "artifacts/existing"; output.mkdir(parents=True)
        marker = output / "mine"; marker.write_text("keep")
        self._export(output=output, ok=False)
        self.assertEqual("keep", marker.read_text())

    def test_output_symlink_and_path_escape_fail(self):
        outside = Path(self.tmp.name) / "outside"; outside.mkdir()
        link = self.root / "artifacts/link"; link.parent.mkdir(); link.symlink_to(outside, target_is_directory=True)
        self._export(output=link, ok=False)
        self._export(output=outside / "escaped", ok=False)

    def test_verifier_rejects_each_semantic_mutation(self):
        artifact, _ = self._export()
        payload_path = artifact / "alternate-dialogue-table.json"
        payload = json.loads(payload_path.read_text())
        for path in (("consumer", "index_upper_bound"), ("promotion", "claims")):
            with self.subTest(path=path):
                changed = json.loads(json.dumps(payload))
                if path[1] == "claims": changed[path[0]][path[1]] = changed[path[0]][path[1]][:-1]
                else: changed[path[0]][path[1]] = 18
                payload_path.write_text(json.dumps(changed))
                self.assertFalse(self._verify(artifact, ok=False)["verified"])
                payload_path.write_text(json.dumps(payload))

    def test_verifier_rejects_nested_artifact_members(self):
        artifact, _ = self._export()
        (artifact / "unexpected").mkdir()
        self.assertFalse(self._verify(artifact, ok=False)["verified"])


if __name__ == "__main__":
    unittest.main()
