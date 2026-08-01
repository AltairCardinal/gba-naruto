import importlib
import json
import tempfile
import unittest
from pathlib import Path


class Group15AllocatorSideRuntimeExporterTests(unittest.TestCase):
    def test_collects_every_audit_declared_output_and_case_provenance(self):
        exporter = importlib.import_module(
            "tools.export_battle_effect_group15_allocator_side_runtime"
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / "batch-audit.json").write_text("{}", encoding="utf-8")
            for case_id in exporter.CASE_IDS:
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
                        files[relative] = "unused"
                (output / "audit.json").write_text(
                    json.dumps({"files": files}), encoding="utf-8"
                )

            members = exporter.collect_source_members(source)

            self.assertEqual(len(members), 113)
            self.assertEqual(set(members), exporter.EXPECTED_SOURCE_MEMBERS)


if __name__ == "__main__":
    unittest.main()
