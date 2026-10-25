#!/usr/bin/env python3
"""One command that reproduces the whole S49 save / boundary evidence.

    python tools/s49_save_boundary/run_all.py            # capture + compare
    python tools/s49_save_boundary/run_all.py --repeat 2 # capture twice and
                                                          # assert byte identity

The command:

1. makes sure the private probe exists (it is built into
   ``build/mgba-probe-w4`` so the shared ``build/mgba-probe`` binary is never
   touched),
2. records the original's battle 14 walk and the remake's boot walk and
   reads the cartridge SRAM at every checkpoint,
3. decodes both save formats, diffs them byte for byte and writes the
   field level difference table,
4. (with ``--repeat``) repeats the capture and asserts that the two runs are
   byte identical.

Exit codes: 0 all good / 2 missing input / 3 the two runs differ.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import capture_sram  # noqa: E402
import compare_save_images  # noqa: E402
from s49_save_common import (  # noqa: E402
    PRIVATE_PROBE,
    REPO,
    RECEIPTS,
    WORK,
    probe_exe,
    sha256_file,
    write_json,
)

EXIT_OK = 0
EXIT_INPUT_ERROR = 2
EXIT_NOT_REPRODUCIBLE = 3


def ensure_probe() -> pathlib.Path:
    """Build the private probe if it is missing (never the shared one)."""

    if PRIVATE_PROBE.is_file():
        return PRIVATE_PROBE
    environment = dict(os.environ)
    environment["KONOHA_PROBE_OUT"] = str(PRIVATE_PROBE.parent)
    completed = subprocess.run(
        [sys.executable, str(REPO / "tools" / "mgba_probe" / "build.py")],
        env=environment, text=True, capture_output=True, check=False,
    )
    if completed.returncode != 0 or not PRIVATE_PROBE.is_file():
        raise SystemExit(
            "ERR could not build the private probe:\n%s"
            % completed.stdout[-2000:] + completed.stderr[-2000:]
        )
    return PRIVATE_PROBE


def _snapshot(receipt: dict) -> dict:
    """The SRAM image hashes of one capture run."""

    snapshot = {}
    for side in ("original", "remake"):
        for name, info in receipt[side]["images"].items():
            snapshot["%s/%s" % (side, name)] = info["sram_sha256"]
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=1,
                        help="capture this many times and compare the runs")
    args = parser.parse_args(argv)

    try:
        ensure_probe()
    except SystemExit as error:
        print(str(error), file=sys.stderr)
        return EXIT_INPUT_ERROR

    runs = []
    for index in range(max(1, args.repeat)):
        print("=== capture run %d/%d ===" % (index + 1, args.repeat))
        receipt = {}
        receipt["original"] = capture_sram.capture_original()
        receipt["remake"] = capture_sram.capture_remake()
        write_json(WORK / "receipts" / "capture_sram.json", receipt)
        report = compare_save_images.build_report(receipt)
        write_json(RECEIPTS / "save_compare.json", report)
        compare_save_images.write_text(
            RECEIPTS / "save_compare.md",
            compare_save_images._markdown(report),
        )
        runs.append({
            "run": index + 1,
            "snapshot": _snapshot(receipt),
            "summary": {
                "original_checkpoints": report["original"]["checkpoint_count"],
                "original_distinct_images": report["original"][
                    "distinct_images"],
                "original_pre_post_diff_bytes": report["original"][
                    "pre_post_differing_bytes"],
                "remake_erased_to_save1": report["remake"][
                    "diff_erased_to_first_save"]["differing_bytes"],
                "remake_save1_to_save2": report["remake"][
                    "diff_first_to_second_save"]["differing_bytes"],
                "remake_save2_to_battle": report["remake"][
                    "diff_second_save_to_last_battle_step"][
                        "differing_bytes"],
                "cross_format_differing_bytes": report["cross_format"][
                    "differing_bytes"],
            },
        })
        print("run %d: %s" % (index + 1, json.dumps(
            runs[-1]["summary"], ensure_ascii=False)))

    identical = None
    if len(runs) > 1:
        first = runs[0]["snapshot"]
        identical = all(
            run["snapshot"] == first for run in runs[1:]
        )
        print("reproducible across %d runs: %s" % (len(runs), identical))

    write_json(RECEIPTS / "run_all.json", {
        "probe": str(probe_exe()),
        "probe_sha256": sha256_file(probe_exe()),
        "runs": runs,
        "identical_across_runs": identical,
    })
    print("wrote %s" % (RECEIPTS / "run_all.json"))
    if identical is False:
        return EXIT_NOT_REPRODUCIBLE
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
