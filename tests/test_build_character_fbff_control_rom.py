from pathlib import Path
import subprocess
import sys
import unittest

from tools.build_character_fbff_control_rom import (
    BASE_ROM_SHA256,
    PATCH_OFFSET,
    build_control_rom,
    build_probe_state,
)
from tools.inspect_mgba_savestate import load_gba_state


ROOT = Path(__file__).resolve().parents[1]


class CharacterFbffControlRomTests(unittest.TestCase):
    def test_direct_cli_entrypoint_loads(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "build_character_fbff_control_rom.py"),
                "--help",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("--source-state", completed.stdout)

    def test_changes_only_the_fbff_high_byte(self):
        base = (ROOT / "rom" / "base.gba").read_bytes()

        control, report = build_control_rom(base)

        self.assertEqual(
            "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
            BASE_ROM_SHA256,
        )
        self.assertEqual(0x25A8E5, PATCH_OFFSET)
        self.assertEqual(b"\xFF\xFB\x00\x00", base[PATCH_OFFSET - 1 : PATCH_OFFSET + 3])
        self.assertEqual(
            b"\xFF\xFF\x00\x00",
            control[PATCH_OFFSET - 1 : PATCH_OFFSET + 3],
        )
        self.assertEqual(
            [PATCH_OFFSET],
            [
                index
                for index, (before, after) in enumerate(zip(base, control))
                if before != after
            ],
        )
        self.assertEqual("0x0025A8E5", report["patch"]["file_offset"])
        self.assertEqual("0x0825A8E5", report["patch"]["gba_address"])
        self.assertEqual("0xFB", report["patch"]["before"])
        self.assertEqual("0xFF", report["patch"]["after"])
        self.assertEqual(BASE_ROM_SHA256, report["base_rom_sha256"])

    def test_rejects_an_unrecognized_rom(self):
        base = bytearray((ROOT / "rom" / "base.gba").read_bytes())
        base[0] ^= 1

        with self.assertRaisesRegex(ValueError, "base ROM SHA-256"):
            build_control_rom(bytes(base))

    def test_builds_the_exact_prepatched_sprite_task_state(self):
        source = (
            ROOT
            / "artifacts"
            / "battle-effect-affine-runtime-v1"
            / "raw"
            / "state-0154.ss9"
        )

        patched, report = build_probe_state(source.read_bytes())
        temporary = self.enterContext(__import__("tempfile").TemporaryDirectory())
        target = Path(temporary) / "input.ss9"
        target.write_bytes(patched)
        task = load_gba_state(target).read_memory(0x03005940, 0x3C)

        self.assertEqual("013600c0", task[0:4].hex())
        self.assertEqual("78005000", task[4:8].hex())
        self.assertEqual("00010001", task[0x0C:0x10].hex())
        self.assertEqual("00030e00", task[0x10:0x14].hex())
        self.assertEqual("0000020000000000", task[0x14:0x1C].hex())
        self.assertEqual("18a92508", task[0x1C:0x20].hex())
        self.assertEqual("48a92508", task[0x20:0x24].hex())
        self.assertEqual("a08c2508", task[0x24:0x28].hex())
        self.assertEqual("00000000", task[0x28:0x2C].hex())
        self.assertEqual("0x03005940", report["probe_state"]["task_address"])
        self.assertEqual(1, report["probe_state"]["write_count"])


if __name__ == "__main__":
    unittest.main()
