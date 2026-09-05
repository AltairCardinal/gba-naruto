from __future__ import annotations

import ast
import gzip
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/mp2k-dispatcher-contract/codex-r1-20260829"
ROM = ROOT / "rom/base.gba"
PACKED_SHA256 = "83f220623fff3f5effb8bf6cd21b7e7ce8d543ab660d7fa721b8632bd26b3bd5"
RANGES = [[638132, 638178], [638244, 638256], [638404, 638444], [638460, 638464]]
COVERAGE_SHA256 = "3926d1cd6e09c8b45b85cb33d0b2f77d83578ec71c17d61fa1282d863f220735"
COVERAGE_TOTALS = {
    "claim_count": 14503,
    "classified_bytes": 6124499,
    "segment_count": 16614,
    "unknown_bytes": 166957,
}


def _load(name):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        return None


def _archive_fixture(directory: Path, *, recovery_kind: str = "direct-frozen-prepromotion-snapshot") -> Path:
    directory.mkdir()
    raw = (ROOT / "sequel/rom-byte-coverage.json").read_bytes()
    compressed = gzip.compress(raw, mtime=0)
    (directory / "rom-byte-coverage.json.gz").write_bytes(compressed)
    (directory / "manifest.json").write_text(json.dumps({
        "schema": "rom-byte-coverage-prepromotion-baseline-v1",
        "artifact_status": "accepted",
        "coverage": {
            "raw": {"canonical_json": True, "schema": "rom-byte-coverage-v1", "sha256": COVERAGE_SHA256, "size": len(raw), "summary": COVERAGE_TOTALS},
            "archive": {"compression": "gzip", "file": "rom-byte-coverage.json.gz", "sha256": hashlib.sha256(compressed).hexdigest(), "size": len(compressed)},
        },
        "recovery": {"kind": recovery_kind},
    }, indent=2, sort_keys=True) + "\n")
    return directory


