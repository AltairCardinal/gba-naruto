from __future__ import annotations

import json
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import ocr_report, ocr_screenshot


class OcrScreenshotTests(unittest.TestCase):
    def test_preflight_rejects_missing_tesseract_executable(self):
        with self.assertRaisesRegex(ocr_screenshot.OcrUnavailable, "executable"):
            ocr_screenshot.preflight_tesseract(
                "definitely-not-a-real-tesseract-binary",
                required_languages=("chi_sim", "jpn", "eng"),
            )

    def test_preflight_rejects_missing_required_language_packs(self):
        completed = mock.Mock(returncode=0, stdout="List of available languages (2):\neng\nosd\n", stderr="")
        with mock.patch("tools.ocr_screenshot.shutil.which", return_value="/usr/bin/tesseract"), mock.patch(
            "tools.ocr_screenshot.subprocess.run", return_value=completed
        ):
            with self.assertRaisesRegex(ocr_screenshot.OcrUnavailable, "chi_sim, jpn"):
                ocr_screenshot.preflight_tesseract(
                    "tesseract", required_languages=("chi_sim", "jpn", "eng")
                )

    def test_tesseract_tsv_is_grouped_into_existing_json_line_schema(self):
        tsv = "\n".join(
            [
                "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext",
                "5\t1\t1\t1\t1\t1\t10\t20\t30\t10\t90\t木叶",
                "5\t1\t1\t1\t1\t2\t42\t20\t20\t10\t80\t战记",
                "5\t1\t1\t1\t2\t1\t15\t50\t40\t20\t70\t开始",
                "5\t1\t1\t1\t2\t2\t60\t50\t10\t20\t-1\t",
            ]
        )
        result = ocr_screenshot.parse_tesseract_tsv(
            tsv, image="screen.png", image_width=100, image_height=100
        )
        self.assertEqual(result["image"], "screen.png")
        self.assertEqual(result["lineCount"], 2)
        self.assertEqual([line["text"] for line in result["lines"]], ["木叶 战记", "开始"])
        self.assertAlmostEqual(result["lines"][0]["confidence"], 0.85)
        self.assertEqual(result["lines"][0]["boundingBox"], [0.1, 0.7, 0.52, 0.1])

    def test_macos_vision_backend_preserves_existing_json_schema(self):
        expected = {
            "image": "screen.png",
            "lineCount": 1,
            "lines": [{"text": "木叶", "confidence": 0.9, "boundingBox": [0.1, 0.2, 0.3, 0.4]}],
        }
        completed = mock.Mock(returncode=0, stdout=json.dumps(expected), stderr="")
        with mock.patch("tools.ocr_screenshot.subprocess.run", return_value=completed):
            actual = ocr_screenshot.run_vision(Path("screen.png"), Path("tools/bin/ocr_screenshot"))
        self.assertEqual(actual, expected)

    def test_linux_cli_fails_explicitly_when_tesseract_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "screen.png"
            image.write_bytes(b"not needed because preflight must fail first")
            with mock.patch.dict(os.environ, {"PATH": ""}, clear=False):
                exit_code = ocr_screenshot.main(
                    [str(image), "--backend", "tesseract", "--tesseract-bin", "missing-tesseract"]
                )
        self.assertEqual(exit_code, 1)

    def test_ocr_report_launches_python_adapter_through_current_interpreter(self):
        command = ocr_report.ocr_command(
            Path("tools/ocr_screenshot.py"), Path("screen.png")
        )
        self.assertEqual(command[0], os.sys.executable)
        self.assertEqual(command[1:], ["tools/ocr_screenshot.py", "screen.png"])

    def test_tesseract_cli_writes_schema_compatible_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = root / "tesseract"
            fake.write_text(
                """#!/usr/bin/env python3
import sys
if '--list-langs' in sys.argv:
    print('List of available languages (3):')
    print('chi_sim')
    print('jpn')
    print('eng')
else:
    print('level\\tpage_num\\tblock_num\\tpar_num\\tline_num\\tword_num\\tleft\\ttop\\twidth\\theight\\tconf\\ttext')
    print('5\\t1\\t1\\t1\\t1\\t1\\t8\\t10\\t32\\t12\\t95\\t木叶')
""",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            image = root / "screen.png"
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 100, 80)
            )
            output = root / "ocr.json"
            exit_code = ocr_screenshot.main(
                [
                    str(image),
                    "--backend",
                    "tesseract",
                    "--tesseract-bin",
                    str(fake),
                    "--output",
                    str(output),
                ]
            )
            result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["lineCount"], 1)
        self.assertEqual(result["lines"][0]["text"], "木叶")


if __name__ == "__main__":
    unittest.main()
