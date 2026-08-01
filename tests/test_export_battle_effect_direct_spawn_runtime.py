import importlib
import io
import tarfile
import tempfile
import unittest
from pathlib import Path


class BattleEffectDirectSpawnRuntimeExporterTests(unittest.TestCase):
    def _write_run_archive(self, path: Path, members: dict[str, bytes]) -> None:
        with tarfile.open(path, "w:gz") as archive:
            for name, payload in members.items():
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                info.mode = 0o644
                archive.addfile(info, io.BytesIO(payload))

    def test_reads_only_regular_members_below_the_expected_run_root(self):
        exporter = importlib.import_module(
            "tools.export_battle_effect_direct_spawn_runtime"
        )
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "run.tar.gz"
            self._write_run_archive(
                archive,
                {
                    "run-01/output/case/profile.json": b"profile",
                    "run-01/output/case/output/audit.json": b"audit",
                },
            )

            payloads = exporter.read_run_archive(archive, run_id="run-01")

            self.assertEqual(
                payloads,
                {
                    "output/case/profile.json": b"profile",
                    "output/case/output/audit.json": b"audit",
                },
            )

    def test_promotes_only_savestate_phase_evidence_not_redundant_memory_dumps(self):
        exporter = importlib.import_module(
            "tools.export_battle_effect_direct_spawn_runtime"
        )

        expected = exporter.expected_source_members()

        self.assertEqual(len(exporter.CASE_ROWS), 4)
        self.assertEqual(len(expected), 51)
        self.assertTrue(all("capture-task-pool.bin" not in name for name in expected))
        self.assertTrue(all("capture-vram.bin" not in name for name in expected))
        self.assertTrue(any(name.endswith("capture.ss9") for name in expected))
        self.assertIn("source/narrow-window-negative/output/timeout.ss9", expected)
        self.assertIn("source/narrow-window-negative/run-inventory.json", expected)
        self.assertIn("source/narrow-window-negative/run-metadata.json", expected)


if __name__ == "__main__":
    unittest.main()
