from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StoryVisualResourceSourceExportTests(unittest.TestCase):
    def test_exports_49_deduplicated_editable_sources_deterministically(self):
        from tools.export_story_visual_resource_sources import export_sources
        from tools.import_story_visual_resource_relocations import (
            catalog_story_visual_relocation_payloads,
        )

        resources = catalog_story_visual_relocation_payloads(ROOT)
        with tempfile.TemporaryDirectory() as first_dir:
            first = Path(first_dir)
            catalog = export_sources(ROOT, first)
            self.assertEqual(
                {
                    "content_resource_count": 49,
                    "physical_payload_count": 72,
                    "logical_pointer_count": 72,
                    "resource_type_counts": {
                        "graphics": 24,
                        "palette": 1,
                        "tilemap": 24,
                    },
                },
                catalog["summary"],
            )
            self.assertEqual(49, len(catalog["resources"]))
            self.assertEqual(51, len(list(first.rglob("*.*"))))
            self.assertEqual(
                catalog,
                json.loads(
                    (first / "source-catalog.json").read_text(encoding="utf-8")
                ),
            )
            promotion = json.loads(
                (first / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual("git-artifact-promotion-v1", promotion["schema"])
            self.assertEqual("accepted", promotion["artifact_status"])
            self.assertEqual("source-catalog.json", promotion["payload_file"])
            self.assertEqual(50, len(promotion["files"]))
            self.assertEqual(
                [
                    "python3",
                    "tools/verify_story_visual_resource_relocation_audit.py",
                    "--root",
                    ".",
                    "--artifact",
                    "artifacts/story-visual-resource-relocation-v1",
                ],
                promotion["verifier"]["command"],
            )
            for relative, digest in promotion["files"].items():
                self.assertEqual(
                    digest,
                    hashlib.sha256((first / relative).read_bytes()).hexdigest(),
                )
            for row in catalog["resources"]:
                key = (row["resource_type"], row["resource_sha256"])
                resource = resources[key]
                source = first / row["source_file"]
                self.assertEqual(resource["content"], source.read_bytes())
                self.assertEqual(
                    row["resource_sha256"],
                    hashlib.sha256(source.read_bytes()).hexdigest(),
                )
                self.assertEqual(
                    resource["physical_offsets"],
                    row["physical_offsets"],
                )
                self.assertEqual(
                    sorted(
                        alias["table_pointer_offset"]
                        for alias in resource["pointer_aliases"]
                    ),
                    row["pointer_offsets"],
                )
            first_files = {
                path.relative_to(first).as_posix(): path.read_bytes()
                for path in first.rglob("*")
                if path.is_file()
            }
            with tempfile.TemporaryDirectory() as second_dir:
                second = Path(second_dir)
                export_sources(ROOT, second)
                second_files = {
                    path.relative_to(second).as_posix(): path.read_bytes()
                    for path in second.rglob("*")
                    if path.is_file()
                }
            self.assertEqual(first_files, second_files)


if __name__ == "__main__":
    unittest.main()
