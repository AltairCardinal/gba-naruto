import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/butano/export_scenario_41_extended_reference.py"


def load_exporter():
    spec = importlib.util.spec_from_file_location("scenario_41_extended_reference", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class Scenario41ExtendedReferenceTest(unittest.TestCase):
    def test_direct_cli_entrypoint_loads(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            cwd=ROOT.parent,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_exports_results_growth_and_all_postbattle_dialogue_pages(self):
        self.assertTrue(SCRIPT.is_file(), "extended reference exporter is missing")
        exporter = load_exporter()
        self.assertEqual(
            tuple(exporter.EXTENDED_CHECKPOINTS),
            (
                "result",
                "level-up-1",
                "level-up-2",
                *(f"postbattle-dialogue-{index}" for index in range(1, 12)),
            ),
        )
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "reference"
            manifest = exporter.export_extended_reference(ROOT / "rom/base.gba", output)
            self.assertEqual(len(manifest["boundaries"]), 14)
            self.assertTrue((output / "result/vram.bin").is_file())
            self.assertTrue((output / "postbattle-dialogue-11/oam.bin").is_file())


if __name__ == "__main__":
    unittest.main()
