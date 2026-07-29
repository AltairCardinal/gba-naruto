import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def directory_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class ExportBgSceneSelectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_bg_scene_selection import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.manifest = export_artifact(ROOT, cls.output)
        cls.battles = json.loads(
            (cls.output / "battle-headers.json").read_text(encoding="utf-8")
        )
        cls.chapter = json.loads(
            (cls.output / "chapter-opcode-1e.json").read_text(encoding="utf-8")
        )
        cls.callers = json.loads(
            (cls.output / "loader-callers.json").read_text(encoding="utf-8")
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_binds_rom_upstream_canvases_and_selection_code(self):
        manifest = self.manifest
        self.assertEqual("bg-scene-selection-v1", manifest["schema"])
        self.assertEqual(
            "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
            manifest["rom"]["sha256"],
        )
        self.assertEqual(
            "27096c9129823cc7d4f98aeb1fde304419a1c6abfadaf1cff6e13b80bf2fa99e",
            manifest["upstream"]["manifest_sha256"],
        )
        self.assertEqual(
            "977b4393a2c5d37124d09e772de42f11d2d9abff9ec832d1160aeeb194a6566c",
            manifest["evidence"]["battle_headers"]["sha256"],
        )
        self.assertEqual(
            "f6c872afd0b653ae2e0e04407bdbc059719eb823801d165e22a1d7e5c98aa099",
            manifest["evidence"]["chapter_pointer_tables"]["primary_sha256"],
        )
        self.assertEqual(
            "767308a8e78947f7795c61965155d27925265327466c9df9d5d547b2f0368b5c",
            manifest["evidence"]["chapter_pointer_tables"]["alternate_sha256"],
        )
        self.assertEqual(
            "bffbff149e2ecf3deb9309a48123cffe724652121f6d4699720dc23b1d8f25dc",
            manifest["evidence"]["opcode_1e_handler"]["sha256"],
        )
        self.assertEqual(
            "5a5e08c007d48247ab0f8cce8c1e6c9b86c0a43c4fd8fd19d364790ac0dc71dd",
            manifest["evidence"]["selection_wrapper"]["sha256"],
        )
        self.assertEqual(12, len(manifest["canvases"]))
        self.assertEqual(
            list(range(1, 8)) + list(range(9, 14)),
            [entry["entry_id"] for entry in manifest["canvases"]],
        )
        for entry in manifest["canvases"]:
            canvas = ROOT / manifest["upstream"]["directory"] / entry["canvas"]
            self.assertEqual(
                entry["canvas_sha256"],
                hashlib.sha256(canvas.read_bytes()).hexdigest(),
            )

    def test_catalogs_all_47_battle_header_selections(self):
        self.assertEqual("bg-battle-header-selections-v1", self.battles["schema"])
        rows = self.battles["entries"]
        self.assertEqual(47, len(rows))
        self.assertEqual(list(range(47)), [row["battle_id"] for row in rows])
        self.assertEqual(
            {1: 23, 2: 3, 3: 5, 4: 4, 5: 1, 6: 1, 7: 10},
            dict(sorted(Counter(row["entry_id"] for row in rows).items())),
        )
        for row in rows:
            self.assertEqual(
                0x0853D910 + row["battle_id"] * 0x20 + 0x1C,
                int(row["selector_address"], 16),
            )
            self.assertEqual(
                f"entry-{row['entry_id']:02d}/canvas.png",
                row["canvas"],
            )

    def test_traverses_every_chapter_root_and_finds_all_opcode_1e(self):
        self.assertEqual("bg-chapter-opcode-1e-selections-v1", self.chapter["schema"])
        self.assertEqual(110, self.chapter["summary"]["non_null_script_slots"])
        self.assertEqual(98, self.chapter["summary"]["unique_script_roots"])
        self.assertEqual(14199, self.chapter["summary"]["unique_instruction_nodes"])
        self.assertEqual(42, self.chapter["summary"]["dynamic_opcode_06_nodes"])
        self.assertEqual(6, self.chapter["summary"]["unique_opcode_1e_records"])
        self.assertEqual([], self.chapter["summary"]["parse_failures"])
        expected = [
            ("0x0804435F", "1e00", 0, 1, [["primary", 51]]),
            ("0x080446F0", "1e33", 51, 10, [["primary", 51]]),
            ("0x080459F4", "1e07", 7, 2, [["primary", 51]]),
            ("0x08046118", "1e07", 7, 2, [["primary", 51]]),
            ("0x08047F40", "1e1e", 30, 7, [["primary", 53]]),
            (
                "0x08048087",
                "1e35",
                53,
                12,
                [["alternate", 53], ["primary", 53]],
            ),
        ]
        actual = [
            (
                row["address"],
                row["raw_hex"],
                row["input_id"],
                row["entry_id"],
                [[root["table"], root["scenario_id"]] for root in row["roots"]],
            )
            for row in self.chapter["selections"]
        ]
        self.assertEqual(expected, actual)
        self.assertTrue(all(row["input_domain_valid"] for row in self.chapter["selections"]))

    def test_catalogs_all_direct_loader_and_wrapper_callers(self):
        self.assertEqual("bg-loader-callers-v1", self.callers["schema"])
        self.assertEqual(
            [
                "0x0807AAA6",
                "0x0808F522",
                "0x08091716",
                "0x080930D6",
            ],
            [row["callsite"] for row in self.callers["direct_loader_calls"]],
        )
        self.assertEqual(
            [
                "0x0808A596",
                "0x0808A648",
                "0x0808F588",
                "0x08097038",
                "0x08097CEC",
            ],
            [row["callsite"] for row in self.callers["selection_wrapper_calls"]],
        )
        self.assertEqual(
            list(range(1, 8)) + list(range(9, 14)),
            self.callers["valid_entry_ids"],
        )
        self.assertEqual([11, 13], self.callers["valid_but_not_static_observed_entry_ids"])
        self.assertFalse(self.callers["loader_bounds_check"])
        self.assertEqual([[0, 46], [50, 54]], self.callers["safe_input_ranges"])
        self.assertEqual([47, 48, 49], self.callers["unsafe_input_ids"])
        self.assertEqual(
            {"47": 96, "48": 36, "49": 214},
            self.callers["unsafe_entry_ids"],
        )

    def test_scope_closes_selection_without_overclaiming_scene_names(self):
        self.assertEqual(
            {
                "battle_header_selection_complete": True,
                "chapter_opcode_1e_selection_complete": True,
                "direct_loader_callers_complete": True,
                "selection_wrapper_callers_complete": True,
                "runtime_entry_selection_mechanisms_complete": True,
                "unsafe_wrapper_input_gap_documented": True,
                "natural_language_scene_names_complete": False,
                "scrolling_and_layer_composition_complete": False,
            },
            self.manifest["scope"],
        )
        self.assertEqual(10, self.manifest["summary"]["statically_observed_entry_count"])
        self.assertEqual([11, 13], self.manifest["summary"]["valid_but_unobserved_entry_ids"])

    def test_independent_verifier_accepts_export_and_rejects_tamper(self):
        from tools.verify_bg_scene_selection import verify_artifact

        source = (
            ROOT / "tools" / "verify_bg_scene_selection.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)

        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual([], report["errors"])
        self.assertEqual(47, report["battle_headers"])
        self.assertEqual(6, report["chapter_opcode_1e_records"])

        for relative in (
            "manifest.json",
            "battle-headers.json",
            "chapter-opcode-1e.json",
            "loader-callers.json",
        ):
            with tempfile.TemporaryDirectory() as temporary:
                tampered = Path(temporary) / "artifact"
                shutil.copytree(self.output, tampered)
                path = tampered / relative
                raw = bytearray(path.read_bytes())
                raw[-2] ^= 1
                path.write_bytes(raw)
                report = verify_artifact(ROOT, tampered)
                self.assertFalse(report["verified"], relative)
                self.assertTrue(report["errors"], relative)

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            (tampered / "unexpected.bin").write_bytes(b"unexpected")
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

    def test_export_is_deterministic_and_cli_is_repository_relative(self):
        from tools.export_bg_scene_selection import export_artifact

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            second = export_artifact(ROOT, output)
            self.assertEqual(self.manifest, second)
            self.assertEqual(directory_hashes(self.output), directory_hashes(output))

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/export_bg_scene_selection.py",
                    "--root",
                    ".",
                    "--output-dir",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn('"chapter_opcode_1e_records": 6', result.stdout)
            self.assertTrue((output / "manifest.json").is_file())

    def test_output_target_rejects_repository_and_unrelated_data(self):
        from tools.export_bg_scene_selection import (
            export_artifact,
            validate_output_target,
        )

        with self.assertRaises(ValueError):
            validate_output_target(ROOT, ROOT)
        with self.assertRaises(ValueError):
            validate_output_target(ROOT, ROOT.parent)

        with tempfile.TemporaryDirectory() as temporary:
            unrelated = Path(temporary) / "unrelated"
            unrelated.mkdir()
            sentinel = unrelated / "keep.txt"
            sentinel.write_text("user data", encoding="utf-8")
            with self.assertRaises(ValueError):
                export_artifact(ROOT, unrelated)
            self.assertEqual("user data", sentinel.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
