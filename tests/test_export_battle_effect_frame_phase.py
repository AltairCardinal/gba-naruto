from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path


class BattleEffectFramePhaseExporterTests(unittest.TestCase):
    def test_description_names_the_actual_effect_group(self):
        exporter = importlib.import_module("tools.export_battle_effect_frame_phase")
        self.assertIn(
            "group 1",
            exporter.artifact_description(1, "zero-input-active-state"),
        )
        self.assertNotIn(
            "group 11",
            exporter.artifact_description(1, "zero-input-active-state"),
        )

    def test_description_does_not_call_an_explicit_sequence_zero_input(self):
        exporter = importlib.import_module("tools.export_battle_effect_frame_phase")
        description = exporter.artifact_description(18, "explicit-input-sequence")
        self.assertIn("explicit-input-sequence", description)
        self.assertNotIn("zero-input", description)

    def test_collects_only_complete_three_phase_capture_files(self):
        exporter = importlib.import_module("tools.export_battle_effect_frame_phase")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for phase in exporter.PHASES:
                directory = root / phase
                directory.mkdir()
                for suffix in exporter.CAPTURE_SUFFIXES:
                    (directory / f"capture{suffix}").write_bytes(suffix.encode())
            (root / "startup-state.json").write_text("{}", encoding="utf-8")
            collected = exporter.collect_phase_files(root)
            self.assertEqual(
                len(collected), len(exporter.PHASES) * len(exporter.CAPTURE_SUFFIXES)
            )
            self.assertNotIn("startup-state.json", collected)
            self.assertEqual(
                collected["renderer-post/capture-submission.bin"],
                root / "renderer-post/capture-submission.bin",
            )

    def test_runtime_records_are_rewritten_without_absolute_paths(self):
        exporter = importlib.import_module("tools.export_battle_effect_frame_phase")
        root = Path("/repo")
        portable = exporter.portable_runtime_record(
            {
                "profile": "/repo/sequel/profile.json",
                "cwd": "/repo",
                "command": [
                    "/Applications/mGBA.app/Contents/MacOS/mGBA",
                    "/repo/tools/capture.lua",
                ],
                "nested": {"already_relative": "artifacts/input.ss9"},
            },
            root,
        )
        self.assertEqual(portable["profile"], "sequel/profile.json")
        self.assertEqual(portable["cwd"], ".")
        self.assertEqual(portable["command"], ["mGBA", "tools/capture.lua"])
        self.assertEqual(
            portable["nested"]["already_relative"], "artifacts/input.ss9"
        )

        def strings(value):
            if isinstance(value, dict):
                for nested in value.values():
                    yield from strings(nested)
            elif isinstance(value, list):
                for nested in value:
                    yield from strings(nested)
            elif isinstance(value, str):
                yield value

        self.assertFalse(any(Path(value).is_absolute() for value in strings(portable)))

    def test_runtime_record_rejects_unknown_external_absolute_path(self):
        exporter = importlib.import_module("tools.export_battle_effect_frame_phase")
        with self.assertRaisesRegex(ValueError, "external absolute path"):
            exporter.portable_runtime_record(
                {"unexpected": "/outside/private/other-tool"}, Path("/repo")
            )


if __name__ == "__main__":
    unittest.main()
