"""Frozen Tier-1 contract tests for the 0x078E38 task callback closure."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import export_rom_task_callback_078e38_closure as exporter
from tools import verify_rom_task_callback_078e38_closure as verifier


ROOT = Path(__file__).resolve().parents[1]


class TaskCallback078E38ClosureTests(unittest.TestCase):
    def test_rebuilds_frozen_closure_denominators_and_hashes(self) -> None:
        payload = exporter.build_payload(ROOT)
        closure = payload["closure"]
        self.assertEqual(342, closure["instruction_count"])
        self.assertEqual(61, closure["basic_block_count"])
        self.assertEqual(718, closure["code_bytes"])
        self.assertEqual(15, closure["literal_reference_count"])
        self.assertEqual(15, closure["unique_literal_word_count"])
        self.assertEqual(60, closure["literal_bytes"])
        self.assertEqual(17, closure["opaque_call_count"])
        self.assertEqual(7, closure["opaque_unique_target_count"])
        self.assertEqual(0, closure["structured_return_count"])
        self.assertEqual(1, closure["frontier_count"])
        self.assertEqual(
            [{"source": 0x079144, "reason": "indirect_pc_target"}],
            closure["frontiers"],
        )
        self.assertNotIn("structured_return", closure)
        self.assertEqual(exporter.C.CODE_PACKED_SHA256, closure["code_bytes_sha256"])
        self.assertEqual(exporter.C.LITERAL_PACKED_SHA256, closure["literal_bytes_sha256"])
        self.assertEqual(exporter.C.CODE_THEN_LITERAL_SHA256, closure["code_then_literal_sha256"])
        self.assertEqual(exporter.C.ADDRESS_ORDER_UNION_SHA256, closure["address_order_union_sha256"])
        self.assertEqual(exporter.C.HOLES_PACKED_SHA256, closure["holes_bytes_sha256"])

    def test_producer_and_lifecycle_are_rebuilt_and_owner_bound(self) -> None:
        payload = exporter.build_payload(ROOT)
        producer = payload["producer"]
        self.assertEqual([], producer["direct_matches"])
        self.assertEqual([0x079378], producer["pointer_occurrences"])
        lifecycle = payload["lifecycle"]
        self.assertEqual(0x0792C0, lifecycle["callback_stack_store"])
        self.assertEqual(0x0626B4, lifecycle["allocator_root"])
        self.assertEqual(0x28, lifecycle["callback_field"])
        self.assertEqual(0x03003BB8, lifecycle["pool_base"])
        self.assertEqual(128, lifecycle["pool_records"])
        self.assertEqual(0x3C, lifecycle["record_size"])
        self.assertEqual(0x062940, lifecycle["dispatcher_root"])
        self.assertEqual(0x09C114, lifecycle["dispatch_veneer"])
        self.assertTrue(lifecycle["source_owner_verified"])
        self.assertTrue(lifecycle["allocator_owner_verified"])
        self.assertTrue(lifecycle["dispatcher_owner_verified"])
        self.assertTrue(lifecycle["field_contract_replayed"])
        self.assertFalse(lifecycle["whole_field_artifact_verifier_claimed"])

    def test_immutable_precoverage_only_and_exact_promotion(self) -> None:
        live = ROOT / "sequel/rom-byte-coverage.json"
        original = Path.read_bytes

        def guarded(path: Path) -> bytes:
            if Path(path).resolve() == live.resolve():
                raise AssertionError("live coverage must not be read")
            return original(path)

        with mock.patch.object(Path, "read_bytes", guarded):
            payload = exporter.build_payload(ROOT)
        promotion = payload["promotion"]
        self.assertEqual(16, len(promotion["claims"]))
        self.assertEqual(778, promotion["promotion_bytes"])
        self.assertEqual(10, promotion["unknown_hole_bytes"])
        self.assertEqual("unknown", promotion["holes_remain_primary_class"])

    def test_return_candidate_stays_unresolved_without_opaque_callee_proof(self) -> None:
        closure = exporter.build_payload(ROOT)["closure"]
        candidate = closure["return_candidate"]
        self.assertEqual([0x079136, 0x079146], candidate["epilogue_range"])
        self.assertFalse(candidate["opaque_callee_stack_effects_proven"])
        self.assertFalse(candidate["structured_return_proven"])

        rom = bytearray((ROOT / exporter.C.ROM_PATH).read_bytes())
        for offset in (0x078E38, 0x079136, 0x07913A, 0x079142, 0x079144):
            with self.subTest(offset=hex(offset)):
                changed = bytearray(rom)
                changed[offset] ^= 1
                with self.assertRaisesRegex(ValueError, "return candidate|closure"):
                    exporter._cfg(bytes(changed))

    def test_direct_scan_includes_final_two_byte_halfword(self) -> None:
        rom = bytes.fromhex("00bffee7")
        self.assertEqual(
            [[2, 2, "thumb_b", 2]],
            exporter._scan_direct_matches(rom, {2}, (-1, -1)),
        )

    def test_representative_rom_mutations_fail_closed(self) -> None:
        rom = bytearray((ROOT / exporter.C.ROM_PATH).read_bytes())
        for offset, message in ((0x078E50, "closure"), (0x078E70, "closure|literal"),
                                (0x0792C0, "lifecycle"), (0x062760, "lifecycle"),
                                (0x062954, "lifecycle")):
            with self.subTest(offset=hex(offset)):
                changed = bytearray(rom)
                changed[offset] ^= 1
                with self.assertRaisesRegex(ValueError, message):
                    exporter._build_from_rom(ROOT, bytes(changed), verify_rom_identity=False)

    def test_export_roundtrip_independent_verifier_and_tamper(self) -> None:
        (ROOT / exporter.C.EXPERIMENT_ROOT).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / exporter.C.EXPERIMENT_ROOT) as directory:
            output = Path(directory) / "candidate"
            exporter.export_artifact(ROOT, output)
            report = verifier.verify_artifact(ROOT, output)
            self.assertTrue(report["verified"], report)
            manifest = json.loads((output / exporter.C.MANIFEST_NAME).read_text())
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual(0, manifest["verifier"]["exit_code"])
            self.assertTrue(manifest["verifier"]["report"]["verified"])
            source = (ROOT / "tools/verify_rom_task_callback_078e38_closure.py").read_text()
            self.assertNotIn(
                "from tools import export_rom_task_callback_078e38_closure",
                source,
            )
            payload_path = output / exporter.C.PAYLOAD_NAME
            payload = json.loads(payload_path.read_text())
            payload["promotion"]["promotion_bytes"] += 1
            raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
            payload_path.write_bytes(raw)
            manifest_path = output / exporter.C.MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][exporter.C.PAYLOAD_NAME] = {
                "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            self.assertFalse(verifier.verify_artifact(ROOT, output)["verified"])

    def test_verifier_rejects_deleted_or_semantically_tampered_contract_fields(self) -> None:
        (ROOT / exporter.C.EXPERIMENT_ROOT).mkdir(parents=True, exist_ok=True)
        mutations = (
            ("closure deletion", lambda p, m: p["closure"].pop("blocks")),
            ("claim kind", lambda p, m: p["promotion"]["claims"][0].__setitem__("kind", "forged")),
            ("lifecycle", lambda p, m: p["lifecycle"].__setitem__("dispatcher_root", 0)),
            ("scope", lambda p, m: p["scope"].__setitem__("natural_runtime_reachability", True)),
            ("implementation", lambda p, m: m["implementation"]["verifier"].__setitem__("sha256", "0" * 64)),
        )
        with tempfile.TemporaryDirectory(dir=ROOT / exporter.C.EXPERIMENT_ROOT) as directory:
            for index, (label, mutate) in enumerate(mutations):
                with self.subTest(label=label):
                    output = Path(directory) / f"candidate-{index}"
                    exporter.export_artifact(ROOT, output)
                    payload_path = output / exporter.C.PAYLOAD_NAME
                    manifest_path = output / exporter.C.MANIFEST_NAME
                    payload = json.loads(payload_path.read_text())
                    manifest = json.loads(manifest_path.read_text())
                    mutate(payload, manifest)
                    raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
                    payload_path.write_bytes(raw)
                    manifest["files"][exporter.C.PAYLOAD_NAME] = {
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "size": len(raw),
                    }
                    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                    self.assertFalse(verifier.verify_artifact(ROOT, output)["verified"])

    def test_export_refuses_to_publish_when_independent_verifier_fails(self) -> None:
        (ROOT / exporter.C.EXPERIMENT_ROOT).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / exporter.C.EXPERIMENT_ROOT) as directory:
            output = Path(directory) / "candidate"
            failed = {
                "schema": exporter.C.VERIFY_SCHEMA,
                "verified": False,
                "contract_ok": False,
                "errors": ["injected verifier failure"],
                "promotion_bytes": None,
            }
            with mock.patch.object(verifier, "verify_artifact", return_value=failed):
                with self.assertRaisesRegex(ValueError, "independent verifier"):
                    exporter.export_artifact(ROOT, output)
            self.assertFalse(output.exists())

    def test_publish_rejects_staging_name_swap_after_candidate_verification(self) -> None:
        (ROOT / exporter.C.EXPERIMENT_ROOT).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / exporter.C.EXPERIMENT_ROOT) as directory:
            output = Path(directory) / "candidate"
            original_publish = exporter._publish_exclusive_at

            def swap_then_publish(parent_fd, source_name, destination_name):
                os.rename(
                    source_name,
                    "held-verified-stage",
                    src_dir_fd=parent_fd,
                    dst_dir_fd=parent_fd,
                )
                os.mkdir(source_name, dir_fd=parent_fd)
                return original_publish(parent_fd, source_name, destination_name)

            with mock.patch.object(
                exporter,
                "_publish_exclusive_at",
                side_effect=swap_then_publish,
            ):
                with self.assertRaisesRegex(ValueError, "published artifact identity"):
                    exporter.export_artifact(ROOT, output)
            self.assertFalse(output.exists())

    def test_artifact_member_and_output_path_safety(self) -> None:
        (ROOT / exporter.C.EXPERIMENT_ROOT).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / exporter.C.EXPERIMENT_ROOT) as directory:
            base = Path(directory)
            output = base / "candidate"
            exporter.export_artifact(ROOT, output)
            (output / "extra").write_text("no")
            self.assertFalse(verifier.verify_artifact(ROOT, output)["verified"])
            with self.assertRaises(FileExistsError):
                exporter.export_artifact(ROOT, output)
            link = base / "link"
            link.symlink_to(base, target_is_directory=True)
            with self.assertRaises(ValueError):
                exporter.export_artifact(ROOT, link / "escape")
            with self.assertRaises(ValueError):
                exporter.export_artifact(ROOT, Path("../escape"))
            artifact_link = base / "artifact-link"
            artifact_link.symlink_to(output, target_is_directory=True)
            self.assertFalse(verifier.verify_artifact(ROOT, artifact_link)["verified"])
            self.assertFalse(verifier.verify_artifact(ROOT, Path("../escape"))["verified"])

    def test_verifier_reads_opened_directory_snapshot_during_path_swap(self) -> None:
        (ROOT / exporter.C.EXPERIMENT_ROOT).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / exporter.C.EXPERIMENT_ROOT) as directory:
            output = Path(directory) / "candidate"
            exporter.export_artifact(ROOT, output)
            real_open = os.open
            swapped = False

            def racing_open(path, flags, mode=0o777, *, dir_fd=None):
                nonlocal swapped
                fd = real_open(path, flags, mode, dir_fd=dir_fd)
                if path == output.name and dir_fd is not None and not swapped:
                    swapped = True
                    os.rename(
                        output.name,
                        "held-candidate",
                        src_dir_fd=dir_fd,
                        dst_dir_fd=dir_fd,
                    )
                    os.mkdir(output.name, dir_fd=dir_fd)
                    (output / "attacker").write_text("replacement")
                return fd

            with mock.patch.object(verifier.os, "open", side_effect=racing_open):
                report = verifier.verify_artifact(ROOT, output)
            self.assertTrue(swapped)
            self.assertTrue(report["verified"], report)

    def test_atomic_publish_requires_platform_no_replace(self) -> None:
        (ROOT / exporter.C.EXPERIMENT_ROOT).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / exporter.C.EXPERIMENT_ROOT) as directory:
            parent = Path(directory)
            source = parent / "source"
            destination = parent / "destination"
            source.mkdir()
            with mock.patch.object(exporter.sys, "platform", "unsupported"):
                with self.assertRaises(OSError):
                    exporter._publish_exclusive(source, destination)


if __name__ == "__main__":
    unittest.main()
