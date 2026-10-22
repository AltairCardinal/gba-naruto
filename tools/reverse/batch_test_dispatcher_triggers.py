#!/usr/bin/env python3
"""Batch-test which tracked .ss9 checkpoint triggers the inner-layer dispatcher.

For each .ss9 in artifacts/runtime-checkpoints/, run a short mGBA + dispatcher
tracer lua script. Save results in build/experiments/active/<task>/<run>/.

This is a debug-only static-by-runtime analyzer; it does not modify manifests.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoints-dir", type=Path, default=REPO_ROOT / "artifacts" / "runtime-checkpoints")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "build" / "experiments" / "active" / "dispatcher-batch")
    parser.add_argument("--mgba", type=Path, default=Path("/tmp/mgba-build/build/qt/mGBA.app/Contents/MacOS/mGBA"))
    parser.add_argument("--rom", type=Path, default=REPO_ROOT / "rom" / "base.gba")
    parser.add_argument("--max-checkpoints", type=int, default=200)
    parser.add_argument("--timeout-s", type=int, default=12)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    checkpoints = sorted(args.checkpoints_dir.glob("*.ss9"))[:args.max_checkpoints]
    results = []

    for ckpt in checkpoints:
        out = args.output_dir / ckpt.stem
        out.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update({
            "QT_QPA_PLATFORM": "offscreen",
            "TRACER_OUTPUT_AUDIT": str(out / "audit.json"),
            "TRACER_OUTPUT_DONE": str(out / "done.json"),
            "TRACER_OUTPUT_PNG": str(out / "trace.png"),
            "TRACER_HIT_LIMIT": "1",
            "TRACER_SHA": ckpt.stem,
        })
        try:
            proc = subprocess.run([
                str(args.mgba),
                "-t", str(ckpt),
                "--script", str(REPO_ROOT / "tools" / "mgba_battle_effect_dispatcher_tracer.lua"),
                str(args.rom),
            ], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=args.timeout_s)
        except subprocess.TimeoutExpired:
            proc = subprocess.CompletedProcess(args=[], returncode=-1, stdout=b"", stderr=b"")
        except Exception as exc:
            results.append({"checkpoint": ckpt.name, "error": str(exc)})
            continue

        audit_path = out / "audit.json"
        if audit_path.exists():
            try:
                audit = json.loads(audit_path.read_text())
                results.append({
                    "checkpoint": ckpt.name,
                    "sha256": _sha256(ckpt),
                    "hit_count": audit.get("hit_count", 0),
                    "first_hit": audit["hits"][0] if audit.get("hits") else None,
                })
            except Exception as exc:
                results.append({"checkpoint": ckpt.name, "error": f"audit parse: {exc}"})
        else:
            results.append({"checkpoint": ckpt.name, "hit_count": 0, "no_audit": True})

    output = args.output_dir / "batch-results.json"
    output.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    triggered = [r for r in results if r.get("hit_count", 0) > 0]
    print(f"tested {len(results)} checkpoints, {len(triggered)} triggered dispatcher")
    for r in triggered:
        print(f"  {r['checkpoint']}: hit_count={r['hit_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())