"""Contract tests for the artifact-bound align4 gap verifier."""

from __future__ import annotations

import ast
from contextlib import ExitStack
import copy
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = ROOT / "rom/base.gba"
VERIFIER_PATH = ROOT / "tools/verify_rom_artifact_bound_alignment_gaps.py"

SCHEDULER_DIR = ROOT / "artifacts/rom-task-scheduler-core-v1"
PSG_DIR = ROOT / "artifacts/rom-psg-frequency-lookup-v1"
HELPER_DIR = ROOT / "artifacts/rom-cgb-helper-bounded-cfg-v1"
CGBSOUND_DIR = ROOT / "artifacts/rom-cgbsound-bounded-cfg-v1"

VERIFY_SCHEMA = "rom-artifact-bound-alignment-gaps-verification-v1"
PROMOTION_BATCH = "rom-artifact-bound-alignment-gaps-v1"
PRIMARY_CLASS = "artifact_bound_4byte_alignment_bytes"
CLAIM_KIND = "artifact_bound_alignment_gap_bytes"

RANGES = (
    (0x061D62, 0x061D64),
    (0x061D7A, 0x061D7C),
    (0x061DEA, 0x061DEC),
    (0x09B4C6, 0x09B4C8),
    (0x09B572, 0x09B574),
    (0x09B586, 0x09B588),
    (0x09B676, 0x09B678),
    (0x09B696, 0x09B698),
    (0x09B702, 0x09B704),
    (0x09B762, 0x09B764),
    (0x09B94A, 0x09B94C),
    (0x09B96E, 0x09B970),
    (0x09B9E2, 0x09B9E4),
)
RANGE_VECTOR_SHA256 = (
    "d6582d3ca46f1bacb82537740370874320c79592f3c9512747affd4db5285741"
)
BOUNDARY_VECTOR_SHA256 = (
    "7dd56d026c90f090f3b4fbceb055bbe3db35786e915e4ace4ae61a6b06230843"
)
CLAIM_DENOMINATOR_SHA256 = (
    "1962c626da011e7ac32287662593e55cea72d5d21b003a419e78085a087b8d46"
)
SOURCE_FILE_VECTOR_SHA256 = (
    "d14919e7abafeb1891e1336d0511b5ab0e44ef6091ee010ca842ca6c6fd3f92f"
)
PACKED_BYTES_SHA256 = (
    "659d36ca563ba4622daabb36a71dafaf6060cdcbf89bb12e75426198496d272c"
)
ZERO_PAIR_SHA256 = (
    "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7"
)

EXPECTED_IDS = (
    "scheduler-return-to-literal-061d62",
    "scheduler-branch-to-function-061d7a",
    "scheduler-return-to-literal-061dea",
    "psg-branch-to-literal-09b4c6",
    "cgb-helper-branch-to-literal-09b572",
    "cgb-helper-return-to-literal-09b586",
    "cgbsound-branch-to-literal-09b676",
    "cgbsound-branch-to-literal-09b696",
    "cgbsound-branch-to-literal-09b702",
    "cgbsound-branch-to-literal-09b762",
    "cgbsound-branch-to-literal-09b94a",
    "cgbsound-branch-to-literal-09b96e",
    "cgbsound-branch-to-literal-09b9e2",
)
EXPECTED_RIGHT_KINDS = (
    "consumed_literal_range",
    "owned_thumb_function",
    "consumed_literal_range",
    "consumed_literal_range",
    "consumed_literal_range",
    "consumed_literal_range",
    "consumed_literal_range",
    "consumed_literal_range",
    "consumed_literal_range",
    "consumed_literal_range",
    "consumed_literal_range",
    "consumed_literal_range",
    "consumed_literal_range",
)
EXPECTED_TERMINALS = (
    ([0x061D60, 0x061D62], "0047", "return", None),
    ([0x061D78, 0x061D7A], "fbe7", "unconditional_branch", 0x061D72),
    ([0x061DE8, 0x061DEA], "0047", "return", None),
    ([0x09B4C4, 0x09B4C6], "33e0", "unconditional_branch", 0x09B52E),
    ([0x09B570, 0x09B572], "07e0", "unconditional_branch", 0x09B582),
    ([0x09B584, 0x09B586], "7047", "return", None),
    ([0x09B674, 0x09B676], "1ae0", "unconditional_branch", 0x09B6AC),
    ([0x09B694, 0x09B696], "0ee0", "unconditional_branch", 0x09B6B4),
    ([0x09B700, 0x09B702], "36e0", "unconditional_branch", 0x09B770),
    ([0x09B760, 0x09B762], "13e0", "unconditional_branch", 0x09B78A),
    ([0x09B948, 0x09B94A], "09e0", "unconditional_branch", 0x09B95E),
    ([0x09B96C, 0x09B96E], "09e0", "unconditional_branch", 0x09B982),
    ([0x09B9E0, 0x09B9E2], "1ee0", "unconditional_branch", 0x09BA20),
)

NEW_SOURCE_IDS = (
    ("cgb-helper-code-09b56c", "cgb-helper-literal-09b574"),
    ("cgb-helper-code-09b578", "cgb-helper-literal-09b588"),
    ("cgbsound-code-09b66c", "cgbsound-literal-09b678"),
    ("cgbsound-code-09b684", "cgbsound-literal-09b698"),
    ("cgbsound-code-09b6a4", "cgbsound-literal-09b704"),
    ("cgbsound-code-09b710", "cgbsound-literal-09b764"),
    ("cgbsound-code-09b768", "cgbsound-literal-09b94c"),
    ("cgbsound-code-09b954", "cgbsound-literal-09b970"),
    ("cgbsound-code-09b974", "cgbsound-literal-09b9e4"),
)

