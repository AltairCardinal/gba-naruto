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
ARTIFACT = ROOT / "artifacts/character-battle-visual-resource-matrix-v1"
VARIANTS = ("baseline", "palette", "component", "timeline")
IMPLEMENTATION_PATHS = (
    "tools/build_character_battle_visual_resource_matrix.py",
    "tools/export_character_battle_visual_resource_matrix_evidence.py",
    "tools/verify_character_battle_visual_resource_matrix_evidence.py",
    "tools/inspect_mgba_savestate.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_single_input_replay.lua",
    "tests/test_build_character_battle_visual_resource_matrix.py",
    "tests/test_character_battle_visual_resource_matrix_evidence.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resign(artifact: Path, relative: str) -> None:
    manifest_path = artifact / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][relative] = _sha256(artifact / relative)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _replace_state_byte(path: Path, state_offset: int, value: int) -> None:
    source = path.read_bytes()
    output = bytearray(source[:8])
    cursor = 8
    while cursor < len(source):
        size = struct.unpack_from(">I", source, cursor)[0]
        tag = source[cursor + 4 : cursor + 8]
        payload = source[cursor + 8 : cursor + 8 + size]
        cursor += 12 + size
        if tag == b"gbAs":
            state = bytearray(zlib.decompress(payload))
            state[state_offset] = value
            payload = zlib.compress(state)
        output.extend(struct.pack(">I", len(payload)))
        output.extend(tag)
        output.extend(payload)
        output.extend(struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))
    path.write_bytes(output)


def _refresh_implementation_hashes(artifact: Path) -> None:
    manifest_path = artifact / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["implementation_sha256"] = {
        relative: _sha256(ROOT / relative) for relative in IMPLEMENTATION_PATHS
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _copy_minimal_root(destination: Path) -> None:
    paths = (
        "rom/base.gba",
        "artifacts/character-battle-visuals-v1/manifest.json",
        *IMPLEMENTATION_PATHS,
    )
    for relative in paths:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)


