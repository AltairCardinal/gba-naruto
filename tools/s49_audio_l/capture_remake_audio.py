#!/usr/bin/env python3
"""Record the remake ROM's own audio output and check that the mixer is alive.

Stream L (S49 audio wiring).  The runtime cue trace proves that a cue was
dispatched and that the Maxmod mixer accepted it, but it cannot prove that
the mixer kept running afterwards: the remake tree's own notes
(``notes/butano-battle-audio-runtime-20260727.md``) document an
"IRQ/Maxmod mixer freeze" that was triggered by repeated WAV sound effect
submission.

This script drives the remake ROM with the same input walk the cue trace
uses, records the emulated GBA's audio output with the remake tree's
``mgba_audio_recorder`` (read-only reuse) and reports, per GBA frame, the
RMS of the recorded PCM.  A freeze shows up as a long silent span; a live
mixer shows a continuous signal.

Usage:
    python tools/s49_audio_l/capture_remake_audio.py --out build/s49-audio-l
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import struct
import subprocess
import sys
import wave

REPO = pathlib.Path(__file__).resolve().parents[2]
REMAKE_ROOT = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\butano-sequel")
DEFAULT_ROM = REMAKE_ROOT / "butano-sequel.gba"
RECORDER = REPO / "build" / "mgba-probe-l" / "mgba-audio-recorder.exe"

ZERO_INPUT_FRAMES = 600
HOLD_FRAMES = 4
SETTLE_FRAMES = 90
A_ROUNDS = 32
TAIL_FRAMES = 300
FRAME_COUNT = (ZERO_INPUT_FRAMES + (HOLD_FRAMES + SETTLE_FRAMES) * (2 + A_ROUNDS)
               + TAIL_FRAMES)
GBA_FPS = 60.0


def input_events() -> list[tuple[int, str, str]]:
    """The same press/release pattern the probe's keyseq command produces."""
    events: list[tuple[int, str, str]] = []
    frame = ZERO_INPUT_FRAMES
    for key in ("Down", "Down"):
        events.append((frame, "press", key))
        events.append((frame + HOLD_FRAMES, "release", key))
        frame += HOLD_FRAMES + SETTLE_FRAMES
    for _ in range(A_ROUNDS):
        events.append((frame, "press", "A"))
        events.append((frame + HOLD_FRAMES, "release", "A"))
        frame += HOLD_FRAMES + SETTLE_FRAMES
    return events


def write_events(path: pathlib.Path) -> None:
    # The recorder parses the log with sscanf and a fixed pattern, so the JSON
    # must not contain spaces.
    lines = [json.dumps({"frame": frame, "event": event, "key": key},
                         ensure_ascii=False, separators=(",", ":")) + "\n"
             for frame, event, key in input_events()]
    path.write_text("".join(lines), encoding="utf-8", newline="\n")


def record(rom: pathlib.Path, out_wav: pathlib.Path, work_dir: pathlib.Path) -> dict:
    if not RECORDER.is_file():
        raise SystemExit(
            f"ERR recorder missing: {RECORDER}\n"
            f"    $env:KONOHA_PROBE_OUT='{REPO / 'build' / 'mgba-probe-l'}'; "
            f"python tools/s49_audio_l/build_recorder.py")
    events_path = work_dir / "remake-input-events.jsonl"
    write_events(events_path)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    environment = {"MGBA_AUDIO_INPUT_EVENTS": str(events_path)}
    import os
    merged = dict(os.environ)
    merged.update(environment)
    result = subprocess.run(
        [str(RECORDER), str(rom), str(out_wav), str(FRAME_COUNT)],
        capture_output=True, text=True, env=merged)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise SystemExit(f"ERR recorder failed with {result.returncode}")
    return {"stderr": result.stderr.strip()}


def analyse(wav_path: pathlib.Path) -> dict:
    with wave.open(str(wav_path), "rb") as stream:
        channels = stream.getnchannels()
        rate = stream.getframerate()
        width = stream.getsampwidth()
        frames = stream.getnframes()
        raw = stream.readframes(frames)
    samples = struct.unpack(f"<{len(raw) // 2}h", raw)
    mono = [0.0] * (len(samples) // channels)
    for index in range(len(mono)):
        total = 0
        for channel in range(channels):
            total += samples[index * channels + channel]
        mono[index] = total / channels

    block = max(1, int(round(rate / GBA_FPS)))
    per_frame = []
    for start in range(0, len(mono), block):
        window = mono[start:start + block]
        if not window:
            break
        rms = math.sqrt(sum(value * value for value in window) / len(window))
        per_frame.append(rms)

    silent = [index for index, rms in enumerate(per_frame) if rms < 1.0]
    longest = 0
    current = 0
    for index in range(len(per_frame)):
        if per_frame[index] < 1.0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    nonzero = sum(1 for value in samples if value != 0)
    return {
        "channels": channels,
        "sample_rate": rate,
        "sample_width_bytes": width,
        "pcm_frames": frames,
        "duration_seconds": round(frames / rate, 3),
        "nonzero_samples": nonzero,
        "nonzero_ratio": round(nonzero / max(1, len(samples)), 6),
        "rms": round(math.sqrt(sum(value * value for value in samples)
                               / max(1, len(samples))), 4),
        "peak": max((abs(value) for value in samples), default=0),
        "g ba_frames": len(per_frame),
        "g ba_frame_rms": [round(value, 3) for value in per_frame],
        "silent_frames": len(silent),
        "longest_silent_run_frames": longest,
        "first_silent_frame": silent[0] if silent else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(REPO / "build" / "s49-audio-l"))
    parser.add_argument("--rom", default=str(DEFAULT_ROM))
    parser.add_argument("--wav", default=None)
    parser.add_argument("--analysis", default=None)
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    wav_path = pathlib.Path(args.wav) if args.wav else out_dir / "remake-audio.wav"
    analysis_path = (pathlib.Path(args.analysis) if args.analysis
                     else out_dir / "remake_audio_analysis.json")

    print(f"recording remake audio ... rom={pathlib.Path(args.rom).name}")
    record(pathlib.Path(args.rom), wav_path, out_dir)
    analysis = analyse(wav_path)
    # Only the file name is recorded: the full path differs between two
    # verification runs, and the analysis has to stay byte identical.
    analysis["wav"] = wav_path.name
    analysis_path.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    print(f"  duration {analysis['duration_seconds']} s, "
          f"nonzero ratio {analysis['nonzero_ratio']}, "
          f"rms {analysis['rms']}, peak {analysis['peak']}")
    print(f"  silent frames {analysis['silent_frames']}, "
          f"longest silent run {analysis['longest_silent_run_frames']} frames")
    print(f"wrote {analysis_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
