#!/usr/bin/env python3
"""Walk one GBA side forward through an explicit key sequence, one step per key.

Earlier S49 pairing attempts failed because the "step N equals picture N"
assumption was inferred from a contact sheet instead of from the capture
contract.  This driver removes that ambiguity:

* the key sequence, frame budgets and every input hash are written to
  ``inputs.json`` before the run, so a step number always resolves to an
  explicit input contract rather than to a position on a grid;
* every step saves its own savestate, so any branch can be resumed from a
  known point without replaying everything before it;
* the run fails closed when the emulator stops early or when a step image is
  missing, so a truncated walk can never masquerade as a complete one.

The original side resumes from a savestate; the remake side boots from
power-on because a remake savestate is not loadable by the original ROM.
Both variants drive the same key/step state machine, so the resulting step
indices mean the same thing on each side.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MGBA = ROOT / "build/macos-mgba/build/qt/mGBA.app/Contents/MacOS/mGBA"
GUARD = ROOT / "tools/run_guarded.py"
STATEFUL_SCRIPT = ROOT / "tools/butano/mgba_original_s49_ui_boundaries.lua"
BOOT_SCRIPT = ROOT / "tools/butano/mgba_boot_input_sequence.lua"

STATEFUL_PREFIX = "MGBA_ORIGINAL_S49_"
BOOT_PREFIX = "MGBA_BOOT_SEQUENCE_"

SUPPORTED_KEYS = (
    "A", "B", "Up", "Down", "Left", "Right", "L", "R", "Start", "Select",
)


class AdvanceError(RuntimeError):
    """The walk did not happen exactly as the contract demanded."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_keys(spec: str) -> list[str]:
    """Expand ``A``/``A,B``/``A*20`` into an explicit ordered key list."""
    keys: list[str] = []
    for token in str(spec).split(","):
        normalized = token.strip()
        if not normalized:
            raise AdvanceError(f"empty key token in sequence: {spec!r}")
        if "*" in normalized:
            name, _, repeats = normalized.partition("*")
            name = name.strip()
            if not repeats.isdigit() or int(repeats) < 1:
                raise AdvanceError(f"invalid repeat count: {normalized!r}")
            keys.extend([name] * int(repeats))
        else:
            keys.append(normalized)
    if not keys:
        raise AdvanceError("empty key sequence")
    for key in keys:
        if key not in SUPPORTED_KEYS:
            raise AdvanceError(f"unsupported key {key!r}; expected one of {SUPPORTED_KEYS}")
    return keys


def build_environment(
    prefix: str,
    out_dir: Path,
    done_marker: Path,
    keys: Sequence[str],
    zero_input_frames: int,
    settle_frames: int,
    hold_frames: int,
    state: Path | None = None,
    state_sha256: str | None = None,
    rom_sha256: str | None = None,
) -> dict[str, str]:
    environment = {
        f"{prefix}OUTPUT_DIR": str(out_dir),
        f"{prefix}DONE_MARKER": str(done_marker),
        f"{prefix}KEY_SEQUENCE": ",".join(keys),
        f"{prefix}ZERO_INPUT_FRAMES": str(zero_input_frames),
        f"{prefix}SETTLE_FRAMES": str(settle_frames),
        f"{prefix}HOLD_FRAMES": str(hold_frames),
    }
    if prefix == STATEFUL_PREFIX:
        if state is None or state_sha256 is None:
            raise AdvanceError("stateful walk requires --state")
        environment[f"{prefix}INPUT_STATE"] = str(state)
        environment[f"{prefix}INPUT_STATE_SHA256"] = state_sha256
    else:
        if rom_sha256 is None:
            raise AdvanceError("power-on walk requires a ROM hash")
        environment[f"{prefix}ROM_SHA256"] = rom_sha256
    return environment


def guard_command(
    summary: Path,
    success_marker: Path,
    child: Sequence[str],
    wall_timeout_s: int = 900,
) -> list[str]:
    return [
        sys.executable, str(GUARD),
        "--summary", str(summary),
        "--success-marker", str(success_marker),
        "--wall-timeout-s", str(wall_timeout_s),
        "--idle-timeout-s", "120",
        "--min-available-mib", "1024",
        "--", *child,
    ]


def verify_walk(out_dir: Path, keys: Sequence[str]) -> dict[str, object]:
    """Fail closed unless the emulator produced the whole declared walk."""
    audit_path = out_dir / "audit.json"
    if not audit_path.is_file():
        raise AdvanceError(f"walk produced no audit: {audit_path}")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("status") != "capture-complete":
        raise AdvanceError(f"walk did not report capture-complete: {audit}")
    if audit.get("captured_steps") != len(keys):
        raise AdvanceError(
            f"walk captured {audit.get('captured_steps')} steps, contract demanded {len(keys)}")

    steps = []
    for index in range(len(keys) + 1):
        # The Lua state machine labels a step with the key that produced it,
        # and step 0 is the untouched start, so the walk yields N+1 images.
        name = ("step-00-base.png" if index == 0
                else f"step-{index:02d}-{keys[index - 1]}.png")
        image = out_dir / name
        state = out_dir / (name[: -len(".png")] + ".ss9")
        if not image.is_file():
            raise AdvanceError(f"missing step image: {image}")
        if not state.is_file():
            raise AdvanceError(f"missing step savestate: {state}")
        steps.append({
            "step": index,
            "key": "none" if index == 0 else keys[index - 1],
            "image": name,
            "image_sha256": sha256_file(image),
            "state": state.name,
            "state_sha256": sha256_file(state),
        })
    return {"audit": audit, "audit_sha256": sha256_file(audit_path), "steps": steps}