class CharacterBattleVisualResourceMatrixEvidenceTests(unittest.TestCase):
    def test_exporter_rebuilds_a_verifiable_artifact(self):
        from tools.export_character_battle_visual_resource_matrix_evidence import export
        from tools.verify_character_battle_visual_resource_matrix_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            temporary = Path(temporary)
            run = temporary / "run"
            (run / "build").mkdir(parents=True)
            shutil.copy2(
                ARTIFACT / "build-manifest.json",
                run / "build/build-manifest.json",
            )
            base = (ROOT / "rom/base.gba").read_bytes()
            for variant in VARIANTS:
                runtime = run / "runtime" / variant
                runtime.mkdir(parents=True)
                for name in (
                    "frame80.ss9",
                    "frame80.png",
                    "audit.json",
                    "sentinel.json",
                    "guard.json",
                    "outer-guard.json",
                ):
                    shutil.copy2(ARTIFACT / variant / name, runtime / name)
                rom = bytearray(base + bytes([0xFF]) * (0x1000000 - len(base)))
                bundle = (ARTIFACT / variant / "bundle.bin").read_bytes()
                rom[0x600000 : 0x600000 + len(bundle)] = bundle
                rom[0x596D5C : 0x596D5C + 16] = struct.pack(
                    "<4I",
                    0x08604A00,
                    0x08604B30,
                    0x08600020,
                    0x08600000,
                )
                (runtime / "staged.gba").write_bytes(rom)

            output = temporary / "artifact"
            manifest = export(ROOT, run, output)
            self.assertEqual(
                "character-battle-visual-resource-matrix-v1",
                manifest["artifact_schema"],
            )
            report = verify(ROOT, output)
            self.assertTrue(report["verified"], report["errors"])

    def test_independent_verifier_accepts_production_artifact(self):
        from tools.verify_character_battle_visual_resource_matrix_evidence import verify

        source = (
            ROOT / "tools/verify_character_battle_visual_resource_matrix_evidence.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools.build_character_battle_visual_resource_matrix", source)
        self.assertNotIn(
            "from tools.export_character_battle_visual_resource_matrix_evidence", source
        )
        self.assertNotIn("from tools.import_character_battle_bundles", source)

        report = verify(ROOT, ARTIFACT)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual({"PRAM": [0x202]}, report["memory_differences"]["palette"])
        self.assertEqual({"OAM": [2]}, report["memory_differences"]["component"])
        self.assertEqual(394, len(report["memory_differences"]["timeline"]["VRAM"]))
        self.assertEqual(
            {"palette": 268, "component": 634, "timeline": 616},
            report["pixel_change_counts"],
        )
        self.assertEqual(
            {"baseline": 3, "palette": 3, "component": 3, "timeline": 4},
            report["selected_frame_ids"],
        )

    def test_rejects_resigned_candidate_bundle_tamper(self):
        from tools.verify_character_battle_visual_resource_matrix_evidence import verify

        for variant, offset in (("palette", 2), ("component", 0x486C), ("timeline", 0x4A64)):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temporary:
                artifact = Path(temporary) / "artifact"
                shutil.copytree(ARTIFACT, artifact)
                path = artifact / variant / "bundle.bin"
                payload = bytearray(path.read_bytes())
                payload[offset] ^= 1
                path.write_bytes(payload)
                _resign(artifact, f"{variant}/bundle.bin")

                report = verify(ROOT, artifact)
                self.assertFalse(report["verified"])
                self.assertTrue(
                    any(f"{variant} bundle" in error for error in report["errors"]),
                    report["errors"],
                )

    def test_rejects_resigned_runtime_domain_tamper(self):
        from tools.verify_character_battle_visual_resource_matrix_evidence import verify

        cases = (
            ("palette", 0x800 + 0x202, 0x84, "palette runtime"),
            ("component", 0xC00 + 2, 0x68, "component runtime"),
            ("timeline", 0x1000 + 0x1009F, 0xFF, "timeline runtime"),
            ("timeline", 0x19000 + 0x597C + 0x14, 0x02, "timeline task"),
        )
        for variant, offset, value, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temporary:
                artifact = Path(temporary) / "artifact"
                shutil.copytree(ARTIFACT, artifact)
                path = artifact / variant / "frame80.ss9"
                _replace_state_byte(path, offset, value)
                _resign(artifact, f"{variant}/frame80.ss9")

                report = verify(ROOT, artifact)
                self.assertFalse(report["verified"])
                self.assertTrue(
                    any(expected in error for error in report["errors"]),
                    report["errors"],
                )

    def test_rejects_resigned_screenshot_or_pixel_contract_tamper(self):
        from tools.verify_character_battle_visual_resource_matrix_evidence import verify

        for kind in ("screenshot", "evidence"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                artifact = Path(temporary) / "artifact"
                shutil.copytree(ARTIFACT, artifact)
                if kind == "screenshot":
                    path = artifact / "palette/frame80.png"
                    shutil.copy2(artifact / "baseline/frame80.png", path)
                    _resign(artifact, "palette/frame80.png")
                    expected = "screenshot"
                else:
                    path = artifact / "runtime-evidence.json"
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    payload["runtime"]["palette"]["pixel_change_count"] = 267
                    path.write_text(
                        json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    _resign(artifact, "runtime-evidence.json")
                    expected = "pixel"

                report = verify(ROOT, artifact)
                self.assertFalse(report["verified"])
                self.assertTrue(
                    any(expected in error for error in report["errors"]),
                    report["errors"],
                )

    def test_rejects_resigned_run_provenance_tamper(self):
        from tools.verify_character_battle_visual_resource_matrix_evidence import verify

        for kind in ("audit", "guard"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                artifact = Path(temporary) / "artifact"
                shutil.copytree(ARTIFACT, artifact)
                if kind == "audit":
                    for name in ("audit.json", "sentinel.json"):
                        path = artifact / "baseline" / name
                        payload = json.loads(path.read_text(encoding="utf-8"))
                        payload["capture_frame"] = 999
                        path.write_text(json.dumps(payload), encoding="utf-8")
                        _resign(artifact, f"baseline/{name}")
                else:
                    path = artifact / "timeline/guard.json"
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    payload["command"] = ["/bin/true"]
                    path.write_text(
                        json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    _resign(artifact, "timeline/guard.json")

                report = verify(ROOT, artifact)
                self.assertFalse(report["verified"])
                self.assertTrue(
                    any("provenance" in error for error in report["errors"]),
                    report["errors"],
                )

    def test_rejects_resigned_provenance_identity_rewrites(self):
        from tools.verify_character_battle_visual_resource_matrix_evidence import verify

        variants = ("baseline", "palette", "component", "timeline")
        for kind in ("child_pid", "run_ids", "outer_argument_pair"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                artifact = Path(temporary) / "artifact"
                shutil.copytree(ARTIFACT, artifact)
                _refresh_implementation_hashes(artifact)
                if kind == "child_pid":
                    guard_path = artifact / "component/guard.json"
                    guard = json.loads(guard_path.read_text(encoding="utf-8"))
                    guard["child_pid"] = 1
                    guard_path.write_text(
                        json.dumps(guard, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    _resign(artifact, "component/guard.json")
                    guard_sha = _sha256(guard_path)
                    for name in ("audit.json", "sentinel.json"):
                        path = artifact / "component" / name
                        payload = json.loads(path.read_text(encoding="utf-8"))
                        payload["guard_summary_sha256"] = guard_sha
                        path.write_text(
                            json.dumps(payload, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8",
                        )
                        _resign(artifact, f"component/{name}")
                elif kind == "run_ids":
                    evidence_path = artifact / "runtime-evidence.json"
                    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
                    for index, variant in enumerate(variants):
                        run_id = f"rewritten-run-{index}"
                        for name in ("audit.json", "sentinel.json"):
                            path = artifact / variant / name
                            payload = json.loads(path.read_text(encoding="utf-8"))
                            payload["run_id"] = run_id
                            path.write_text(
                                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                                encoding="utf-8",
                            )
                            _resign(artifact, f"{variant}/{name}")
                        evidence["runs"][variant]["run_id"] = run_id
                    evidence_path.write_text(
                        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    _resign(artifact, "runtime-evidence.json")
                    manifest_path = artifact / "manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["payload_sha256"] = _sha256(evidence_path)
                    manifest_path.write_text(
                        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                else:
                    path = artifact / "timeline/outer-guard.json"
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    command = payload["command"]
                    index = command.index("--expected-rom-sha256")
                    correct = command[index + 1]
                    command[index + 1] = "0" * 64
                    command.append(correct)
                    path.write_text(
                        json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    _resign(artifact, "timeline/outer-guard.json")

                report = verify(ROOT, artifact)
                self.assertFalse(report["verified"], kind)
                self.assertTrue(
                    any("provenance" in error for error in report["errors"]),
                    report["errors"],
                )

    def test_timeline_selection_requires_animation_table_indirection(self):
        from tools.verify_character_battle_visual_resource_matrix_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            _refresh_implementation_hashes(artifact)
            path = artifact / "timeline/bundle.bin"
            payload = bytearray(path.read_bytes())
            struct.pack_into("<I", payload, 0x4B34, 0x08604A68)
            path.write_bytes(payload)
            _resign(artifact, "timeline/bundle.bin")

            report = verify(ROOT, artifact)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any(
                    "timeline animation selection" in error
                    for error in report["errors"]
                ),
                report["errors"],
            )

    def test_rejects_missing_or_tampered_parent_checkpoint(self):
        from tools.verify_character_battle_visual_resource_matrix_evidence import verify

        for kind in ("missing", "tampered"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "root"
                _copy_minimal_root(root)
                if kind == "tampered":
                    checkpoint = root / "artifacts/runtime-checkpoints/scenario-41-start-row.ss9"
                    checkpoint.parent.mkdir(parents=True)
                    checkpoint.write_bytes(b"tampered checkpoint")

                report = verify(root, ARTIFACT)
                self.assertFalse(report["verified"])
                self.assertIn("input checkpoint identity mismatch", report["errors"])

    def test_rejects_resigned_build_scope_or_verifier_tamper(self):
        from tools.verify_character_battle_visual_resource_matrix_evidence import verify

        for kind in ("build", "scope", "verifier"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                artifact = Path(temporary) / "artifact"
                shutil.copytree(ARTIFACT, artifact)
                if kind == "build":
                    path = artifact / "build-manifest.json"
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    payload["runtime_contract"]["capture_frame"] = 79
                    path.write_text(
                        json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    _resign(artifact, "build-manifest.json")
                    expected = "build manifest"
                else:
                    path = artifact / "manifest.json"
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if kind == "scope":
                        payload["scope"]["all_250_resources_runtime_verified"] = True
                    else:
                        payload["verifier"]["command"] = ["false"]
                        payload["verifier"]["result"] = {"verified": False}
                    path.write_text(
                        json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    expected = "promotion manifest"

                report = verify(ROOT, artifact)
                self.assertFalse(report["verified"])
                self.assertTrue(
                    any(expected in error for error in report["errors"]),
                    report["errors"],
                )


if __name__ == "__main__":
    unittest.main()
