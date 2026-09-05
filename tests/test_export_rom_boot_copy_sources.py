"""Tests for the boot copy-source packet."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import export_rom_boot_copy_sources as exporter
from tools import verify_rom_boot_copy_sources as verifier


ROOT = Path(__file__).resolve().parents[1]


class BootCopySourceTests(unittest.TestCase):
    def test_cli_entrypoints_work_from_project_root(self) -> None:
        holder = tempfile.TemporaryDirectory(dir=ROOT / "build/experiments")
        try:
            output = Path(holder.name) / "candidate"
            exported = subprocess.run(
                ["python3", "tools/export_rom_boot_copy_sources.py", "--root", ".", "--output", str(output)],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(0, exported.returncode, exported.stderr)
            verified = subprocess.run(
                ["python3", "tools/verify_rom_boot_copy_sources.py", "--root", ".", "--artifact", str(output)],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(0, verified.returncode, verified.stdout + verified.stderr)
        finally:
            holder.cleanup()

    def test_payload_freezes_exact_copy_union(self) -> None:
        payload = exporter.build_payload(ROOT)
        self.assertEqual("rom-boot-copy-sources-v1", payload["schema"])
        self.assertEqual([0x4C8, 0x734], payload["promotion"]["range"])
        self.assertEqual(620, payload["promotion"]["bytes"])
        self.assertEqual(
            "0be5228ec171480a4097db134e32c030972f43fbf637a425f3f4826450944e80",
            payload["promotion"]["bytes_sha256"],
        )
        self.assertEqual(
            [[0x4C8, 0x6C8], [0x520, 0x5C4], [0x5AC, 0x60C],
             [0x638, 0x694], [0x690, 0x734]],
            [row["source_range"] for row in payload["copy_operations"]],
        )
        self.assertEqual(
            "0x03005CE8",
            next(row for row in payload["copy_operations"] if row["id"] == "cpuset-v12")["destination"],
        )
        self.assertEqual([0x4C8, 0x734], payload["copy_operation_union"]["range"])

    def test_local_consumer_and_upstream_membership_are_complete(self) -> None:
        payload = exporter.build_payload(ROOT)
        local = payload["local_dma_consumer"]
        self.assertEqual([0x61624, 0x61710], local["code_range"])
        self.assertEqual([0x60FE0], local["producer_denominator"]["thumb_bl"])
        self.assertEqual([], local["producer_denominator"]["thumb_b"])
        self.assertEqual([], local["producer_denominator"]["thumb_bcond"])
        self.assertEqual([], local["producer_denominator"]["rom_pointers"])
        self.assertEqual(9, len(local["dma_descriptor_denominator"]))
        self.assertEqual(3, sum(row["candidate_hit"] for row in local["dma_descriptor_denominator"]))
        self.assertEqual("bx r0", local["strict_return"])
        self.assertTrue(payload["upstream_evidence"]["boot_thumb_handoff"]["verified"])
        self.assertTrue(payload["upstream_evidence"]["cfg_v12"]["verified"])

    def test_scope_is_narrow_and_payload_has_no_live_coverage_identity(self) -> None:
        payload = exporter.build_payload(ROOT)
        self.assertTrue(payload["scope"]["fixed_rom_copy_source_bytes"])
        for key, value in payload["scope"].items():
            if key != "fixed_rom_copy_source_bytes":
                self.assertFalse(value)
        serialized = json.dumps(payload, sort_keys=True)
        self.assertNotIn(exporter.BASELINE_COVERAGE_SHA256, serialized)
        self.assertNotIn("observed_coverage_state", serialized)

    def test_export_and_independent_verifier_round_trip(self) -> None:
        holder = tempfile.TemporaryDirectory(dir=ROOT / "build/experiments")
        try:
            output = Path(holder.name) / "candidate"
            exporter.export_artifact(ROOT, output)
            report = verifier.verify_artifact(ROOT, output)
            self.assertTrue(report["verified"], report["errors"])
            self.assertTrue(report["contract_ok"])
            self.assertEqual(620, report["promotion_bytes"])
            source = (ROOT / "tools/verify_rom_boot_copy_sources.py").read_text()
            self.assertNotIn("import export_rom_boot_copy_sources", source)
        finally:
            holder.cleanup()

    def test_candidate_and_consumer_mutations_fail_for_the_right_reason(self) -> None:
        rom = bytearray((ROOT / exporter.ROM_PATH).read_bytes())
        with tempfile.TemporaryDirectory() as temp:
            candidate = Path(temp) / "mutated.gba"
            rom[0x4C8] ^= 1
            candidate.write_bytes(rom)
            with mock.patch.object(exporter, "ROM_PATH", candidate), mock.patch.object(
                exporter, "ROM_SHA256", hashlib.sha256(rom).hexdigest()
            ):
                with self.assertRaisesRegex(ValueError, "copy-source bytes changed"):
                    exporter.build_payload(ROOT)

            rom = bytearray((ROOT / exporter.ROM_PATH).read_bytes())
            rom[0x6164A] ^= 1
            candidate.write_bytes(rom)
            with mock.patch.object(exporter, "ROM_PATH", candidate), mock.patch.object(
                exporter, "ROM_SHA256", hashlib.sha256(rom).hexdigest()
            ):
                with self.assertRaisesRegex(ValueError, "local DMA consumer changed"):
                    exporter.build_payload(ROOT)

            rom = bytearray((ROOT / exporter.ROM_PATH).read_bytes())
            rom[0x64634] ^= 1
            candidate.write_bytes(rom)
            with mock.patch.object(exporter, "ROM_PATH", candidate), mock.patch.object(
                exporter, "ROM_SHA256", hashlib.sha256(rom).hexdigest()
            ):
                with self.assertRaisesRegex(ValueError, "v12 CpuSet destination changed"):
                    exporter.build_payload(ROOT)

    def test_output_symlink_ancestor_and_existing_target_are_rejected(self) -> None:
        holder = tempfile.TemporaryDirectory(dir=ROOT / "build/experiments")
        try:
            base = Path(holder.name)
            real = base / "real"; real.mkdir()
            (base / "alias").symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink ancestor"):
                exporter.export_artifact(ROOT, base / "alias" / "candidate")
            output = real / "candidate"
            exporter.export_artifact(ROOT, output)
            with self.assertRaises(FileExistsError):
                exporter.export_artifact(ROOT, output)
        finally:
            holder.cleanup()

    def test_fsync_failure_before_publish_leaves_no_target(self) -> None:
        holder = tempfile.TemporaryDirectory(dir=ROOT / "build/experiments")
        try:
            output = Path(holder.name) / "candidate"
            with mock.patch.object(exporter.os, "fsync", side_effect=OSError("synthetic fsync")):
                with self.assertRaisesRegex(OSError, "synthetic fsync"):
                    exporter.export_artifact(ROOT, output)
            self.assertFalse(output.exists())
        finally:
            holder.cleanup()

    def test_verifier_replays_after_synthetic_coverage_promotion(self) -> None:
        holder = tempfile.TemporaryDirectory(dir=ROOT / "build/experiments")
        try:
            output = Path(holder.name) / "candidate"
            exporter.export_artifact(ROOT, output)
            coverage = json.loads((ROOT / exporter.COVERAGE_PATH).read_text())
            for segment in coverage["segments"]:
                if segment["range"] == [0x3E0, 0x1CD0]:
                    segment["range"] = [0x3E0, 0x4C8]
                    break
            coverage["segments"].insert(1, {
                "range": [0x4C8, 0x734], "primary_class": "synthetic_copy_source",
                "primary_claim_ids": ["synthetic"], "secondary_claim_ids": [],
            })
            synthetic = Path(holder.name) / "coverage.json"
            synthetic.write_text(json.dumps(coverage))
            with mock.patch.object(verifier, "COVERAGE_PATH", synthetic):
                self.assertTrue(verifier.verify_artifact(ROOT, output)["verified"])
        finally:
            holder.cleanup()

    def test_verifier_rejects_non_candidate_descriptor_tampering(self) -> None:
        holder = tempfile.TemporaryDirectory(dir=ROOT / "build/experiments")
        try:
            output = Path(holder.name) / "candidate"
            exporter.export_artifact(ROOT, output)
            payload_path = output / exporter.PAYLOAD_NAME
            manifest_path = output / exporter.MANIFEST_NAME
            payload = json.loads(payload_path.read_text())
            payload["local_dma_consumer"]["dma_descriptor_denominator"][0]["destination"] = "0x03000080"
            raw = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
            payload_path.write_bytes(raw)
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][exporter.PAYLOAD_NAME] = {
                "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()
            }
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            report = verifier.verify_artifact(ROOT, output)
            self.assertFalse(report["verified"])
            self.assertTrue(any("descriptor" in error for error in report["errors"]))
        finally:
            holder.cleanup()

    def test_independent_verifier_rebuilds_local_cfg_and_dma_dataflow(self) -> None:
        rom = (ROOT / exporter.ROM_PATH).read_bytes()
        self.assertEqual(112, len(verifier._decode_local_cfg(rom)))
        self.assertEqual(verifier.EXPECTED_DESCRIPTORS, verifier._rebuild_dma_descriptors(rom))

        tampered = bytearray(rom)
        tampered[0x61652:0x61654] = bytes.fromhex("0160")  # str r1, [r0] instead of str r3, [r0, #8]
        with self.assertRaisesRegex(ValueError, "DMA descriptor dataflow changed"):
            verifier._rebuild_dma_descriptors(bytes(tampered))

        tampered = bytearray(rom)
        tampered[0x61670:0x61672] = bytes.fromhex("00e0")  # unexpected local branch
        with self.assertRaisesRegex(ValueError, "local DMA CFG changed"):
            verifier._decode_local_cfg(bytes(tampered))

    def test_verifier_rejects_rom_upstream_and_promotion_contract_tampering(self) -> None:
        holder = tempfile.TemporaryDirectory(dir=ROOT / "build/experiments")
        try:
            for mutate in (
                lambda payload: payload["rom"].__setitem__("path", "rom/other.gba"),
                lambda payload: payload["upstream_evidence"]["cfg_v12"].__setitem__(
                    "source_code_range", [0x64574, 0x6462E]
                ),
                lambda payload: payload["promotion"].__setitem__("claim_kind", "arm_code"),
            ):
                output = Path(holder.name) / f"candidate-{len(list(Path(holder.name).iterdir()))}"
                exporter.export_artifact(ROOT, output)
                payload_path = output / exporter.PAYLOAD_NAME
                manifest_path = output / exporter.MANIFEST_NAME
                payload = json.loads(payload_path.read_text())
                mutate(payload)
                raw = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
                payload_path.write_bytes(raw)
                manifest = json.loads(manifest_path.read_text())
                manifest["files"][exporter.PAYLOAD_NAME] = {
                    "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()
                }
                manifest_path.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
                )
                report = verifier.verify_artifact(ROOT, output)
                self.assertFalse(report["verified"], report)
                self.assertTrue(
                    any("contract" in error or "evidence" in error for error in report["errors"]),
                    report["errors"],
                )
        finally:
            holder.cleanup()

    def test_verifier_rejects_noncanonical_payload_even_with_updated_digest(self) -> None:
        holder = tempfile.TemporaryDirectory(dir=ROOT / "build/experiments")
        try:
            output = Path(holder.name) / "candidate"
            exporter.export_artifact(ROOT, output)
            payload_path = output / exporter.PAYLOAD_NAME
            manifest_path = output / exporter.MANIFEST_NAME
            payload = json.loads(payload_path.read_text())
            raw = json.dumps(payload, sort_keys=True).encode()
            payload_path.write_bytes(raw)
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][exporter.PAYLOAD_NAME] = {
                "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()
            }
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            report = verifier.verify_artifact(ROOT, output)
            self.assertFalse(report["verified"])
            self.assertTrue(any("canonical" in error for error in report["errors"]))
        finally:
            holder.cleanup()

    def test_parent_fsync_failure_preserves_published_artifact(self) -> None:
        holder = tempfile.TemporaryDirectory(dir=ROOT / "build/experiments")
        calls = 0
        real_fsync = exporter.os.fsync

        def fail_after_publish(fd):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise OSError("synthetic parent fsync")
            return real_fsync(fd)

        try:
            output = Path(holder.name) / "candidate"
            with mock.patch.object(exporter.os, "fsync", side_effect=fail_after_publish):
                with self.assertRaisesRegex(OSError, "synthetic parent fsync"):
                    exporter.export_artifact(ROOT, output)
            self.assertTrue(output.is_dir())
            self.assertTrue(verifier.verify_artifact(ROOT, output)["verified"])
        finally:
            holder.cleanup()
