#!/usr/bin/env python3
"""Compare a delayed same-player cue replacement against isolated engines."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

try:
    from tools.build_delayed_audio_retrigger_probe import build_probe
    from tools.compare_mgba_audio_capture import (
        capture_state_hashes_valid,
        read_capture_rom,
    )
    from tools.compare_mgba_linked_audio_capture import PLAYER_STATE_OFFSETS
    from tools.m4a_song_engine import M4ASongEngine
    from tools.m4a_scheduler import BUFFER_FRAMES
except ModuleNotFoundError:
    from build_delayed_audio_retrigger_probe import build_probe
    from compare_mgba_audio_capture import capture_state_hashes_valid, read_capture_rom
    from compare_mgba_linked_audio_capture import PLAYER_STATE_OFFSETS
    from m4a_song_engine import M4ASongEngine
    from m4a_scheduler import BUFFER_FRAMES


CHANNEL_STATE_SIZE = 0x40


def _entry(bank: dict, sound_id: int) -> dict:
    try:
        return next(row for row in bank["entries"] if row["sound_id"] == sound_id)
    except StopIteration as exc:
        raise ValueError(f"sound ID {sound_id} is not active") from exc


def _interleave(right: bytes, left: bytes) -> bytes:
    if len(right) != BUFFER_FRAMES or len(left) != BUFFER_FRAMES:
        raise ValueError("captured FIFO planes must contain exactly 264 bytes")
    pcm = bytearray()
    for right_sample, left_sample in zip(right, left):
        pcm.extend((right_sample, left_sample))
    return bytes(pcm)


def compare_retrigger_capture(
    rom: bytes,
    bank: dict,
    decoded: dict,
    capture: dict,
    *,
    first_sound_id: int,
    replacement_sound_id: int,
    switch_after_invocations: int,
    captured_rom: bytes,
) -> dict:
    if capture.get("timed_out"):
        raise ValueError("mGBA capture timed out")
    if capture.get("error"):
        raise ValueError(f"mGBA capture failed: {capture['error']}")
    if switch_after_invocations <= 0:
        raise ValueError("switch invocations must be positive")
    first_entry = _entry(bank, first_sound_id)
    replacement_entry = _entry(bank, replacement_sound_id)
    expected_probe_rom = build_probe(
        rom,
        first_sound_id=first_sound_id,
        replacement_sound_id=replacement_sound_id,
        switch_after_invocations=switch_after_invocations,
    )
    expected_probe_hash = hashlib.sha256(expected_probe_rom).hexdigest()
    captured_probe_hash = hashlib.sha256(captured_rom).hexdigest()
    if first_entry["player_index"] != replacement_entry["player_index"]:
        raise ValueError("retrigger comparison requires one shared player slot")
    if first_entry["reverb"] != 0 or replacement_entry["reverb"] != 0:
        raise ValueError("retrigger FIFO comparison requires zero-reverb cues")
    if switch_after_invocations >= len(capture["captures"]):
        raise ValueError("capture must include at least one replacement invocation")

    slot = first_entry["player_index"]
    first = M4ASongEngine.from_bank(
        rom, bank, decoded, sound_id=first_sound_id
    )
    replacement = None
    comparisons = []
    actual_combined = bytearray()
    expected_combined = bytearray()
    capture_hashes_valid = True
    switch_active_statuses = None
    for invocation, row in enumerate(capture["captures"]):
        if row["invocation"] != invocation:
            raise ValueError("capture invocations must be contiguous from zero")
        if invocation < switch_after_invocations:
            step = first.advance_soundmain()
            expected_clock = invocation + 1
        else:
            if replacement is None:
                replacement = M4ASongEngine.from_bank(
                    rom, bank, decoded, sound_id=replacement_sound_id
                )
            step = replacement.advance_soundmain()
            expected_clock = invocation - switch_after_invocations + 1

        expected_pcm = _interleave(
            bytes(sample & 0xFF for sample in step.right),
            bytes(sample & 0xFF for sample in step.left),
        )
        actual_pcm = _interleave(
            bytes.fromhex(row["right_hex"]),
            bytes.fromhex(row["left_hex"]),
        )
        actual_hash = hashlib.sha256(actual_pcm).hexdigest()
        expected_hash = hashlib.sha256(expected_pcm).hexdigest()
        capture_hash_valid = row["pcm_sha256"] == actual_hash
        capture_hashes_valid &= capture_hash_valid
        actual_combined.extend(actual_pcm)
        expected_combined.extend(expected_pcm)

        player_state = bytes.fromhex(row["player_state_hex"])
        actual_clock = struct.unpack_from(
            "<I", player_state, PLAYER_STATE_OFFSETS[slot] + 0x0C
        )[0]
        channels = bytes.fromhex(row["direct_channels_hex"])
        if len(channels) != 12 * CHANNEL_STATE_SIZE:
            raise ValueError("SoundInfo channel state must contain 0x300 bytes")
        active_statuses = [
            channels[index * CHANNEL_STATE_SIZE]
            for index in range(10)
            if channels[index * CHANNEL_STATE_SIZE] & 0xC7
        ]
        if invocation == switch_after_invocations:
            switch_active_statuses = active_statuses
        comparisons.append({
            "invocation": invocation,
            "phase": "first" if invocation < switch_after_invocations else "replacement",
            "pcm_match": actual_pcm == expected_pcm,
            "capture_hash_valid": capture_hash_valid,
            "captured_pcm_sha256": actual_hash,
            "expected_pcm_sha256": expected_hash,
            "player_clock": actual_clock,
            "expected_player_clock": expected_clock,
            "player_clock_match": actual_clock == expected_clock,
            "active_direct_statuses": active_statuses,
        })

    actual_combined_hash = hashlib.sha256(actual_combined).hexdigest()
    expected_combined_hash = hashlib.sha256(expected_combined).hexdigest()
    capture_hashes_valid &= (
        capture["combined_pcm_sha256"] == actual_combined_hash
    )
    pcm_mismatches = [row for row in comparisons if not row["pcm_match"]]
    clock_mismatches = [
        row for row in comparisons if not row["player_clock_match"]
    ]
    state_hashes_valid = capture_state_hashes_valid(capture)
    counter_sequence_valid = capture.get("counter_sequence_valid") is True
    result = {
        "format": "gba-naruto-mgba-same-player-retrigger-differential-v1",
        "first_sound_id": first_sound_id,
        "replacement_sound_id": replacement_sound_id,
        "player_slot": slot,
        "switch_after_invocations": switch_after_invocations,
        "invocation_count": len(comparisons),
        "counter_sequence_valid": counter_sequence_valid,
        "capture_hashes_valid": capture_hashes_valid,
        "capture_state_hashes_valid": state_hashes_valid,
        "expected_probe_rom_sha256": expected_probe_hash,
        "captured_probe_rom_sha256": captured_probe_hash,
        "probe_rom_match": captured_rom == expected_probe_rom,
        "matched_chunk_count": len(comparisons) - len(pcm_mismatches),
        "all_chunks_match": not pcm_mismatches,
        "first_pcm_mismatch_invocation": (
            pcm_mismatches[0]["invocation"] if pcm_mismatches else None
        ),
        "all_player_clocks_match": not clock_mismatches,
        "first_clock_mismatch_invocation": (
            clock_mismatches[0]["invocation"] if clock_mismatches else None
        ),
        "old_pool_empty_at_switch": switch_active_statuses == [],
        "switch_active_direct_statuses": switch_active_statuses,
        "captured_combined_pcm_sha256": actual_combined_hash,
        "expected_combined_pcm_sha256": expected_combined_hash,
        "combined_pcm_match": actual_combined == expected_combined,
        "replacement_engine_finished": (
            replacement.finished if replacement is not None else False
        ),
        "comparisons": comparisons,
    }
    result["verification_passed"] = (
        result["all_chunks_match"]
        and result["all_player_clocks_match"]
        and result["old_pool_empty_at_switch"]
        and result["capture_hashes_valid"]
        and result["capture_state_hashes_valid"]
        and result["counter_sequence_valid"]
        and result["probe_rom_match"]
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--first-sound-id", type=lambda value: int(value, 0), required=True)
    parser.add_argument(
        "--replacement-sound-id", type=lambda value: int(value, 0), required=True
    )
    parser.add_argument("--switch-after-invocations", type=int, required=True)
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
    result = compare_retrigger_capture(
        args.rom.read_bytes(),
        json.loads(args.bank.read_text()),
        json.loads(args.decoded.read_text()),
        capture,
        first_sound_id=args.first_sound_id,
        replacement_sound_id=args.replacement_sound_id,
        switch_after_invocations=args.switch_after_invocations,
        captured_rom=read_capture_rom(capture, args.capture),
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
