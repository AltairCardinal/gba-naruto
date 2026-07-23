import tempfile
import unittest
import subprocess
import sys
from pathlib import Path

from tools.butano.export_scenario_41_attack_gpu_bases import export_gpu_bases
from tools.inspect_mgba_savestate import png_screen_fingerprint


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "build" / "scenario-41-attack-trace-20260722-04"


class Scenario41AttackGpuBasesTest(unittest.TestCase):
    def test_cli_loads_from_direct_script_path(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "butano" / "export_scenario_41_attack_gpu_bases.py"),
                "--help",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_exports_two_unfaded_gpu_bases(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "gpu-bases"
            manifest = export_gpu_bases(SOURCE, output)
            self.assertEqual(manifest["source_frames"], [56, 63])
            self.assertEqual(
                manifest["frames"]["56"]["rgb_sha256"],
                "aa65f3a032c364d7dbb93aacdad175657093eab3177b7ebf853305f3dea43417",
            )
            self.assertEqual(
                manifest["frames"]["63"]["rgb_sha256"],
                "a011d354d30a00b473ff1a400a44576188a021eacd907466aedc3bd28380fe23",
            )
            for frame in (56, 63):
                frame_dir = output / f"frame-{frame:04d}"
                self.assertEqual(
                    png_screen_fingerprint(frame_dir / "unfaded.png")["rgb_pixels_sha256"],
                    manifest["frames"][str(frame)]["rgb_sha256"],
                )
                self.assertEqual((frame_dir / "io.bin").stat().st_size, 0x400)
                self.assertEqual((frame_dir / "pram.bin").stat().st_size, 0x400)
                self.assertEqual((frame_dir / "oam.bin").stat().st_size, 0x400)
                self.assertEqual((frame_dir / "vram.bin").stat().st_size, 0x18000)


if __name__ == "__main__":
    unittest.main()
