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
ARTIFACT = ROOT / "artifacts/residual-wram-tilemap-pixel-ab-v1"


def _rewrite_state(path: Path, mutate) -> None:
    payload = path.read_bytes()
    output = bytearray(payload[:8])
    cursor = 8
    while cursor < len(payload):
        size = struct.unpack_from(">I", payload, cursor)[0]
        tag = payload[cursor + 4 : cursor + 8]
        data = payload[cursor + 8 : cursor + 8 + size]
        if tag == b"gbAs":
            state = bytearray(zlib.decompress(data))
            mutate(state)
            data = zlib.compress(state)
        output += struct.pack(">I", len(data)) + tag + data
        output += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        cursor += 12 + size
    path.write_bytes(output)


def _rewrite_state_u16(path: Path, state_offset: int, value: int) -> None:
    _rewrite_state(path, lambda state: struct.pack_into("<H", state, state_offset, value))


def _toggle_state_byte(path: Path, state_offset: int) -> None:
    def mutate(state: bytearray) -> None:
        state[state_offset] ^= 1

    _rewrite_state(path, mutate)


class ResidualWramTilemapPixelAbEvidenceTests(unittest.TestCase):
    def test_production_artifact_verifies(self):
        from tools.verify_residual_wram_tilemap_pixel_ab_evidence import verify

        report = verify(ROOT, ARTIFACT)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(50, report["summary"]["differing_pixel_count"])
        self.assertEqual(
            "0x06000A16", report["summary"]["changed_vram_entry_address"]
        )

    def test_resigned_runtime_staging_tamper_fails_semantically(self):
        from tools.verify_residual_wram_tilemap_pixel_ab_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            path = copied / "candidate/staging.bin"
            payload = bytearray(path.read_bytes())
            payload[0] ^= 1
            path.write_bytes(payload)
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["candidate/staging.bin"] = hashlib.sha256(
                payload
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("staging" in error for error in report["errors"]),
                report["errors"],
            )

    def test_resigned_build_semantic_tamper_fails(self):
        from tools.verify_residual_wram_tilemap_pixel_ab_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            build_path = copied / "build-manifest.json"
            build = json.loads(build_path.read_text(encoding="utf-8"))
            build["roms"]["candidate"]["target_decoded_sha256"] = "0" * 64
            build_path.write_text(
                json.dumps(build, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["build-manifest.json"] = hashlib.sha256(
                build_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("decoded" in error for error in report["errors"]),
                report["errors"],
            )

    def test_resigned_bg1_scroll_state_tamper_fails_semantically(self):
        from tools.verify_residual_wram_tilemap_pixel_ab_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            path = copied / "candidate/frame1.ss9"
            _rewrite_state_u16(path, 0x400 + 0x14, 8)
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["candidate/frame1.ss9"] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("BG1" in error for error in report["errors"]),
                report["errors"],
            )

    def test_resigned_non_target_vram_tamper_fails_semantically(self):
        from tools.verify_residual_wram_tilemap_pixel_ab_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            path = copied / "candidate/queue-post.ss9"
            _toggle_state_byte(path, 0x1000 + 0x20)
            queue_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            replay_path = copied / "candidate/replay-audit.json"
            replay = json.loads(replay_path.read_text(encoding="utf-8"))
            replay["input_state_sha256"] = queue_hash
            replay_path.write_text(
                json.dumps(replay, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["candidate/queue-post.ss9"] = queue_hash
            manifest["files"]["candidate/replay-audit.json"] = hashlib.sha256(
                replay_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            report = verify(ROOT, copied)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("full VRAM" in error for error in report["errors"]),
                report["errors"],
            )

    def test_verifier_does_not_import_exporter_or_builder(self):
        source = (
            ROOT / "tools/verify_residual_wram_tilemap_pixel_ab_evidence.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "from tools.export_residual_wram_tilemap_pixel_ab_evidence", source
        )
        self.assertNotIn(
            "from tools.build_residual_wram_tilemap_pixel_ab", source
        )


if __name__ == "__main__":
    unittest.main()
