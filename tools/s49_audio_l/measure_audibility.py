#!/usr/bin/env python3
"""Measure the audible contribution of every sound effect cue (stream L).

Why an A/B
-----------
The runtime trace records that a cue was dispatched, but the handle that
Butano returns is its own sequential counter, not a success flag, so the trace
alone cannot prove that the cue was audible.  The proof is an A/B of the two
remake ROMs that differ in exactly one thing: one of them submits the sound
effect to the Maxmod mixer, the other does not.  The difference of the two
recorded PCM streams is exactly the sound effects' contribution.

Usage:
    python tools/s49_audio_l/measure_audibility.py \
        --full build/s49-audio-l/full/remake-audio.wav \
        --nosfx build/s49-audio-l/nosfx/remake-audio.wav \
        --trace build/s49-audio-l/full/remake_trace.json \
        --out build/s49-audio-l/audibility.json
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import struct
import wave

REPO = pathlib.Path(__file__).resolve().parents[2]
REMAKE_ROOT = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano")
MANIFEST_DIR = REMAKE_ROOT / "artifacts" / "scenario-41-audio-reference-v1"

GBA_FPS = 60.0


def read_wav(path: pathlib.Path) -> tuple[list[int], int]:
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        rate = stream.getframerate()
        frames = stream.getnframes()
        raw = stream.readframes(frames)
    samples = struct.unpack(f"<{len(raw) // 2}h", raw)
    mono = [0] * (len(samples) // channels)
    for index in range(len(mono)):
        total = 0
        for channel in range(channels):
            total += samples[index * channels + channel]
        mono[index] = total // channels
    return mono, rate


def cue_durations() -> dict[int, float]:
    durations: dict[int, float] = {}
    sfx = MANIFEST_DIR / "sfx-manifest.json"
    if sfx.is_file():
        for entry in json.loads(sfx.read_text(encoding="utf-8"))["entries"]:
            durations[int(entry["sound_id"])] = float(entry["duration_seconds"])
    return durations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--full", required=True)
    parser.add_argument("--nosfx", required=True)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    full, rate = read_wav(pathlib.Path(args.full))
    nosfx, nosfx_rate = read_wav(pathlib.Path(args.nosfx))
    if rate != nosfx_rate:
        raise SystemExit(f"ERR sample rate mismatch: {rate} vs {nosfx_rate}")
    trace = json.loads(pathlib.Path(args.trace).read_text(encoding="utf-8"))
    durations = cue_durations()

    samples_per_frame = rate / GBA_FPS
    length = min(len(full), len(nosfx))
    diff = [abs(full[index] - nosfx[index]) for index in range(length)]

    # Per frame RMS of the difference.
    frame_rms: list[float] = []
    for start in range(0, length, int(samples_per_frame)):
        window = diff[start:start + int(samples_per_frame)]
        if not window:
            break
        frame_rms.append(math.sqrt(sum(value * value for value in window)
                                    / len(window)))

    overall_rms = math.sqrt(sum(value * value for value in diff) / length)
    nonzero_ratio = sum(1 for value in diff if value != 0) / max(1, length)

    rows = []
    for event in trace["events"]:
        if event["kind"] != "sound":
            continue
        cue = event["cue"]
        start = int(event["emulator_frame"])
        duration = durations.get(cue, 0.3)
        end = min(len(frame_rms), start + max(1, int(round(duration * GBA_FPS))))
        window = frame_rms[start:end]
        peak = max(window) if window else 0.0
        mean = sum(window) / len(window) if window else 0.0
        baseline = [frame_rms[max(0, start - 20):start] or [0.0],
                    frame_rms[end:end + 20] or [0.0]]
        baseline_rms = sum(
            sum(part) / len(part) for part in baseline) / len(baseline)
        rows.append({
            "cue": cue,
            "emulator_frame": start,
            "duration_seconds": round(duration, 3),
            "difference_peak": round(peak, 2),
            "difference_mean": round(mean, 2),
            "baseline_rms": round(baseline_rms, 2),
            "ratio_to_baseline": round(mean / baseline_rms, 3)
            if baseline_rms > 0 else None,
            "audible": peak > 0.0,
        })

    per_cue: dict[int, dict] = {}
    for row in rows:
        cue = row["cue"]
        entry = per_cue.setdefault(cue, {
            "cue": cue,
            "dispatches": 0,
            "audible_dispatches": 0,
            "max_difference_peak": 0.0,
            "max_ratio_to_baseline": 0.0,
        })
        entry["dispatches"] += 1
        if row["audible"]:
            entry["audible_dispatches"] += 1
        entry["max_difference_peak"] = max(
            entry["max_difference_peak"], row["difference_peak"])
        if row["ratio_to_baseline"] is not None:
            entry["max_ratio_to_baseline"] = max(
                entry["max_ratio_to_baseline"], row["ratio_to_baseline"])

    payload = {
        "full_wav": args.full,
        "nosfx_wav": args.nosfx,
        "sample_rate": rate,
        "difference_rms": round(overall_rms, 3),
        "difference_nonzero_ratio": round(nonzero_ratio, 6),
        "per_dispatch": rows,
        "per_cue": per_cue,
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"difference rms {overall_rms:.2f}, nonzero ratio {nonzero_ratio:.6f}")
    for cue, entry in sorted(per_cue.items()):
        print(f"  cue {cue:3d}: {entry['audible_dispatches']}/{entry['dispatches']}"
              f" audible, peak diff {entry['max_difference_peak']:.1f}, "
              f"max ratio {entry['max_ratio_to_baseline']:.2f}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
