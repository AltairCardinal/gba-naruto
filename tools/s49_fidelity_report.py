#!/usr/bin/env python3
"""S49 fidelity report -- one command, one receipt.

This is the *yardstick* for the three-day S49 replication project.  It turns
"re-record the original, re-record the remake, cross-align, measure the
battlefield residual" into a single reproducible command:

    python tools/s49_fidelity_report.py --out build/s49-report/report.json

What it does, in order:

1.  **Re-record the original** (25 frames) from the battle-14 savestate with
    ``mgba_original_s49_ui_boundaries.lua`` (env contract ``MGBA_ORIGINAL_S49_*``).
2.  **Re-record the remake** (35 frames) from power-on with
    ``mgba_boot_input_sequence.lua`` (env contract ``MGBA_BOOT_SEQUENCE_*``),
    key sequence ``Down,Down,A x32``.
    Both recordings go through ``tools/mgba_probe/probe_client.py``.
3.  **Read the content anchors.**  Every step of a walk saved a savestate
    next to its PNG, so the machine state that produced the frame can be
    read back (IO registers, palette RAM, video RAM) without re-running the
    walk.  The anchors are the camera registers, the fade (black) state and
    the per-cell overlay family map.
4.  **Cross-align** the two frame sets: for every original frame, find the
    remake frame that matches it best.  Pixel logic is identical to
    ``tools/compare_frame_dirs.py`` (a pixel counts as different when any of
    its three channels differ); the matching logic is identical to
    ``tools/align_frame_dirs.py`` (arg-min over the full distance matrix).
    Best match is chosen on the battlefield area (default ``0 0 240 128``).
5.  **Attribute the residual.**  A big residual is only interesting once you
    know *why* it is big:

    * ``identical``     -- zero residual on the battlefield area.
    * ``product_diff``  -- the two frames are the *same game moment*; the
      residual is a real rendering difference and the product code is wrong.
    * ``pairing_diff``  -- the two frames are *different game moments*; the
      residual says nothing about the product code and must not be "fixed".
      A pairing diff is refined into three machine readable buckets:
      ``black_transition`` (the original fades the screen out), ``static_frame``
      (the remake holds a still frame) and ``moment_mismatch``.

    The moment test is a majority vote of three content signals (see
    ``classify.vote``).  Every frame carries the raw signals, the thresholds,
    the vote, the margin and a confidence, so a reader can re-derive the
    verdict instead of trusting it.
6.  **Emit a receipt**: a JSON document plus a Markdown table.  The JSON
    carries ``content_sha256`` -- the digest of everything except the
    timestamp -- so "the report is reproducible" is a checkable claim, not a
    promise.  Two consecutive runs must produce the same digest.

Reproducibility notes
---------------------
* The probe is deterministic: the same ROM plus the same input sequence gives
  the same frames.  The captured PNGs are hashed into the report so the
  evidence identity is pinned.
* The real BIOS is **off by default**.  Measured on this machine: the baseline
  captures in ``build/s49-original-walk`` and ``build/s49-remake`` were taken
  with mGBA's HLE BIOS (adding ``--bios`` changes 4/25 original frames and
  35/35 remake frames, and the remake boot never reaches the battle scene).
  Pass ``--bios <path>`` to opt in; the report records which mode was used.
* Files written by this tool are UTF-8 without BOM and LF line endings: the
  repository treats SHA-256 as the evidence identity, so a stray CRLF would
  invalidate every pinned hash.

The ratchet
-----------
``--ratchet <baseline report>`` compares the residual of this run against a
baseline report and **fails when the residual got bigger**.  This is the
"the residual may only get smaller" rule of the project, and it is what the
acceptance of a change should be judged by.

The gate has **three** verdicts (wave 15 / W2), and the exit code tells them
apart:

===== ========================================== ======
code  verdict                                    meaning
===== ========================================== ======
0     ``pass``                                   comparable, nothing got worse
1     ``fail``                                   something got worse
2     ``incomparable``                           the ROM changed and nothing
                                                 got worse: the two numbers
                                                 are **not** the same
                                                 measurement, so the verdict
                                                 is "not comparable" -- and
                                                 explicitly **not** a pass
===== ========================================== ======

A residual that grew is a failure **even across a ROM change**: the ROM
change explains *who* moved the number, but "it got bigger" stays a
meaningful statement in pixels and is exactly the regression this gate
exists to catch.

Reproducibility
---------------
The ratchet is only meaningful when the bench reads the *same* number twice
on the *same* input.  ``--repeat N`` reads the bench N times and checks that
the readings agree (residual summaries, attribution, the three buckets, the
per frame pairing and the sha256 of every captured PNG).  The verdict is
written into the report's ``run.determinism`` section.

A ROM that changed between two readings makes the comparison **void**, not
failed: the residual delta then belongs to the ROM change, not to the bench.
Wave 10 measured a "+/-9,520 px jitter" that was exactly this -- the remake
ROM was rebuilt between the two runs -- so the distinction is kept explicit
instead of being folded into a pass/fail.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from s49_fidelity_report import anchors as anchors_module  # noqa: E402
from s49_fidelity_report import capture as capture_module  # noqa: E402
from s49_fidelity_report import determinism as determinism_module  # noqa: E402
from s49_fidelity_report import ratchet as ratchet_module  # noqa: E402
from s49_fidelity_report import report as report_module  # noqa: E402
from s49_fidelity_report.paths import PROBE_EXE, REPO  # noqa: E402


def compare_reports(left: dict, right: dict) -> dict:
    """Compare two reports.

    *measurement_same* compares the part that matters downstream -- config,
    captures, frames and summary.  It is what ``content_sha256`` covers.
    *full_same* additionally compares the run provenance section.

    When the two reports have different schemas the whole document can no
    longer be compared, so the **measurement core** is compared instead: the
    per-frame residual and attribution, and the summary's residual numbers.
    That is what tells a reader whether the *measurement* changed or only the
    report gained fields.
    """
    def strip(doc, drop_run):
        clone = json.loads(json.dumps(doc))
        clone.pop("generated_at", None)
        if drop_run:
            clone.pop("run", None)
        return clone

    measurement_left = strip(left, drop_run=True)
    measurement_right = strip(right, drop_run=True)
    measurement_same = measurement_left == measurement_right
    full_same = strip(left, drop_run=False) == strip(right, drop_run=False)

    differences = []
    for key in sorted(set(measurement_left) | set(measurement_right)):
        if measurement_left.get(key) != measurement_right.get(key):
            differences.append(f"  field `{key}` differs")
            if key == "frames":
                for fa, fb in zip(measurement_left.get(key, []),
                                   measurement_right.get(key, [])):
                    if fa != fb:
                        differences.append(
                            f"    frame `{fa.get('original')}` vs `{fb.get('original')}`")

    core_same = True
    core_differences = []
    if not measurement_same:
        core_same, core_differences = compare_measurement_core(left, right)
    return {
        "measurement_same": measurement_same,
        "full_same": full_same,
        "differences": differences,
        "core_same": core_same,
        "core_differences": core_differences,
        "schema_left": left.get("schema"),
        "schema_right": right.get("schema"),
    }


def compare_measurement_core(left: dict, right: dict) -> tuple[bool, list[str]]:
    """Compare the residual and the attribution of two reports."""
    differences = []

    def summary_of(doc):
        return (doc.get("summary") or {})

    for key in ("field_residual", "full_residual"):
        a = summary_of(left).get(key) or {}
        b = summary_of(right).get(key) or {}
        for metric in ("min", "median", "max", "sum", "zero_frames", "frames"):
            if metric in a or metric in b:
                if a.get(metric) != b.get(metric):
                    differences.append(
                        f"  summary.{key}.{metric}: {a.get(metric)} vs {b.get(metric)}")

    for kind in ("identical", "product_diff", "pairing_diff"):
        a = (summary_of(left).get("attribution") or {}).get(kind)
        b = (summary_of(right).get("attribution") or {}).get(kind)
        if a != b:
            differences.append(f"  attribution.{kind}: {a} vs {b}")

    rows_left = {row["original"]: row for row in left.get("frames", [])}
    for row in right.get("frames", []):
        old = rows_left.get(row["original"])
        if old is None:
            differences.append(f"  frame `{row['original']}` is new")
            continue
        for key in ("field_residual_px", "full_residual_px", "best_match"):
            if old.get(key) != row.get(key):
                differences.append(
                    f"  frame `{row['original']}`.{key}: "
                    f"{old.get(key)} vs {row.get(key)}")
        if (old.get("verdict") or {}).get("class") != \
                (row.get("verdict") or {}).get("class"):
            differences.append(
                f"  frame `{row['original']}`.verdict.class: "
                f"{(old.get('verdict') or {}).get('class')} vs "
                f"{(row.get('verdict') or {}).get('class')}")
    return not differences, differences


def _measure(args, work_dir: pathlib.Path, original_rom: pathlib.Path,
             remake_rom: pathlib.Path, original_lua: pathlib.Path,
             remake_lua: pathlib.Path, original_state: pathlib.Path,
             quiet: bool) -> tuple[dict, dict]:
    """One complete reading of the bench: capture, anchors, report body.

    Everything it produces is a pure function of the two ROMs, the two Lua
    scripts and the work directory -- which is what makes two readings of the
    same ROM comparable at all.
    """
    captures = {}
    reuse = bool(args.skip_capture)
    if not reuse and not quiet:
        print("recording original (25 frames from savestate)...")
    captures["original"] = capture_module.run_capture(
        name="original",
        rom=original_rom,
        lua=original_lua,
        env_extra={
            "MGBA_ORIGINAL_S49_INPUT_STATE": str(original_state),
            "MGBA_ORIGINAL_S49_INPUT_STATE_SHA256":
                capture_module.ORIGINAL_STATE_SHA256,
            "MGBA_ORIGINAL_S49_OUTPUT_DIR": str(work_dir / "capture-original"),
            "MGBA_ORIGINAL_S49_DONE_MARKER":
                str(work_dir / "capture-original" / "done.json"),
            "MGBA_ORIGINAL_S49_KEY_SEQUENCE":
                ",".join(capture_module.ORIGINAL_KEY_SEQUENCE),
            "MGBA_ORIGINAL_S49_ZERO_INPUT_FRAMES":
                str(capture_module.ORIGINAL_ZERO_INPUT_FRAMES),
            "MGBA_ORIGINAL_S49_SETTLE_FRAMES":
                str(capture_module.ORIGINAL_SETTLE_FRAMES),
            "MGBA_ORIGINAL_S49_HOLD_FRAMES": str(capture_module.HOLD_FRAMES),
        },
        out_dir=work_dir / "capture-original",
        frames_budget=capture_module.ORIGINAL_FRAMES_BUDGET,
        bios=args.bios,
        expected_frames=25,
        reuse=reuse,
    )
    if not reuse and not quiet:
        print("recording remake (35 frames from power-on)...")
    captures["remake"] = capture_module.run_capture(
        name="remake",
        rom=remake_rom,
        lua=remake_lua,
        env_extra={
            "MGBA_BOOT_SEQUENCE_OUTPUT_DIR": str(work_dir / "capture-remake"),
            "MGBA_BOOT_SEQUENCE_DONE_MARKER":
                str(work_dir / "capture-remake" / "done.json"),
            # The remake capture records the digest of the ROM it actually
            # booted.  It used to be handed the *original* ROM's digest, so
            # the receipt claimed the wrong ROM identity for the remake side.
            "MGBA_BOOT_SEQUENCE_ROM_SHA256":
                capture_module.sha256_file(remake_rom),
            "MGBA_BOOT_SEQUENCE_KEY_SEQUENCE":
                ",".join(capture_module.REMAKE_KEY_SEQUENCE),
            "MGBA_BOOT_SEQUENCE_ZERO_INPUT_FRAMES":
                str(capture_module.REMAKE_ZERO_INPUT_FRAMES),
            "MGBA_BOOT_SEQUENCE_SETTLE_FRAMES":
                str(capture_module.REMAKE_SETTLE_FRAMES),
            "MGBA_BOOT_SEQUENCE_HOLD_FRAMES": str(capture_module.HOLD_FRAMES),
        },
        out_dir=work_dir / "capture-remake",
        frames_budget=capture_module.REMAKE_FRAMES_BUDGET,
        bios=args.bios,
        expected_frames=35,
        reuse=reuse,
    )

    # --- the content anchors ------------------------------------------------
    anchor_status = {}
    anchors = {}
    if not args.no_anchors:
        if not quiet:
            print("reading the content anchors (IO / PRAM / VRAM per step)...")
        from s49_fidelity_report.pixels import load_rgb
        cache_dir = work_dir / "anchors"
        for side, capture_dir, rom in (
                ("original", work_dir / "capture-original", original_rom),
                ("remake", work_dir / "capture-remake", remake_rom)):
            images = {path.name: load_rgb(path)
                      for path in sorted(capture_dir.glob("step-*.png"))}
            anchors[side] = anchors_module.side_anchors(
                side, capture_dir, rom, images, cache_dir)
            anchor_status[side] = anchors[side]["status"]
            if not quiet:
                print(f"  anchors[{side}]: {anchors[side]['status']}")
    else:
        for side in ("original", "remake"):
            anchors[side] = {"schema": anchors_module.ANCHOR_SCHEMA, "side": side,
                             "status": "skipped", "reason": "--no-anchors",
                             "frames": {}}
            anchor_status[side] = "skipped"

    return report_module.build_report(args, captures, work_dir, anchors), anchor_status


def main() -> int:
    # The console on this machine is GBK: a character it cannot encode would
    # raise UnicodeEncodeError *after* the measurements are done and turn a
    # green step red.  Replacing instead of raising keeps the exit code
    # honest.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError):
                pass
    ap = argparse.ArgumentParser(
        description="S49 保真度判定报告：重录 + 交叉对齐 + 残差归因，一条命令出收据。")
    ap.add_argument("--out", type=pathlib.Path,
                    default=REPO / "build" / "s49-report" / "report.json",
                    help="JSON report path")
    ap.add_argument("--work-dir", type=pathlib.Path, default=None,
                    help="scratch directory for the captures (default: <out dir>)")
    ap.add_argument("--markdown", type=pathlib.Path, default=None,
                    help="Markdown receipt path (default: <out> with .md)")
    ap.add_argument("--butano-root", default=None,
                    help="butano-sequel checkout root")
    ap.add_argument("--bios", type=pathlib.Path, default=None,
                    help="opt in to a real GBA BIOS (default: mGBA HLE, which is "
                         "what the pinned baseline captures used)")
    ap.add_argument("--field-area", nargs=4, type=int, default=[0, 0, 240, 128],
                    metavar=("X", "Y", "W", "H"),
                    help="battlefield area used for the residual (default 0 0 240 128)")
    ap.add_argument("--skip-capture", action="store_true",
                    help="reuse the captures already in --work-dir")
    ap.add_argument("--compare", type=pathlib.Path, default=None,
                    help="compare the freshly built report against this report "
                         "(ignoring the timestamp)")
    ap.add_argument("--ratchet", type=pathlib.Path, default=None,
                    help="gate: the residual may only get smaller than this "
                         "baseline report; a bigger residual exits non zero")
    ap.add_argument("--no-anchors", action="store_true",
                    help="skip the content anchor pass (no probe reads)")
    ap.add_argument("--repeat", type=int, default=1,
                    help="read the bench N times on the same ROM and prove the "
                         "reading is reproducible; N>1 fails when the readings "
                         "disagree (default 1)")
    ap.add_argument("--original-rom", type=pathlib.Path, default=None,
                    help="override the original ROM (default: <butano>/rom/base.gba)")
    ap.add_argument("--remake-rom", type=pathlib.Path, default=None,
                    help="override the remake ROM "
                         "(default: <butano>/butano-sequel/butano-sequel.gba)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.repeat < 1:
        raise SystemExit("ERR --repeat must be at least 1")

    out_path = args.out if args.out.is_absolute() else REPO / args.out
    work_dir = args.work_dir
    if work_dir is None:
        work_dir = out_path.parent
    elif not work_dir.is_absolute():
        work_dir = REPO / work_dir
    markdown_path = args.markdown
    if markdown_path is None:
        markdown_path = out_path.with_suffix(".md")
    elif not markdown_path.is_absolute():
        markdown_path = REPO / markdown_path

    butano = capture_module.resolve_butano_root(args.butano_root)
    original_rom = butano / "rom" / "base.gba"
    if args.original_rom:
        original_rom = (args.original_rom if args.original_rom.is_absolute()
                        else REPO / args.original_rom)
    original_state = (butano / "artifacts" / "runtime-checkpoints"
                      / "scenario-49-battle-14-entry.ss9")
    original_lua = butano / "tools" / "butano" / "mgba_original_s49_ui_boundaries.lua"
    remake_rom = butano / "butano-sequel" / "butano-sequel.gba"
    if args.remake_rom:
        remake_rom = (args.remake_rom if args.remake_rom.is_absolute()
                      else REPO / args.remake_rom)
    remake_lua = butano / "tools" / "butano" / "mgba_boot_input_sequence.lua"
    for required in (capture_module.PROBE_CLIENT, PROBE_EXE, original_rom,
                     original_state, original_lua, remake_rom, remake_lua):
        if not pathlib.Path(required).exists():
            raise SystemExit(f"ERR missing required input: {required}")

    if args.bios and not pathlib.Path(args.bios).exists():
        raise SystemExit(f"ERR bios not found: {args.bios}")

    # --- the readings -------------------------------------------------------
    # Every reading is taken on the *same* ROMs, so a difference between two
    # readings can only come from the bench itself.
    readings = []
    anchor_status = {}
    for index in range(1, args.repeat + 1):
        iteration_dir = work_dir if index == 1 else work_dir / f"repeat-{index}"
        if not args.quiet and args.repeat > 1:
            print(f"reading {index}/{args.repeat} ...")
        reading, anchor_status = _measure(
            args, iteration_dir, original_rom, remake_rom,
            original_lua, remake_lua, original_state, args.quiet)
        readings.append(reading)
    report = readings[0]
    determinism = determinism_module.compare(readings)

    report["generated_at"] = datetime.datetime.now().astimezone().isoformat(
        timespec="seconds")
    # Run provenance (was the capture re-recorded or reused, how many frame
    # budgets were burned) is kept out of the measurement digest: two runs
    # that produced the same pixels must produce the same content_sha256.
    run_meta = {"attempts": {}, "reused": {}}
    for key, capture in report["captures"].items():
        run_meta["attempts"][key] = capture.pop("attempts")
        run_meta["reused"][key] = capture.pop("reused")
    run_meta["determinism"] = determinism
    report["run"] = run_meta
    body = {key: value for key, value in report.items()
            if key not in ("generated_at", "content_sha256", "run", "ratchet")}
    report["content_sha256"] = hashlib.sha256(
        capture_module.canonical_json(body).encode("utf-8")).hexdigest()

    ratchet_result = None
    if args.ratchet:
        baseline_path = args.ratchet
        if not baseline_path.is_absolute():
            baseline_path = REPO / baseline_path
        if not baseline_path.exists():
            raise SystemExit(f"ERR ratchet baseline not found: {baseline_path}")
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        ratchet_result = ratchet_module.compare(baseline, report)
        ratchet_result["baseline"] = str(baseline_path)
        report["ratchet"] = ratchet_result

    capture_module.write_text(out_path, json.dumps(report, ensure_ascii=False,
                                                   indent=1) + "\n")
    capture_module.write_text(markdown_path, report_module.render_markdown(report))

    summary = report["summary"]
    if not args.quiet:
        print()
        print(f"report      : {out_path}")
        print(f"markdown    : {markdown_path}")
        print(f"content_sha : {report['content_sha256']}")
        print(f"field px    : min {summary['field_residual']['min']}  "
              f"median {summary['field_residual']['median']}  "
              f"max {summary['field_residual']['max']}  "
              f"zeros {summary['field_residual']['zero_frames']}/"
              f"{summary['field_residual']['frames']}")
        print(f"attribution : {summary['attribution']}")
        print(f"subclasses  : {summary['pairing_diff_subclasses']}")
        print(f"overlay px  : sum {summary['overlay_residual'].get('sum')}  "
              f"max {summary['overlay_residual'].get('max')}")
        print(f"anchors     : {anchor_status}  "
              f"pairing quality "
              f"{summary['pairing_quality']['anchor_supports_pairing']}/"
              f"{summary['pairing_quality']['frames']}")
        print(f"confidence  : {summary['confidence']}")
        if args.repeat > 1:
            print(f"determinism : {determinism['note']}")
            for reading in determinism["runs"]:
                print(f"  reading {reading['iteration']}: sum "
                      f"{reading['field_residual_sum']}  median "
                      f"{reading['field_residual_median']}  zeros "
                      f"{reading['zero_frames']}  capture "
                      f"{reading['capture_digest'][:12]}")

    exit_code = 0

    if not determinism["identical"]:
        print("DETERMINISM FAIL: the bench read different numbers on the same "
              "ROM; the ratchet cannot be trusted", file=sys.stderr)
        for line in determinism["differences"]:
            print(f"  {line}", file=sys.stderr)
        exit_code = 1

    if args.compare:
        other_path = args.compare
        if not other_path.is_absolute():
            other_path = REPO / other_path
        if not other_path.exists():
            raise SystemExit(f"ERR comparison report not found: {other_path}")
        other = json.loads(other_path.read_text(encoding="utf-8"))
        verdict = compare_reports(report, other)
        print(f"\nmeasurement  : "
              f"{'IDENTICAL' if verdict['measurement_same'] else 'DIFFERENT'}"
              f"  (content_sha256 {report['content_sha256'][:16]} vs "
              f"{other.get('content_sha256', '?')[:16]})")
        print(f"full report  : {'identical' if verdict['full_same'] else 'differs'}"
              f" (ignoring generated_at)")
        if not verdict["measurement_same"]:
            if verdict["schema_left"] != verdict["schema_right"]:
                print(f"note: the schemas differ "
                      f"({verdict['schema_left']} vs {verdict['schema_right']}), "
                      f"so only the measurement core is compared:")
                for line in verdict["core_differences"]:
                    print(line)
                if verdict["core_same"]:
                    print("MEASUREMENT CORE IDENTICAL: the residual and the "
                          "attribution did not change, the report only gained "
                          "fields")
                    print(f"note: re-pin the baseline "
                          f"(content_sha256 {report['content_sha256']})")
                else:
                    print("MEASUREMENT CORE DIFFERENT")
                    exit_code = 1
            else:
                print("differences:")
                for line in verdict["differences"]:
                    print(line)
                exit_code = 1
        else:
            print("REPRODUCIBLE: byte-identical to "
                  f"{other_path} (ignoring generated_at)")

    if ratchet_result is not None:
        status = ratchet_result.get("status") or (
            "pass" if ratchet_result["ok"] else "fail")
        label = {"pass": "PASS", "fail": "FAIL",
                 "incomparable": "INCOMPARABLE（不可比）"}[status]
        print("\nratchet      : " + label)
        for check in ratchet_result["checks"]:
            if not check["ok"]:
                print(f"  FAIL {check['label']}: baseline {check['baseline']} -> "
                      f"candidate {check['candidate']} "
                      f"({'bigger is worse' if check['direction'] == 'higher' else 'smaller is worse'})")
        rom = ratchet_result.get("rom") or {}
        if rom.get("changed"):
            print(f"  note: the ROM changed between the two readings "
                  f"({rom.get('baseline')} -> {rom.get('candidate')}): the "
                  f"residual delta belongs to the ROM change, not to the bench")
        if status == "incomparable":
            # Not a failure, but definitely **not** a pass either: the two
            # residual numbers are not the same measurement, so the ratchet
            # has nothing to say about this run.  Exit code 2 tells the
            # caller "incomparable" apart from "failed" (1) and "passed" (0).
            print("RATCHET INCOMPARABLE: the baseline ROM differs from this "
                  "run's ROM => the two residual numbers are not the same "
                  "measurement => this is NOT a pass; the new baseline has to "
                  "be accepted explicitly", file=sys.stderr)
            if not exit_code:
                exit_code = 2
        elif status == "fail":
            print("RATCHET FAIL: the residual got bigger; this run must not "
                  "be accepted", file=sys.stderr)
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
