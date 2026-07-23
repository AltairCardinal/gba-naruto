import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import accept_prebattle_candidate as acceptance


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


ROOT = Path(__file__).resolve().parents[1]
ACTUAL_STEP2_PATHS = acceptance.step2_paths(ROOT)
ACTUAL_STEP2_AVAILABLE = all(
    path.is_file()
    and acceptance.sha256_file(path)
    == acceptance.STEP2_SHA256[key]
    for key, path in ACTUAL_STEP2_PATHS.items()
    if key != "tracked_patch"
)


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
        patch = (
            Path(__file__).resolve().parents[1]
            / "tools/patches/mgba-0.10.5-qt-script-cli.patch"
        ).read_bytes()
        (root / "tracked.patch").write_bytes(patch)
        manifest = {
            "label": "mGBA 0.10.5 + Qt script backport",
            "version": "0.10.5",
            "source_commit": "26b7884bc25a5933960f3cdcd98bac1ae14d42e2",
            "backport_commit": "7cacae126207de5499857439b9c7919bf8e882c2",
            "architecture": "x86_64",
            "patch_sha256": sha256(patch),
            "binary_sha256": sha256(files["mGBA"]),
            "guard": {
                "summaries": {
                    "prepare": {"command": ["prepare", base64.b64encode(patch).decode()]},
                    "sentinel": {
                        "command": [
                            "python",
                            "build_macos_mgba.py",
                            "_sentinel",
                            str(root / "mGBA"),
                        ]
                    },
                }
            },
        }
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        guard = {
            "reason": "completed",
            "exit_code": 0,
            "completion_trigger": "success-marker",
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
            "peak_tree_rss_mib": 51.0,
            "audit": str(root / "audit.json"),
            "sentinel": str(root / "sentinel.json"),
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
        (root / "sentinel.json").write_text(json.dumps(audit), encoding="utf-8")
        return audit_path, root / "base.gba"

    def strict_expectations(self, root: Path):
        paths = {
            "audit": root / "audit.json",
            "sentinel": root / "sentinel.json",
            "guard_summary": root / "guard.json",
            "base_rom": root / "base.gba",
            "input_state": root / "input.ss9",
            "output_state": root / "output.ss9",
            "output_png": root / "output.png",
            "staged_rom": root / "staged.gba",
            "replay_script": root / "replay.lua",
            "build_manifest": root / "manifest.json",
            "binary": root / "mGBA",
            "tracked_patch": root / "tracked.patch",
        }
        hashes = {
            name: acceptance.sha256_file(path)
            for name, path in paths.items()
            if name != "tracked_patch"
        }
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        hashes["patch"] = manifest["patch_sha256"]
        return paths, hashes

    def test_authenticates_every_strict_replay_dependency_from_real_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_path, rom_path = self.make_strict_replay(root)
            caller_paths, caller_hashes = self.strict_expectations(root)

            result = acceptance.validate_strict_replay(
                audit_path,
                rom_path,
                root / "guard.json",
                caller_paths=caller_paths,
                caller_hashes=caller_hashes,
                canonical_tracked_patch_path=root / "tracked.patch",
            )

        self.assertEqual(result["run_id"], "strict-run")
        self.assertEqual(result["emulator"]["version"], "0.10.5")
        self.assertEqual(result["emulator"]["architecture"], "x86_64")
        self.assertEqual(result["guard"]["reason"], "completed")
        self.assertTrue(result["zero_input_verified"])
        self.assertEqual(result["caller_known_sha256"], caller_hashes)

    def test_caller_known_pins_reject_a_fully_self_consistent_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_path, rom_path = self.make_strict_replay(root)
            caller_paths, caller_hashes = self.strict_expectations(root)
            for name, payload in {
                "base.gba": b"drifted-rom",
                "staged.gba": b"drifted-rom",
                "input.ss9": b"drifted-input",
                "output.ss9": b"drifted-output",
                "output.png": b"drifted-png",
                "replay.lua": b"drifted-script",
                "mGBA": b"drifted-binary",
            }.items():
                (root / name).write_bytes(payload)
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["binary_sha256"] = acceptance.sha256_file(root / "mGBA")
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
            )
            guard_path = root / "guard.json"
            guard = json.loads(guard_path.read_text(encoding="utf-8"))
            guard_path.write_text(
                json.dumps(guard, indent=2, sort_keys=True), encoding="utf-8"
            )
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            audit.update(
                {
                    "rom_sha256": acceptance.sha256_file(root / "base.gba"),
                    "staged_rom_sha256": acceptance.sha256_file(root / "staged.gba"),
                    "input_state_sha256": acceptance.sha256_file(root / "input.ss9"),
                    "output_state_sha256": acceptance.sha256_file(root / "output.ss9"),
                    "output_png_sha256": acceptance.sha256_file(root / "output.png"),
                    "replay_script_sha256": acceptance.sha256_file(root / "replay.lua"),
                    "binary_sha256": acceptance.sha256_file(root / "mGBA"),
                    "build_manifest_sha256": acceptance.sha256_file(manifest_path),
                    "guard_summary_sha256": acceptance.sha256_file(guard_path),
                }
            )
            encoded = json.dumps(audit)
            audit_path.write_text(encoded, encoding="utf-8")
            (root / "sentinel.json").write_text(encoded, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "caller-known"):
                acceptance.validate_strict_replay(
                    audit_path,
                    rom_path,
                    root / "guard.json",
                    caller_paths=caller_paths,
                    caller_hashes=caller_hashes,
                    canonical_tracked_patch_path=root / "tracked.patch",
                )

    def test_rejects_wrong_script_binary_patch_manifest_guard_and_staged_path(self):
        mutators = {
            "script": lambda root, audit, guard, manifest: (
                (root / "replay.lua").write_bytes(b"wrong-script")
            ),
            "binary": lambda root, audit, guard, manifest: (
                (root / "mGBA").write_bytes(b"wrong-binary")
            ),
            "manifest": lambda root, audit, guard, manifest: (
                (root / "manifest.json").write_text("{}", encoding="utf-8")
            ),
            "guard": lambda root, audit, guard, manifest: guard.update(
                {"protection_backend": "degraded-process-tree"}
            ),
            "command": lambda root, audit, guard, manifest: guard.update(
                {"command": [str(root / "mGBA"), str(root / "staged.gba")]}
            ),
            "staged_path": lambda root, audit, guard, manifest: guard["command"].__setitem__(
                -1, str(root / "input.ss9")
            ),
            "patch": lambda root, audit, guard, manifest: manifest.update(
                {"patch_sha256": "0" * 64}
            ),
        }
        for name, mutate in mutators.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                audit_path, rom_path = self.make_strict_replay(root)
                caller_paths, caller_hashes = self.strict_expectations(root)
                guard_path = root / "guard.json"
                manifest_path = root / "manifest.json"
                audit = json.loads(audit_path.read_text(encoding="utf-8"))
                guard = json.loads(guard_path.read_text(encoding="utf-8"))
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                mutate(root, audit, guard, manifest)
                guard_path.write_text(json.dumps(guard), encoding="utf-8")
                if name in ("patch",):
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                audit["guard_summary_sha256"] = acceptance.sha256_file(guard_path)
                audit["build_manifest_sha256"] = acceptance.sha256_file(manifest_path)
                encoded = json.dumps(audit)
                audit_path.write_text(encoded, encoding="utf-8")
                (root / "sentinel.json").write_text(encoded, encoding="utf-8")
                with self.assertRaises(ValueError):
                    acceptance.validate_strict_replay(
                        audit_path,
                        rom_path,
                        guard_path,
                        caller_paths=caller_paths,
                        caller_hashes=caller_hashes,
                        canonical_tracked_patch_path=root / "tracked.patch",
                    )

    def test_guard_requires_positive_pgid_backend_finite_rss_and_audit_match(self):
        mutations = {
            "pid": ("child_pid", 0),
            "backend": ("protection_backend", "degraded"),
            "zero_rss": ("peak_tree_rss_mib", 0),
            "nan_rss": ("peak_tree_rss_mib", float("nan")),
        }
        for name, (field, value) in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                audit_path, rom_path = self.make_strict_replay(root)
                guard_path = root / "guard.json"
                guard = json.loads(guard_path.read_text(encoding="utf-8"))
                guard[field] = value
                guard_path.write_text(json.dumps(guard), encoding="utf-8")
                audit = json.loads(audit_path.read_text(encoding="utf-8"))
                audit["guard_summary_sha256"] = acceptance.sha256_file(guard_path)
                if field == "child_pid":
                    audit["child_pgid"] = value
                encoded = json.dumps(audit)
                audit_path.write_text(encoded, encoding="utf-8")
                (root / "sentinel.json").write_text(encoded, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "guard|RSS|PGID"):
                    acceptance.validate_strict_replay(audit_path, rom_path, guard_path)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_path, rom_path = self.make_strict_replay(root)
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            audit["peak_tree_rss_mib"] = 52.0
            encoded = json.dumps(audit)
            audit_path.write_text(encoded, encoding="utf-8")
            (root / "sentinel.json").write_text(encoded, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "peak RSS"):
                acceptance.validate_strict_replay(
                    audit_path, rom_path, root / "guard.json"
                )

    def test_caller_known_replay_requires_the_fixed_sentinel_and_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_path, rom_path = self.make_strict_replay(root)
            caller_paths, caller_hashes = self.strict_expectations(root)
            (root / "sentinel.json").unlink()
            with self.assertRaisesRegex(ValueError, "sentinel"):
                acceptance.validate_strict_replay(
                    audit_path,
                    rom_path,
                    root / "guard.json",
                    caller_paths=caller_paths,
                    caller_hashes=caller_hashes,
                    canonical_tracked_patch_path=root / "tracked.patch",
                )

            self.make_strict_replay(root)
            caller_paths, caller_hashes = self.strict_expectations(root)
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            alternate_script = root / "alternate.lua"
            alternate_script.write_bytes((root / "replay.lua").read_bytes())
            audit["replay_script"] = str(alternate_script)
            encoded = json.dumps(audit)
            audit_path.write_text(encoded, encoding="utf-8")
            (root / "sentinel.json").write_text(encoded, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "path"):
                acceptance.validate_strict_replay(
                    audit_path,
                    rom_path,
                    root / "guard.json",
                    caller_paths=caller_paths,
                    caller_hashes=caller_hashes,
                    canonical_tracked_patch_path=root / "tracked.patch",
                )

    def test_step1_manifest_must_authenticate_the_fixed_binary_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_path, rom_path = self.make_strict_replay(root)
            alternate = root / "alternate-mGBA"
            alternate.write_bytes((root / "mGBA").read_bytes())
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["guard"]["summaries"]["sentinel"]["command"][3] = str(alternate)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            audit["build_manifest_sha256"] = acceptance.sha256_file(manifest_path)
            encoded = json.dumps(audit)
            audit_path.write_text(encoded, encoding="utf-8")
            (root / "sentinel.json").write_text(encoded, encoding="utf-8")
            caller_paths, caller_hashes = self.strict_expectations(root)

            with self.assertRaisesRegex(ValueError, "manifest.*binary path"):
                acceptance.validate_strict_replay(
                    audit_path,
                    rom_path,
                    root / "guard.json",
                    caller_paths=caller_paths,
                    caller_hashes=caller_hashes,
                    canonical_tracked_patch_path=root / "tracked.patch",
                )

    def test_caller_mode_rejects_tracked_patch_bytes_that_differ_from_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_path, rom_path = self.make_strict_replay(root)
            caller_paths, caller_hashes = self.strict_expectations(root)
            (root / "tracked.patch").write_bytes(b"self-consistent-looking replacement")

            with self.assertRaisesRegex(ValueError, "tracked patch"):
                acceptance.validate_strict_replay(
                    audit_path,
                    rom_path,
                    root / "guard.json",
                    caller_paths=caller_paths,
                    caller_hashes=caller_hashes,
                    canonical_tracked_patch_path=root / "tracked.patch",
                )

    def test_caller_mode_rejects_tracked_patch_at_wrong_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_path, rom_path = self.make_strict_replay(root)
            caller_paths, caller_hashes = self.strict_expectations(root)
            wrong_location = root / "copied-tracked.patch"
            wrong_location.write_bytes((root / "tracked.patch").read_bytes())
            caller_paths["tracked_patch"] = wrong_location

            with self.assertRaisesRegex(ValueError, "tracked patch path mismatch"):
                acceptance.validate_strict_replay(
                    audit_path,
                    rom_path,
                    root / "guard.json",
                    caller_paths=caller_paths,
                    caller_hashes=caller_hashes,
                )

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

    def test_rejects_each_zero_input_field_and_guard_failure_independently(self):
        mutations = {
            "zero_input_verified": ("zero_input_verified", False, "zero-input"),
            "evidence_mode": ("evidence_mode", "script-order-diagnostic", "zero-input"),
            "pre_scripts": ("pre_scripts", [{"path": "pre.lua"}], "pre-scripts"),
            "inputs": ("inputs", ["A"], "zero-input"),
        }
        for name, (field, value, message) in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                audit_path, rom_path = self.make_strict_replay(root)
                audit = json.loads(audit_path.read_text(encoding="utf-8"))
                audit[field] = value
                encoded = json.dumps(audit)
                audit_path.write_text(encoded, encoding="utf-8")
                (root / "sentinel.json").write_text(encoded, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    acceptance.validate_strict_replay(
                        audit_path, rom_path, root / "guard.json"
                    )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_path, rom_path = self.make_strict_replay(root)
            guard_path = root / "guard.json"
            guard = json.loads(guard_path.read_text(encoding="utf-8"))
            guard["reason"] = "memory-limit"
            guard["exit_code"] = 125
            guard_path.write_text(json.dumps(guard), encoding="utf-8")
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            audit["guard_summary_sha256"] = acceptance.sha256_file(guard_path)
            encoded = json.dumps(audit)
            audit_path.write_text(encoded, encoding="utf-8")
            (root / "sentinel.json").write_text(encoded, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "guard"):
                acceptance.validate_strict_replay(audit_path, rom_path, guard_path)

    def test_prebattle_state_boundary_rejects_wrong_chain_and_wram_flag(self):
        self.assertTrue(
            hasattr(acceptance, "validate_prebattle_state"),
            "validate_prebattle_state is not implemented",
        )
        report = {
            "tasks": [
                {},
                {"sp": "0x030011D8", "resume_pc": "0x08067D02"},
            ],
            "active_unwind": {
                "raw_return_words": [
                    "0x080885C1",
                    "0x08088F9F",
                    "0x0808F92D",
                ]
            },
            "memory_bytes": {"0x0202680C": 0},
        }
        acceptance.validate_prebattle_state(report)

        wrong_chain = json.loads(json.dumps(report))
        wrong_chain["active_unwind"]["raw_return_words"][-1] = "0x0808F957"
        with self.assertRaisesRegex(ValueError, "unwind|controller"):
            acceptance.validate_prebattle_state(wrong_chain)
        wrong_wram = json.loads(json.dumps(report))
        wrong_wram["memory_bytes"]["0x0202680C"] = 1
        with self.assertRaisesRegex(ValueError, "battle-control"):
            acceptance.validate_prebattle_state(wrong_wram)

    @unittest.skipUnless(ACTUAL_STEP2_AVAILABLE, "local Step2 raw replay is unavailable")
    def test_actual_builder_uses_caller_pins_and_rejects_residue(self):
        clean_residue = {
            "checked_pgid": 20050,
            "pgid_clean": True,
            "mgba_listener_clean": True,
        }
        with mock.patch.object(
            acceptance, "probe_runtime_residue", return_value=clean_residue
        ):
            evidence = acceptance.build_prebattle_evidence(ROOT)
        self.assertEqual(
            evidence["strict_replay"]["caller_known_sha256"],
            acceptance.STEP2_SHA256,
        )
        self.assertEqual(
            evidence["screen_identity"]["method"],
            "strict PNG decode to normalized RGB8 pixel SHA-256",
        )
        self.assertIn("tracked_patch", evidence["strict_replay"]["files"])
        self.assertEqual(
            evidence["strict_replay"]["files"]["tracked_patch"],
            {
                "path": str(
                    ROOT / "tools/patches/mgba-0.10.5-qt-script-cli.patch"
                ),
                "repo_relative_path": "tools/patches/mgba-0.10.5-qt-script-cli.patch",
                "sha256": acceptance.STEP2_SHA256["patch"],
            },
        )

        with mock.patch.object(
            acceptance, "probe_runtime_residue", return_value=clean_residue
        ), mock.patch.dict(
            acceptance.STEP2_SHA256, {"output_state": "0" * 64}
        ):
            with self.assertRaisesRegex(ValueError, "caller-known"):
                acceptance.build_prebattle_evidence(ROOT)
        with mock.patch.object(
            acceptance,
            "probe_runtime_residue",
            side_effect=ValueError("listener residue detected"),
        ):
            with self.assertRaisesRegex(ValueError, "residue"):
                acceptance.build_prebattle_evidence(ROOT)
        with mock.patch.object(
            acceptance, "probe_runtime_residue", return_value=clean_residue
        ), mock.patch.dict(
            acceptance.STEP2_SHA256, {"guard_summary": "0" * 64}
        ):
            with self.assertRaisesRegex(ValueError, "caller-known"):
                acceptance.build_prebattle_evidence(ROOT)

        paths = acceptance.step2_paths(ROOT)
        actual_report = acceptance.inspect_savestate(
            paths["output_state"],
            rom_path=paths["base_rom"],
            task_slot=2,
            unwind_frames=[
                (address, target)
                for address, _, target in acceptance.EXPECTED_UNWIND
            ],
            memory_bytes=[0x0202680C],
        )
        wrong_chain = json.loads(json.dumps(actual_report))
        wrong_chain["active_unwind"]["raw_return_words"][-1] = "0x0808F957"
        wrong_wram = json.loads(json.dumps(actual_report))
        wrong_wram["memory_bytes"]["0x0202680C"] = 1
        for name, report, message in (
            ("controller", wrong_chain, "unwind|controller"),
            ("wram", wrong_wram, "battle-control"),
        ):
            with self.subTest(name=name), mock.patch.object(
                acceptance, "inspect_savestate", return_value=report
            ), mock.patch.object(
                acceptance, "probe_runtime_residue", return_value=clean_residue
            ):
                with self.assertRaisesRegex(ValueError, message):
                    acceptance.build_prebattle_evidence(ROOT)

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
        self.assertEqual(record["rom_sha256"], acceptance.STEP2_SHA256["base_rom"])
        self.assertEqual(record["parent"], "scenario-41-pre-controller-lineup")
        self.assertEqual(record["inputs"], ["B"])
        self.assertEqual(record["screen"], "scenario-41-prebattle-menu")
        self.assertTrue(record["stable_zero_input"])
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
        self.assertEqual(
            evidence["scope"]["proves"],
            ["stable zero-input scenario 41 prebattle menu"],
        )
        self.assertIn("battle controller entry", evidence["scope"]["does_not_prove"])
        self.assertIn("player control", evidence["scope"]["does_not_prove"])


if __name__ == "__main__":
    unittest.main()
