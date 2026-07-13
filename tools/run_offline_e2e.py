#!/usr/bin/env python3
"""Run a persistent build-to-native-mGBA smoke test without network or OCR."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "artifacts/e2e/offline-smoke-20260713"
DEFAULT_CHECKPOINT = ROOT / "artifacts/runtime-checkpoints/actionable-move-grid.ss9"


def _sha(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_build_identity(
    report: dict, *, actual_sha1: str, actual_size: int
) -> dict[str, bool]:
    expected = report["output_rom"]
    sha_matches = expected["sha1"] == actual_sha1
    size_matches = expected["size"] == actual_size
    if not sha_matches:
        raise ValueError(
            f"output ROM SHA-1 mismatch: report={expected['sha1']} actual={actual_sha1}"
        )
    if not size_matches:
        raise ValueError(
            f"output ROM size mismatch: report={expected['size']} actual={actual_size}"
        )
    return {"sha1_matches": sha_matches, "size_matches": size_matches}


def _first_word(snapshot: dict, address: str) -> int:
    for dump in snapshot.get("memory_dumps", []):
        if dump.get("address", "").lower() == address.lower() and dump.get("words"):
            return int(dump["words"][0], 16)
    raise ValueError(f"runtime snapshot missing {address}")


def validate_runtime_snapshot(snapshot: dict) -> dict:
    battle_bytes = _first_word(snapshot, "0x02026804").to_bytes(4, "little")
    map_bytes = _first_word(snapshot, "0x0201BE28").to_bytes(4, "little")
    naruto_bytes = _first_word(snapshot, "0x02024358").to_bytes(4, "little")
    iruka_bytes = _first_word(snapshot, "0x0202452C").to_bytes(4, "little")
    result = {
        "battle_id": battle_bytes[1],
        "map": {
            "width": map_bytes[0],
            "height": map_bytes[1],
            "grid_width": map_bytes[2],
            "grid_height": map_bytes[3],
        },
        "naruto": {"x": naruto_bytes[0], "y": naruto_bytes[1]},
        "iruka": {"x": iruka_bytes[0], "y": iruka_bytes[1]},
    }
    expected = {
        "battle_id": 41,
        "map": {"width": 36, "height": 44, "grid_width": 9, "grid_height": 22},
        "naruto": {"x": 4, "y": 10},
        "iruka": {"x": 4, "y": 4},
    }
    if result["battle_id"] != expected["battle_id"]:
        raise ValueError(
            f"runtime battle ID mismatch: expected 41 got {result['battle_id']}"
        )
    for key in ("map", "naruto", "iruka"):
        if result[key] != expected[key]:
            raise ValueError(
                f"runtime {key} mismatch: expected {expected[key]} got {result[key]}"
            )
    return result


def _run(command: list[str], *, timeout: int) -> dict:
    completed = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, timeout=timeout
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def run(output_dir: Path, checkpoint: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    build_tests_path = output_dir / "build-tests.json"
    runtime_path = output_dir / "runtime.json"
    summary_path = output_dir / "summary.json"
    summary: dict = {
        "format": "offline build-to-native-mGBA E2E smoke",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "failed",
        "stages": {},
    }
    try:
        build_stage = _run(
            [sys.executable, "tools/automated_test.py", "--json-output", str(build_tests_path)],
            timeout=240,
        )
        summary["stages"]["build_tests"] = build_stage
        if build_stage["returncode"] != 0:
            raise ValueError("automated build verification failed")

        project = json.loads((ROOT / "sequel/project.json").read_text(encoding="utf-8"))
        report_path = ROOT / project["build"]["report"]
        report = json.loads(report_path.read_text(encoding="utf-8"))
        rom_path = ROOT / project["build"]["output_rom"]
        actual_sha1 = _sha(rom_path, "sha1")
        identity = validate_build_identity(
            report, actual_sha1=actual_sha1, actual_size=rom_path.stat().st_size
        )
        summary["stages"]["build_identity"] = {
            **identity,
            "rom": str(rom_path.relative_to(ROOT)),
            "sha1": actual_sha1,
            "size": rom_path.stat().st_size,
            "build_report": str(report_path.relative_to(ROOT)),
        }

        runtime_stage = _run(
            [
                sys.executable,
                "tools/mgba-headless-snapshot.py",
                "--rom", str(rom_path),
                "--mode", "snapshot",
                "--savestate", str(checkpoint),
                "--frames", "1",
                "--timeout", "15",
                "--dump", "0x02026804:16",
                "--dump", "0x0201BE28:16",
                "--dump", "0x02024358:16",
                "--dump", "0x0202452C:16",
                "--output", str(runtime_path),
            ],
            timeout=120,
        )
        summary["stages"]["native_mgba"] = runtime_stage
        if runtime_stage["returncode"] != 0:
            raise ValueError("native mGBA snapshot command failed")
        snapshot = json.loads(runtime_path.read_text(encoding="utf-8"))
        runtime_assertions = validate_runtime_snapshot(snapshot)
        summary["stages"]["runtime_assertions"] = runtime_assertions
        summary["checkpoint"] = {
            "path": str(checkpoint.relative_to(ROOT)),
            "sha256": _sha(checkpoint, "sha256"),
        }
        summary["status"] = "passed"
    except Exception as exc:
        summary["error"] = f"{type(exc).__name__}: {exc}"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    args = parser.parse_args()
    summary = run(args.output_dir.resolve(), args.checkpoint.resolve())
    print(json.dumps({"status": summary["status"], "output_dir": str(args.output_dir)}, indent=2))
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
