import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools import accept_prebattle_candidate as acceptance


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class AcceptPrebattleCandidateTests(unittest.TestCase):
    def make_strict_replay(self, root: Path) -> tuple[Path, Path]:
        files = {
            "base.gba": b"rom",
            "input.ss9": b"input-state",
            "output.ss9": b"output-state",
            "output.png": b"output-png",
            "staged.gba": b"rom",
            "replay.lua": b"script",
            "mGBA": b"binary",
        }
        for name, data in files.items():
            (root / name).write_bytes(data)
        patch = b"qt-script-backport"
        manifest = {
            "version": "0.10.5",
            "source_commit": "26b7884bc25a5933960f3cdcd98bac1ae14d42e2",
            "backport_commit": "7cacae126207de5499857439b9c7919bf8e882c2",
            "architecture": "x86_64",
            "patch_sha256": sha256(patch),
            "binary_sha256": sha256(files["mGBA"]),
            "guard": {
                "summaries": {
                    "prepare": {"command": ["prepare", base64.b64encode(patch).decode()]}
                }
            },
        }
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        guard = {
            "reason": "completed",
            "exit_code": 0,
            "child_pid": 20050,
            "peak_tree_rss_mib": 51.0,
            "protection_backend": "posix-process-group",
            "degraded": False,
            "command": [
                str(root / "mGBA"),
                "--script",
                str(root / "replay.lua"),
                str(root / "staged.gba"),
            ],
        }
        guard_path = root / "guard.json"
        guard_path.write_text(json.dumps(guard), encoding="utf-8")
        audit = {
            "run_id": "strict-run",
            "success": True,
            "status": "capture-complete",
            "evidence_mode": "zero-input",
            "zero_input_verified": True,
            "inputs": [],
            "pre_scripts": [],
            "capture_frame": 80,
            "frame": 80,
            "child_pgid": 20050,
            "pgid_clean": True,
            "input_state": str(root / "input.ss9"),
            "input_state_sha256": sha256(files["input.ss9"]),
            "output_state": str(root / "output.ss9"),
            "output_state_sha256": sha256(files["output.ss9"]),
            "output_png": str(root / "output.png"),
            "output_png_sha256": sha256(files["output.png"]),
            "staged_rom": str(root / "staged.gba"),
            "staged_rom_sha256": sha256(files["staged.gba"]),
            "rom_sha256": sha256(files["base.gba"]),
            "replay_script": str(root / "replay.lua"),
            "replay_script_sha256": sha256(files["replay.lua"]),
            "build_manifest": str(manifest_path),
            "build_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "binary_sha256": sha256(files["mGBA"]),
            "patch_sha256": sha256(patch),
            "guard_summary_sha256": hashlib.sha256(guard_path.read_bytes()).hexdigest(),
        }
        audit_path = root / "audit.json"
        audit_path.write_text(json.dumps(audit), encoding="utf-8")
        return audit_path, root / "base.gba"

    def test_authenticates_every_strict_replay_dependency_from_real_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_path, rom_path = self.make_strict_replay(root)

            result = acceptance.validate_strict_replay(
                audit_path, rom_path, root / "guard.json"
            )

        self.assertEqual(result["run_id"], "strict-run")
        self.assertEqual(result["emulator"]["version"], "0.10.5")
        self.assertEqual(result["emulator"]["architecture"], "x86_64")
        self.assertEqual(result["guard"]["reason"], "completed")
        self.assertTrue(result["zero_input_verified"])

    def test_rejects_drifted_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_path, rom_path = self.make_strict_replay(root)
            (root / "output.ss9").write_bytes(b"drifted")

            with self.assertRaisesRegex(ValueError, "hash"):
                acceptance.validate_strict_replay(
                    audit_path, rom_path, root / "guard.json"
                )

    def test_rejects_wrong_capture_frame_and_guard_rom_wiring(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_path, rom_path = self.make_strict_replay(root)
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            audit["capture_frame"] = 79
            audit_path.write_text(json.dumps(audit), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "frame-80"):
                acceptance.validate_strict_replay(
                    audit_path, rom_path, root / "guard.json"
                )

            audit_path, rom_path = self.make_strict_replay(root)
            guard_path = root / "guard.json"
            guard = json.loads(guard_path.read_text(encoding="utf-8"))
            guard["command"][-1] = str(root / "input.ss9")
            guard_path.write_text(json.dumps(guard), encoding="utf-8")
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            audit["guard_summary_sha256"] = hashlib.sha256(
                guard_path.read_bytes()
            ).hexdigest()
            audit_path.write_text(json.dumps(audit), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "staged ROM"):
                acceptance.validate_strict_replay(audit_path, rom_path, guard_path)

            audit_path, rom_path = self.make_strict_replay(root)
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            audit["inputs"] = ["A"]
            audit_path.write_text(json.dumps(audit), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "zero-input"):
                acceptance.validate_strict_replay(
                    audit_path, rom_path, root / "guard.json"
                )

    def test_runtime_residue_requires_exact_pgid_and_no_mgba_listener(self):
        clean = acceptance.validate_runtime_residue(
            20050,
            "  10   999 Python\n",
            "",
            lsof_exit_code=1,
        )
        self.assertTrue(clean["pgid_clean"])
        self.assertTrue(clean["mgba_listener_clean"])

        with self.assertRaisesRegex(ValueError, "PGID"):
            acceptance.validate_runtime_residue(
                20050,
                "  22 20050 mGBA\n",
                "",
                lsof_exit_code=1,
            )
        with self.assertRaisesRegex(ValueError, "listener"):
            acceptance.validate_runtime_residue(
                20050,
                "",
                "p22\ncmGBA\nn*:1234\n",
                lsof_exit_code=0,
            )
        with self.assertRaisesRegex(ValueError, "lsof"):
            acceptance.validate_runtime_residue(
                20050,
                "",
                "permission denied",
                lsof_exit_code=2,
            )

    def test_persisted_acceptance_evidence_and_ledger_share_the_strict_boundary(self):
        root = Path(__file__).resolve().parents[1]
        evidence = json.loads(
            (
                root
                / "artifacts/runtime-checkpoints/scenario-41-prebattle-menu-evidence.json"
            ).read_text(encoding="utf-8")
        )
        ledger = json.loads(
            (root / "artifacts/runtime-checkpoints/scenario-41-checkpoints.json").read_text(
                encoding="utf-8"
            )
        )
        records = [
            checkpoint
            for checkpoint in ledger["checkpoints"]
            if checkpoint["name"] == "scenario-41-prebattle-menu"
        ]
        self.assertEqual(len(records), 1)
        record = records[0]

        self.assertEqual(evidence["verdict"], "accepted")
        self.assertEqual(record["status"], "accepted")
        self.assertEqual(record["sha256"], evidence["checkpoint"]["sha256"])
        self.assertEqual(
            record["zero_input_evidence"],
            ["artifacts/runtime-checkpoints/scenario-41-prebattle-menu-evidence.json"],
        )
        self.assertTrue(evidence["screen_identity"]["identical"])
        self.assertEqual(
            evidence["savestate"]["active_unwind"]["raw_return_words"],
            ["0x080885C1", "0x08088F9F", "0x0808F92D"],
        )
        self.assertTrue(evidence["savestate"]["controller_return_absent"])
        self.assertEqual(evidence["savestate"]["memory_bytes"]["0x0202680C"], 0)
        self.assertTrue(evidence["strict_replay"]["zero_input_verified"])
        self.assertEqual(evidence["strict_replay"]["inputs"], [])
        self.assertEqual(evidence["strict_replay"]["guard"]["reason"], "completed")
        self.assertEqual(evidence["strict_replay"]["guard"]["exit_code"], 0)
        self.assertFalse(evidence["strict_replay"]["guard"]["degraded"])
        self.assertTrue(evidence["runtime_residue"]["pgid_clean"])
        self.assertTrue(evidence["runtime_residue"]["mgba_listener_clean"])


if __name__ == "__main__":
    unittest.main()
