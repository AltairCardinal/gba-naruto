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
ARTIFACT = ROOT / "artifacts/character-battle-graphics-pixel-ab-v1"
IMPLEMENTATION_PATHS = (
    "tools/build_character_battle_graphics_pixel_ab.py",
    "tools/export_character_battle_graphics_pixel_ab_evidence.py",
    "tools/verify_character_battle_graphics_pixel_ab_evidence.py",
    "tools/inspect_mgba_savestate.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_single_input_replay.lua",
    "tests/test_build_character_battle_graphics_pixel_ab.py",
    "tests/test_character_battle_graphics_pixel_ab_evidence.py",
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


def _replace_state_u16(path: Path, state_offset: int, value: int) -> None:
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
            struct.pack_into("<H", state, state_offset, value)
            payload = zlib.compress(state)
        output.extend(struct.pack(">I", len(payload)))
        output.extend(tag)
        output.extend(payload)
        output.extend(struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))
    path.write_bytes(output)


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


class CharacterBattleGraphicsPixelAbEvidenceTests(unittest.TestCase):
    def test_exporter_rebuilds_a_verifiable_artifact(self):
        from tools.export_character_battle_graphics_pixel_ab_evidence import export
        from tools.verify_character_battle_graphics_pixel_ab_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            temporary = Path(temporary)
            run = temporary / "run"
            (run / "build").mkdir(parents=True)
            shutil.copy2(
                ARTIFACT / "build-manifest.json",
                run / "build/build-manifest.json",
            )
            base = (ROOT / "rom/base.gba").read_bytes()
            for variant in ("baseline", "candidate"):
                runtime = run / "runtime" / variant
                runtime.mkdir(parents=True)
                for name in (
                    "frame80.ss9",
                    "frame80.png",
                    "audit.json",
                    "sentinel.json",
                    "guard.json",
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
                "character-battle-graphics-pixel-ab-v1",
                manifest["artifact_schema"],
            )
            report = verify(ROOT, output)
            self.assertTrue(report["verified"], report["errors"])

    def test_independent_verifier_accepts_production_artifact(self):
        from tools.verify_character_battle_graphics_pixel_ab_evidence import verify

        source = (
            ROOT / "tools/verify_character_battle_graphics_pixel_ab_evidence.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "from tools.build_character_battle_graphics_pixel_ab", source
        )
        self.assertNotIn(
            "from tools.export_character_battle_graphics_pixel_ab_evidence", source
        )
        self.assertNotIn("from tools.import_character_battle_bundles", source)

        report = verify(ROOT, ARTIFACT)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual({"VRAM": [0x10126]}, report["memory_differences"])
        self.assertEqual(
            [[117, 25, [33, 33, 33], [255, 0, 0]]],
            report["pixel_changes"],
        )
        self.assertEqual(0, report["resource_id"])
        self.assertEqual(3, report["frame_id"])

    def test_rejects_resigned_bundle_byte_tamper(self):
        from tools.verify_character_battle_graphics_pixel_ab_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            path = artifact / "candidate/bundle.bin"
            payload = bytearray(path.read_bytes())
            payload[0xD46] ^= 1
            path.write_bytes(payload)
            _resign(artifact, "candidate/bundle.bin")

            report = verify(ROOT, artifact)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("candidate bundle" in error for error in report["errors"]),
                report["errors"],
            )

    def test_rejects_resigned_pixel_contract_tamper(self):
        from tools.verify_character_battle_graphics_pixel_ab_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            path = artifact / "runtime-evidence.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["runtime"]["pixel_changes"][0][0] = 118
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _resign(artifact, "runtime-evidence.json")

            report = verify(ROOT, artifact)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("pixel" in error for error in report["errors"]),
                report["errors"],
            )

    def test_rejects_resigned_run_provenance_tamper(self):
        from tools.verify_character_battle_graphics_pixel_ab_evidence import verify

        for kind in ("audit", "guard"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                artifact = Path(temporary) / "artifact"
                shutil.copytree(ARTIFACT, artifact)
                if kind == "audit":
                    for name in ("audit.json", "sentinel.json"):
                        path = artifact / "baseline" / name
                        payload = json.loads(path.read_text(encoding="utf-8"))
                        payload["success"] = False
                        payload["status"] = "failed"
                        payload["capture_frame"] = 999
                        path.write_text(
                            json.dumps(payload, separators=(",", ":")),
                            encoding="utf-8",
                        )
                        _resign(artifact, f"baseline/{name}")
                else:
                    path = artifact / "candidate/guard.json"
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    payload["child_pid"] = 1
                    payload["command"] = ["/bin/true"]
                    path.write_text(
                        json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    _resign(artifact, "candidate/guard.json")

                report = verify(ROOT, artifact)
                self.assertFalse(report["verified"])
                self.assertTrue(
                    any("provenance" in error for error in report["errors"]),
                    report["errors"],
                )

    def test_rejects_resigned_display_state_tamper(self):
        from tools.verify_character_battle_graphics_pixel_ab_evidence import verify

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            for variant in ("baseline", "candidate"):
                path = artifact / variant / "frame80.ss9"
                _replace_state_u16(path, 0x400, 0x1900)
                _resign(artifact, f"{variant}/frame80.ss9")

            report = verify(ROOT, artifact)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any(
                    "IO state identity" in error or "display/OBJ" in error
                    for error in report["errors"]
                ),
                report["errors"],
            )

    def test_rejects_missing_or_tampered_parent_checkpoint(self):
        from tools.verify_character_battle_graphics_pixel_ab_evidence import verify

        for kind in ("missing", "tampered"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "root"
                _copy_minimal_root(root)
                if kind == "tampered":
                    checkpoint = (
                        root
                        / "artifacts/runtime-checkpoints/scenario-41-start-row.ss9"
                    )
                    checkpoint.parent.mkdir(parents=True)
                    checkpoint.write_bytes(b"tampered checkpoint")

                report = verify(root, ARTIFACT)
                self.assertFalse(report["verified"])
                self.assertIn("input checkpoint identity mismatch", report["errors"])

    def test_rejects_resigned_build_and_scope_tamper(self):
        from tools.verify_character_battle_graphics_pixel_ab_evidence import verify

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
                elif kind == "scope":
                    path = artifact / "manifest.json"
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    payload["scope"]["all_250_resources_runtime_verified"] = True
                    path.write_text(
                        json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                else:
                    path = artifact / "manifest.json"
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    payload["verifier"]["command"] = ["false"]
                    payload["verifier"]["result"] = {"verified": False}
                    path.write_text(
                        json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )

                report = verify(ROOT, artifact)
                self.assertFalse(report["verified"])
                expected = "build manifest" if kind == "build" else "promotion manifest"
                self.assertTrue(
                    any(expected in error for error in report["errors"]),
                    report["errors"],
                )


if __name__ == "__main__":
    unittest.main()
