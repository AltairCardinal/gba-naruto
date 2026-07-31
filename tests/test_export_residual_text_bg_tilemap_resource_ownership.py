from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExportResidualTextBgTilemapResourceOwnershipTests(unittest.TestCase):
    @staticmethod
    def _resign(artifact: Path, payload: dict) -> None:
        payload_path = artifact / "resource-ownership.json"
        payload_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        digest = hashlib.sha256(payload_path.read_bytes()).hexdigest()
        manifest_path = artifact / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["payload_sha256"] = digest
        manifest["files"] = {"resource-ownership.json": digest}
        manifest_path.write_text(
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

    def test_closes_text_bg_graphics_palette_and_bg_ownership(self):
        from tools.export_residual_text_bg_tilemap_resource_ownership import (
            export_ownership,
        )
        from tools.verify_residual_text_bg_tilemap_resource_ownership import (
            verify_artifact,
        )

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "ownership"
            payload = export_ownership(ROOT, artifact)
            report = verify_artifact(ROOT, artifact)

        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(
            {
                "tilemap_source_count": 1,
                "bg_control_complete_count": 1,
                "graphics_ownership_complete_count": 1,
                "palette_ownership_complete_count": 1,
                "remaining_unresolved_count": 0,
            },
            payload["summary"],
        )
        record = payload["ownership_record"]
        self.assertEqual("0x08349368", record["tilemap_source_pointer"])
        self.assertEqual("0x06001000", record["vram_destination"])
        self.assertEqual([0, 5], record["tile_index_range"])
        self.assertEqual([1], record["palette_banks"])
        self.assertEqual("BG2", record["bg"]["name"])
        self.assertEqual("0x0204", record["bg"]["control_value"])
        self.assertEqual(
            "0x08348F00",
            record["graphics"]["source_pointer"],
        )
        self.assertEqual(
            [0, 67],
            record["graphics"]["loaded_tile_index_range"],
        )
        self.assertEqual(
            "0x0834941C",
            record["palette"]["source_pointer"],
        )
        self.assertEqual(1, record["palette"]["bank"])
        self.assertEqual("0x0808B58C", record["resource_setup_function"])
        self.assertEqual("0x0808B2C8", record["tilemap_setup_function"])
        self.assertEqual("0x0808B640", record["setup_link_call"])
        self.assertEqual(
            ["0x0808F844", "0x0808FA04"],
            record["natural_entry_callers"],
        )

    def test_verifier_rejects_resigned_graphics_destination_tamper(self):
        from tools.export_residual_text_bg_tilemap_resource_ownership import (
            export_ownership,
        )
        from tools.verify_residual_text_bg_tilemap_resource_ownership import (
            verify_artifact,
        )

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "ownership"
            export_ownership(ROOT, artifact)
            payload = json.loads(
                (artifact / "resource-ownership.json").read_text()
            )
            payload["ownership_record"]["graphics"][
                "vram_destination"
            ] = "0x06004020"
            self._resign(artifact, payload)
            report = verify_artifact(ROOT, artifact)

        self.assertFalse(report["verified"])
        self.assertTrue(report["errors"])

    def test_independent_static_semantics_rejects_broken_setup_link(self):
        from tools.verify_residual_text_bg_tilemap_resource_ownership import (
            ROM_BASE,
            _validate_static_semantics,
        )

        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        offset = 0x0808B640 - ROM_BASE
        rom[offset : offset + 2] = b"\x00\x00"
        with self.assertRaisesRegex(ValueError, "setup link"):
            _validate_static_semantics(bytes(rom))

    def test_independent_static_semantics_rejects_bg_control_drift(self):
        from tools.verify_residual_text_bg_tilemap_resource_ownership import (
            ROM_BASE,
            _validate_static_semantics,
        )

        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        offset = 0x0808B2FC - ROM_BASE
        rom[offset : offset + 2] = b"\x82\x22"
        with self.assertRaisesRegex(ValueError, "BG2 control"):
            _validate_static_semantics(bytes(rom))

    def test_promoted_artifact_passes_independent_verifier(self):
        from tools.verify_residual_text_bg_tilemap_resource_ownership import (
            verify_artifact,
        )

        report = verify_artifact(
            ROOT,
            ROOT
            / "artifacts/residual-text-bg-tilemap-resource-ownership-v1",
        )
        self.assertTrue(report["verified"], report["errors"])
