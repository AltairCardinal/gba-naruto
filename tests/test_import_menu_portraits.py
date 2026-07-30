from __future__ import annotations

import hashlib
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from tools.extract_tileset import lz77_decompress


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "artifacts/menu-portraits-v1/manifest.json"
sys.path.insert(0, str(ROOT / "tools"))


class ImportMenuPortraitsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        self.resource = self.catalog["unique_resources"][0]
        self.logical = next(
            row
            for row in self.catalog["portraits"]
            if row["resource_id"] == self.resource["resource_id"]
        )

    def tearDown(self):
        self.temporary.cleanup()

    def _edited_png(self, *, change_pixel: bool = True) -> Path:
        source = ROOT / "artifacts/menu-portraits-v1" / self.logical["png"]
        image = Image.open(source)
        self.assertEqual("P", image.mode)
        if change_pixel:
            pixels = bytearray(image.tobytes())
            pixels[0] = (pixels[0] + 1) % 64
            image.frombytes(bytes(pixels))
        palette = image.getpalette()
        palette[3:6] = [255, 0, 0]
        image.putpalette(palette)
        output = self.temp / "edited.png"
        image.save(output, transparency=image.info["transparency"])
        return output

    def _spec(self, png: Path, *, resource_id: int | None = None) -> Path:
        resource_id = (
            self.resource["resource_id"]
            if resource_id is None
            else resource_id
        )
        spec = {
            "schema": "menu-portrait-import-v1",
            "source_catalog": "artifacts/menu-portraits-v1/manifest.json",
            "edits": [
                {
                    "id": "portrait-edit",
                    "resource_id": resource_id,
                    "png": str(png),
                    "expected": {
                        "gfx_pointer": self.resource["gfx_pointer"],
                        "palette_pointer": self.resource["palette_pointer"],
                        "compressed_sha256": self.resource[
                            "compressed_sha256"
                        ],
                        "palette_sha256": self.resource["palette_sha256"],
                    },
                }
            ],
        }
        path = self.temp / "spec.json"
        path.write_text(json.dumps(spec), encoding="utf-8")
        return path

    def test_canvas_inverse_and_lz77_encoder_round_trip(self):
        from tools.import_menu_portraits import (
            encode_gba_lz77,
            portrait_canvas_to_stream,
        )
        from tools.export_menu_portraits import render_portrait_indices

        rom = (ROOT / "rom/base.gba").read_bytes()
        original = lz77_decompress(rom, self.resource["gfx_file_offset"])
        canvas = render_portrait_indices(original)
        rebuilt = portrait_canvas_to_stream(canvas)
        compressed = encode_gba_lz77(rebuilt)

        self.assertEqual(original, rebuilt)
        self.assertEqual(original, lz77_decompress(compressed, 0))
        self.assertLessEqual(
            len(compressed),
            self.resource["compressed_size"],
        )

    def test_all_74_resources_and_single_pixel_mutations_fit_original_slots(self):
        from tools.import_menu_portraits import encode_gba_lz77

        rom = (ROOT / "rom/base.gba").read_bytes()
        self.assertEqual(74, len(self.catalog["unique_resources"]))
        for resource in self.catalog["unique_resources"]:
            original = lz77_decompress(rom, resource["gfx_file_offset"])
            self.assertLessEqual(
                len(encode_gba_lz77(original)),
                resource["compressed_size"],
                resource["resource_id"],
            )
            mutated = bytearray(original)
            mutated[0] = (mutated[0] + 1) % 64
            self.assertLessEqual(
                len(encode_gba_lz77(bytes(mutated))),
                resource["compressed_size"],
                resource["resource_id"],
            )

    def test_resolver_emits_guarded_fixed_length_graphics_and_palette_patches(self):
        from tools.import_menu_portraits import resolve_menu_portrait_patches

        rom = (ROOT / "rom/base.gba").read_bytes()
        patches = resolve_menu_portrait_patches(
            ROOT,
            self._spec(self._edited_png()),
            rom=rom,
        )

        self.assertEqual(
            ["menu_portrait_graphics", "menu_portrait_palette"],
            [item["asset_type"] for item in patches],
        )
        for item in patches:
            self.assertEqual("bytes", item["type"])
            self.assertEqual(
                len(bytes.fromhex(item["before_hex"])),
                len(bytes.fromhex(item["after_hex"])),
            )
            self.assertEqual(self.resource["resource_id"], item["resource_id"])
            self.assertGreaterEqual(len(item["affected_portraits"]), 1)

        graphics = patches[0]
        patched = bytearray(rom)
        for item in patches:
            offset = item["offset"]
            after = bytes.fromhex(item["after_hex"])
            patched[offset : offset + len(after)] = after
        decoded = lz77_decompress(bytes(patched), graphics["offset"])
        from tools.export_menu_portraits import render_portrait_indices

        rendered = render_portrait_indices(decoded)
        expected = Image.open(self.temp / "edited.png").tobytes()
        self.assertEqual(expected, rendered)

    def test_exported_png_is_a_noop_and_palette_only_edit_stays_palette_only(self):
        from tools.import_menu_portraits import resolve_menu_portrait_patches

        rom = (ROOT / "rom/base.gba").read_bytes()
        logical_by_resource = {}
        for portrait in self.catalog["portraits"]:
            logical_by_resource.setdefault(portrait["resource_id"], portrait)
        noop_spec = {
            "schema": "menu-portrait-import-v1",
            "source_catalog": "artifacts/menu-portraits-v1/manifest.json",
            "edits": [
                {
                    "id": f"noop-{resource['resource_id']}",
                    "resource_id": resource["resource_id"],
                    "png": str(
                        ROOT
                        / "artifacts/menu-portraits-v1"
                        / logical_by_resource[resource["resource_id"]]["png"]
                    ),
                    "expected": {
                        "gfx_pointer": resource["gfx_pointer"],
                        "palette_pointer": resource["palette_pointer"],
                        "compressed_sha256": resource["compressed_sha256"],
                        "palette_sha256": resource["palette_sha256"],
                    },
                }
                for resource in self.catalog["unique_resources"]
            ],
        }
        noop_spec_path = self.temp / "noop-spec.json"
        noop_spec_path.write_text(json.dumps(noop_spec), encoding="utf-8")
        self.assertEqual(
            [],
            resolve_menu_portrait_patches(
                ROOT,
                noop_spec_path,
                rom=rom,
            ),
        )
        patches = resolve_menu_portrait_patches(
            ROOT,
            self._spec(self._edited_png(change_pixel=False)),
            rom=rom,
        )
        self.assertEqual(
            ["menu_portrait_palette"],
            [item["asset_type"] for item in patches],
        )

    def test_rejects_stale_provenance_bad_png_and_unknown_resource(self):
        from tools.import_menu_portraits import resolve_menu_portrait_patches

        rom = (ROOT / "rom/base.gba").read_bytes()
        png = self._edited_png()
        spec_path = self._spec(png)
        spec = json.loads(spec_path.read_text())
        spec["edits"][0]["expected"]["compressed_sha256"] = "0" * 64
        spec_path.write_text(json.dumps(spec))
        with self.assertRaisesRegex(ValueError, "compressed provenance"):
            resolve_menu_portrait_patches(ROOT, spec_path, rom=rom)

        with self.assertRaisesRegex(ValueError, "unknown portrait resource"):
            resolve_menu_portrait_patches(
                ROOT,
                self._spec(png, resource_id=999),
                rom=rom,
            )

        invalid = Image.new("RGB", (80, 80))
        invalid_path = self.temp / "invalid.png"
        invalid.save(invalid_path)
        with self.assertRaisesRegex(ValueError, "indexed"):
            resolve_menu_portrait_patches(
                ROOT,
                self._spec(invalid_path),
                rom=rom,
            )

    def test_resolver_rejects_duplicate_resources_and_slot_overflow(self):
        from tools.import_menu_portraits import resolve_menu_portrait_patches

        rom = (ROOT / "rom/base.gba").read_bytes()
        spec_path = self._spec(self._edited_png())
        spec = json.loads(spec_path.read_text())
        spec["edits"].append(dict(spec["edits"][0], id="duplicate"))
        spec_path.write_text(json.dumps(spec))
        with self.assertRaisesRegex(ValueError, "duplicate resource"):
            resolve_menu_portrait_patches(ROOT, spec_path, rom=rom)

        noisy = Image.new("P", (80, 80))
        noisy.putpalette(
            [component for value in range(64) for component in (value, value, value)]
        )
        rng = random.Random(0x4E415255)
        noisy.putdata(
            bytes(rng.randrange(64) for _ in range(6400))
        )
        noisy_path = self.temp / "noisy.png"
        noisy.save(noisy_path, transparency=0)
        with self.assertRaisesRegex(ValueError, "does not fit"):
            resolve_menu_portrait_patches(
                ROOT,
                self._spec(noisy_path),
                rom=rom,
            )

    def test_build_manifest_dispatch_applies_portrait_edit(self):
        import tools.build_mod as build_mod

        temp_root = self.temp / "project"
        (temp_root / "rom").mkdir(parents=True)
        (temp_root / "sequel/content/menu-portraits").mkdir(parents=True)
        (temp_root / "artifacts/menu-portraits-v1").mkdir(parents=True)
        base = (ROOT / "rom/base.gba").read_bytes()
        (temp_root / "rom/base.gba").write_bytes(base)
        (temp_root / "artifacts/menu-portraits-v1/manifest.json").write_bytes(
            CATALOG_PATH.read_bytes()
        )

        edited = self._edited_png()
        local_png = temp_root / "sequel/content/menu-portraits/edited.png"
        local_png.write_bytes(edited.read_bytes())
        spec = self._spec(local_png)
        local_spec = temp_root / "sequel/content/menu-portraits/edit.json"
        local_spec.write_bytes(spec.read_bytes())
        manifest = {
            "patches": [
                {
                    "id": "portrait-import",
                    "type": "menu_portrait",
                    "spec": "sequel/content/menu-portraits/edit.json",
                }
            ]
        }
        (temp_root / "sequel/patches").mkdir(parents=True)
        (temp_root / "sequel/patches/manifest.json").write_text(
            json.dumps(manifest)
        )
        project = {
            "project_id": "menu-portrait-build-test",
            "base_rom": {
                "path": "rom/base.gba",
                "sha1": hashlib.sha1(base).hexdigest(),
            },
            "patch_manifest": "sequel/patches/manifest.json",
            "build": {
                "output_rom": "build/output.gba",
                "report": "build/report.json",
            },
        }
        project_path = temp_root / "sequel/project.json"
        project_path.write_text(json.dumps(project))

        with patch.object(build_mod, "ROOT", temp_root):
            report = build_mod.build(project_path)

        output = (temp_root / "build/output.gba").read_bytes()
        decoded = lz77_decompress(output, self.resource["gfx_file_offset"])
        from tools.export_menu_portraits import render_portrait_indices

        self.assertEqual(
            Image.open(local_png).tobytes(),
            render_portrait_indices(decoded),
        )
        self.assertEqual(
            ["menu_portrait_graphics", "menu_portrait_palette"],
            [
                patch_row["asset_type"]
                for patch_row in report["applied_patches"]
            ],
        )

    def test_writeback_audit_closes_all_74_original_and_mutation_slots(self):
        from tools.export_menu_portrait_writeback_audit import (
            export_menu_portrait_writeback_audit,
        )

        output = self.temp / "menu-portrait-writeback-v1"
        payload = export_menu_portrait_writeback_audit(ROOT, output)

        self.assertEqual(74, payload["summary"]["resource_count"])
        self.assertEqual(74, payload["summary"]["original_roundtrip_fit_count"])
        self.assertEqual(74, payload["summary"]["single_pixel_mutation_fit_count"])
        self.assertTrue(
            all(row["palette_fixed_length_writeback"] for row in payload["resources"])
        )
        self.assertTrue(payload["scope"]["all_unique_resources_audited"])
        self.assertTrue(
            payload["scope"]["single_pixel_mutation_capacity_complete"]
        )
        self.assertFalse(payload["scope"]["arbitrary_png_slot_fit_complete"])
        self.assertFalse(payload["scope"]["resource_relocation_complete"])
        self.assertFalse(payload["scope"]["runtime_pixel_equivalence"])

    def test_independent_writeback_audit_verifier_accepts_export(self):
        from tools.export_menu_portrait_writeback_audit import (
            export_menu_portrait_writeback_audit,
        )
        from tools.verify_menu_portrait_writeback_audit import (
            verify_menu_portrait_writeback_audit,
        )

        output = self.temp / "menu-portrait-writeback-v1"
        export_menu_portrait_writeback_audit(ROOT, output)
        report = verify_menu_portrait_writeback_audit(ROOT, output)

        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(74, report["resource_count"])

    def test_independent_writeback_audit_verifier_rejects_resigned_tamper(self):
        from tools.export_menu_portrait_writeback_audit import (
            export_menu_portrait_writeback_audit,
        )
        from tools.verify_menu_portrait_writeback_audit import (
            verify_menu_portrait_writeback_audit,
        )

        output = self.temp / "menu-portrait-writeback-v1"
        export_menu_portrait_writeback_audit(ROOT, output)
        payload_path = output / "menu-portrait-writeback.json"
        payload = json.loads(payload_path.read_text())
        payload["resources"][0]["single_pixel_mutation_encoded_size"] += 1
        payload_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest_path = output / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        payload_hash = hashlib.sha256(payload_path.read_bytes()).hexdigest()
        manifest["payload_sha256"] = payload_hash
        manifest["files"]["menu-portrait-writeback.json"] = payload_hash
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        report = verify_menu_portrait_writeback_audit(ROOT, output)
        self.assertFalse(report["verified"])
        self.assertTrue(
            any("resource records mismatch" in error for error in report["errors"]),
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()
