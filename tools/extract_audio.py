#!/usr/bin/env python3
"""Scan and extract DirectSound PCM audio samples from the GBA ROM.

GBA m4a/mp2k audio driver sample format:
  +0x00  u8   type        0x00 = uncompressed signed 8-bit PCM
  +0x01  u8   loop_flag   0x00 = no loop, 0x40 = loop
  +0x02  u16  freq        natural frequency / pitch (Hz, see note below)
  +0x04  u32  loop_start  sample index where loop begins
  +0x08  u32  size        total sample count
  +0x0C  s8[] data        PCM samples (signed 8-bit, mono)

Note: GBA m4a uses 13379 Hz or 16756 Hz as typical playback base rate.
The `freq` field indicates the recorded pitch (used for transposing notes).
We export at 13379 Hz by default; adjust with --sample-rate.

Usage:
    python tools/extract_audio.py rom.gba               # scan only
    python tools/extract_audio.py rom.gba --extract     # scan + export WAV
    python tools/extract_audio.py rom.gba --extract --output-dir build/audio
    python tools/extract_audio.py rom.gba --min-size 1000  # filter small samples
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

# GBA m4a typical playback rate
DEFAULT_SAMPLE_RATE = 13379

# Sample header size (before PCM data)
SAMPLE_HEADER_SIZE = 12

# Sanity bounds for valid sample detection
FREQ_MIN = 2000
FREQ_MAX = 50000
SIZE_MIN = 64        # minimum useful sample length
SIZE_MAX = 2_000_000


def read_u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def find_samples(data: bytes, min_size: int = SIZE_MIN) -> list[dict]:
    """Scan ROM for DirectSound sample headers."""
    results = []
    prev_end = 0

    for off in range(0, len(data) - SAMPLE_HEADER_SIZE, 4):
        stype      = data[off]
        loop_flag  = data[off + 1]
        freq       = read_u16(data, off + 2)
        loop_start = read_u32(data, off + 4)
        size       = read_u32(data, off + 8)

        if (stype == 0x00
                and loop_flag in (0x00, 0x40)
                and FREQ_MIN <= freq <= FREQ_MAX
                and min_size <= size <= SIZE_MAX
                and loop_start <= size
                and off + SAMPLE_HEADER_SIZE + size <= len(data)):

            # Skip if overlapping a previous sample (likely a false positive)
            if off < prev_end:
                continue

            data_end = off + SAMPLE_HEADER_SIZE + size
            prev_end = data_end

            results.append({
                "offset":      off,
                "type":        stype,
                "loop_flag":   loop_flag,
                "freq":        freq,
                "loop_start":  loop_start,
                "size":        size,
                "data_end":    data_end,
                "looping":     loop_flag == 0x40,
            })

    return results


def write_wav(path: Path, pcm_data: bytes, sample_rate: int) -> None:
    """Write a mono signed-8-bit PCM WAV file."""
    num_channels   = 1
    bits_per_sample = 8   # signed 8-bit
    byte_rate      = sample_rate * num_channels * bits_per_sample // 8
    block_align    = num_channels * bits_per_sample // 8
    data_size      = len(pcm_data)
    riff_size      = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", riff_size, b"WAVE",
        b"fmt ", 16,
        1,               # PCM
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data", data_size,
    )
    path.write_bytes(header + pcm_data)


def export_sample(
    rom: bytes,
    sample: dict,
    output_dir: Path,
    index: int,
    sample_rate: int,
) -> Path:
    """Extract one sample as a WAV file."""
    off  = sample["offset"]
    size = sample["size"]
    pcm  = rom[off + SAMPLE_HEADER_SIZE : off + SAMPLE_HEADER_SIZE + size]

    loop_tag = "loop" if sample["looping"] else "once"
    fname = f"sample_{index:04d}_{off:06X}_{loop_tag}_{sample['freq']}hz.wav"
    out_path = output_dir / fname
    write_wav(out_path, pcm, sample_rate)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan and extract GBA DirectSound PCM samples.")
    parser.add_argument("rom", type=Path)
    parser.add_argument("--extract", action="store_true", help="Export WAV files")
    parser.add_argument("--output-dir", type=Path, default=Path("build/audio"))
    parser.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE,
                        help=f"Playback sample rate for WAV export (default {DEFAULT_SAMPLE_RATE})")
    parser.add_argument("--min-size", type=int, default=SIZE_MIN,
                        help=f"Minimum sample size to include (default {SIZE_MIN})")
    parser.add_argument("--max-results", type=int, default=500)
    args = parser.parse_args()

    if not args.rom.exists():
        print(f"Error: ROM not found: {args.rom}", file=sys.stderr)
        return 1

    rom = args.rom.read_bytes()
    print(f"ROM size: {len(rom):,} bytes")
    print(f"Scanning for DirectSound samples (size >= {args.min_size})...")

    samples = find_samples(rom, args.min_size)
    samples = samples[: args.max_results]

    total_bytes = sum(s["size"] for s in samples)
    looping = sum(1 for s in samples if s["looping"])
    print(f"Found {len(samples)} samples ({looping} looping) — {total_bytes:,} total PCM bytes\n")

    header = f"{'#':>4}  {'file_offset':>12}  {'freq':>6}  {'size':>8}  {'loop':>5}  {'loop_start':>10}"
    print(header)
    print("-" * len(header))
    for i, s in enumerate(samples):
        print(f"{i:4d}  0x{s['offset']:08X}    {s['freq']:5d}  {s['size']:8d}  {'YES' if s['looping'] else 'no':>5}  {s['loop_start']:10d}")

    if args.extract:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"\nExporting {len(samples)} WAV files to {args.output_dir}/...")
        for i, s in enumerate(samples):
            path = export_sample(rom, s, args.output_dir, i, args.sample_rate)
            print(f"  [{i:4d}] {path.name}")
        print(f"\nDone. {len(samples)} files written.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
