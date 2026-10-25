#!/usr/bin/env python3
"""Record only the remake walk of the judgement bench.

The original side is copied from an earlier package (its audit still attests
the same original ROM and the same savestate, so the bench may reuse it);
only the remake side is recorded again, against the lane ROM.

Usage:
    python tools/s49_w24g1/capture_remake.py \
        --rom build/w20-e1/butano-sequel/butano-sequel.gba \
        --work-dir build/w24-g1/work \
        --original build/s49-package-w22/work/s49-report/capture-original
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from s49_fidelity_report import capture as capture_module  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--work-dir", type=pathlib.Path, required=True)
    parser.add_argument("--original", type=pathlib.Path, required=True)
    parser.add_argument(
        "--butano-root", type=pathlib.Path,
        default=pathlib.Path(r"D:\Shell\Github\gba-naruto-butano"))
    args = parser.parse_args()

    work_dir = args.work_dir
    work_dir.mkdir(parents=True, exist_ok=True)
    original_dir = work_dir / "capture-original"
    if not original_dir.exists():
        shutil.copytree(args.original, original_dir)
        print(f"copied the original capture into {original_dir}")
    else:
        print(f"reusing {original_dir}")

    remake_lua = args.butano_root / "tools" / "butano" / \
        "mgba_boot_input_sequence.lua"
    remake_dir = work_dir / "capture-remake"
    result = capture_module.run_capture(
        name="remake",
        rom=args.rom,
        lua=remake_lua,
        env_extra={
            "MGBA_BOOT_SEQUENCE_OUTPUT_DIR": str(remake_dir),
            "MGBA_BOOT_SEQUENCE_DONE_MARKER": str(remake_dir / "done.json"),
            "MGBA_BOOT_SEQUENCE_ROM_SHA256":
                capture_module.sha256_file(args.rom),
            "MGBA_BOOT_SEQUENCE_KEY_SEQUENCE":
                ",".join(capture_module.REMAKE_KEY_SEQUENCE),
            "MGBA_BOOT_SEQUENCE_ZERO_INPUT_FRAMES":
                str(capture_module.REMAKE_ZERO_INPUT_FRAMES),
            "MGBA_BOOT_SEQUENCE_SETTLE_FRAMES":
                str(capture_module.REMAKE_SETTLE_FRAMES),
            "MGBA_BOOT_SEQUENCE_HOLD_FRAMES":
                str(capture_module.HOLD_FRAMES),
        },
        out_dir=remake_dir,
        frames_budget=capture_module.REMAKE_FRAMES_BUDGET,
        bios=None,
        expected_frames=35,
        reuse=False,
    )
    print(f"remake frames: {result['frame_count']} "
          f"(ok={result['capture_ok']})")
    return 0 if result["capture_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
