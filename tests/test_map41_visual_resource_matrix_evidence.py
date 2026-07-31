from __future__ import annotations

import hashlib
import json
import shutil
import struct
import tempfile
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/map41-visual-resource-matrix-v1"


def _resign_file(artifact: Path, relative: str) -> None:
    manifest_path = artifact / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256((artifact / relative).read_bytes()).hexdigest()
    manifest["files"][relative] = digest
    if relative == manifest["payload_file"]:
        manifest["payload_sha256"] = digest
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _rewrite_state_byte(path: Path, address: int, value: int) -> None:
    regions = (
        (0x04000000, 0x00400, 0x00400),
        (0x05000000, 0x00400, 0x00800),
        (0x07000000, 0x00400, 0x00C00),
        (0x06000000, 0x18000, 0x01000),
        (0x03000000, 0x08000, 0x19000),
        (0x02000000, 0x40000, 0x21000),
    )
    state_offset = next(
        offset + address - base
        for base, length, offset in regions
        if base <= address < base + length
    )
    container = path.read_bytes()
    output = bytearray(container[:8])
    cursor = 8
    while cursor < len(container):
        size = struct.unpack_from(">I", container, cursor)[0]
        tag = container[cursor + 4 : cursor + 8]
        payload = container[cursor + 8 : cursor + 8 + size]
        if tag == b"gbAs":
            state = bytearray(zlib.decompress(payload))
            state[state_offset] = value
            payload = zlib.compress(state)
        output += struct.pack(">I", len(payload)) + tag + payload
        output += struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        cursor += size + 12
    path.write_bytes(output)


class Map41VisualResourceMatrixEvidenceTests(unittest.TestCase):
    def test_production_artifact_verifies_all_three_resource_routes(self):
        from tools.verify_map41_visual_resource_matrix_evidence import verify

        report = verify(ROOT, ARTIFACT)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(
            {
                "tile_graphics": {
                    "memory_differences": {"VRAM": [0x6A20]},
                    "pixel_count": 1,
                    "screen_bbox": [160, 32, 160, 32],
                },
                "bg_palette": {
                    "memory_differences": {"PRAM": [0x4A]},
                    "pixel_count": 119,
                    "screen_bbox": [0, 104, 238, 116],
                },
                "metatile_definitions": {
                    "memory_differences": {
                        "EWRAM": [0x1E05C],
                        "VRAM": [0x418],
                    },
                    "pixel_count": 56,
                    "screen_bbox": [72, 24, 79, 31],
                },
            },
            report["summary"]["candidates"],
        )

    def test_artifact_verifies_before_promotion(self):
        from tools.verify_map41_visual_resource_matrix_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "final"
            shutil.copytree(ARTIFACT, copied)
            report = verify(ROOT, copied)
            self.assertTrue(report["verified"], report["errors"])

    def test_resigned_runtime_resource_tamper_fails_semantically(self):
        from tools.verify_map41_visual_resource_matrix_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            state_path = copied / "tile_graphics/frame80.ss9"
            _rewrite_state_byte(state_path, 0x06006A20, 0x36)
            _resign_file(copied, "tile_graphics/frame80.ss9")
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("runtime resource" in error for error in report["errors"]),
                report["errors"],
            )

    def test_resigned_alias_denominator_tamper_fails_semantically(self):
        from tools.verify_map41_visual_resource_matrix_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            build_path = copied / "build-manifest.json"
            build = json.loads(build_path.read_text(encoding="utf-8"))
            build["resources"]["bg_palette"]["physical_offsets"].pop()
            build_path.write_text(
                json.dumps(build, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _resign_file(copied, "build-manifest.json")
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("alias denominator" in error for error in report["errors"]),
                report["errors"],
            )

    def test_resigned_shared_topology_tamper_fails_semantically(self):
        from tools.verify_map41_visual_resource_matrix_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            build_path = copied / "build-manifest.json"
            build = json.loads(build_path.read_text(encoding="utf-8"))
            build["variants"]["bg_palette"]["patch_ledger"][0]["offset"] += 4
            build_path.write_text(
                json.dumps(build, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _resign_file(copied, "build-manifest.json")
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("patch topology" in error for error in report["errors"]),
                report["errors"],
            )

    def test_resigned_external_png_tamper_fails_embedded_binding(self):
        from PIL import Image

        from tools.verify_map41_visual_resource_matrix_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            png_path = copied / "bg_palette/frame80.png"
            image = Image.open(png_path).convert("RGB")
            image.putpixel((100, 100), (1, 2, 3))
            image.save(png_path)
            png_hash = hashlib.sha256(png_path.read_bytes()).hexdigest()
            for name in ("audit.json", "sentinel.json"):
                path = copied / "bg_palette" / name
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["output_png_sha256"] = png_hash
                path.write_text(
                    json.dumps(payload, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                _resign_file(copied, f"bg_palette/{name}")
            _resign_file(copied, "bg_palette/frame80.png")
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("embedded screenshot" in error for error in report["errors"]),
                report["errors"],
            )

    def test_resigned_guard_tamper_fails_semantically(self):
        from tools.verify_map41_visual_resource_matrix_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            guard_path = copied / "metatile_definitions/guard.json"
            guard = json.loads(guard_path.read_text(encoding="utf-8"))
            guard["degraded"] = True
            guard_path.write_text(
                json.dumps(guard, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            guard_hash = hashlib.sha256(guard_path.read_bytes()).hexdigest()
            for name in ("audit.json", "sentinel.json"):
                path = copied / "metatile_definitions" / name
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["guard_summary_sha256"] = guard_hash
                path.write_text(
                    json.dumps(payload, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                _resign_file(copied, f"metatile_definitions/{name}")
            _resign_file(copied, "metatile_definitions/guard.json")
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("guard" in error for error in report["errors"]),
                report["errors"],
            )

    def test_resigned_pixel_oracle_tamper_fails_semantically(self):
        from tools.verify_map41_visual_resource_matrix_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            evidence_path = copied / "runtime-evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            changes = evidence["runtime"]["candidates"]["tile_graphics"][
                "pixel_changes"
            ]
            changes[0][2] = [1, 2, 3]
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _resign_file(copied, "runtime-evidence.json")
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("evidence memory result" in error for error in report["errors"]),
                report["errors"],
            )

    def test_manifest_implementation_hash_tamper_fails(self):
        from tools.verify_map41_visual_resource_matrix_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["implementation_sha256"][
                "tools/inspect_mgba_savestate.py"
            ] = "0" * 64
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("implementation hashes" in error for error in report["errors"]),
                report["errors"],
            )

    def test_verifier_does_not_import_builder_or_exporter(self):
        path = ROOT / "tools/verify_map41_visual_resource_matrix_evidence.py"
        source = path.read_text(encoding="utf-8")
        self.assertNotIn(
            "from tools.build_map41_visual_resource_matrix", source
        )
        self.assertNotIn(
            "from tools.export_map41_visual_resource_matrix_evidence", source
        )


if __name__ == "__main__":
    unittest.main()
