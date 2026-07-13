#!/usr/bin/env python3
"""Compare captured mGBA DirectSound FIFO bytes with the offline MP2K engine."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from tools.m4a_song_engine import M4ASongEngine
    from tools.m4a_scheduler import BUFFER_FRAMES
except ModuleNotFoundError:
    from m4a_song_engine import M4ASongEngine
    from m4a_scheduler import BUFFER_FRAMES


def _interleave(right: bytes, left: bytes) -> bytes:
    if len(right) != BUFFER_FRAMES or len(left) != BUFFER_FRAMES:
        raise ValueError("captured FIFO planes must contain exactly 264 bytes")
    pcm = bytearray()
    for right_sample, left_sample in zip(right, left):
        pcm.extend((right_sample, left_sample))
    return bytes(pcm)


def _engine_pcm(step) -> bytes:
    return _interleave(
        bytes(sample & 0xFF for sample in step.right),
        bytes(sample & 0xFF for sample in step.left),
    )


def compare_capture(rom: bytes, bank: dict, decoded: dict, capture: dict) -> dict:
    if capture.get("timed_out"):
        raise ValueError("mGBA capture timed out")
    if capture.get("error"):
        raise ValueError(f"mGBA capture failed: {capture['error']}")
    sound_id = capture["sound_id"]
    engine = M4ASongEngine.from_bank(
        rom, bank, decoded, sound_id=sound_id
    )
    actual_combined = bytearray()
    expected_combined = bytearray()
    comparisons = []
    capture_hashes_valid = True
    for invocation, row in enumerate(capture["captures"]):
        if row["invocation"] != invocation:
            raise ValueError("capture invocations must be contiguous from zero")
        actual_pcm = _interleave(
            bytes.fromhex(row["right_hex"]),
            bytes.fromhex(row["left_hex"]),
        )
        expected_pcm = _engine_pcm(engine.advance_soundmain())
        actual_hash = hashlib.sha256(actual_pcm).hexdigest()
        expected_hash = hashlib.sha256(expected_pcm).hexdigest()
        row_hash_valid = row["pcm_sha256"] == actual_hash
        capture_hashes_valid &= row_hash_valid
        actual_combined.extend(actual_pcm)
        expected_combined.extend(expected_pcm)
        comparisons.append({
            "invocation": invocation,
            "match": actual_pcm == expected_pcm,
            "capture_hash_valid": row_hash_valid,
            "captured_pcm_sha256": actual_hash,
            "expected_pcm_sha256": expected_hash,
        })

    actual_combined_hash = hashlib.sha256(actual_combined).hexdigest()
    expected_combined_hash = hashlib.sha256(expected_combined).hexdigest()
    capture_hashes_valid &= (
        capture["combined_pcm_sha256"] == actual_combined_hash
    )
    mismatches = [row for row in comparisons if not row["match"]]
    return {
        "format": "gba-naruto-mgba-mp2k-differential-v1",
        "sound_id": sound_id,
        "invocation_count": len(comparisons),
        "counter_sequence_valid": capture.get("counter_sequence_valid"),
        "capture_hashes_valid": capture_hashes_valid,
        "matched_chunk_count": sum(row["match"] for row in comparisons),
        "all_chunks_match": not mismatches,
        "first_mismatch_invocation": (
            mismatches[0]["invocation"] if mismatches else None
        ),
        "captured_combined_pcm_sha256": actual_combined_hash,
        "expected_combined_pcm_sha256": expected_combined_hash,
        "combined_pcm_match": actual_combined == expected_combined,
        "offline_engine_finished": engine.finished,
        "comparisons": comparisons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument(
        "--bank", type=Path, default=Path("sequel/content/audio/bank.json")
    )
    parser.add_argument(
        "--decoded", type=Path,
        default=Path("build/audio-v2/tracks-decoded.json"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = compare_capture(
        args.rom.read_bytes(),
        json.loads(args.bank.read_text()),
        json.loads(args.decoded.read_text()),
        json.loads(args.capture.read_text()),
    )
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["all_chunks_match"] and result["capture_hashes_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