class Mp2kDispatcherVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exporter = _load("tools.export_rom_mp2k_dispatcher")
        cls.verifier = _load("tools.verify_rom_mp2k_dispatcher")

    def _implemented(self):
        self.assertIsNotNone(self.exporter, "MP2K dispatcher exporter is absent")
        self.assertIsNotNone(self.verifier, "MP2K dispatcher verifier is absent")
        return self.exporter, self.verifier

    def _candidate(self, directory: Path, **kwargs) -> Path:
        exporter, _ = self._implemented()
        target = directory / "candidate"
        exporter.write_candidate(ROOT, target, **kwargs)
        return target

    def test_independent_rebuild_matches_contract_and_is_standalone(self) -> None:
        exporter, verifier = self._implemented()
        evidence = verifier.independent_rebuild(ROOT, ROM.read_bytes())
        self.assertTrue(evidence["verified"])
        self.assertEqual(evidence["schema"], "rom-mp2k-dispatcher-verification-v1")
        self.assertEqual(evidence["bundle_sha256"], PACKED_SHA256)
        self.assertEqual(evidence["bundle_size"], 102)
        self.assertEqual(evidence["payload"]["promotion"]["ranges"], RANGES)
        self.assertEqual(evidence["payload"]["cfg"]["summary"]["instruction_count"], 129)
        self.assertEqual(evidence["payload"]["dispatcher"]["table"]["entry_count"], 18)
        self.assertEqual(evidence["producer_denominator"]["scan"]["alignment_bytes_by_form"], {
            "arm_b": 4,
            "arm_bl": 4,
            "bytewise_u32_entry": 1,
            "bytewise_u32_thumb_pointer": 1,
            "thumb_b": 2,
            "thumb_b_conditional": 2,
            "thumb_bl": 2,
        })
        tree = ast.parse((ROOT / "tools/verify_rom_mp2k_dispatcher.py").read_text())
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        self.assertNotIn("tools.export_rom_mp2k_dispatcher", imported)
        self.assertNotIn("export_rom_mp2k_dispatcher", imported)
        self.assertNotIn("capstone", imported)

    def test_candidate_requires_explicit_opt_in_and_validates_three_files(self) -> None:
        _, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            candidate = self._candidate(Path(temp))
            with self.assertRaisesRegex(ValueError, "candidate"):
                verifier.verify_artifact(ROOT, candidate)
            report = verifier.verify_artifact(ROOT, candidate, allow_candidate=True)
            self.assertEqual(report["artifact_status"], "candidate")
            self.assertTrue(report["verified"])
            for name, mutate in (
                ("rom-mp2k-dispatcher.bin", lambda value: value.__setitem__(0, value[0] ^ 1)),
                ("rom-mp2k-dispatcher.json", lambda value: value.__setitem__("schema", "forged")),
                ("manifest.json", lambda value: value.__setitem__("artifact_schema", "forged")),
            ):
                target = Path(temp) / (name.replace(".", "-") + "-mutated")
                shutil.copytree(candidate, target)
                path = target / name
                if path.suffix == ".bin":
                    blob = bytearray(path.read_bytes())
                    mutate(blob)
                    path.write_bytes(blob)
                else:
                    obj = json.loads(path.read_text())
                    mutate(obj)
                    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
                with self.subTest(name=name), self.assertRaises(ValueError):
                    verifier.verify_artifact(ROOT, target, allow_candidate=True)

    def test_rebuild_rejects_every_promotion_byte_and_cfg_frontier_or_middle_escape(self) -> None:
        _, verifier = self._implemented()
        original = ROM.read_bytes()
        for start, end in RANGES:
            changed = bytearray(original)
            changed[start] ^= 1
            with self.subTest(start=start), mock.patch.object(verifier, "_validate_rom"), mock.patch.object(verifier, "_rebuild_cfg", side_effect=AssertionError("CFG rebuild ran")):
                with self.assertRaisesRegex(ValueError, "promotion range"):
                    verifier.independent_rebuild(ROOT, bytes(changed))
        with mock.patch.object(verifier, "EXPECTED_CODE_RANGES", [[638133, 638178], [638256, 638458], [638464, 638476]]):
            with self.assertRaises(ValueError):
                verifier.independent_rebuild(ROOT, original)

    def test_rebuild_raw_target_producer_scan_rejects_injected_forms(self) -> None:
        _, verifier = self._implemented()
        original = ROM.read_bytes()
        source = 638000
        root = 638132
        handler = 638256
        delta = root - (source + 4)
        variants = {
            "thumb_b": struct.pack("<H", 0xE000 | ((delta >> 1) & 0x07FF)),
            "thumb_b_conditional": struct.pack("<H", 0xD000 | ((delta >> 1) & 0x00FF)),
            "thumb_bl": struct.pack("<HH", 0xF000 | ((delta >> 12) & 0x07FF), 0xF800 | ((delta >> 1) & 0x07FF)),
            "arm_b": struct.pack("<I", 0xEA000000 | (((root - (source + 8)) >> 2) & 0x00FFFFFF)),
            "arm_bl": struct.pack("<I", 0xEB000000 | (((root - (source + 8)) >> 2) & 0x00FFFFFF)),
            "bytewise_u32_entry": struct.pack("<I", 0x08000000 + handler),
            "bytewise_u32_thumb_pointer": struct.pack("<I", 0x08000000 + root + 1),
        }
        for name, raw in variants.items():
            changed = bytearray(original)
            changed[source:source + len(raw)] = raw
            with self.subTest(form=name), mock.patch.object(verifier, "_validate_rom"):
                with self.assertRaisesRegex(ValueError, "producer.*denominator|denominator.*producer"):
                    verifier.independent_rebuild(ROOT, bytes(changed))

    def test_opaque_call_fallthrough_and_raw_dispatch_boundaries_are_checked(self) -> None:
        _, verifier = self._implemented()
        expected = verifier.independent_rebuild(ROOT, ROM.read_bytes())["payload"]
        call = expected["cfg"]["calls"][0]
        self.assertEqual(call["source_instruction_offset"], 638452)
        self.assertEqual(call["target_offset"], 639256)
        self.assertEqual(call["resolution"], "opaque_thumb_bl")
        self.assertTrue(any(edge["kind"] == "fallthrough" and edge["target_offset"] == 638456 for edge in expected["cfg"]["instructions"][-10:][0].get("successors", [])) or any(edge.get("target_offset") == 638456 for node in expected["cfg"]["instructions"] for edge in node.get("successors", [])))
        with mock.patch.object(verifier, "TABLE_TARGETS", [*expected["dispatcher"]["table"]["targets"][:-1], 638434]):
            with self.assertRaises(ValueError):
                verifier.independent_rebuild(ROOT, ROM.read_bytes())

    def test_candidate_027_relation_and_partition_are_immutable(self) -> None:
        _, verifier = self._implemented()
        payload = verifier.independent_rebuild(ROOT, ROM.read_bytes())["payload"]
        self.assertEqual(payload["provenance"]["candidate_027"]["status"], "rejected")
        self.assertEqual(payload["provenance"]["candidate_027"]["relation"], "crosses_canonical_table_boundary")
        self.assertEqual(payload["provenance"]["candidate_027"]["partitions"], [[638180, 638184], [638184, 638244]])

    def test_acceptance_replays_embedded_candidate_and_rejects_nonempty_or_escaping_output(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            root = Path(temp)
            archive = _archive_fixture(root / "precoverage")
            candidate = self._candidate(root, coverage_baseline_artifact=archive.relative_to(ROOT))
            accepted = root / "accepted"
            report = verifier.accept_candidate(ROOT, candidate, accepted)
            self.assertEqual(report["artifact_status"], "accepted")
            self.assertEqual(verifier.verify_artifact(ROOT, accepted)["artifact_status"], "accepted")
            self.assertTrue((accepted / "candidate").is_dir())
            occupied = root / "occupied"
            occupied.mkdir()
            (occupied / "sentinel").write_text("keep")
            with self.assertRaises(ValueError):
                verifier.accept_candidate(ROOT, candidate, occupied)
            with self.assertRaises(ValueError):
                verifier.accept_candidate(ROOT, candidate, ROOT.parent / "mp2k-dispatcher-escape")
            link = root / "accepted-link"
            link.symlink_to(accepted, target_is_directory=True)
            with self.assertRaises(ValueError):
                verifier.verify_artifact(ROOT, link)

    def test_acceptance_rejects_toc_tou_parent_symlink_swap(self) -> None:
        _, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp, tempfile.TemporaryDirectory() as outside_raw:
            root = Path(temp)
            archive = _archive_fixture(root / "precoverage")
            candidate = self._candidate(root, coverage_baseline_artifact=archive.relative_to(ROOT))
            parent = root / "publish-parent"
            parent.mkdir()
            output = parent / "accepted"
            real_validate = verifier._validate_output

            def raced_validate(repository, requested):
                target = real_validate(repository, requested)
                parent.rename(root / "publish-parent-original")
                parent.symlink_to(Path(outside_raw), target_is_directory=True)
                return target

            with mock.patch.object(verifier, "_validate_output", side_effect=raced_validate):
                with self.assertRaisesRegex(ValueError, "symlink|anchor|output"):
                    verifier.accept_candidate(ROOT, candidate, output)
            self.assertFalse((Path(outside_raw) / "accepted").exists())

    def test_acceptance_rejects_real_parent_identity_swap_and_preserves_replacement(self) -> None:
        _, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            root = Path(temp)
            archive = _archive_fixture(root / "precoverage")
            candidate = self._candidate(root, coverage_baseline_artifact=archive.relative_to(ROOT))
            parent = root / "publish-parent"
            parent.mkdir()
            output = parent / "accepted"
            real_validate = verifier._validate_output

            def replaced_parent_validate(repository, requested):
                validated = real_validate(repository, requested)
                parent.rename(root / "publish-parent-original")
                parent.mkdir()
                return validated

            with mock.patch.object(verifier, "_validate_output", side_effect=replaced_parent_validate):
                with self.assertRaisesRegex(ValueError, "identity|changed|output"):
                    verifier.accept_candidate(ROOT, candidate, output)
            self.assertFalse(output.exists())

            parent.rmdir()
            (root / "publish-parent-original").rename(parent)
            replacement: list[Path] = []

            def replace_owned_directory(_directory_fd, _name, _raw):
                owned = next(path for path in parent.iterdir() if path.name == "accepted" or path.name.startswith(".accepted."))
                owned.rename(parent / f"{owned.name}.owned")
                owned.mkdir()
                (owned / "sentinel").write_text("keep")
                replacement.append(owned)
                raise OSError("injected write failure")

            with mock.patch.object(verifier, "_write_file_at", side_effect=replace_owned_directory):
                with self.assertRaisesRegex(OSError, "injected"):
                    verifier.accept_candidate(ROOT, candidate, output)
            self.assertEqual(len(replacement), 1)
            self.assertEqual((replacement[0] / "sentinel").read_text(), "keep")

    def test_acceptance_cleans_owned_directory_when_open_fails(self) -> None:
        _, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            root = Path(temp)
            archive = _archive_fixture(root / "precoverage")
            candidate = self._candidate(root, coverage_baseline_artifact=archive.relative_to(ROOT))
            output = root / "accepted"
            real_open = verifier.os.open

            def fail_target_open(path, flags, mode=0o777, *, dir_fd=None):
                if path == output.name and dir_fd is not None:
                    raise OSError("injected directory open failure")
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with mock.patch.object(verifier.os, "open", side_effect=fail_target_open):
                with self.assertRaisesRegex(OSError, "injected"):
                    verifier.accept_candidate(ROOT, candidate, output)
            self.assertFalse(output.exists())

    def test_optional_accepted_precoverage_replay_does_not_consult_live_coverage(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            root = Path(temp)
            archive = _archive_fixture(root / "precoverage")
            candidate = self._candidate(root, coverage_baseline_artifact=archive.relative_to(ROOT))
            accepted = root / "accepted"
            verifier.accept_candidate(ROOT, candidate, accepted)
            shutil.rmtree(ROOT / "build/experiments/active/mp2k-dispatcher-contract/codex-r1-20260829/nonexistent", ignore_errors=True)
            with mock.patch.object(verifier, "_coverage_from_file", side_effect=AssertionError("live coverage consulted")):
                self.assertEqual(verifier.verify_artifact(ROOT, accepted)["artifact_status"], "accepted")
            with self.assertRaisesRegex(ValueError, "embedded coverage|external coverage"):
                verifier.verify_artifact(ROOT, accepted, coverage_baseline_artifact=archive.relative_to(ROOT))

    def test_accepted_artifact_replays_without_external_source_candidate(self) -> None:
        _, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            root = Path(temp)
            archive = _archive_fixture(root / "precoverage")
            candidate = self._candidate(root, coverage_baseline_artifact=archive.relative_to(ROOT))
            accepted = root / "accepted"
            verifier.accept_candidate(ROOT, candidate, accepted)
            shutil.rmtree(candidate)
            report = verifier.verify_artifact(ROOT, accepted)
            self.assertEqual(report["artifact_status"], "accepted")
            self.assertTrue(report["contract_ok"])
            acceptance = json.loads((accepted / "manifest.json").read_text())["acceptance"]
            self.assertNotIn("source_candidate_artifact", acceptance)
            self.assertNotIn("source_candidate_identity", acceptance)

    def test_precoverage_recovery_kind_is_fail_closed(self) -> None:
        _, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            archive = _archive_fixture(Path(temp) / "precoverage", recovery_kind="mutable-live-file")
            with self.assertRaisesRegex(ValueError, "recovery"):
                verifier.independent_rebuild(ROOT, ROM.read_bytes(), coverage_baseline_artifact=archive.relative_to(ROOT))

    def test_path_validation_rejects_repo_root_parent_absolute_and_symlink_components(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            root = Path(temp)
            candidate = self._candidate(root)
            for output in (ROOT, ROOT.parent, "/tmp/mp2k-dispatcher-escape"):
                with self.subTest(output=str(output)), self.assertRaises(ValueError):
                    exporter.write_candidate(ROOT, output)
            link_parent = root / "parent-link"
            link_parent.symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                verifier._validate_output(ROOT, link_parent / "new")
            with self.assertRaises(ValueError):
                verifier.accept_candidate(ROOT, candidate, root / "candidate")

    def test_cli_verification_reports_candidate_status(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            candidate = self._candidate(Path(temp))
            command = ["python3", "tools/verify_rom_mp2k_dispatcher.py", str(candidate.relative_to(ROOT)), "--allow-candidate"]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual(report["artifact_status"], "candidate")
            self.assertTrue(report["verified"])


if __name__ == "__main__":
    unittest.main()