NEW_ARTIFACT_CASES = (
    ("helper_payload", "HELPER_PAYLOAD_SHA256", RANGES[4], (0x09B56C, 0x09B572), (0x09B574, 0x09B578)),
    ("helper_payload", "HELPER_PAYLOAD_SHA256", RANGES[5], (0x09B578, 0x09B586), (0x09B588, 0x09B58C)),
    ("cgbsound_payload", "CGBSOUND_PAYLOAD_SHA256", RANGES[6], (0x09B66C, 0x09B676), (0x09B678, 0x09B684)),
    ("cgbsound_payload", "CGBSOUND_PAYLOAD_SHA256", RANGES[7], (0x09B684, 0x09B696), (0x09B698, 0x09B6A4)),
    ("cgbsound_payload", "CGBSOUND_PAYLOAD_SHA256", RANGES[8], (0x09B6A4, 0x09B702), (0x09B704, 0x09B710)),
    ("cgbsound_payload", "CGBSOUND_PAYLOAD_SHA256", RANGES[9], (0x09B710, 0x09B762), (0x09B764, 0x09B768)),
    ("cgbsound_payload", "CGBSOUND_PAYLOAD_SHA256", RANGES[10], (0x09B768, 0x09B94A), (0x09B94C, 0x09B954)),
    ("cgbsound_payload", "CGBSOUND_PAYLOAD_SHA256", RANGES[11], (0x09B954, 0x09B96E), (0x09B970, 0x09B974)),
    ("cgbsound_payload", "CGBSOUND_PAYLOAD_SHA256", RANGES[12], (0x09B974, 0x09B9E2), (0x09B9E4, 0x09B9EC)),
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_sha(value: object) -> str:
    raw = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return _sha(raw)


def _compact_sha(value: object) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return _sha(raw)


EXPECTED_SOURCE_FILES = (
    ("rom-task-scheduler-core-v1", "artifacts/rom-task-scheduler-core-v1/manifest.json", "88ef48526ed1bd096a8ece9a58aa4f5770f207084634a125f04dc99561c7d58c", 80_919),
    ("rom-task-scheduler-core-v1", "artifacts/rom-task-scheduler-core-v1/rom-task-scheduler-core.json", "298dc0cf30765e0afe33487f92cce231bd76d4056719f825c1c9cef98d12a59d", 226_440),
    ("rom-task-scheduler-core-v1", "artifacts/rom-task-scheduler-core-v1/rom-task-scheduler-core.bin", "2cdbf5ee8ee1f24e9d5590363f05cf177c21821209d8b735666b4844c829842f", 308),
    ("rom-psg-frequency-lookup-v1", "artifacts/rom-psg-frequency-lookup-v1/manifest.json", "4fffbcc7e252595834adb368d10b3ce8f13323aee18cc518d98e0ff9c519575f", 10_899),
    ("rom-psg-frequency-lookup-v1", "artifacts/rom-psg-frequency-lookup-v1/rom-psg-frequency-lookup.json", "d2631b1a65a2e9fa0114dbd76a4e2c89853e3b2f402a491fdbc466e79dacd733", 13_876),
    ("rom-psg-frequency-lookup-v1", "artifacts/rom-psg-frequency-lookup-v1/rom-psg-frequency-lookup.bin", "e625a5fcc208a971a1ec98723f12b863a707fa9dd3ba8442f7f6d86b3099623b", 226),
    ("rom-cgb-helper-bounded-cfg-v1", "artifacts/rom-cgb-helper-bounded-cfg-v1/manifest.json", "8a53b3ee982799583e08ef852fb2cac9771f856e77ed104cc2814cfd1e7ef6d1", 1_609),
    ("rom-cgb-helper-bounded-cfg-v1", "artifacts/rom-cgb-helper-bounded-cfg-v1/rom-cgb-helper-bounded-cfg.json", "dccdca087744e57136b180dba1c3e4151c123efecec10d5d53f90894dc760960", 42_154),
    ("rom-cgb-helper-bounded-cfg-v1", "artifacts/rom-cgb-helper-bounded-cfg-v1/rom-cgb-helper-bounded-cfg.bin", "87c62bbe5f0e9d25ee5b11398ecdd3ed5b41782d4873871205f71c1122a4c1dc", 180),
    ("rom-cgbsound-bounded-cfg-v1", "artifacts/rom-cgbsound-bounded-cfg-v1/manifest.json", "4248c0fed46682d06918ac124d3c861a60c12117023a773190ff831840963b6e", 1_594),
    ("rom-cgbsound-bounded-cfg-v1", "artifacts/rom-cgbsound-bounded-cfg-v1/rom-cgbsound-bounded-cfg.json", "362a3dc1b5819a57310482b7fbdd94bb2f79e9d439ea44713798140d1d79b18d", 178_551),
    ("rom-cgbsound-bounded-cfg-v1", "artifacts/rom-cgbsound-bounded-cfg-v1/rom-cgbsound-bounded-cfg.bin", "edebdbe6e5cf5f9cf04fdb93839846f7e37e6516914b77a7517413c88ee9a151", 1_084),
)


def _load_verifier():
    try:
        return importlib.import_module(
            "tools.verify_rom_artifact_bound_alignment_gaps"
        )
    except ModuleNotFoundError as error:
        raise AssertionError(
            "target verifier module is absent (the expected RED condition)"
        ) from error


class ArtifactBoundAlignmentGapVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM_PATH.read_bytes()
        cls.scheduler_manifest = json.loads(
            (SCHEDULER_DIR / "manifest.json").read_text(encoding="utf-8")
        )
        cls.scheduler_payload = json.loads(
            (SCHEDULER_DIR / "rom-task-scheduler-core.json").read_text(
                encoding="utf-8"
            )
        )
        cls.scheduler_binary = (
            SCHEDULER_DIR / "rom-task-scheduler-core.bin"
        ).read_bytes()
        cls.psg_manifest = json.loads(
            (PSG_DIR / "manifest.json").read_text(encoding="utf-8")
        )
        cls.psg_payload = json.loads(
            (PSG_DIR / "rom-psg-frequency-lookup.json").read_text(
                encoding="utf-8"
            )
        )
        cls.psg_binary = (PSG_DIR / "rom-psg-frequency-lookup.bin").read_bytes()
        cls.helper_manifest = json.loads(
            (HELPER_DIR / "manifest.json").read_text(encoding="utf-8")
        )
        cls.helper_payload = json.loads(
            (HELPER_DIR / "rom-cgb-helper-bounded-cfg.json").read_text(
                encoding="utf-8"
            )
        )
        cls.helper_binary = (
            HELPER_DIR / "rom-cgb-helper-bounded-cfg.bin"
        ).read_bytes()
        cls.cgbsound_manifest = json.loads(
            (CGBSOUND_DIR / "manifest.json").read_text(encoding="utf-8")
        )
        cls.cgbsound_payload = json.loads(
            (CGBSOUND_DIR / "rom-cgbsound-bounded-cfg.json").read_text(
                encoding="utf-8"
            )
        )
        cls.cgbsound_binary = (
            CGBSOUND_DIR / "rom-cgbsound-bounded-cfg.bin"
        ).read_bytes()

    def _verify_inputs(self, rom: bytes, **overrides):
        verifier = _load_verifier()
        values = {
            "scheduler_manifest": self.scheduler_manifest,
            "scheduler_payload": self.scheduler_payload,
            "scheduler_binary": self.scheduler_binary,
            "psg_manifest": self.psg_manifest,
            "psg_payload": self.psg_payload,
            "psg_binary": self.psg_binary,
            "helper_manifest": self.helper_manifest,
            "helper_payload": self.helper_payload,
            "helper_binary": self.helper_binary,
            "cgbsound_manifest": self.cgbsound_manifest,
            "cgbsound_payload": self.cgbsound_payload,
            "cgbsound_binary": self.cgbsound_binary,
        }
        values.update(overrides)
        return verifier.verify_inputs(rom, **values)

    def _verify_resigned_payload(
        self,
        artifact: str,
        payload: dict,
        *,
        bypass_semantic_receipts: bool = True,
    ) -> dict:
        verifier = _load_verifier()
        details = {
            "scheduler": (
                "scheduler_manifest",
                "scheduler_payload",
                "rom-task-scheduler-core.json",
                "SCHEDULER_MANIFEST_SHA256",
                "SCHEDULER_MANIFEST_SIZE",
                "SCHEDULER_PAYLOAD_SHA256",
                "SCHEDULER_PAYLOAD_SIZE",
            ),
            "psg": (
                "psg_manifest",
                "psg_payload",
                "rom-psg-frequency-lookup.json",
                "PSG_MANIFEST_SHA256",
                "PSG_MANIFEST_SIZE",
                "PSG_PAYLOAD_SHA256",
                "PSG_PAYLOAD_SIZE",
            ),
            "helper": (
                "helper_manifest",
                "helper_payload",
                "rom-cgb-helper-bounded-cfg.json",
                "HELPER_MANIFEST_SHA256",
                "HELPER_MANIFEST_SIZE",
                "HELPER_PAYLOAD_SHA256",
                "HELPER_PAYLOAD_SIZE",
            ),
            "cgbsound": (
                "cgbsound_manifest",
                "cgbsound_payload",
                "rom-cgbsound-bounded-cfg.json",
                "CGBSOUND_MANIFEST_SHA256",
                "CGBSOUND_MANIFEST_SIZE",
                "CGBSOUND_PAYLOAD_SHA256",
                "CGBSOUND_PAYLOAD_SIZE",
            ),
        }[artifact]
        manifest_attr, payload_attr, payload_name, manifest_sha_attr, manifest_size_attr, payload_sha_attr, payload_size_attr = details
        payload_raw = (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        payload_sha = _sha(payload_raw)
        manifest = copy.deepcopy(getattr(self, manifest_attr))
        manifest["files"][payload_name] = {
            "sha256": payload_sha,
            "size": len(payload_raw),
        }
        if artifact in {"helper", "cgbsound"}:
            manifest["acceptance"]["source_candidate_identity"][
                "payload_sha256"
            ] = payload_sha
            manifest["verification"]["payload_sha256"] = payload_sha
        manifest_raw = (
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(verifier, payload_sha_attr, payload_sha))
            stack.enter_context(mock.patch.object(verifier, payload_size_attr, len(payload_raw)))
            stack.enter_context(mock.patch.object(verifier, manifest_sha_attr, _sha(manifest_raw)))
            stack.enter_context(mock.patch.object(verifier, manifest_size_attr, len(manifest_raw)))
            if bypass_semantic_receipts and artifact in {"scheduler", "psg"}:
                prefix = artifact.upper()
                stack.enter_context(
                    mock.patch.object(
                        verifier,
                        f"{prefix}_MANIFEST_SEMANTIC_SHA256",
                        _sha(
                            json.dumps(
                                manifest,
                                ensure_ascii=False,
                                separators=(",", ":"),
                                sort_keys=True,
                            ).encode("utf-8")
                        ),
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        verifier,
                        f"{prefix}_PAYLOAD_SEMANTIC_SHA256",
                        _sha(
                            json.dumps(
                                payload,
                                ensure_ascii=False,
                                separators=(",", ":"),
                                sort_keys=True,
                            ).encode("utf-8")
                        ),
                    )
                )
            return self._verify_inputs(
                self.rom,
                **{manifest_attr: manifest, payload_attr: payload},
            )

    @staticmethod
    def _copy_project(project: Path) -> None:
        (project / "tools").mkdir(parents=True)
        (project / "tests").mkdir()
        (project / "rom").mkdir()
        shutil.copy2(ROM_PATH, project / "rom/base.gba")
        for artifact in (SCHEDULER_DIR, PSG_DIR, HELPER_DIR, CGBSOUND_DIR):
            shutil.copytree(artifact, project / artifact.relative_to(ROOT))

    def test_exact_denominator_boundary_kinds_and_ordered_report(self) -> None:
        report = _load_verifier().verify_root(ROOT)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(VERIFY_SCHEMA, report["schema"])
        self.assertEqual([], report["errors"])
        self.assertEqual(PROMOTION_BATCH, report["promotion_batch"])
        self.assertEqual(PRIMARY_CLASS, report["primary_class"])
        self.assertEqual(CLAIM_KIND, report["claim_kind"])
        self.assertEqual(13, report["gap_count"])
        self.assertEqual(26, report["byte_count"])
        self.assertEqual(26, report["zero_byte_count"])
        self.assertEqual([list(pair) for pair in RANGES], report["ranges"])
        self.assertEqual(RANGE_VECTOR_SHA256, report["range_vector_sha256"])
        self.assertEqual(BOUNDARY_VECTOR_SHA256, report["boundary_vector_sha256"])
        self.assertEqual(
            CLAIM_DENOMINATOR_SHA256, report["claim_denominator_sha256"]
        )
        self.assertEqual(
            SOURCE_FILE_VECTOR_SHA256, report["source_file_vector_sha256"]
        )
        self.assertEqual(PACKED_BYTES_SHA256, report["packed_bytes_sha256"])
        self.assertEqual(
            {"consumed_literal_range": 12, "owned_thumb_function": 1},
            report["right_kind_counts"],
        )
        self.assertEqual(4, report["source_artifact_count"])
        self.assertTrue(report["all_alignment_equations_hold"])
        self.assertTrue(report["all_boundaries_exact"])
        self.assertEqual(EXPECTED_IDS, tuple(row["id"] for row in report["gaps"]))
        self.assertEqual(
            EXPECTED_RIGHT_KINDS,
            tuple(row["right_kind"] for row in report["gaps"]),
        )
        self.assertEqual(
            NEW_SOURCE_IDS,
            tuple(
                (row["left_source_id"], row["right_source_id"])
                for row in report["gaps"][4:]
            ),
        )

    def test_report_vectors_are_recomputed_from_explicit_rows(self) -> None:
        report = _load_verifier().verify_root(ROOT)
        ranges = [row["gap_range"] for row in report["gaps"]]
        self.assertEqual([list(pair) for pair in RANGES], ranges)
        self.assertEqual(sorted(ranges), ranges)
        self.assertTrue(all(left[1] <= right[0] for left, right in zip(ranges, ranges[1:])))
        self.assertEqual(RANGE_VECTOR_SHA256, _compact_sha(ranges))

        boundaries = [
            [
                row["id"],
                row["source_artifact_schema"],
                row["left_owner_range"],
                row["left_owner_kind"],
                row["left_source_id"],
                row["left_terminal"]["range"],
                row["left_terminal"]["flow_kind"],
                row["left_terminal"]["mnemonic"],
                row["left_terminal"]["operand"],
                row["left_terminal"]["raw_hex"],
                row["left_terminal"]["target_offset"],
                row["gap_range"],
                row["right_kind"],
                row["right_range"],
                row["right_source_id"],
            ]
            for row in report["gaps"]
        ]
        claims = [
            [
                row["id"],
                row["gap_range"],
                PRIMARY_CLASS,
                CLAIM_KIND,
                row["right_kind"],
                row["source_artifact_schema"],
            ]
            for row in report["gaps"]
        ]
        self.assertEqual(BOUNDARY_VECTOR_SHA256, _compact_sha(boundaries))
        self.assertEqual(CLAIM_DENOMINATOR_SHA256, _compact_sha(claims))

        artifacts = report["source_artifacts"]
        self.assertEqual(
            {
                "rom-task-scheduler-core-v1",
                "rom-psg-frequency-lookup-v1",
                "rom-cgb-helper-bounded-cfg-v1",
                "rom-cgbsound-bounded-cfg-v1",
            },
            set(artifacts),
        )
        source_rows = []
        source_receipts = []
        for schema, path, sha256, size in EXPECTED_SOURCE_FILES:
            self.assertEqual(
                {"sha256": sha256, "size": size}, artifacts[schema]["files"][path]
            )
            source_rows.append([path, sha256, size])
            source_receipts.append(
                {"path": path, "sha256": sha256, "size": size}
            )
        self.assertEqual(source_receipts, report["source_file_receipts"])
        self.assertEqual(12, len(report["source_file_receipts"]))
        self.assertEqual(SOURCE_FILE_VECTOR_SHA256, _compact_sha(source_rows))
        self.assertEqual(len(artifacts), report["source_artifact_count"])
        self.assertEqual(
            "e1f4d0b840d52b19ee996ee7c0ba18c41511f0c96b37f498f77954a24c9105b7",
            artifacts["rom-cgb-helper-bounded-cfg-v1"]["contract_sha256"],
        )
        self.assertEqual(
            "build/experiments/active/cgbsound-bounded-cfg-20260829/candidate",
            artifacts["rom-cgbsound-bounded-cfg-v1"]["source_candidate_artifact"],
        )
        self.assertEqual(
            {
                "artifact_status": "candidate",
                "bundle_sha256": "87c62bbe5f0e9d25ee5b11398ecdd3ed5b41782d4873871205f71c1122a4c1dc",
                "manifest_sha256": "cad4873e706f5425e75ee080af43096420be41a85d0f0cdf863496f0f792b3ad",
                "payload_sha256": "dccdca087744e57136b180dba1c3e4151c123efecec10d5d53f90894dc760960",
            },
            artifacts["rom-cgb-helper-bounded-cfg-v1"]["source_candidate_identity"],
        )

    def test_old_artifact_semantic_forgery_fails_after_complete_resign(self) -> None:
        scheduler_claim = copy.deepcopy(self.scheduler_payload)
        scheduler_claim["coverage_claims"][2]["kind"] = "literal"
        report = self._verify_resigned_payload("scheduler", scheduler_claim)
        self.assertFalse(report["verified"], report)
        self.assertTrue(any("claim" in error for error in report["errors"]), report["errors"])

        scheduler_owner = copy.deepcopy(self.scheduler_payload)
        scheduler_owner["existing_owned_provenance"][1]["primary_class"] = "forged"
        report = self._verify_resigned_payload("scheduler", scheduler_owner)
        self.assertFalse(report["verified"], report)
        self.assertTrue(any("owner" in error or "provenance" in error for error in report["errors"]), report["errors"])

        psg_semantic = copy.deepcopy(self.psg_payload)
        psg_semantic["promotion"]["semantic_ranges"][1]["kind"] = "forged"
        report = self._verify_resigned_payload("psg", psg_semantic)
        self.assertFalse(report["verified"], report)
        self.assertTrue(any("semantic" in error or "owner" in error for error in report["errors"]), report["errors"])

        psg_binding = copy.deepcopy(self.psg_payload)
        psg_binding["literal_bindings"][0]["pointer"] ^= 4
        report = self._verify_resigned_payload("psg", psg_binding)
        self.assertFalse(report["verified"], report)
        self.assertTrue(any("binding" in error or "literal" in error for error in report["errors"]), report["errors"])

    def test_old_accepted_manifest_exact_receipt_rejects_resigning(self) -> None:
        verifier = _load_verifier()
        for prefix, manifest_attr in (("SCHEDULER", "scheduler_manifest"), ("PSG", "psg_manifest")):
            manifest = copy.deepcopy(getattr(self, manifest_attr))
            manifest["unexpected"] = False
            manifest["verification"]["report"]["verified"] = False
            manifest["verifier"] = copy.deepcopy(manifest["verification"])
            raw = (
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            with self.subTest(artifact=prefix), mock.patch.object(
                verifier, f"{prefix}_MANIFEST_SHA256", _sha(raw)
            ), mock.patch.object(verifier, f"{prefix}_MANIFEST_SIZE", len(raw)):
                report = self._verify_inputs(
                    self.rom, **{manifest_attr: manifest}
                )
                self.assertFalse(report["verified"], report)
                self.assertTrue(any("receipt" in error or "manifest" in error for error in report["errors"]), report["errors"])

    def test_old_manifest_and_payload_scope_drift_fail_after_complete_resign(self) -> None:
        verifier = _load_verifier()
        cases = (
            (
                "scheduler",
                "scheduler_manifest",
                "SCHEDULER_MANIFEST_SHA256",
                "SCHEDULER_MANIFEST_SIZE",
                "allocatable_free_space_proven",
            ),
            (
                "psg",
                "psg_manifest",
                "PSG_MANIFEST_SHA256",
                "PSG_MANIFEST_SIZE",
                "playback_behavior_proven",
            ),
        )
        for artifact, manifest_attr, sha_attr, size_attr, scope_key in cases:
            manifest = copy.deepcopy(getattr(self, manifest_attr))
            self.assertIs(manifest["scope"][scope_key], False)
            manifest["scope"][scope_key] = True
            raw = (
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n"
            ).encode("utf-8")
            with self.subTest(artifact=artifact, layer="manifest"), mock.patch.object(
                verifier, sha_attr, _sha(raw)
            ), mock.patch.object(verifier, size_attr, len(raw)):
                report = self._verify_inputs(
                    self.rom, **{manifest_attr: manifest}
                )
            self.assertFalse(report["verified"], report)
            self.assertTrue(
                any("manifest" in error or "receipt" in error for error in report["errors"]),
                report["errors"],
            )

            payload = copy.deepcopy(getattr(self, f"{artifact}_payload"))
            self.assertIs(payload["scope"][scope_key], False)
            payload["scope"][scope_key] = True
            validator = (
                verifier._validate_scheduler_payload
                if artifact == "scheduler"
                else verifier._validate_psg_payload
            )
            with self.subTest(artifact=artifact, layer="payload-validator"), self.assertRaisesRegex(
                ValueError, "payload semantic"
            ):
                validator(payload)
            report = self._verify_resigned_payload(
                artifact,
                payload,
                bypass_semantic_receipts=False,
            )
            self.assertFalse(report["verified"], report)
            self.assertTrue(
                any(
                    marker in error
                    for error in report["errors"]
                    for marker in ("payload", "scope", "manifest", "receipt")
                ),
                report["errors"],
            )

    def test_bounded_split_and_literal_binding_forgery_fail_after_resign(self) -> None:
        helper = copy.deepcopy(self.helper_payload)
        row = helper["promotion"]["ranges"].pop(0)
        split = 636238
        helper["promotion"]["ranges"][0:0] = [
            {"bytes": split - row["range"][0], "kind": row["kind"], "range": [row["range"][0], split], "sha256": _sha(self.rom[row["range"][0]:split])},
            {"bytes": row["range"][1] - split, "kind": row["kind"], "range": [split, row["range"][1]], "sha256": _sha(self.rom[split:row["range"][1]])},
        ]
        helper["promotion_ranges"] = copy.deepcopy(helper["promotion"]["ranges"])
        report = self._verify_resigned_payload("helper", helper)
        self.assertFalse(report["verified"], report)
        self.assertTrue(any("promotion" in error or "range" in error for error in report["errors"]), report["errors"])

        cgbsound = copy.deepcopy(self.cgbsound_payload)
        cgbsound["literal_projection"]["bindings"][0][2] ^= 4
        report = self._verify_resigned_payload("cgbsound", cgbsound)
        self.assertFalse(report["verified"], report)
        self.assertTrue(any("binding" in error or "literal" in error for error in report["errors"]), report["errors"])

    def test_each_gap_binds_terminal_align4_right_owner_and_raw_rom(self) -> None:
        report = _load_verifier().verify_root(ROOT)
        for index, row in enumerate(report["gaps"]):
            start, end = RANGES[index]
            terminal_range, raw_hex, flow_kind, target = EXPECTED_TERMINALS[index]
            self.assertEqual([start, end], row["gap_range"])
            self.assertEqual("0000", row["gap_raw_hex"])
            self.assertEqual(ZERO_PAIR_SHA256, row["gap_sha256"])
            self.assertEqual(2, row["gap_size"])
            self.assertEqual(terminal_range, row["left_terminal"]["range"])
            self.assertEqual(raw_hex, row["left_terminal"]["raw_hex"])
            self.assertEqual(flow_kind, row["left_terminal"]["flow_kind"])
            self.assertEqual(target, row["left_terminal"]["target_offset"])
            self.assertEqual(start, row["left_owner_range"][1])
            self.assertEqual(end, row["right_range"][0])
            self.assertEqual(end, (start + 3) & ~3)
            self.assertTrue(row["gap_start_equals_left_owner_end"])
            self.assertTrue(row["gap_end_equals_align4_left_end"])
            self.assertTrue(row["right_start_equals_gap_end"])
            self.assertEqual(self.rom[start:end].hex(), row["gap_raw_hex"])
        self.assertEqual(
            "owned_thumb_function", report["gaps"][1]["right_kind"]
        )
        self.assertNotEqual(
            "consumed_literal_range", report["gaps"][1]["right_kind"]
        )
        new_rows = report["gaps"][4:]
        self.assertEqual(8, sum(row["left_terminal"]["mnemonic"] == "b" for row in new_rows))
        self.assertEqual(1, sum(row["left_terminal"]["operand"] == "lr" for row in new_rows))

    def test_new_artifact_semantics_fail_after_outer_payload_hash_bypass(self) -> None:
        verifier = _load_verifier()
        for payload_attr, sha_attr, gap_range, left_range, right_range in NEW_ARTIFACT_CASES:
            original = getattr(self, payload_attr)

            excluded = copy.deepcopy(original)
            excluded_row = next(
                row for row in excluded["excluded_ranges"] if row["range"] == list(gap_range)
            )
            excluded_row["promoted"] = True
            with self.subTest(gap=hex(gap_range[0]), layer="excluded"), mock.patch.object(
                verifier, sha_attr, _canonical_sha(excluded)
            ):
                report = self._verify_inputs(self.rom, **{payload_attr: excluded})
                self.assertFalse(report["verified"])
                self.assertTrue(any("excluded" in error or "gap" in error for error in report["errors"]), report["errors"])

            terminal = copy.deepcopy(original)
            terminal_row = next(
                row for row in terminal["cfg"]["instructions"] if row["offset"] == gap_range[0] - 2
            )
            terminal_row["mnemonic"] = "movs"
            with self.subTest(gap=hex(gap_range[0]), layer="instruction"), mock.patch.object(
                verifier, sha_attr, _canonical_sha(terminal)
            ):
                report = self._verify_inputs(self.rom, **{payload_attr: terminal})
                self.assertFalse(report["verified"])
                self.assertTrue(any("instruction" in error or "terminal" in error for error in report["errors"]), report["errors"])

            left = copy.deepcopy(original)
            left_row = next(
                row for row in left["promotion"]["ranges"] if row["range"] == list(left_range)
            )
            left_row["kind"] = "forged_thumb_code"
            with self.subTest(gap=hex(gap_range[0]), layer="left"), mock.patch.object(
                verifier, sha_attr, _canonical_sha(left)
            ):
                report = self._verify_inputs(self.rom, **{payload_attr: left})
                self.assertFalse(report["verified"])
                self.assertTrue(any("promotion" in error or "left" in error for error in report["errors"]), report["errors"])

            right = copy.deepcopy(original)
            right["literal_projection"]["ranges"].remove(list(right_range))
            with self.subTest(gap=hex(gap_range[0]), layer="right"), mock.patch.object(
                verifier, sha_attr, _canonical_sha(right)
            ):
                report = self._verify_inputs(self.rom, **{payload_attr: right})
                self.assertFalse(report["verified"])
                self.assertTrue(any("literal" in error or "right" in error for error in report["errors"]), report["errors"])

    def test_new_accepted_receipts_reject_semantic_resigning(self) -> None:
        verifier = _load_verifier()
        for manifest_attr, sha_attr in (
            ("helper_manifest", "HELPER_MANIFEST_SHA256"),
            ("cgbsound_manifest", "CGBSOUND_MANIFEST_SHA256"),
        ):
            manifest = copy.deepcopy(getattr(self, manifest_attr))
            manifest["artifact_status"] = "candidate"
            with self.subTest(manifest=manifest_attr), mock.patch.object(
                verifier, sha_attr, _canonical_sha(manifest)
            ):
                report = self._verify_inputs(self.rom, **{manifest_attr: manifest})
                self.assertFalse(report["verified"])
                self.assertTrue(any("accepted" in error or "receipt" in error for error in report["errors"]), report["errors"])

    def test_rom_and_source_semantic_mutations_fail_after_shallow_resign(self) -> None:
        verifier = _load_verifier()
        for start, _ in RANGES:
            with self.subTest(gap=hex(start)):
                mutated = bytearray(self.rom)
                mutated[start] = 1
                with mock.patch.object(verifier, "ROM_SHA256", _sha(bytes(mutated))):
                    report = self._verify_inputs(bytes(mutated))
                self.assertFalse(report["verified"])
                self.assertTrue(any("gap" in error or "zero" in error for error in report["errors"]))

        for terminal_range, _, _, _ in EXPECTED_TERMINALS:
            offset = terminal_range[0]
            with self.subTest(terminal=hex(offset)):
                mutated = bytearray(self.rom)
                mutated[offset] ^= 1
                with mock.patch.object(verifier, "ROM_SHA256", _sha(bytes(mutated))):
                    report = self._verify_inputs(bytes(mutated))
                self.assertFalse(report["verified"])
                self.assertTrue(
                    any(
                        marker in error
                        for error in report["errors"]
                        for marker in ("terminal", "branch", "return", "boundary")
                    ),
                    report["errors"],
                )

        scheduler = copy.deepcopy(self.scheduler_payload)
        scheduler["unclassified_unknown_ranges"].reverse()
        report = self._verify_inputs(self.rom, scheduler_payload=scheduler)
        self.assertFalse(report["verified"])
        self.assertTrue(any("scheduler" in error or "range" in error for error in report["errors"]))

        psg = copy.deepcopy(self.psg_payload)
        psg["consumer"]["unclassified_unknown_ranges"] = [[0x09B4C4, 0x09B4C8]]
        report = self._verify_inputs(self.rom, psg_payload=psg)
        self.assertFalse(report["verified"])
        self.assertTrue(any("PSG" in error or "range" in error for error in report["errors"]))

    def test_source_artifacts_are_hash_bound_canonical_and_fail_closed(self) -> None:
        verifier = _load_verifier()
        report = verifier.verify_root(ROOT)
        self.assertEqual(
            "88ef48526ed1bd096a8ece9a58aa4f5770f207084634a125f04dc99561c7d58c",
            report["source_artifacts"]["rom-task-scheduler-core-v1"][
                "manifest_sha256"
            ],
        )
        self.assertEqual(
            "4fffbcc7e252595834adb368d10b3ce8f13323aee18cc518d98e0ff9c519575f",
            report["source_artifacts"]["rom-psg-frequency-lookup-v1"][
                "manifest_sha256"
            ],
        )
        self.assertEqual(
            "8a53b3ee982799583e08ef852fb2cac9771f856e77ed104cc2814cfd1e7ef6d1",
            report["source_artifacts"]["rom-cgb-helper-bounded-cfg-v1"][
                "manifest_sha256"
            ],
        )
        self.assertEqual(
            "4248c0fed46682d06918ac124d3c861a60c12117023a773190ff831840963b6e",
            report["source_artifacts"]["rom-cgbsound-bounded-cfg-v1"][
                "manifest_sha256"
            ],
        )

        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
            project = Path(raw) / "project"
            (project / "tools").mkdir(parents=True)
            (project / "tests").mkdir()
            (project / "rom").mkdir()
            shutil.copy2(ROM_PATH, project / "rom/base.gba")
            shutil.copytree(SCHEDULER_DIR, project / SCHEDULER_DIR.relative_to(ROOT))
            shutil.copytree(PSG_DIR, project / PSG_DIR.relative_to(ROOT))
            shutil.copytree(HELPER_DIR, project / HELPER_DIR.relative_to(ROOT))
            shutil.copytree(CGBSOUND_DIR, project / CGBSOUND_DIR.relative_to(ROOT))
            payload = (
                project
                / "artifacts/rom-task-scheduler-core-v1/rom-task-scheduler-core.json"
            )
            data = json.loads(payload.read_text(encoding="utf-8"))
            data["unclassified_unknown_ranges"].reverse()
            payload.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            tampered = verifier.verify_root(project)
            self.assertFalse(tampered["verified"])
            self.assertTrue(any("identity" in error or "hash" in error for error in tampered["errors"]))

    def test_wrong_missing_and_symlink_roots_or_artifacts_fail_closed(self) -> None:
        verifier = _load_verifier()
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
            temp = Path(raw)
            self.assertFalse(verifier.verify_root(temp / "missing")["verified"])
            root_link = temp / "root-link"
            root_link.symlink_to(ROOT, target_is_directory=True)
            linked = verifier.verify_root(root_link)
            self.assertFalse(linked["verified"])
            self.assertTrue(any("symlink" in error for error in linked["errors"]))

            artifact_link_project = temp / "artifact-link-project"
            (artifact_link_project / "tools").mkdir(parents=True)
            (artifact_link_project / "tests").mkdir()
            (artifact_link_project / "rom").mkdir()
            shutil.copy2(ROM_PATH, artifact_link_project / "rom/base.gba")
            (artifact_link_project / "artifacts").mkdir()
            (
                artifact_link_project / "artifacts/rom-task-scheduler-core-v1"
            ).symlink_to(SCHEDULER_DIR, target_is_directory=True)
            shutil.copytree(
                PSG_DIR,
                artifact_link_project / "artifacts/rom-psg-frequency-lookup-v1",
            )
            shutil.copytree(
                HELPER_DIR,
                artifact_link_project / "artifacts/rom-cgb-helper-bounded-cfg-v1",
            )
            shutil.copytree(
                CGBSOUND_DIR,
                artifact_link_project / "artifacts/rom-cgbsound-bounded-cfg-v1",
            )
            linked_artifact = verifier.verify_root(artifact_link_project)
            self.assertFalse(linked_artifact["verified"])
            self.assertTrue(
                any("symlink" in error for error in linked_artifact["errors"])
            )

    def test_new_artifact_file_member_and_symlink_mutations_fail_closed(self) -> None:
        verifier = _load_verifier()
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
            temp = Path(raw)

            changed = temp / "changed"
            self._copy_project(changed)
            binary = changed / HELPER_DIR.relative_to(ROOT) / "rom-cgb-helper-bounded-cfg.bin"
            mutated = bytearray(binary.read_bytes())
            mutated[0] ^= 1
            binary.write_bytes(mutated)
            report = verifier.verify_root(changed)
            self.assertFalse(report["verified"])
            self.assertTrue(any("identity" in error or "hash" in error for error in report["errors"]), report["errors"])

            extra = temp / "extra"
            self._copy_project(extra)
            (extra / CGBSOUND_DIR.relative_to(ROOT) / "unexpected.txt").write_text(
                "unexpected", encoding="utf-8"
            )
            report = verifier.verify_root(extra)
            self.assertFalse(report["verified"])
            self.assertTrue(any("denominator" in error or "file" in error for error in report["errors"]), report["errors"])

            linked = temp / "linked"
            self._copy_project(linked)
            payload = linked / HELPER_DIR.relative_to(ROOT) / "rom-cgb-helper-bounded-cfg.json"
            payload.unlink()
            payload.symlink_to(HELPER_DIR / "rom-cgb-helper-bounded-cfg.json")
            report = verifier.verify_root(linked)
            self.assertFalse(report["verified"])
            self.assertTrue(any("symlink" in error for error in report["errors"]), report["errors"])

    def test_artifact_member_set_and_replacement_races_fail_closed(self) -> None:
        verifier = _load_verifier()
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
            temp = Path(raw)
            for mode in ("extra", "replacement"):
                project = temp / mode
                self._copy_project(project)
                artifact = project / HELPER_DIR.relative_to(ROOT)
                manifest_raw = (artifact / "manifest.json").read_bytes()
                triggered = False
                real_sha = verifier._sha

                def racing_sha(data: bytes) -> str:
                    nonlocal triggered
                    if not triggered and data == manifest_raw:
                        triggered = True
                        if mode == "extra":
                            (artifact / "unexpected-race").write_bytes(b"race")
                        else:
                            payload = artifact / "rom-cgb-helper-bounded-cfg.json"
                            saved = payload.read_bytes()
                            payload.rename(artifact / "replaced-original.json")
                            payload.write_bytes(saved)
                    return real_sha(data)

                with self.subTest(mode=mode), mock.patch.object(
                    verifier, "_sha", side_effect=racing_sha
                ):
                    report = verifier.verify_root(project)
                self.assertTrue(triggered)
                self.assertFalse(report["verified"], report)
                self.assertTrue(
                    any(
                        marker in error
                        for error in report["errors"]
                        for marker in ("snapshot", "member", "directory", "identity")
                    ),
                    report["errors"],
                )

    def test_artifact_ancestor_symlink_swap_race_fails_closed(self) -> None:
        verifier = _load_verifier()
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
            temp = Path(raw)
            project = temp / "project"
            self._copy_project(project)
            artifacts = project / "artifacts"
            original = project / "artifacts-original"
            outside = temp / "outside-artifacts"
            shutil.copytree(artifacts, outside)
            target = artifacts / SCHEDULER_DIR.name
            real_open = verifier.os.open
            real_close = verifier.os.close
            triggered = False
            raced_directory_fd: int | None = None

            def restore() -> None:
                if artifacts.is_symlink():
                    artifacts.unlink()
                    original.rename(artifacts)

            def racing_open(path, flags, *args, **kwargs):
                nonlocal triggered, raced_directory_fd
                old_absolute_open = Path(path) == target
                anchored_component_open = (
                    path == "artifacts" and kwargs.get("dir_fd") is not None
                )
                if not triggered and (old_absolute_open or anchored_component_open):
                    triggered = True
                    artifacts.rename(original)
                    artifacts.symlink_to(outside, target_is_directory=True)
                descriptor = real_open(path, flags, *args, **kwargs)
                if old_absolute_open and triggered:
                    raced_directory_fd = descriptor
                return descriptor

            def racing_close(descriptor: int) -> None:
                real_close(descriptor)
                if descriptor == raced_directory_fd:
                    restore()

            try:
                with mock.patch.object(
                    verifier.os, "open", side_effect=racing_open
                ), mock.patch.object(
                    verifier.os, "close", side_effect=racing_close
                ):
                    report = verifier.verify_root(project)
            finally:
                restore()
            self.assertTrue(triggered)
            self.assertFalse(report["verified"], report)
            self.assertTrue(
                any(
                    marker in error
                    for error in report["errors"]
                    for marker in ("ancestor", "snapshot", "symlink", "open")
                ),
                report["errors"],
            )

    def test_cli_is_deterministic_and_verifier_is_independent(self) -> None:
        command = [sys.executable, str(VERIFIER_PATH), "--root", str(ROOT)]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(1, len(completed.stdout.splitlines()))
        self.assertEqual(
            _load_verifier().verify_root(ROOT), json.loads(completed.stdout)
        )

        tree = ast.parse(VERIFIER_PATH.read_text(encoding="utf-8"))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        forbidden = (
            "export_rom_task_scheduler_core",
            "export_rom_psg_frequency_lookup",
            "verify_rom_task_scheduler_core",
            "verify_rom_psg_frequency_lookup",
            "export_rom_cgb_helper_bounded_cfg",
            "verify_rom_cgb_helper_bounded_cfg",
            "export_rom_cgbsound_bounded_cfg",
            "verify_rom_cgbsound_bounded_cfg",
            "audit_rom_byte_coverage",
        )
        self.assertFalse(
            any(name.endswith(suffix) for name in imports for suffix in forbidden),
            imports,
        )

    def test_non_claims_remain_false(self) -> None:
        report = _load_verifier().verify_root(ROOT)
        self.assertTrue(report["verified"], report["errors"])
        self.assertTrue(report["non_claims"])
        self.assertTrue(all(value is False for value in report["non_claims"].values()))
        for key, value in report["non_claims"].items():
            self.assertIn(key, report)
            self.assertIs(report[key], value)


if __name__ == "__main__":
    unittest.main()
