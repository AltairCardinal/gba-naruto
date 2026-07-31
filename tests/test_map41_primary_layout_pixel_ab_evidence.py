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
ARTIFACT = ROOT / "artifacts/map41-primary-layout-pixel-ab-v1"


def _resign_file(artifact: Path, relative: str) -> None:
    manifest_path = artifact / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][relative] = hashlib.sha256(
        (artifact / relative).read_bytes()
    ).hexdigest()
    if relative == manifest["payload_file"]:
        manifest["payload_sha256"] = manifest["files"][relative]
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _rewrite_state(path: Path, address: int, value: int) -> None:
    container = path.read_bytes()
    output = bytearray(container[:8])
    cursor = 8
    while cursor < len(container):
        size = struct.unpack_from(">I", container, cursor)[0]
        tag = container[cursor + 4 : cursor + 8]
        payload = container[cursor + 8 : cursor + 8 + size]
        if tag == b"gbAs":
            state = bytearray(zlib.decompress(payload))
            state_offset = 0x21000 + (address - 0x02000000)
            state[state_offset] = value
            payload = zlib.compress(state)
        output += struct.pack(">I", len(payload)) + tag + payload
        output += struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        cursor += size + 12
    path.write_bytes(output)


class Map41PrimaryLayoutPixelAbEvidenceTests(unittest.TestCase):
    def test_production_artifact_verifies(self):
        from tools.verify_map41_primary_layout_pixel_ab_evidence import verify

        report = verify(ROOT, ARTIFACT)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual("0x0201BF08", report["summary"]["runtime_layout_word"])
        self.assertEqual(8, report["summary"]["vram_differing_byte_count"])
        self.assertEqual(204, report["summary"]["differing_pixel_count"])
        self.assertEqual([8, 0, 39, 7], report["summary"]["screen_bbox"])

    def test_artifact_verifies_from_pre_promotion_final_directory(self):
        from tools.verify_map41_primary_layout_pixel_ab_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            final = Path(temporary) / "final"
            shutil.copytree(ARTIFACT, final)
            report = verify(ROOT, final)
            self.assertTrue(report["verified"], report["errors"])

    def test_resigned_runtime_layout_tamper_fails_semantically(self):
        from tools.verify_map41_primary_layout_pixel_ab_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            state = copied / "candidate/frame80.ss9"
            _rewrite_state(state, 0x0201BF08, 0x34)
            _resign_file(copied, "candidate/frame80.ss9")
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("runtime layout" in error for error in report["errors"]),
                report["errors"],
            )

    def test_resigned_alias_split_tamper_fails_semantically(self):
        from tools.verify_map41_primary_layout_pixel_ab_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            build_path = copied / "build-manifest.json"
            build = json.loads(build_path.read_text(encoding="utf-8"))
            build["alias_split"]["preserved_map_ids"] = [39, 40, 42, 43, 44]
            build_path.write_text(
                json.dumps(build, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _resign_file(copied, "build-manifest.json")
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("alias split" in error for error in report["errors"]),
                report["errors"],
            )

    def test_resigned_build_edit_metadata_tamper_fails_semantically(self):
        from tools.verify_map41_primary_layout_pixel_ab_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            build_path = copied / "build-manifest.json"
            build = json.loads(build_path.read_text(encoding="utf-8"))
            build["edit"]["coarse_y"] = 5
            build_path.write_text(
                json.dumps(build, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _resign_file(copied, "build-manifest.json")
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("build edit" in error for error in report["errors"]),
                report["errors"],
            )

    def test_resigned_patch_ledger_provenance_tamper_fails_semantically(self):
        from tools.verify_map41_primary_layout_pixel_ab_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            build_path = copied / "build-manifest.json"
            build = json.loads(build_path.read_text(encoding="utf-8"))
            build["patch_ledgers"]["candidate"][0]["source_sha256"] = "0" * 64
            build_path.write_text(
                json.dumps(build, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _resign_file(copied, "build-manifest.json")
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("patch ledger provenance" in error for error in report["errors"]),
                report["errors"],
            )

    def test_resigned_input_audit_tamper_fails_semantically(self):
        from tools.verify_map41_primary_layout_pixel_ab_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            audit_path = copied / "candidate/audit.json"
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            audit["inputs"][0]["up_frame"] = 14
            audit_path.write_text(
                json.dumps(audit, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _resign_file(copied, "candidate/audit.json")
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("audit" in error for error in report["errors"]),
                report["errors"],
            )

    def test_resigned_guard_backend_tamper_fails_semantically(self):
        from tools.verify_map41_primary_layout_pixel_ab_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            guard_path = copied / "candidate/guard.json"
            guard = json.loads(guard_path.read_text(encoding="utf-8"))
            guard["protection_backend"] = "none"
            guard_path.write_text(
                json.dumps(guard, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            guard_hash = hashlib.sha256(guard_path.read_bytes()).hexdigest()
            for name in ("audit.json", "sentinel.json"):
                path = copied / "candidate" / name
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["guard_summary_sha256"] = guard_hash
                path.write_text(
                    json.dumps(payload, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                _resign_file(copied, f"candidate/{name}")
            _resign_file(copied, "candidate/guard.json")
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("guard" in error for error in report["errors"]),
                report["errors"],
            )

    def test_resigned_runtime_word_metadata_tamper_fails_semantically(self):
        from tools.verify_map41_primary_layout_pixel_ab_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            evidence_path = copied / "runtime-evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["runtime"]["candidate_word"] = "0xDEADBEEF"
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _resign_file(copied, "runtime-evidence.json")
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("memory result" in error for error in report["errors"]),
                report["errors"],
            )

    def test_resigned_external_png_tamper_fails_embedded_frame_binding(self):
        from PIL import Image

        from tools.verify_map41_primary_layout_pixel_ab_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            for variant in ("baseline", "candidate"):
                png_path = copied / variant / "frame80.png"
                image = Image.open(png_path).convert("RGB")
                image.putpixel((100, 100), (1, 2, 3))
                image.save(png_path)
                png_hash = hashlib.sha256(png_path.read_bytes()).hexdigest()
                for name in ("audit.json", "sentinel.json"):
                    path = copied / variant / name
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    payload["output_png_sha256"] = png_hash
                    path.write_text(
                        json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    _resign_file(copied, f"{variant}/{name}")
                _resign_file(copied, f"{variant}/frame80.png")
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("embedded screenshot" in error for error in report["errors"]),
                report["errors"],
            )

    def test_verifier_does_not_import_exporter_or_builder(self):
        source = (
            ROOT / "tools/verify_map41_primary_layout_pixel_ab_evidence.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "from tools.export_map41_primary_layout_pixel_ab_evidence", source
        )
        self.assertNotIn(
            "from tools.build_map41_primary_layout_pixel_ab", source
        )


if __name__ == "__main__":
    unittest.main()
