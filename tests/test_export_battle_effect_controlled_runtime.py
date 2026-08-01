from __future__ import annotations

import importlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

class ControlledBattleEffectRuntimeExporterTests(unittest.TestCase):
    def test_candidate_output_is_limited_to_active_experiment_final_directory(self):
        exporter = importlib.import_module(
            "tools.export_battle_effect_controlled_runtime"
        )
        accepted = (
            exporter.ROOT
            / "build/experiments/active/battle-effect-controlled-runtime/run-1/final"
        )
        rejected = exporter.ROOT / "build/experiments/active/unmanaged-final"

        self.assertTrue(exporter.is_allowed_artifact_output(accepted))
        self.assertFalse(exporter.is_allowed_artifact_output(rejected))

    def test_collects_complete_batch_provenance_and_declared_outputs(self):
        exporter = importlib.import_module(
            "tools.export_battle_effect_controlled_runtime"
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / "batch-audit.json").write_text("{}", encoding="utf-8")
            declared = {}
            for case_id in exporter.EXPECTED_CASE_IDS:
                case = source / case_id
                output = case / "output"
                for relative in (
                    "profile.json",
                    "guard-summary.json",
                    "guard-summary.json.done.json",
                ):
                    path = case / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(relative, encoding="utf-8")
                files = {}
                for phase in exporter.PHASE_NAMES:
                    for name in exporter.CAPTURE_OUTPUT_NAMES:
                        relative = f"{phase}/{name}"
                        path = output / relative
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(relative.encode())
                        files[relative] = "unused-by-collector"
                audit = output / "audit.json"
                audit.write_text(json.dumps({"files": files}), encoding="utf-8")
                declared[case_id] = files

            members = exporter.collect_batch_members(source)

            self.assertEqual(len(members), 729)
            self.assertEqual(
                set(members),
                {
                    "source/batch-audit.json",
                    *(
                        f"source/{case_id}/{relative}"
                        for case_id in exporter.EXPECTED_CASE_IDS
                        for relative in (
                            "profile.json",
                            "guard-summary.json",
                            "guard-summary.json.done.json",
                            "output/audit.json",
                        )
                    ),
                    *(
                        f"source/{case_id}/output/{relative}"
                        for case_id, files in declared.items()
                        for relative in files
                    ),
                },
            )

    def test_collects_exact_case_phase_cartesian_product(self):
        exporter = importlib.import_module(
            "tools.export_battle_effect_controlled_runtime"
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            for case_id in exporter.EXPECTED_CASE_IDS:
                for phase in exporter.PHASE_NAMES:
                    path = source / case_id / "output" / phase / "capture.ss9"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(f"{case_id}:{phase}".encode())

            members = exporter.collect_state_members(source)

            self.assertEqual(len(members), 52)
            self.assertEqual(
                list(members),
                sorted(
                    f"raw/{case_id}/{phase}.ss9"
                    for case_id in exporter.EXPECTED_CASE_IDS
                    for phase in exporter.PHASE_NAMES
                ),
            )

    def test_writes_byte_deterministic_regular_only_tar(self):
        exporter = importlib.import_module(
            "tools.export_battle_effect_controlled_runtime"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = {}
            for name, payload in (("raw/a.ss9", b"a"), ("raw/b.ss9", b"bb")):
                path = root / name.replace("/", "-")
                path.write_bytes(payload)
                sources[name] = path
            first = root / "first.tar"
            second = root / "second.tar"

            exporter.write_deterministic_tar(sources, first)
            exporter.write_deterministic_tar(dict(reversed(list(sources.items()))), second)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            with tarfile.open(first, "r:") as archive:
                members = archive.getmembers()
            self.assertEqual([row.name for row in members], ["raw/a.ss9", "raw/b.ss9"])
            self.assertTrue(all(row.isfile() for row in members))
            self.assertTrue(all(row.uid == row.gid == row.mtime == 0 for row in members))
            self.assertTrue(all(row.mode == 0o644 for row in members))

    def test_classifies_only_complete_target_patterns(self):
        exporter = importlib.import_module(
            "tools.export_battle_effect_controlled_runtime"
        )
        positive = [False, True, True, True]
        negative = [False, False, False, False]
        partial = [False, True, False, True]

        self.assertEqual(
            exporter.classify_target_presence(positive),
            "verified_target_transaction",
        )
        self.assertEqual(
            exporter.classify_target_presence(negative),
            "target_absent_negative",
        )
        self.assertEqual(
            exporter.classify_target_presence(partial),
            "invalid_inconclusive",
        )

    def test_phase_frame_metadata_is_not_the_byte_after_pending(self):
        exporter = importlib.import_module(
            "tools.export_battle_effect_controlled_runtime"
        )
        class State:
            registers = [0] * 15 + [0x0809E85C]
            cpsr = 0x3F

            @staticmethod
            def read_memory(address, size):
                values = {
                    (exporter.SCRATCH, 4): (1).to_bytes(4, "little"),
                    (exporter.PENDING, 1): b"\x00",
                    (exporter.PENDING + 1, 1): b"\x01",
                }
                return values[(address, size)]

        state = State()

        exporter.validate_state_boundary(state, "0x0809E85A", pending=0)

        self.assertEqual(state.read_memory(exporter.PENDING + 1, 1), b"\x01")


if __name__ == "__main__":
    unittest.main()
