"""TDD contract for the frozen text-BG loop continuation packet."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from tools import export_rom_text_bg_loop_continuation as exporter
from tools import verify_rom_text_bg_loop_continuation as verifier


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/text-bg-loop-continuation-20260902/luna-r1"


class TextBgLoopContinuationTests(unittest.TestCase):
    def _temporary_root(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        holder = tempfile.TemporaryDirectory()
        root = Path(holder.name)
        (root / "rom").mkdir()
        (root / "sequel").mkdir()
        shutil.copy2(ROOT / exporter.ROM_PATH, root / exporter.ROM_PATH)
        shutil.copy2(ROOT / exporter.COVERAGE_PATH, root / exporter.COVERAGE_PATH)
        dependencies = [
            Path("artifacts/residual-text-bg-tilemap-resource-ownership-v1/manifest.json"),
            Path("artifacts/residual-text-bg-tilemap-resource-ownership-v1/resource-ownership.json"),
            Path("artifacts/rom-pointer-lz77-inventory-v1/rom-pointer-lz77-inventory.json"),
            Path("artifacts/rom-pointer-lz77-graphics-v1/graphics-catalog.json"),
            Path("artifacts/residual-lz77-graphics-relocation-v1/full-relocation-spec.json"),
            Path("artifacts/direct-image-palette-relocation-v1/full-relocation-spec.json"),
            Path("tools/extract_tileset.py"),
            Path("tools/gba_image_export.py"),
            Path("tools/export_residual_text_bg_tilemap_resource_ownership.py"),
            Path("tools/verify_residual_text_bg_tilemap_resource_ownership.py"),
            Path("tools/export_rom_text_bg_loop_continuation.py"),
            Path("tools/verify_rom_text_bg_loop_continuation.py"),
            Path("tests/test_export_rom_text_bg_loop_continuation.py"),
        ]
        for relative in dependencies:
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, root / relative)
        return holder, root.resolve()

    def test_red_phase_failed_for_missing_packet_modules(self) -> None:
        red = (EXPERIMENT / "red.log").read_text()
        self.assertIn("ImportError", red)
        self.assertIn("FAILED (errors=1)", red)

    def test_builds_exact_source_owned_cfg_and_literal_contract(self) -> None:
        payload = exporter.build_payload(ROOT)
        self.assertEqual(exporter.SCHEMA, payload["schema"])
        self.assertEqual([0x08B644], payload["producer_denominator"]["forms"]["thumb_bl"])
        self.assertEqual(1, payload["producer_denominator"]["matching_producer_count"])
        self.assertEqual([0x08B640, 0x08B64E], payload["source_owner"]["range"])
        self.assertEqual("consumer_code_slice", payload["source_owner"]["primary_class"])
        cfg = payload["target_local_cfg"]
        self.assertEqual([0x08ACC8, 0x08ACF2], cfg["code_range"])
        self.assertEqual(21, cfg["instruction_count"])
        self.assertEqual(0, cfg["frontier_count"])
        self.assertEqual([0x08AEB4, 0x08AEC0], cfg["literal_range"])
        self.assertEqual(4, cfg["literal_reference_count"])
        self.assertEqual(3, cfg["unique_literal_word_count"])
        self.assertEqual(54, payload["promotion"]["promotion_bytes"])
        self.assertEqual(2, len(payload["promotion"]["claims"]))
        self.assertTrue(payload["source_membership"]["producer_instruction_membership_proven"])
        self.assertEqual(55, payload["source_membership"]["instruction_count"])
        self.assertEqual([0x08ACF2, 0x08AD08], payload["opaque_boundary_owner"]["range"])
        self.assertNotIn("observed_sha256", payload["coverage_baseline"])
        self.assertNotIn("state", payload["coverage_baseline"])

    def test_export_is_canonical_and_independent_verifier_accepts(self) -> None:
        parent = ROOT / "build/experiments/active/text-bg-loop-continuation-20260902"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            output = Path(directory) / "candidate"
            exporter.export_artifact(ROOT, output)
            report = verifier.verify_artifact(ROOT, output)
            self.assertTrue(report["verified"], report)
            self.assertTrue(report["contract_ok"])
            self.assertEqual(54, report["promotion_bytes"])
            for name in (exporter.MANIFEST_NAME, exporter.PAYLOAD_NAME):
                raw = (output / name).read_bytes()
                canonical = (json.dumps(json.loads(raw), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
                self.assertEqual(canonical, raw)

    def test_verifier_does_not_import_or_call_exporter(self) -> None:
        source = (ROOT / "tools/verify_rom_text_bg_loop_continuation.py").read_text()
        self.assertNotIn("from tools import export_rom_text_bg_loop_continuation", source)
        self.assertNotIn("import tools.export_rom_text_bg_loop_continuation", source)
        self.assertNotIn("build_payload", source)

    def test_low_level_mutations_fail_for_the_correct_contract_reason(self) -> None:
        rom = bytearray((ROOT / exporter.ROM_PATH).read_bytes())
        mutated = bytearray(rom); mutated[0x08B644] ^= 1
        with self.assertRaisesRegex(ValueError, "producer denominator|producer bytes"):
            exporter._producer_denominator(bytes(mutated))
        mutated = bytearray(rom); mutated[0x08ACC8] ^= 1
        with self.assertRaisesRegex(ValueError, "code bytes|instruction denominator"):
            exporter._cfg(bytes(mutated))
        mutated = bytearray(rom); mutated[0x08AEB4] ^= 1
        with self.assertRaisesRegex(ValueError, "literal binding|literal bytes"):
            exporter._cfg(bytes(mutated))
        mutated = bytearray(rom); mutated[0x08B608] ^= 1
        with self.assertRaisesRegex(ValueError, "source membership"):
            exporter._source_membership(ROOT, bytes(mutated))

    def test_rejects_coverage_identity_and_source_owner_mutation(self) -> None:
        holder, root = self._temporary_root()
        try:
            coverage = json.loads((root / exporter.COVERAGE_PATH).read_text())
            for row in coverage["segments"]:
                if row["range"] == [0x08B640, 0x08B64E]:
                    row["primary_class"] = "unknown"
                    break
            (root / exporter.COVERAGE_PATH).write_text(json.dumps(coverage))
            with self.assertRaisesRegex(ValueError, "source owner"):
                exporter.build_payload(root)
        finally:
            holder.cleanup()

    def test_rejects_artifact_payload_and_extra_file_mutations(self) -> None:
        holder, root = self._temporary_root()
        try:
            output = root / "candidate"
            exporter.export_artifact(root, output)
            payload = bytearray((output / exporter.PAYLOAD_NAME).read_bytes())
            payload[-2] ^= 1
            (output / exporter.PAYLOAD_NAME).write_bytes(payload)
            self.assertFalse(verifier.verify_artifact(root, output)["verified"])
            shutil.rmtree(output)
            exporter.export_artifact(root, output)
            (output / "extra").write_text("x")
            self.assertFalse(verifier.verify_artifact(root, output)["verified"])
        finally:
            holder.cleanup()

    def test_immutable_payload_replays_after_post_promotion_coverage(self) -> None:
        holder, root = self._temporary_root()
        try:
            output = root / "candidate"
            exporter.export_artifact(root, output)
            coverage = json.loads((root / exporter.COVERAGE_PATH).read_text())
            overlays = [
                (0x08ACC8, 0x08ACF2, exporter.CODE_CLASS, "text-bg-loop-continuation-code"),
                (0x08AEB4, 0x08AEC0, exporter.LITERAL_CLASS, "text-bg-loop-continuation-literals"),
            ]
            segments = []
            for row in coverage["segments"]:
                pieces = [row]
                for start, end, primary, claim_id in overlays:
                    next_pieces = []
                    for piece in pieces:
                        a, b = piece["range"]
                        if b <= start or end <= a:
                            next_pieces.append(piece); continue
                        if a < start: next_pieces.append({**piece, "range": [a, start]})
                        lo, hi = max(a, start), min(b, end)
                        next_pieces.append({"range": [lo, hi], "primary_class": primary, "primary_claim_ids": [claim_id]})
                        if end < b: next_pieces.append({**piece, "range": [end, b]})
                    pieces = next_pieces
                segments.extend(pieces)
            coverage["segments"] = segments
            (root / exporter.COVERAGE_PATH).write_text(json.dumps(coverage))
            report = verifier.verify_artifact(root, output)
            self.assertTrue(report["verified"], report)
            self.assertEqual("post-promotion", report["coverage_state"])
        finally:
            holder.cleanup()

    def test_output_is_noreplace_and_cannot_escape_or_use_symlink(self) -> None:
        holder, root = self._temporary_root()
        outside = tempfile.TemporaryDirectory()
        try:
            exporter.export_artifact(root, Path("candidate"))
            with self.assertRaises(FileExistsError):
                exporter.export_artifact(root, Path("candidate"))
            with self.assertRaisesRegex(ValueError, "escapes"):
                exporter.export_artifact(root, Path(outside.name) / "escape")
            (root / "linked-rom").symlink_to(root / exporter.ROM_PATH)
            original = exporter.ROM_PATH
            try:
                exporter.ROM_PATH = Path("linked-rom")
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    exporter.build_payload(root)
            finally:
                exporter.ROM_PATH = original
        finally:
            holder.cleanup()
            outside.cleanup()

    def test_rejects_symlink_ancestor_and_atomic_publish_never_replaces(self) -> None:
        holder, root = self._temporary_root()
        try:
            real = root / "real"; real.mkdir()
            output = real / "candidate"; exporter.export_artifact(root, output)
            (root / "alias").symlink_to(real, target_is_directory=True)
            self.assertFalse(verifier.verify_artifact(root, Path("alias/candidate"))["verified"])
            with self.assertRaisesRegex(ValueError, "symlink ancestor"):
                exporter.export_artifact(root, Path("alias/new-candidate"))
            source = real / "source"; source.mkdir()
            with self.assertRaises(FileExistsError):
                exporter._publish_exclusive(source, output)
            self.assertTrue(source.exists())
        finally:
            holder.cleanup()

    def test_fsync_failure_does_not_publish_target(self) -> None:
        holder, root = self._temporary_root()
        try:
            with mock.patch.object(exporter.os, "fsync", side_effect=OSError("synthetic fsync failure")):
                with self.assertRaisesRegex(OSError, "synthetic fsync failure"):
                    exporter.export_artifact(root, Path("candidate"))
            self.assertFalse((root / "candidate").exists())
        finally:
            holder.cleanup()

    def test_parent_fsync_failure_preserves_already_published_target(self) -> None:
        holder, root = self._temporary_root()
        calls = 0
        real_fsync = exporter.os.fsync
        def fail_after_publish(fd):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise OSError("synthetic parent fsync failure")
            return real_fsync(fd)
        try:
            with mock.patch.object(exporter.os, "fsync", side_effect=fail_after_publish):
                with self.assertRaisesRegex(OSError, "synthetic parent fsync failure"):
                    exporter.export_artifact(root, Path("candidate"))
            self.assertTrue((root / "candidate").is_dir())
            self.assertTrue(verifier.verify_artifact(root, root / "candidate")["verified"])
        finally:
            holder.cleanup()

    def test_scope_keeps_adjacent_and_runtime_claims_false(self) -> None:
        scope = exporter.build_payload(ROOT)["scope"]
        self.assertTrue(scope)
        self.assertTrue(all(value is False for value in scope.values()))


if __name__ == "__main__":
    unittest.main()
