#!/usr/bin/env python3
"""Compare a zero-reverb linked-player mGBA capture with isolated cue sums."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

try:
    from tools.build_controlled_audio_runtime_probe import build_probe
    from tools.compare_mgba_audio_capture import (
        capture_state_hashes_valid,
        read_capture_rom,
    )
    from tools.m4a_song_engine import M4ASongEngine
    from tools.m4a_scheduler import BUFFER_FRAMES
except ModuleNotFoundError:
    from build_controlled_audio_runtime_probe import build_probe
    from compare_mgba_audio_capture import capture_state_hashes_valid, read_capture_rom
    from m4a_song_engine import M4ASongEngine
    from m4a_scheduler import BUFFER_FRAMES


PLAYER_STATE_OFFSETS = {0: 0x00, 1: 0x40, 2: 0x80, 3: 0xD0}
PLAYER_TRACK_BASES = {
    0: 0x03005E58,
    1: 0x03006178,
    2: 0x030061C8,
    3: 0x03006218,
}
TRACK_STATE_SIZE = 0x50
CHANNEL_STATE_SIZE = 0x40
CHANNEL_TRACK_OFFSET = 0x2C


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


def compare_linked_capture(
    rom: bytes,
    bank: dict,
    decoded: dict,
    capture: dict,
    *,
    sound_ids: tuple[int, ...],
    captured_rom: bytes,
) -> dict:
    if capture.get("timed_out"):
        raise ValueError("mGBA capture timed out")
    if capture.get("error"):
        raise ValueError(f"mGBA capture failed: {capture['error']}")
    if len(sound_ids) < 2:
        raise ValueError("linked comparison requires at least two sound IDs")
    entries = [_entry(bank, sound_id) for sound_id in sound_ids]
    expected_probe_rom = build_probe(rom, sound_ids=sound_ids)
    expected_probe_hash = hashlib.sha256(expected_probe_rom).hexdigest()
    captured_probe_hash = hashlib.sha256(captured_rom).hexdigest()
    player_slots = [entry["player_index"] for entry in entries]
    if len(set(player_slots)) != len(player_slots):
        raise ValueError("linked comparison requires distinct player slots")
    if any(entry["reverb"] != 0 for entry in entries):
        raise ValueError("isolated-sum comparison requires zero-reverb cues")
    engines = [
        M4ASongEngine.from_bank(
            rom, bank, decoded, sound_id=sound_id
        )
        for sound_id in sound_ids
    ]
    expected_track_ptrs = {
        sound_id: [
            PLAYER_TRACK_BASES[entry["player_index"]] + index * TRACK_STATE_SIZE
            for index in range(entry["track_count"])
        ]
        for sound_id, entry in zip(sound_ids, entries)
    }
    observed_track_ptrs: set[int] = set()
    comparisons = []
    actual_combined = bytearray()
    expected_combined = bytearray()
    capture_hashes_valid = True
    for invocation, row in enumerate(capture["captures"]):
        if row["invocation"] != invocation:
            raise ValueError("capture invocations must be contiguous from zero")
        steps = [engine.advance_soundmain() for engine in engines]
        if any(
            allocation.kind == "cgb"
            for engine in engines
            for runner in engine.runners
            for allocation in runner.allocations
        ):
            raise ValueError("linked FIFO sum does not support CGB cues")
        expected_right = bytes(
            sum(step.right[frame] for step in steps) & 0xFF
            for frame in range(BUFFER_FRAMES)
        )
        expected_left = bytes(
            sum(step.left[frame] for step in steps) & 0xFF
            for frame in range(BUFFER_FRAMES)
        )
        expected_pcm = _interleave(expected_right, expected_left)
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
        clocks = {
            slot: struct.unpack_from(
                "<I", player_state, PLAYER_STATE_OFFSETS[slot] + 0x0C
            )[0]
            for slot in player_slots
        }
        channels = bytes.fromhex(row["direct_channels_hex"])
        if len(channels) != 12 * CHANNEL_STATE_SIZE:
            raise ValueError("SoundInfo channel state must contain 0x300 bytes")
        active_tracks = []
        for index in range(10):
            offset = index * CHANNEL_STATE_SIZE
            if channels[offset] & 0xC7:
                track_ptr = struct.unpack_from(
                    "<I", channels, offset + CHANNEL_TRACK_OFFSET
                )[0]
                active_tracks.append(track_ptr)
                observed_track_ptrs.add(track_ptr)
        comparisons.append({
            "invocation": invocation,
            "pcm_match": actual_pcm == expected_pcm,
            "capture_hash_valid": capture_hash_valid,
            "captured_pcm_sha256": actual_hash,
            "expected_pcm_sha256": expected_hash,
            "player_clocks": {str(slot): clocks[slot] for slot in player_slots},
            "player_clocks_match": all(
                clock == invocation + 1 for clock in clocks.values()
            ),
            "active_track_state_ptrs": [
                f"0x{track_ptr:08X}" for track_ptr in active_tracks
            ],
        })

    actual_combined_hash = hashlib.sha256(actual_combined).hexdigest()
    expected_combined_hash = hashlib.sha256(expected_combined).hexdigest()
    capture_hashes_valid &= (
        capture["combined_pcm_sha256"] == actual_combined_hash
    )
    pcm_mismatches = [row for row in comparisons if not row["pcm_match"]]
    clock_mismatches = [
        row for row in comparisons if not row["player_clocks_match"]
    ]
    shared_pool_tracks_observed = all(
        any(track_ptr in observed_track_ptrs for track_ptr in track_ptrs)
        for track_ptrs in expected_track_ptrs.values()
    )
    state_hashes_valid = capture_state_hashes_valid(capture)
    counter_sequence_valid = capture.get("counter_sequence_valid") is True
    result = {
        "format": "gba-naruto-mgba-linked-player-differential-v1",
        "sound_ids": list(sound_ids),
        "player_slots": player_slots,
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
        "shared_pool_tracks_observed": shared_pool_tracks_observed,
        "expected_track_state_ptrs": {
            str(sound_id): [f"0x{ptr:08X}" for ptr in ptrs]
            for sound_id, ptrs in expected_track_ptrs.items()
        },
        "observed_active_track_state_ptrs": [
            f"0x{ptr:08X}" for ptr in sorted(observed_track_ptrs)
        ],
        "captured_combined_pcm_sha256": actual_combined_hash,
        "expected_combined_pcm_sha256": expected_combined_hash,
        "combined_pcm_match": actual_combined == expected_combined,
        "comparisons": comparisons,
    }
    result["verification_passed"] = (
        result["all_chunks_match"]
        and result["all_player_clocks_match"]
        and result["shared_pool_tracks_observed"]
        and result["capture_hashes_valid"]
        and result["capture_state_hashes_valid"]
        and result["counter_sequence_valid"]
        and result["probe_rom_match"]
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument(
        "--sound-id", type=lambda value: int(value, 0), action="append", required=True,
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
    result = compare_linked_capture(
        args.rom.read_bytes(),
        json.loads(args.bank.read_text()),
        json.loads(args.decoded.read_text()),
        capture,
        sound_ids=tuple(args.sound_id),
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
