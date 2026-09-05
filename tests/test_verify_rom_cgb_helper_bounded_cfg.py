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
ROM = ROOT / "rom/base.gba"
EXPERIMENT = ROOT / "build/experiments/active/cgb-helper-contract/codex-r1-20260829"
CONTRACT_SHA256 = "e1f4d0b840d52b19ee996ee7c0ba18c41511f0c96b37f498f77954a24c9105b7"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PROMOTION_PACKED_SHA256 = "87c62bbe5f0e9d25ee5b11398ecdd3ed5b41782d4873871205f71c1122a4c1dc"
PROMOTED_RANGES = [
    [636220, 636256],
    [636256, 636260],
    [636260, 636264],
    [636264, 636268],
    [636268, 636274],
    [636276, 636280],
    [636280, 636294],
    [636296, 636300],
    [636300, 636404],
]
CODE_RANGES = [[636220, 636256], [636260, 636264], [636268, 636274], [636280, 636294], [636300, 636404]]
LITERAL_RANGES = [[636256, 636260], [636264, 636268], [636276, 636280], [636296, 636300]]
EXCLUDED_RANGES = [[636274, 636276], [636294, 636296]]
EXCLUDED_SHA256 = [
    "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
    "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
]
COVERAGE_SHA256 = "22f8f88ca0929468289b749cb94b4aaa4c47d7a53fa68fe10cb93c9a01816839"
COVERAGE_TOTALS = {
    "claim_count": 14507,
    "classified_bytes": 6124601,
    "segment_count": 16617,
    "unknown_bytes": 166855,
}
LITERAL_BINDINGS = [
    {"consumer_offset": 636246, "load_raw_hex": "0249", "range": [636256, 636260], "value": 67108963},
    {"consumer_offset": 636260, "load_raw_hex": "0049", "range": [636264, 636268], "value": 67108969},
    {"consumer_offset": 636268, "load_raw_hex": "0149", "range": [636276, 636280], "value": 67108976},
    {"consumer_offset": 636280, "load_raw_hex": "0349", "range": [636296, 636300], "value": 67108985},
]
UPSTREAM = {
    "m4a_initializer_chain": {
        "manifest_sha256": "9b9b9f2f49a1ee8224703ca47b73dc608d75ba83d2be44564e24873c44237c9c",
        "payload_sha256": "7f019b01e800a3dd769463cbea907049429b1cad416dc17ed8719a561837babd",
    }
}
SCOPE = {
    "allocatable_free_space_proven": False,
    "audio_behavior_proven": False,
    "computed_or_indirect_producer_denominator_complete": False,
    "editing_relocation_writeback_safe": False,
    "global_caller_or_code_denominator_complete": False,
    "global_ram_writer_denominator_complete": False,
    "input_value_domain_complete": False,
    "literal_target_semantics_claimed": False,
    "natural_runtime_reachability": False,
    "target_limited_raw_producer_denominator_complete": True,
}


def _canonical(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=False).encode()


def _rewrite_manifest_identity(candidate: Path, name: str) -> None:
    manifest_path = candidate / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    raw = (candidate / name).read_bytes()
    manifest["files"][name]["sha256"] = hashlib.sha256(raw).hexdigest()
    manifest["files"][name]["size"] = len(raw)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def _load(name):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        return None


class CgbHelperVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exporter = _load("tools.export_rom_cgb_helper_bounded_cfg")
        cls.verifier = _load("tools.verify_rom_cgb_helper_bounded_cfg")

    def _implemented(self):
        self.assertIsNotNone(self.exporter, "CGB helper exporter is absent")
        self.assertIsNotNone(self.verifier, "CGB helper verifier is absent")
        return self.exporter, self.verifier

    def _candidate(self, directory: Path, **kwargs) -> Path:
        exporter, _ = self._implemented()
        target = directory / "candidate"
        exporter.write_candidate(ROOT, target, **kwargs)
        return target

    def test_independent_rebuild_matches_contract_cfg_and_stays_standalone(self) -> None:
        exporter, verifier = self._implemented()
        contract_path = EXPERIMENT / "CONTRACT.json"
        contract = json.loads(contract_path.read_text())
        self.assertEqual(hashlib.sha256(contract_path.read_bytes()).hexdigest(), CONTRACT_SHA256)
        evidence = verifier.independent_rebuild(ROOT, ROM.read_bytes())
        self.assertTrue(evidence["verified"])
        self.assertEqual(evidence["schema"], "rom-cgb-helper-bounded-cfg-verification-v1")
        self.assertEqual(evidence["bundle_sha256"], PROMOTION_PACKED_SHA256)
        self.assertEqual(evidence["bundle_size"], 180)
        payload = evidence["payload"]
        self.assertEqual(payload["rom"], {"path": "rom/base.gba", "size": 6291456, "sha256": ROM_SHA256})
        self.assertEqual(payload["cfg"]["instruction_count"], 82)
        self.assertEqual(payload["cfg"]["code_bytes"], 164)
        self.assertEqual(payload["cfg"]["block_count"], 23)
        self.assertEqual(payload["cfg"]["internal_edge_count"], 29)
        self.assertEqual(payload["cfg"]["external_edge_count"], 0)
        self.assertEqual(payload["cfg"]["structured_return_count"], 2)
        self.assertEqual(payload["cfg"]["frontier_count"], 0)
        self.assertEqual(payload["cfg"]["roots"], contract["cfg"]["roots"])
        self.assertEqual(payload["cfg"]["semantic_instruction_vector_sha256"], "66df11b0f24f38a6aa9aa3b202c5b07b949ff98631ddb3f8c97f46d602d8f5db")
        self.assertEqual(payload["cfg"]["block_range_vector_sha256"], "421415d1f0c255dc581a1076ec73441ef031ed7fd623ce6d8e224b2e51ab55ce")
        self.assertEqual(payload["cfg"]["edge_vector_sha256"], "7c080763f41c5afb6556bc4dcdf44ccd884a96ac8b14d8270aa68f77c36a2978")
        self.assertEqual(len(payload["cfg"]["instructions"]), 82)
        self.assertEqual(len(payload["cfg"]["blocks"]), 23)
        self.assertEqual(len(payload["cfg"]["block_edges"]), 29)
        instruction_offsets = {row["offset"] for row in payload["cfg"]["instructions"]}
        edge_kinds = set()
        for row in payload["cfg"]["instructions"]:
            for edge in row.get("successors", []):
                edge_kinds.add(edge["kind"])
                self.assertIn(edge["target_offset"], instruction_offsets)
                self.assertFalse(any(start <= edge["target_offset"] < end for start, end in EXCLUDED_RANGES))
        self.assertIn("branch", edge_kinds)
        self.assertIn("fallthrough", edge_kinds)
        self.assertEqual([(row["offset"], row["register"]) for row in payload["cfg"]["returns"]], [(636292, "lr"), (636402, "r0")])
        semantic = [[row["offset"], row["size"], row["mnemonic"], row["op_str"]] for row in sorted(payload["cfg"]["instructions"], key=lambda row: row["offset"])]
        blocks = [row["range"] for row in sorted(payload["cfg"]["blocks"], key=lambda row: row["range"][0])]
        edges = sorted([[row["source_instruction_offset"], row["target_offset"], row["kind"]] for row in payload["cfg"]["block_edges"]], key=lambda row: (row[0], 0 if row[2] == "branch" else 1))
        self.assertEqual(hashlib.sha256(_canonical(semantic)).hexdigest(), payload["cfg"]["semantic_instruction_vector_sha256"])
        self.assertEqual(hashlib.sha256(_canonical(blocks)).hexdigest(), payload["cfg"]["block_range_vector_sha256"])
        self.assertEqual(hashlib.sha256(_canonical(edges)).hexdigest(), payload["cfg"]["edge_vector_sha256"])
        self.assertEqual(edges, sorted([[row["offset"], edge["target_offset"], edge["kind"]] for row in payload["cfg"]["instructions"] for edge in row.get("successors", [])], key=lambda row: (row[0], 0 if row[2] == "branch" else 1)))
        self.assertEqual(payload["promotion"]["ranges"], contract["promotion"]["ranges"])
        tree = ast.parse((ROOT / "tools/verify_rom_cgb_helper_bounded_cfg.py").read_text())
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
                imported.extend(alias.name for alias in node.names)
        self.assertNotIn("tools.export_rom_cgb_helper_bounded_cfg", imported)
        self.assertNotIn("export_rom_cgb_helper_bounded_cfg", imported)
        source = (ROOT / "tools/verify_rom_cgb_helper_bounded_cfg.py").read_text()
        self.assertNotIn("import_module", source)
        self.assertNotIn("export_rom_cgb_helper_bounded_cfg", source)
        with mock.patch.object(exporter, "build_payload", side_effect=AssertionError("exporter consulted")), mock.patch.object(exporter, "build_payload_from_rom", side_effect=AssertionError("exporter consulted")):
            self.assertTrue(verifier.independent_rebuild(ROOT, ROM.read_bytes())["verified"])
        self.assertIsNotNone(exporter)

    def test_candidate_requires_opt_in_and_three_files_are_mutation_checked(self) -> None:
        _, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            candidate = self._candidate(Path(temp))
            with self.assertRaisesRegex(ValueError, "candidate"):
                verifier.verify_artifact(ROOT, candidate)
            report = verifier.verify_artifact(ROOT, candidate, allow_candidate=True)
            self.assertEqual(report["artifact_status"], "candidate")
            self.assertTrue(report["verified"])
            for name, mutate in (
                ("rom-cgb-helper-bounded-cfg.bin", lambda value: value.__setitem__(0, value[0] ^ 1)),
                ("rom-cgb-helper-bounded-cfg.json", lambda value: value.__setitem__("schema", "forged")),
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

    def test_coherent_forgery_and_noncanonical_json_are_rejected(self) -> None:
        _, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            source = self._candidate(Path(temp))
            forged = Path(temp) / "coherent-forged"
            shutil.copytree(source, forged)
            payload_path = forged / "rom-cgb-helper-bounded-cfg.json"
            payload = json.loads(payload_path.read_text())
            payload["cfg"]["instruction_count"] = 81
            payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            _rewrite_manifest_identity(forged, payload_path.name)
            with self.assertRaises(ValueError):
                verifier.verify_artifact(ROOT, forged, allow_candidate=True)
            for name in ("rom-cgb-helper-bounded-cfg.json", "manifest.json"):
                target = Path(temp) / (name + "-noncanonical")
                shutil.copytree(source, target)
                path = target / name
                path.write_text(json.dumps(json.loads(path.read_text()), separators=(",", ":")))
                if name != "manifest.json":
                    _rewrite_manifest_identity(target, name)
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, "canonical"):
                    verifier.verify_artifact(ROOT, target, allow_candidate=True)

    def test_rebuild_rejects_promotion_bytes_and_middle_or_gap_cfg_escapes(self) -> None:
        _, verifier = self._implemented()
        original = ROM.read_bytes()
        for start, end in PROMOTED_RANGES:
            changed = bytearray(original)
            changed[start] ^= 1
            with self.subTest(start=start), mock.patch.object(verifier, "_validate_rom"), mock.patch.object(verifier, "_rebuild_cfg", side_effect=AssertionError("CFG rebuild ran")):
                with self.assertRaisesRegex(ValueError, "promotion range"):
                    verifier.independent_rebuild(ROOT, bytes(changed))
        for bad_ranges in (
            [[636221, 636256], *CODE_RANGES[1:]],
            [[636220, 636276], [636280, 636294], [636300, 636404]],
            [[636220, 636256], [636260, 636264], [636268, 636274], [636280, 636294], [636300, 636405]],
        ):
            with self.subTest(bad_ranges=bad_ranges), mock.patch.object(verifier, "EXPECTED_CODE_RANGES", bad_ranges):
                with self.assertRaises(ValueError):
                    verifier.independent_rebuild(ROOT, original)
        for offset, raw in ((636230, b"\x00\xe0"), (636292, b"\x00\x47"), (636246, b"\xff\x49")):
            changed = bytearray(original)
            changed[offset : offset + 2] = raw
            with self.subTest(raw_decoder_offset=offset), self.assertRaises(ValueError):
                verifier.rebuild_cfg_from_rom(bytes(changed))

    def test_raw_target_producer_scan_rejects_all_direct_and_pointer_forms(self) -> None:
        _, verifier = self._implemented()
        original = ROM.read_bytes()
        source = 636000
        root = 636220
        handler = 636300
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
            changed[source : source + len(raw)] = raw
            with self.subTest(form=name), mock.patch.object(verifier, "_validate_rom"):
                with self.assertRaisesRegex(ValueError, "producer.*denominator|denominator.*producer"):
                    verifier.independent_rebuild(ROOT, bytes(changed))

    def test_literals_initializer_owner_and_unknown_gaps_are_rebuilt_independently(self) -> None:
        _, verifier = self._implemented()
        contract = json.loads((EXPERIMENT / "CONTRACT.json").read_text())
        evidence = verifier.independent_rebuild(ROOT, ROM.read_bytes())
        payload = evidence["payload"]
        projection = payload["literal_projection"]
        self.assertEqual(projection["binding_count"], 4)
        self.assertEqual(projection["word_count"], 4)
        self.assertEqual(projection["bytes"], 16)
        self.assertEqual(projection["ranges"], LITERAL_RANGES)
        self.assertEqual(projection["bindings"], LITERAL_BINDINGS)
        for binding in projection["bindings"]:
            halfword = struct.unpack("<H", bytes.fromhex(binding["load_raw_hex"]))[0]
            self.assertEqual(binding["range"][0], ((binding["consumer_offset"] + 4) & ~3) + ((halfword & 0xFF) * 4))
            self.assertFalse(any(binding["range"] == code_range for code_range in CODE_RANGES))
        self.assertEqual(payload["initializer_binding"], contract["initializer_binding"])
        self.assertEqual(payload["upstream_receipts"], UPSTREAM)
        for row, expected_range, expected_sha in zip(payload["excluded_ranges"], EXCLUDED_RANGES, EXCLUDED_SHA256):
            self.assertEqual(row["range"], expected_range)
            self.assertEqual(row["raw_hex"], "0000")
            self.assertEqual(row["sha256"], expected_sha)
            self.assertFalse(row["promoted"])
            self.assertEqual(row["semantic_class"], "unknown")
        for offset in (634224, 634226, 634368):
            changed = bytearray(ROM.read_bytes())
            changed[offset] ^= 1
            with self.subTest(initializer_offset=offset), mock.patch.object(verifier, "_validate_rom"):
                with self.assertRaises(ValueError):
                    verifier.independent_rebuild(ROOT, bytes(changed))

    def test_acceptance_replays_shared_coverage_and_rejects_nonempty_or_escaping_output(self) -> None:
        _, verifier = self._implemented()
        shared = Path("artifacts/rom-cgb-audio-precoverage-v1")
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            root = Path(temp)
            candidate = self._candidate(root, coverage_baseline_artifact=shared)
            accepted = root / "accepted"
            report = verifier.accept_candidate(ROOT, candidate, accepted)
            self.assertEqual(report["artifact_status"], "accepted")
            self.assertTrue(verifier.verify_artifact(ROOT, accepted)["verified"])
            self.assertEqual(verifier.verify_artifact(ROOT, accepted)["artifact_status"], "accepted")
            with mock.patch.object(verifier, "_coverage_from_file", side_effect=AssertionError("live coverage consulted")):
                self.assertEqual(verifier.verify_artifact(ROOT, accepted)["artifact_status"], "accepted")
            for overlap in (candidate, candidate / "accepted", root):
                with self.subTest(overlap=str(overlap)), self.assertRaises(ValueError):
                    verifier.accept_candidate(ROOT, candidate, overlap)
            occupied = root / "occupied"
            occupied.mkdir()
            (occupied / "sentinel").write_text("keep")
            with self.assertRaises(ValueError):
                verifier.accept_candidate(ROOT, candidate, occupied)
            for escaped in (ROOT, ROOT.parent, Path("/tmp/cgb-helper-escape")):
                with self.subTest(escaped=str(escaped)), self.assertRaises(ValueError):
                    verifier.accept_candidate(ROOT, candidate, escaped)
            link = root / "accepted-link"
            link.symlink_to(accepted, target_is_directory=True)
            with self.assertRaises(ValueError):
                verifier.verify_artifact(ROOT, link)
            link_parent = root / "link-parent"
            link_parent.symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                verifier.accept_candidate(ROOT, candidate, link_parent / "new")

    def test_replay_chain_is_independent_of_live_and_corruption_fails(self) -> None:
        _, verifier = self._implemented()
        shared = Path("artifacts/rom-cgb-audio-precoverage-v1")
        with mock.patch.object(verifier, "_coverage_from_file", side_effect=AssertionError("live coverage consulted")):
            evidence = verifier.independent_rebuild(ROOT, ROM.read_bytes(), coverage_baseline_artifact=shared)
        self.assertEqual(evidence["payload"]["coverage_baseline"]["immutable_artifact"]["archive_sha256"], "e345bf5a605d796c1e38a4243b4aefbcb7b8229f70bea13ce40ca044d4edf04b")
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            for case in ("gzip", "manifest", "raw", "recovery"):
                target = Path(temp) / case
                shutil.copytree(ROOT / shared, target)
                manifest_path = target / "manifest.json"
                manifest = json.loads(manifest_path.read_text())
                if case == "gzip":
                    (target / "rom-byte-coverage.json.gz").write_bytes(b"not-gzip")
                elif case == "manifest":
                    manifest["coverage"]["archive"]["sha256"] = "0" * 64
                    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                elif case == "raw":
                    manifest["coverage"]["raw"]["size"] += 1
                    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                else:
                    manifest["recovery"]["kind"] = "mutable-live-file"
                    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                with self.subTest(case=case), self.assertRaises(ValueError):
                    verifier.independent_rebuild(ROOT, ROM.read_bytes(), coverage_baseline_artifact=target.relative_to(ROOT))

    def test_acceptance_rejects_parent_symlink_identity_swap_and_cleans_failed_open(self) -> None:
        _, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp, tempfile.TemporaryDirectory() as outside_raw:
            root = Path(temp)
            candidate = self._candidate(root)
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

            parent.unlink()
            (root / "publish-parent-original").rename(parent)
            replaced = root / "accepted-replaced"
            real_validate = verifier._validate_output

            def replaced_parent_validate(repository, requested):
                target = real_validate(repository, requested)
                parent.rename(root / "publish-parent-original-2")
                parent.mkdir()
                return target

            with mock.patch.object(verifier, "_validate_output", side_effect=replaced_parent_validate):
                with self.assertRaisesRegex(ValueError, "identity|changed|output"):
                    verifier.accept_candidate(ROOT, candidate, parent / replaced.name)
            self.assertFalse((parent / replaced.name).exists())

            parent.rmdir()
            (root / "publish-parent-original-2").rename(parent)
            output = parent / "open-fails"
            real_open = verifier.os.open
            injected = False

            def fail_target_open(path, flags, mode=0o777, *, dir_fd=None):
                nonlocal injected
                if not injected and isinstance(path, str) and path.startswith(f".{output.name}.") and dir_fd is not None:
                    injected = True
                    raise OSError("injected directory open failure")
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with mock.patch.object(verifier.os, "open", side_effect=fail_target_open):
                with self.assertRaisesRegex(OSError, "injected"):
                    verifier.accept_candidate(ROOT, candidate, output)
            self.assertFalse(output.exists())
            self.assertFalse(any(path.name.startswith(f".{output.name}.") for path in output.parent.iterdir()))

    def test_output_contract_rejects_dotdot_and_arbitrary_repo_targets(self) -> None:
        _, verifier = self._implemented()
        self.assertEqual(verifier.CANONICAL_TARGET, Path("artifacts/rom-cgb-helper-bounded-cfg-v1"))
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            root = Path(temp)
            candidate = self._candidate(root)
            for output in (root / "nested" / ".." / "accepted", ROOT / "notes" / "forbidden-helper"):
                with self.subTest(output=str(output)), self.assertRaises(ValueError):
                    verifier.accept_candidate(ROOT, candidate, output)

    def test_accepted_requires_exact_receipts_and_cli_accept_is_mutually_exclusive(self) -> None:
        _, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            root = Path(temp)
            candidate = self._candidate(root)
            forged = root / "status-only"
            shutil.copytree(candidate, forged)
            manifest_path = forged / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["artifact_status"] = "accepted"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "acceptance|receipt"):
                verifier.verify_artifact(ROOT, forged)
            extra = root / "extra-key"
            shutil.copytree(candidate, extra)
            manifest_path = extra / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["forged"] = True
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "manifest.*key|schema"):
                verifier.verify_artifact(ROOT, extra, allow_candidate=True)
            accepted = root / "accepted"
            accepted_report = verifier.accept_candidate(ROOT, candidate, accepted)
            accepted_manifest = json.loads((accepted / "manifest.json").read_text())
            self.assertEqual(set(accepted_manifest), {"schema", "artifact_schema", "artifact_status", "contract_sha256", "files", "acceptance", "verifier", "verification"})
            self.assertEqual(
                accepted_report["candidate_identity"],
                accepted_manifest["acceptance"]["source_candidate_identity"],
            )
            for section in ("acceptance", "verifier", "verification"):
                changed = root / f"accepted-{section}"
                shutil.copytree(accepted, changed)
                path = changed / "manifest.json"
                obj = json.loads(path.read_text())
                obj[section] = {"forged": True}
                path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
                with self.subTest(section=section), self.assertRaisesRegex(ValueError, "acceptance|verifier|verification|receipt"):
                    verifier.verify_artifact(ROOT, changed)
            with (
                mock.patch.object(verifier, "CANONICAL_TARGET", accepted.relative_to(ROOT)),
                mock.patch.object(verifier, "SOURCE_CANDIDATE", candidate.relative_to(ROOT)),
            ):
                self.assertTrue(verifier.verify_artifact(ROOT, accepted)["verified"])
                path = accepted / "manifest.json"
                obj = json.loads(path.read_text())
                obj["acceptance"]["source_candidate_artifact"] = extra.relative_to(ROOT).as_posix()
                path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
                with self.assertRaisesRegex(ValueError, "source-candidate|source candidate|acceptance"):
                    verifier.verify_artifact(ROOT, accepted)
            result = subprocess.run(["python3", "tools/verify_rom_cgb_helper_bounded_cfg.py", str(candidate.relative_to(ROOT)), "--allow-candidate", "--accept-to", str((root / "cli-accepted").relative_to(ROOT))], cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not allowed with argument", result.stderr)

    def test_artifact_members_rom_and_candidate_are_single_anchored_snapshots(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            root = Path(temp)
            candidate = self._candidate(root)
            linked = root / "linked"
            shutil.copytree(candidate, linked)
            member = linked / "rom-cgb-helper-bounded-cfg.bin"
            outside = root / "outside.bin"
            outside.write_bytes(member.read_bytes())
            member.unlink()
            member.symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "symlink"):
                verifier.verify_artifact(ROOT, linked, allow_candidate=True)
            real_safe_file = verifier._safe_file
            rom_reads = 0
            def counted_safe_file(repository, relative):
                nonlocal rom_reads
                path = real_safe_file(repository, relative)
                if Path(relative) == verifier.ROM_PATH:
                    rom_reads += 1
                return path
            with mock.patch.object(verifier, "_safe_file", side_effect=counted_safe_file):
                verifier.verify_artifact(ROOT, candidate, allow_candidate=True)
            self.assertEqual(rom_reads, 1)
            accepted = root / "accepted-race"
            real_verify = verifier.verify_artifact
            def mutate_after_verify(repository, artifact, **kwargs):
                report = real_verify(repository, artifact, **kwargs)
                if kwargs.get("allow_candidate"):
                    path = candidate / "manifest.json"
                    obj = json.loads(path.read_text())
                    obj["raced"] = True
                    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
                return report
            with mock.patch.object(verifier, "verify_artifact", side_effect=mutate_after_verify):
                with self.assertRaisesRegex(ValueError, "candidate.*changed|identity"):
                    verifier.accept_candidate(ROOT, candidate, accepted)
            self.assertFalse(accepted.exists())

    def test_final_acceptance_failure_cleans_owned_output_but_preserves_replacement(self) -> None:
        _, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            root = Path(temp)
            candidate = self._candidate(root)
            accepted = root / "accepted"
            real_verify = verifier.verify_artifact
            calls = 0
            def fail_final(repository, artifact, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise ValueError("forced final verification")
                return real_verify(repository, artifact, **kwargs)
            with mock.patch.object(verifier, "verify_artifact", side_effect=fail_final):
                with self.assertRaisesRegex(ValueError, "forced final"):
                    verifier.accept_candidate(ROOT, candidate, accepted)
            self.assertFalse(accepted.exists())
            calls = 0
            moved = root / "owned-moved"
            sentinel = accepted / "sentinel"
            def replace_then_fail(repository, artifact, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    accepted.rename(moved)
                    accepted.mkdir()
                    sentinel.write_text("replacement\n")
                    raise ValueError("forced replacement race")
                return real_verify(repository, artifact, **kwargs)
            with mock.patch.object(verifier, "verify_artifact", side_effect=replace_then_fail):
                with self.assertRaisesRegex(ValueError, "forced replacement"):
                    verifier.accept_candidate(ROOT, candidate, accepted)
            self.assertEqual(sentinel.read_text(), "replacement\n")

    def test_initializer_semantics_are_independently_decoded_and_upstream_bound(self) -> None:
        _, verifier = self._implemented()
        rom = ROM.read_bytes()
        self.assertEqual(verifier.decode_initializer_semantics(rom)["store"], {"offset": 634226, "source": "r0", "base": "r4", "width": "word", "field_offset": 44})
        for offset, raw in ((634224, bytes.fromhex("2248")), (634226, bytes.fromhex("e162"))):
            changed = bytearray(rom)
            changed[offset : offset + 2] = raw
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, "initializer.*semantic|semantic.*initializer"):
                verifier._initializer(bytes(changed), ROOT)

    def test_cli_reports_candidate_and_scope_names_are_neutral_and_bounded(self) -> None:
        _, verifier = self._implemented()
        source = (ROOT / "tools/verify_rom_cgb_helper_bounded_cfg.py").read_text()
        self.assertNotIn("CgbSoundStop", source)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            candidate = self._candidate(Path(temp))
            command = [
                "python3",
                "tools/verify_rom_cgb_helper_bounded_cfg.py",
                str(candidate.relative_to(ROOT)),
                "--allow-candidate",
            ]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual(report["artifact_status"], "candidate")
            self.assertTrue(report["verified"])
            payload = verifier.independent_rebuild(ROOT, ROM.read_bytes())["payload"]
            self.assertEqual(payload["scope"], SCOPE)
            self.assertEqual([row["id"] for row in payload["cfg"]["roots"]], ["cgb_helper_09b53c", "cgb_helper_09b58c"])
            self.assertNotIn("CgbSoundStop", json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
