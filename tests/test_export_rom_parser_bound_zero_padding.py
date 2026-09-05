from __future__ import annotations

import ast
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "build/experiments/active/parser-bound-zero-padding/codex-r4-20260821"
FINAL = RUN / "final"
SCHEMA = "rom-parser-bound-zero-padding-v1"
PAYLOAD_NAME = "rom-parser-bound-zero-padding.json"
BUNDLE_NAME = "parser-bound-zero-padding.bin"

EXPECTED_GROUPS = {
    "m4a_wave_alignment_zero_padding": {
        "structure_count": 62,
        "structure_bytes": 122,
        "structure_range_sha256": "d6d1ff7eb0a8a1951b7b41d2068ba6553ce2fa55a59d9fbd634b12fb8a504acc",
        "accepted_count": 57,
        "accepted_bytes": 113,
        "accepted_range_sha256": "419028d3e627c2a81f1a46182f417b59fb4d444e60875761c01ef496dc62a9e5",
        "accepted_packed_sha256": "951b1c95584b91fd8776e1d26b25d745ad5d508f6337686b9f7131d7c2f7096a",
        "structural_rejected_count": 5,
        "structural_rejected_bytes": 9,
        "structural_rejected_range_sha256": "ef0f19220f9e98fa22f5ae65633df50f5b0062950b6885df5a208a106694cae1",
        "structural_rejected_bytes_sha256": "3863ffe80e143fa7f2003da77bd2d5fd705da5f440f88efbd88a710e149bd147",
    },
    "chapter_terminal_to_fixed_root_zero_padding": {
        "structure_count": 89,
        "structure_bytes": 3764,
        "structure_range_sha256": "5dd8da7a37873fd409f9b2964dd7626f04ff3a6836f13c39b0f4183099dc9f98",
        "accepted_count": 85,
        "accepted_bytes": 85,
        "accepted_range_sha256": "a49ad4eb183548d973bded8f8f3b25beef69166eeb4b5ba10daf477174d49a56",
        "accepted_packed_sha256": "6a3a9301bb8dd782bb5c170bedfa73e9e7c60235e6e1840f14bd14b812127ef2",
        "all_gap_count": 91,
        "all_gap_bytes": 3769,
        "all_gap_range_sha256": "a837e8ad9e59d3016bb527b3ca2a4bf3bebf828327328744847a38e106cb1d3b",
        "all_gap_bytes_sha256": "93b2b61f760b4e7d94f241e73e986b155ddd2926219d74d37834f75ec3f62d04",
        "structural_rejected_count": 4,
        "structural_rejected_bytes": 3679,
        "structural_rejected_range_sha256": "606cf93f1815780c140721bd42e19c8495735e4aad8c2db097b8043121b082c7",
        "structural_rejected_bytes_sha256": "bc16b3f0db513d90b092baee021e2ef834f995d27a2191e504f3d97da0bade56",
        "contract_excluded_count": 2,
        "contract_excluded_bytes": 5,
        "contract_excluded_range_sha256": "a921f64f02561dade5a990b79f2094c67420c970f33f36bb25e729aca8887e2f",
        "contract_excluded_bytes_sha256": "cb54af94086516aeda8d7ea81ee1335e14d2ca13e9df113319b0c42280fc91d2",
    },
}


def _compact_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


class ParserPaddingEvidenceHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_parser_bound_zero_padding import export_artifact

        export_artifact(ROOT, FINAL)

    def _fixture_final(self) -> Path:
        return FINAL

    def _copy_current_fixture(self, directory: str) -> Path:
        target = Path(directory).resolve() / "final"
        shutil.copytree(self._fixture_final(), target)
        payload_path = target / PAYLOAD_NAME
        manifest_path = target / "manifest.json"
        payload = json.loads(payload_path.read_text())
        manifest = json.loads(manifest_path.read_text())
        implementation = {
            "exporter_sha256": hashlib.sha256(
                (ROOT / "tools/export_rom_parser_bound_zero_padding.py").read_bytes()
            ).hexdigest(),
            "verifier_sha256": hashlib.sha256(
                (ROOT / "tools/verify_rom_parser_bound_zero_padding.py").read_bytes()
            ).hexdigest(),
            "test_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
        payload["implementation"] = implementation
        payload_path.write_bytes(_canonical_bytes(payload))
        manifest["producer"].update(implementation)
        manifest["producer"]["command"] = [
            "python3",
            "tools/export_rom_parser_bound_zero_padding.py",
            "--root",
            ".",
            "--output-dir",
            RUN.relative_to(ROOT).joinpath("final").as_posix(),
        ]
        manifest["verifier"]["verifier_sha256"] = implementation["verifier_sha256"]
        manifest["verifier"]["command"] = [
            "python3",
            "tools/verify_rom_parser_bound_zero_padding.py",
            "--root",
            ".",
            "--artifact-dir",
            RUN.relative_to(ROOT).joinpath("final").as_posix(),
        ]
        manifest["files"][PAYLOAD_NAME] = hashlib.sha256(
            payload_path.read_bytes()
        ).hexdigest()
        manifest_path.write_bytes(_canonical_bytes(manifest))
        return target

    def _copy_run_fixture(self, directory: str) -> Path:
        target_run = Path(directory).resolve() / "run"
        target_run.mkdir()
        shutil.copytree(RUN / "final", target_run / "final")
        shutil.copytree(RUN / "candidate", target_run / "candidate")
        for name in ("candidate-receipt.json", "accepted-receipt.json"):
            shutil.copy2(RUN / name, target_run / name)
        return target_run

    def _existing_run_verifier(self, run: Path):
        candidate_manifest = json.loads(
            (run / "candidate/manifest.json").read_text()
        )
        candidate_receipt = json.loads(
            (run / "candidate-receipt.json").read_text()
        )
        accepted_receipt = json.loads(
            (run / "accepted-receipt.json").read_text()
        )
        report = accepted_receipt["report"]

        def verify(root, artifact):
            if artifact == run / "final":
                return accepted_receipt["command"], report
            if artifact == run / "candidate":
                return candidate_manifest["verifier"]["command"], candidate_receipt[
                    "report"
                ]
            raise AssertionError(f"unexpected artifact: {artifact}")

        return verify

    def test_resigned_fixture_baseline_verifies_before_tamper(self):
        from tools.verify_rom_parser_bound_zero_padding import verify_artifact

        with tempfile.TemporaryDirectory() as directory:
            target = self._copy_current_fixture(directory)
            report = verify_artifact(ROOT, target)
            self.assertTrue(report["verified"], report)

    def test_resigned_contract_and_limitations_tamper_are_rejected(self):
        from tools.verify_rom_parser_bound_zero_padding import verify_artifact

        for mutate in (
            lambda payload: payload["source_contracts"][
                "m4a_wave_alignment_zero_padding"
            ].update(alignment=8),
            lambda payload: payload["limitations"].append(
                "The bytes are safe free space."
            ),
        ):
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as directory:
                target = self._copy_current_fixture(directory)
                payload_path = target / PAYLOAD_NAME
                manifest_path = target / "manifest.json"
                payload = json.loads(payload_path.read_text())
                mutate(payload)
                payload_path.write_bytes(_canonical_bytes(payload))
                manifest = json.loads(manifest_path.read_text())
                manifest["files"][PAYLOAD_NAME] = hashlib.sha256(
                    payload_path.read_bytes()
                ).hexdigest()
                manifest_path.write_bytes(_canonical_bytes(manifest))
                report = verify_artifact(ROOT, target)
                self.assertFalse(report["verified"], report)

    def test_resigned_noncanonical_payload_and_manifest_are_rejected(self):
        from tools.verify_rom_parser_bound_zero_padding import verify_artifact

        with tempfile.TemporaryDirectory() as directory:
            target = self._copy_current_fixture(directory)
            payload_path = target / PAYLOAD_NAME
            manifest_path = target / "manifest.json"
            payload = json.loads(payload_path.read_text())
            payload_path.write_text(json.dumps(payload, separators=(",", ":")))
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][PAYLOAD_NAME] = hashlib.sha256(
                payload_path.read_bytes()
            ).hexdigest()
            manifest_path.write_bytes(_canonical_bytes(manifest))
            report = verify_artifact(ROOT, target)
            self.assertFalse(report["verified"], report)

        with tempfile.TemporaryDirectory() as directory:
            target = self._copy_current_fixture(directory)
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest_path.write_text(json.dumps(manifest, separators=(",", ":")))
            report = verify_artifact(ROOT, target)
            self.assertFalse(report["verified"], report)

    def test_manifest_scope_and_producer_receipt_tamper_are_rejected(self):
        from tools.verify_rom_parser_bound_zero_padding import verify_artifact

        for mutate in (
            lambda manifest: manifest["scope"].update(free_space_complete=True),
            lambda manifest: manifest["producer"]["command"].append("--forged"),
        ):
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as directory:
                target = self._copy_current_fixture(directory)
                manifest_path = target / "manifest.json"
                manifest = json.loads(manifest_path.read_text())
                mutate(manifest)
                manifest_path.write_bytes(_canonical_bytes(manifest))
                report = verify_artifact(ROOT, target)
                self.assertFalse(report["verified"], report)

    def test_verifier_rejects_outside_root_ancestor_symlink(self):
        from tools.verify_rom_parser_bound_zero_padding import verify_artifact

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            real_parent = base / "real"
            real_parent.mkdir()
            self._copy_current_fixture(real_parent.as_posix())
            link = base / "link"
            link.symlink_to(real_parent, target_is_directory=True)
            report = verify_artifact(ROOT, link / "final")
            self.assertFalse(report["verified"], report)
            self.assertEqual(["artifact directory is missing or symlink"], report["errors"])

    def test_existing_final_requires_exact_receipts(self):
        import tools.export_rom_parser_bound_zero_padding as exporter

        with tempfile.TemporaryDirectory(dir=RUN.parent) as directory:
            fixture_run = self._copy_run_fixture(directory)
            verifier = self._existing_run_verifier(fixture_run)
            (fixture_run / "accepted-receipt.json").unlink()
            with mock.patch.object(
                exporter, "RUN_RELATIVE", fixture_run
            ), mock.patch.object(
                exporter, "_validate_output", return_value=fixture_run / "final"
            ), mock.patch.object(
                exporter, "_verify_cli", side_effect=verifier
            ):
                with self.assertRaisesRegex(ValueError, "receipt"):
                    exporter.export_artifact(ROOT, fixture_run / "final")

    def test_existing_final_rejects_receipt_leaf_and_ancestor_symlinks(self):
        import tools.export_rom_parser_bound_zero_padding as exporter

        for receipt_name in (
            "candidate-receipt.json",
            "accepted-receipt.json",
        ):
            with self.subTest(kind="leaf", receipt=receipt_name), tempfile.TemporaryDirectory(
                dir=RUN.parent
            ) as directory:
                run = self._copy_run_fixture(directory)
                receipt = run / receipt_name
                external = Path(directory) / f"external-{receipt_name}"
                receipt.replace(external)
                receipt.symlink_to(external)
                with mock.patch.object(
                    exporter, "RUN_RELATIVE", run
                ), mock.patch.object(
                    exporter, "_validate_output", return_value=run / "final"
                ), mock.patch.object(
                    exporter,
                    "_verify_cli",
                    side_effect=self._existing_run_verifier(run),
                ):
                    with self.assertRaisesRegex(ValueError, "symlink"):
                        exporter.export_artifact(ROOT, run / "final")

        with tempfile.TemporaryDirectory(dir=RUN.parent) as directory:
            base = Path(directory).resolve()
            real_parent = base / "real-parent"
            real_parent.mkdir()
            real_run = self._copy_run_fixture(real_parent.as_posix())
            linked_parent = base / "linked-parent"
            linked_parent.symlink_to(real_parent, target_is_directory=True)
            linked_run = linked_parent / "run"
            with mock.patch.object(
                exporter, "RUN_RELATIVE", linked_run
            ), mock.patch.object(
                exporter, "_validate_output", return_value=linked_run / "final"
            ), mock.patch.object(
                exporter,
                "_verify_cli",
                side_effect=self._existing_run_verifier(linked_run),
            ):
                with self.assertRaisesRegex(ValueError, "symlink"):
                    exporter.export_artifact(ROOT, linked_run / "final")

    def test_fresh_export_rejects_dangling_receipt_symlink_without_writing_target(self):
        import tools.export_rom_parser_bound_zero_padding as exporter

        fixture = self._fixture_final()
        payload = json.loads((fixture / PAYLOAD_NAME).read_text())
        bundle = (fixture / BUNDLE_NAME).read_bytes()
        report = json.loads((fixture / "manifest.json").read_text())["verifier"][
            "report"
        ]

        with tempfile.TemporaryDirectory(dir=RUN.parent) as directory:
            base = Path(directory).resolve()
            run = base / "run"
            run.mkdir()
            final = run / "final"
            external = base / "external-candidate-receipt.json"
            (run / "candidate-receipt.json").symlink_to(external)

            def verify(root, artifact):
                return exporter._verifier_command(root, artifact), report

            with mock.patch.object(
                exporter, "RUN_RELATIVE", run
            ), mock.patch.object(
                exporter, "_validate_output", return_value=final
            ), mock.patch.object(
                exporter, "_build", return_value=(payload, bundle, {})
            ), mock.patch.object(
                exporter, "_verify_cli", side_effect=verify
            ):
                with self.assertRaisesRegex(ValueError, "receipt.*symlink"):
                    exporter.export_artifact(ROOT, final)

            self.assertFalse(external.exists())
            self.assertTrue((run / "candidate-receipt.json").is_symlink())
            self.assertFalse(final.exists())
            self.assertFalse((run / "candidate").exists())

    def test_candidate_manifest_is_pending_and_records_actual_preflight_command(self):
        candidate_manifest = json.loads(
            (RUN / "candidate/manifest.json").read_text()
        )
        candidate_receipt = json.loads(
            (RUN / "candidate-receipt.json").read_text()
        )
        verifier = candidate_manifest["verifier"]
        self.assertIsNone(verifier["exit_code"])
        self.assertIsNone(verifier["report"])
        self.assertEqual(candidate_receipt["command"], verifier["command"])

    def test_failed_accepted_verification_removes_this_run_receipts(self):
        import tools.export_rom_parser_bound_zero_padding as exporter

        fixture = self._fixture_final()
        payload = json.loads((fixture / PAYLOAD_NAME).read_text())
        bundle = (fixture / BUNDLE_NAME).read_bytes()
        report = json.loads((fixture / "manifest.json").read_text())["verifier"][
            "report"
        ]
        verify_calls = 0

        def fail_accepted(root, artifact):
            nonlocal verify_calls
            verify_calls += 1
            if verify_calls == 1:
                return exporter._verifier_command(root, artifact), report
            raise ValueError("accepted failed")

        with tempfile.TemporaryDirectory(dir=RUN.parent) as directory:
            run = Path(directory) / "run"
            final = run / "final"
            with mock.patch.object(exporter, "RUN_RELATIVE", run), mock.patch.object(
                exporter, "_validate_output", return_value=final
            ), mock.patch.object(
                exporter, "_build", return_value=(payload, bundle, {})
            ), mock.patch.object(
                exporter,
                "_verify_cli",
                side_effect=fail_accepted,
            ):
                with self.assertRaisesRegex(ValueError, "accepted failed"):
                    exporter.export_artifact(ROOT, final)
            self.assertFalse(final.exists())
            self.assertFalse((run / "candidate").exists())
            self.assertFalse((run / "candidate-receipt.json").exists())
            self.assertFalse((run / "accepted-receipt.json").exists())


class RomParserBoundZeroPaddingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_parser_bound_zero_padding import export_artifact

        cls.payload = export_artifact(ROOT, FINAL)
        cls.bundle = (FINAL / BUNDLE_NAME).read_bytes()

    def test_final_run_artifact_is_present_and_exactly_three_files(self):
        self.assertTrue(FINAL.is_dir())
        self.assertEqual(
            {PAYLOAD_NAME, BUNDLE_NAME, "manifest.json"},
            {path.name for path in FINAL.iterdir()},
        )
        self.assertEqual(SCHEMA, self.payload["schema"])
        self.assertEqual(142, len(self.payload["classified_ranges"]))
        self.assertEqual(142, self.payload["summary"]["accepted_range_count"])
        self.assertEqual(198, self.payload["summary"]["accepted_byte_count"])
        self.assertEqual(
            "936959996300e6971bf0afa70ebe8fa116bb57c92a824b710daa91cd5b08a4c1",
            self.payload["summary"]["accepted_range_sha256"],
        )
        self.assertEqual(
            "a6eab4025a7c9c0877549f6e5d790f66af88ee7f2320e814954e638d8051f812",
            self.payload["files"][BUNDLE_NAME]["sha256"],
        )
        self.assertEqual(198, len(self.bundle))
        self.assertEqual(bytes(198), self.bundle)

    def test_group_denominators_and_acceptance_hashes_are_frozen(self):
        groups = self.payload["group_summaries"]
        for source_kind, expected in EXPECTED_GROUPS.items():
            with self.subTest(source_kind=source_kind):
                actual = groups[source_kind]
                for key, value in expected.items():
                    if value:
                        self.assertEqual(value, actual[key], key)
                if source_kind == "chapter_terminal_to_fixed_root_zero_padding":
                    self.assertEqual(89, actual["structure_count"])
                    self.assertEqual(3764, actual["structure_bytes"])
                    self.assertEqual(85, actual["accepted_count"])
                    self.assertEqual(85, actual["accepted_bytes"])
                    self.assertEqual(4, actual["structural_rejected_count"])
                    self.assertEqual(3679, actual["structural_rejected_bytes"])
                    self.assertEqual(2, actual["contract_excluded_count"])
                    self.assertEqual(5, actual["contract_excluded_bytes"])
        self.assertEqual(5, groups["m4a_wave_alignment_zero_padding"]["structural_rejected_count"])
        self.assertEqual(9, groups["m4a_wave_alignment_zero_padding"]["structural_rejected_bytes"])
        self.assertEqual(9, self.payload["summary"]["rejected_range_count"])
        self.assertEqual(3688, self.payload["summary"]["rejected_byte_count"])
        self.assertEqual(2, self.payload["summary"]["contract_excluded_range_count"])
        self.assertEqual(5, self.payload["summary"]["contract_excluded_byte_count"])
        self.assertEqual(2, len(self.payload["contract_excluded_ranges"]))
        self.assertTrue(all(item["rejection_reason"] == "nonterminal_or_nonroot_gap" for item in self.payload["contract_excluded_ranges"]))
        accepted = self.payload["classified_ranges"]
        vector = [[r["range"][0], r["range"][1]] for r in accepted]
        self.assertEqual(
            "936959996300e6971bf0afa70ebe8fa116bb57c92a824b710daa91cd5b08a4c1",
            _compact_hash(vector),
        )
        self.assertEqual(
            sorted(accepted, key=lambda r: (tuple(r["range"]), r["source_kind"], r["range_id"])),
            accepted,
        )

    def test_accepted_records_bind_both_parser_sources_and_are_zero_only(self):
        accepted = self.payload["classified_ranges"]
        self.assertEqual(
            {
                "m4a_wave_alignment_zero_padding",
                "chapter_terminal_to_fixed_root_zero_padding",
            },
            {record["source_kind"] for record in accepted},
        )
        for record in accepted:
            with self.subTest(range_id=record["range_id"]):
                self.assertTrue(record["all_zero"])
                self.assertFalse(record["safe_allocatable_space_claimed"])
                start, end = record["range"]
                self.assertEqual(end - start, record["size"])
                self.assertEqual(hashlib.sha256(bytes(record["size"])).hexdigest(), record["bytes_sha256"])
                self.assertEqual(record["size"], record["packed_range"][1] - record["packed_range"][0])
                if record["source_kind"].startswith("m4a_"):
                    self.assertEqual(4, record["alignment"])
                    self.assertIn("left_claim_id", record)
                    self.assertIn("right_claim_id", record)
                else:
                    self.assertEqual("0x00", record["terminal_opcode"])
                    self.assertIn("terminal_offset", record)
                    self.assertIn("right_root", record)
                    self.assertIn("right_pointer_table", record)

    def test_sources_record_exact_upstream_verifier_reports(self):
        sources = self.payload["sources"]
        self.assertEqual(
            {
                "schema": "rom-m4a-byte-inventory-verification-v1",
                "verified": True,
                "claim_count": 842,
                "byte_count": 887018,
                "sound_id_count": 159,
                "active_sound_id_count": 80,
                "empty_sound_id_count": 79,
                "track_reference_count": 217,
                "track_stream_count": 217,
                "voicegroup_count": 23,
                "tone_record_count": 387,
                "wave_count": 79,
                "unclaimed_dense_window_bytes": 318,
                "errors": [],
            },
            sources["m4a"]["verifier"]["report"],
        )
        chapter_report = sources["chapter"]["verifier"]["report"]
        self.assertEqual(
            {
                "schema": "rom-chapter-script-inventory-verification-v1",
                "verified": True,
                "pointer_table_slot_count": 204,
                "non_null_script_slots": 200,
                "unique_script_roots": 188,
                "unique_instruction_nodes": 18994,
                "dynamic_opcode_06_nodes": 42,
                "observed_opcode_count": 43,
                "terminal_node_count": 590,
                "parse_failure_count": 0,
                "raw_node_bytes": 334060,
                "node_overlap_bytes": 0,
                "merged_range_count": 92,
                "merged_range_bytes": 334060,
                "internal_gap_count": 91,
                "internal_gap_bytes": 3769,
                "packed_script_bytes": 334060,
                "errors": [],
            },
            chapter_report,
        )

    def test_scope_and_limitations_are_explicit(self):
        scope = self.payload["scope"]
        for key in (
            "natural_execution_reachability_complete",
            "arbitrary_zero_holes_complete",
            "free_space_complete",
            "edit_safety_complete",
            "rejected_gaps_classified",
            "all_m4a_unclaimed_classified",
            "all_chapter_gaps_classified",
        ):
            self.assertFalse(scope[key], key)
        text = " ".join(self.payload["limitations"])
        for phrase in ("natural", "zero", "free", "edit", "rejected"):
            self.assertIn(phrase, text.lower())

    def test_verifier_is_independent_of_new_exporter(self):
        source = (ROOT / "tools/verify_rom_parser_bound_zero_padding.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names]
                self.assertNotIn("tools.export_rom_parser_bound_zero_padding", names)
                self.assertNotIn("export_rom_parser_bound_zero_padding", names)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotEqual("export_artifact", node.func.id)
        self.assertIn("def verify_artifact", source)

    def _tampered(self, mutate):
        temporary = tempfile.TemporaryDirectory()
        target = Path(temporary.name).resolve() / "final"
        shutil.copytree(FINAL, target)
        payload_path = target / PAYLOAD_NAME
        payload = json.loads(payload_path.read_text())
        mutate(payload, target)
        payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        manifest_path = target / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][PAYLOAD_NAME] = hashlib.sha256(payload_path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        return temporary, target

    def _passed_root(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name).resolve() / "repo"
        root.mkdir()
        (root / "rom").mkdir()
        (root / "artifacts").mkdir()
        (root / "tools").mkdir()
        (root / "tests").mkdir()
        for relative in (
            "verify_rom_m4a_byte_inventory.py",
            "verify_rom_chapter_script_inventory.py",
            "export_rom_m4a_byte_inventory.py",
            "export_rom_chapter_script_inventory.py",
            "verify_rom_parser_bound_zero_padding.py",
        ):
            shutil.copy2(ROOT / "tools" / relative, root / "tools" / relative)
        shutil.copy2(ROOT / "tests/test_export_rom_chapter_script_inventory.py", root / "tests/test_export_rom_chapter_script_inventory.py")
        shutil.copy2(ROOT / "tests/test_export_rom_parser_bound_zero_padding.py", root / "tests/test_export_rom_parser_bound_zero_padding.py")
        shutil.copy2(ROOT / "rom/base.gba", root / "rom/base.gba")
        for name in ("rom-m4a-byte-inventory-v1", "rom-chapter-script-inventory-v1"):
            shutil.copytree(ROOT / "artifacts" / name, root / "artifacts" / name)
        target = Path(temporary.name).resolve() / "final"
        shutil.copytree(FINAL, target)
        return temporary, root, target

    def _assert_passed_root_sources_verified(self, root):
        m4a = subprocess.run(
            [sys.executable, "tools/verify_rom_m4a_byte_inventory.py", "--root", ".", "--manifest", "artifacts/rom-m4a-byte-inventory-v1/manifest.json"],
            cwd=root, capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, m4a.returncode, m4a.stderr)
        self.assertTrue(json.loads(m4a.stdout)["verified"], m4a.stdout)
        chapter = subprocess.run(
            [sys.executable, "tools/verify_rom_chapter_script_inventory.py", "--root", ".", "--artifact-dir", "artifacts/rom-chapter-script-inventory-v1"],
            cwd=root, capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, chapter.returncode, chapter.stderr)
        self.assertTrue(json.loads(chapter.stdout)["verified"], chapter.stdout)

    def test_verifier_rejects_source_endpoint_identity_alignment_and_chapter_binding_tamper(self):
        from tools.verify_rom_parser_bound_zero_padding import verify_artifact

        mutations = [
            lambda p, _: next(r for r in p["classified_ranges"] if r["source_kind"] == "m4a_wave_alignment_zero_padding").update(left_claim_id="tampered"),
            lambda p, _: next(r for r in p["classified_ranges"] if r["source_kind"] == "m4a_wave_alignment_zero_padding")["range"].__setitem__(1, next(r for r in p["classified_ranges"] if r["source_kind"] == "m4a_wave_alignment_zero_padding")["range"][1] + 1),
            lambda p, _: next(r for r in p["classified_ranges"] if r["source_kind"] == "m4a_wave_alignment_zero_padding").update(alignment=8),
            lambda p, _: next(r for r in p["classified_ranges"] if r["source_kind"].startswith("chapter_")).update(terminal_opcode="0x07"),
            lambda p, _: next(r for r in p["classified_ranges"] if r["source_kind"].startswith("chapter_")).update(right_root=0),
            lambda p, _: next(r for r in p["classified_ranges"] if r["source_kind"].startswith("chapter_")).update(all_zero=False),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                temporary, target = self._tampered(mutate)
                try:
                    report = verify_artifact(ROOT, target)
                    self.assertFalse(report["verified"], report)
                finally:
                    temporary.cleanup()

    def test_verifier_rejects_delete_add_reorder_overlap_rejected_and_bundle_tamper(self):
        from tools.verify_rom_parser_bound_zero_padding import verify_artifact

        def mutate_delete(p, _):
            del p["classified_ranges"][0]

        def mutate_add(p, _):
            p["classified_ranges"].append(copy.deepcopy(p["classified_ranges"][0]))

        def mutate_reorder(p, _):
            p["classified_ranges"][:2] = reversed(p["classified_ranges"][:2])

        def mutate_overlap(p, _):
            p["classified_ranges"][1]["range"][0] = p["classified_ranges"][0]["range"][0]

        def mutate_rejected(p, _):
            p["rejected_ranges"][0]["bytes"][0] ^= 1

        mutations = [mutate_delete, mutate_add, mutate_reorder, mutate_overlap, mutate_rejected]
        for mutate in mutations:
            with self.subTest(mutate=mutate.__name__):
                temporary, target = self._tampered(mutate)
                try:
                    self.assertFalse(verify_artifact(ROOT, target)["verified"])
                finally:
                    temporary.cleanup()
        temporary, target = self._tampered(lambda _p, t: (t / BUNDLE_NAME).write_bytes(b"\x00" * 197))
        try:
            self.assertFalse(verify_artifact(ROOT, target)["verified"])
        finally:
            temporary.cleanup()
        temporary, target = self._tampered(lambda _p, t: (t / BUNDLE_NAME).write_bytes(b"\x01" + bytes(197)))
        try:
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][BUNDLE_NAME] = hashlib.sha256((target / BUNDLE_NAME).read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            self.assertFalse(verify_artifact(ROOT, target)["verified"])
        finally:
            temporary.cleanup()

    def test_verifier_rejects_source_identity_and_rom_mutation_in_passed_root(self):
        from tools.verify_rom_parser_bound_zero_padding import verify_artifact

        temporary, root, target = self._passed_root()
        try:
            self._assert_passed_root_sources_verified(root)
            m4a_manifest = root / "artifacts/rom-m4a-byte-inventory-v1/manifest.json"
            m4a = json.loads(m4a_manifest.read_text())
            source_kind = "m4a_directsound_wave"
            wave = next(claim for claim in m4a["claims"] if claim["semantic_class"] == source_kind)
            wave["range"][1] += 1
            m4a_manifest.write_text(json.dumps(m4a, indent=2, sort_keys=True) + "\n")
            report = verify_artifact(root, target)
            self.assertFalse(report["verified"])
            self.assertEqual(["M4A source manifest identity changed"], report["errors"])
        finally:
            temporary.cleanup()

        temporary, root, target = self._passed_root()
        try:
            self._assert_passed_root_sources_verified(root)
            chapter_payload = root / "artifacts/rom-chapter-script-inventory-v1/chapter-script-inventory.json"
            chapter = json.loads(chapter_payload.read_text())
            chapter["ranges"][0]["range"][1] += 1
            chapter_payload.write_text(json.dumps(chapter, indent=2, sort_keys=True) + "\n")
            report = verify_artifact(root, target)
            self.assertFalse(report["verified"])
            self.assertEqual(["chapter source payload identity changed"], report["errors"])
        finally:
            temporary.cleanup()

    def test_verifier_rejects_rom_byte_mutation_for_accepted_and_rejected_gap(self):
        from tools.verify_rom_parser_bound_zero_padding import verify_artifact

        for offset in (4633009, 51906):
            with self.subTest(offset=offset):
                temporary, root, target = self._passed_root()
                try:
                    rom_path = root / "rom/base.gba"
                    self._assert_passed_root_sources_verified(root)
                    raw = bytearray(rom_path.read_bytes())
                    raw[offset] ^= 1
                    rom_path.write_bytes(raw)
                    report = verify_artifact(root, target)
                    self.assertFalse(report["verified"])
                    self.assertEqual(["ROM identity mismatch"], report["errors"])
                finally:
                    temporary.cleanup()

    def test_exporter_rejects_repo_root_ancestor_foreign_and_real_symlink_outputs(self):
        from tools.export_rom_parser_bound_zero_padding import export_artifact

        for path in (ROOT, ROOT.parent, RUN, RUN / "foreign"):
            with self.subTest(path=path):
                self.assertRaises(ValueError, export_artifact, ROOT, path)

        with tempfile.TemporaryDirectory() as directory:
            temp_root = Path(directory).resolve() / "repo"
            (temp_root / "build/experiments/active/parser-bound-zero-padding/codex-r4-20260821").mkdir(parents=True)
            foreign = Path(directory).resolve() / "foreign"
            foreign.mkdir()
            leaf = temp_root / "build/experiments/active/parser-bound-zero-padding/codex-r4-20260821/final"
            leaf.symlink_to(foreign, target_is_directory=True)
            self.assertRaises(ValueError, export_artifact, temp_root, leaf)

        with tempfile.TemporaryDirectory() as directory:
            temp_root = Path(directory).resolve() / "repo"
            (temp_root / "build/experiments/active").mkdir(parents=True)
            foreign = Path(directory).resolve() / "foreign"
            foreign.mkdir()
            (temp_root / "build/experiments/active/parser-bound-zero-padding").symlink_to(foreign, target_is_directory=True)
            output = temp_root / "build/experiments/active/parser-bound-zero-padding/codex-r4-20260821/final"
            self.assertRaises(ValueError, export_artifact, temp_root, output)

        from tools.verify_rom_parser_bound_zero_padding import verify_artifact
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "final"
            shutil.copytree(FINAL, target)
            (target / "member-link").symlink_to(FINAL / PAYLOAD_NAME)
            report = verify_artifact(ROOT, target)
            self.assertFalse(report["verified"])
            self.assertTrue(any("file set" in e.lower() or "symlink" in e.lower() for e in report["errors"]), report)

    def test_verifier_rejects_directory_or_symlink_in_exact_member_set(self):
        from tools.verify_rom_parser_bound_zero_padding import verify_artifact

        for member, make_member in (
            ("foreign-directory", lambda target: (target / "foreign-directory").mkdir()),
            ("member-link", lambda target: (target / "member-link").symlink_to(target / PAYLOAD_NAME)),
        ):
            with self.subTest(member=member), tempfile.TemporaryDirectory() as directory:
                target = Path(directory).resolve() / "final"
                shutil.copytree(FINAL, target)
                make_member(target)
                report = verify_artifact(ROOT, target)
                self.assertFalse(report["verified"])
                self.assertEqual(["artifact file set mismatch"], report["errors"])

    def test_verifier_rejects_real_ancestor_symlink_inside_repository(self):
        from tools.verify_rom_parser_bound_zero_padding import verify_artifact

        link = RUN / "verify-ancestor-link"
        self.assertFalse(link.exists())
        link.symlink_to(RUN, target_is_directory=True)
        try:
            report = verify_artifact(ROOT, link / "final")
            self.assertFalse(report["verified"], report)
            self.assertEqual(["artifact directory is missing or symlink"], report["errors"])
        finally:
            link.unlink()

    def test_verifier_rejects_resigned_payload_and_bundle_tamper(self):
        from tools.verify_rom_parser_bound_zero_padding import verify_artifact

        def payload_tamper(payload, _):
            payload["summary"]["accepted_byte_count"] += 1

        def bundle_tamper(_, target):
            bundle = target / BUNDLE_NAME
            bundle.write_bytes(b"\x01" + bundle.read_bytes()[1:])
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][BUNDLE_NAME] = hashlib.sha256(bundle.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

        for mutate, expected in (
            (payload_tamper, "payload differs from independent parser-bound rebuild"),
            (bundle_tamper, "bundle differs from ROM-bound accepted bytes"),
        ):
            with self.subTest(mutate=mutate.__name__):
                temporary, target = self._tampered(mutate)
                try:
                    report = verify_artifact(ROOT, target)
                    self.assertFalse(report["verified"])
                    self.assertEqual([expected], report["errors"])
                finally:
                    temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