def advance(
    out_dir: Path,
    rom: Path,
    state: Path | None,
    keys: Sequence[str],
    zero_input_frames: int,
    settle_frames: int,
    hold_frames: int,
    mgba: Path = DEFAULT_MGBA,
    label: str = "walk",
    run: bool = True,
) -> dict[str, object]:
    out_dir = Path(out_dir)
    rom = Path(rom)
    state = Path(state) if state else None
    mgba = Path(mgba)
    if out_dir.exists():
        raise AdvanceError(f"walk directory already exists: {out_dir}")
    if not rom.is_file():
        raise AdvanceError(f"missing ROM: {rom}")
    if not mgba.is_file():
        raise AdvanceError(f"missing mGBA: {mgba}")
    script = STATEFUL_SCRIPT if state else BOOT_SCRIPT
    if not script.is_file():
        raise AdvanceError(f"missing capture script: {script}")
    if state and not state.is_file():
        raise AdvanceError(f"missing savestate: {state}")
    if zero_input_frames < 0 or settle_frames < 1 or hold_frames < 1:
        raise AdvanceError("frame budgets must be positive (zero_input_frames may be 0)")

    rom_sha256 = sha256_file(rom)
    sidecar = rom.with_suffix(".sav")
    prefix = STATEFUL_PREFIX if state else BOOT_PREFIX
    done_marker = out_dir / "done.json"
    environment = build_environment(
        prefix, out_dir, done_marker, keys, zero_input_frames, settle_frames,
        hold_frames,
        state=state,
        state_sha256=sha256_file(state) if state else None,
        rom_sha256=rom_sha256,
    )
    inputs = {
        "schema": "konoha.s49-advance-inputs.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "start": "savestate" if state else "power-on",
        "rom": str(rom),
        "rom_sha256": rom_sha256,
        "save_sidecar": str(sidecar) if sidecar.is_file() else None,
        "save_sha256": sha256_file(sidecar) if sidecar.is_file() else None,
        "state": str(state) if state else None,
        "state_sha256": sha256_file(state) if state else None,
        "mgba": str(mgba),
        "mgba_sha256": sha256_file(mgba),
        "script": str(script.relative_to(ROOT)) if script.is_relative_to(ROOT) else str(script),
        "script_sha256": sha256_file(script),
        "guard": str(GUARD),
        "guard_sha256": sha256_file(GUARD),
        "keys": list(keys),
        "zero_input_frames": zero_input_frames,
        "settle_frames": settle_frames,
        "hold_frames": hold_frames,
    }

    if not run:
        return {"inputs": inputs, "environment": environment}

    out_dir.mkdir(parents=True)
    (out_dir / "inputs.json").write_text(
        json.dumps(inputs, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    child = [str(mgba), "--script", str(script), str(rom)]
    completed = subprocess.run(
        guard_command(out_dir / "guard.json", done_marker, child),
        env={**os.environ, **environment},
        text=True, capture_output=True, check=False,
    )
    if completed.returncode != 0:
        raise AdvanceError(
            f"guarded walk failed with exit {completed.returncode}: "
            f"{completed.stderr.strip()[:400]}")
    result = verify_walk(out_dir, keys)
    (out_dir / "steps.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"inputs": inputs, "out_dir": str(out_dir), **result}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--state", type=Path, default=None,
                        help="resume from this savestate; omit to boot from power-on")
    parser.add_argument("--keys", required=True,
                        help="ordered key list, e.g. A, A*20 or A,B,Down*3")
    parser.add_argument("--zero-input-frames", type=int, required=True)
    parser.add_argument("--settle-frames", type=int, required=True)
    parser.add_argument("--hold-frames", type=int, required=True)
    parser.add_argument("--label", default="walk")
    parser.add_argument("--mgba", type=Path, default=DEFAULT_MGBA)
    parser.add_argument("--dry-run", action="store_true",
                        help="resolve and print the contract without running mGBA")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        keys = parse_keys(args.keys)
        result = advance(
            args.out_dir, args.rom, args.state, keys, args.zero_input_frames,
            args.settle_frames, args.hold_frames, args.mgba, args.label,
            run=not args.dry_run,
        )
    except (AdvanceError, OSError, ValueError, KeyError) as error:
        print(f"capture_s49_advance: {error}", file=sys.stderr)
        return 2
    if args.dry_run:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    steps = result["steps"]
    print(json.dumps({
        "out_dir": result["out_dir"],
        "captured_steps": len(steps),
        "last_step": steps[-1]["image"],
        "last_step_sha256": steps[-1]["image_sha256"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
