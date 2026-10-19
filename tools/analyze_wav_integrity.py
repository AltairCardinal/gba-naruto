#!/usr/bin/env python3
"""Measure deterministic PCM integrity signals in a 16-bit WAV capture."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import wave
from pathlib import Path


JUMP_THRESHOLDS = (8192, 16384)


def analyze_wav(path: Path) -> dict[str, object]:
    raw_file = path.read_bytes()
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        sample_width = source.getsampwidth()
        sample_rate = source.getframerate()
        frame_count = source.getnframes()
        pcm = source.readframes(frame_count)

    if channels <= 0:
        raise ValueError("WAV must contain at least one channel")
    if sample_width != 2:
        raise ValueError("only signed 16-bit PCM WAV is supported")
    expected_bytes = frame_count * channels * sample_width
    if len(pcm) != expected_bytes:
        raise ValueError("truncated WAV PCM payload")

    samples = [
        int.from_bytes(
            pcm[offset : offset + 2],
            "little",
            signed=True,
        )
        for offset in range(0, len(pcm), 2)
    ]
    sample_count = len(samples)
    transition_count = max(0, frame_count - 1) * channels
    jump_counts = {threshold: 0 for threshold in JUMP_THRESHOLDS}
    for channel in range(channels):
        previous = samples[channel]
        for frame in range(1, frame_count):
            current = samples[frame * channels + channel]
            difference = abs(current - previous)
            for threshold in JUMP_THRESHOLDS:
                if difference >= threshold:
                    jump_counts[threshold] += 1
            previous = current

    mean = sum(samples) / sample_count if sample_count else 0.0
    rms = (
        math.sqrt(
            sum(sample * sample for sample in samples) /
            sample_count
        )
        if sample_count
        else 0.0
    )
    return {
        "path": str(path),
        "sha256": hashlib.sha256(raw_file).hexdigest(),
        "channels": channels,
        "sample_width_bytes": sample_width,
        "sample_rate": sample_rate,
        "frame_count": frame_count,
        "sample_count": sample_count,
        "nonzero_sample_count": sum(
            sample != 0 for sample in samples
        ),
        "peak_absolute_sample": max(
            (abs(sample) for sample in samples),
            default=0,
        ),
        "mean": mean,
        "rms": rms,
        "adjacent_transition_count": transition_count,
        "adjacent_jump_counts": {
            str(threshold): jump_counts[threshold]
            for threshold in JUMP_THRESHOLDS
        },
        "adjacent_jump_rates": {
            str(threshold): (
                jump_counts[threshold] / transition_count
                if transition_count
                else 0.0
            )
            for threshold in JUMP_THRESHOLDS
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = analyze_wav(args.wav)
    rendered = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
