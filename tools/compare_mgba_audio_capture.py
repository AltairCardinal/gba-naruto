#!/usr/bin/env python3
"""Compare captured mGBA DirectSound FIFO bytes with the offline MP2K engine."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from tools.build_controlled_audio_runtime_probe import build_probe
    from tools.m4a_song_engine import M4ASongEngine
    from tools.m4a_scheduler import BUFFER_FRAMES
except ModuleNotFoundError:
    from build_controlled_audio_runtime_probe import build_probe
    from m4a_song_engine import M4ASongEngine
    from m4a_scheduler import BUFFER_FRAMES


STATE_HASH_FIELDS = (
    ("player_state_hex", "player_state_sha256"),
    ("direct_channels_hex", "direct_channels_sha256"),
    ("cgb_state_hex", "cgb_state_sha256"),
)


def capture_state_hashes_valid(capture: dict) -> bool:
    valid = True
    for row in capture.get("captures", []):
        for hex_field, hash_field in STATE_HASH_FIELDS:
            if hex_field not in row and hash_field not in row:
                continue
            if hex_field not in row or hash_field not in row:
                valid = False
                continue
            actual = hashlib.sha256(bytes.fromhex(row[hex_field])).hexdigest()
            valid &= row[hash_field] == actual
    return valid


def read_capture_rom(capture: dict, capture_path: Path) -> bytes:
    rom_path = Path(capture["rom"])
    if not rom_path.is_absolute():
        rom_path = capture_path.parent / rom_path
    return rom_path.read_bytes()


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


def compare_capture(
    rom: bytes,
    bank: dict,
    decoded: dict,
    capture: dict,
    *,
    captured_rom: bytes,
    dispatch_sequence: tuple[int, ...],
) -> dict:
    if capture.get("timed_out"):
        raise ValueError("mGBA capture timed out")
    if capture.get("error"):
        raise ValueError(f"mGBA capture failed: {capture['error']}")
    sound_id = capture["sound_id"]
    if not dispatch_sequence:
        raise ValueError("dispatch sequence must not be empty")
    expected_probe_rom = build_probe(rom, sound_ids=dispatch_sequence)
    expected_probe_hash = hashlib.sha256(expected_probe_rom).hexdigest()
    captured_probe_hash = hashlib.sha256(captured_rom).hexdigest()
    probe_rom_match = captured_rom == expected_probe_rom
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
    state_hashes_valid = capture_state_hashes_valid(capture)
    counter_sequence_valid = capture.get("counter_sequence_valid") is True
    final_sound_id_match = dispatch_sequence[-1] == sound_id
    result = {
        "format": "gba-naruto-mgba-mp2k-differential-v1",
        "sound_id": sound_id,
        "final_sound_id": sound_id,
        "dispatch_sequence": list(dispatch_sequence),
        "final_sound_id_match": final_sound_id_match,
        "expected_probe_rom_sha256": expected_probe_hash,
        "captured_probe_rom_sha256": captured_probe_hash,
        "probe_rom_match": probe_rom_match,
        "invocation_count": len(comparisons),
        "counter_sequence_valid": counter_sequence_valid,
        "capture_hashes_valid": capture_hashes_valid,
        "capture_state_hashes_valid": state_hashes_valid,
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
    result["verification_passed"] = (
        result["all_chunks_match"]
        and result["capture_hashes_valid"]
        and result["capture_state_hashes_valid"]
        and result["counter_sequence_valid"]
        and result["probe_rom_match"]
        and result["final_sound_id_match"]
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument(
        "--dispatch-id", type=lambda value: int(value, 0), action="append",
        help="Controlled pre-SoundMain dispatch sequence metadata",
    )
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
    capture = json.loads(args.capture.read_text())
    dispatch_sequence = tuple(args.dispatch_id or [capture["sound_id"]])
    result = compare_capture(
        args.rom.read_bytes(),
        json.loads(args.bank.read_text()),
        json.loads(args.decoded.read_text()),
        capture,
        captured_rom=read_capture_rom(capture, args.capture),
        dispatch_sequence=dispatch_sequence,
    )
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
