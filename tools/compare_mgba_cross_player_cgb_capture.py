#!/usr/bin/env python3
"""Verify synthetic cross-player competition for the fixed CGB noise channel."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

try:
    from tools.build_cross_player_cgb_probe import build_probe
    from tools.compare_mgba_audio_capture import (
        capture_state_hashes_valid,
        read_capture_rom,
    )
    from tools.compare_mgba_cgb_capture import compare_cgb_capture
    from tools.compare_mgba_linked_audio_capture import (
        PLAYER_STATE_OFFSETS,
        PLAYER_TRACK_BASES,
    )
except ModuleNotFoundError:
    from build_cross_player_cgb_probe import build_probe
    from compare_mgba_audio_capture import capture_state_hashes_valid, read_capture_rom
    from compare_mgba_cgb_capture import compare_cgb_capture
    from compare_mgba_linked_audio_capture import (
        PLAYER_STATE_OFFSETS,
        PLAYER_TRACK_BASES,
    )


CGB4_STATE_OFFSET = 0xC0
CHANNEL_TRACK_OFFSET = 0x2C


def _entry(bank: dict, sound_id: int) -> dict:
    try:
        return next(row for row in bank["entries"] if row["sound_id"] == sound_id)
    except StopIteration as exc:
        raise ValueError(f"sound ID {sound_id} is not active") from exc


def compare_cross_player_cgb_capture(
    rom: bytes,
    bank: dict,
    decoded: dict,
    capture: dict,
    *,
    source_sound_id: int,
    clone_sound_id: int,
    clone_player_slot: int,
    captured_rom: bytes,
) -> dict:
    source = _entry(bank, source_sound_id)
    source_slot = source["player_index"]
    if clone_player_slot == source_slot:
        raise ValueError("clone player slot must differ from source slot")
    if clone_sound_id == source_sound_id:
        raise ValueError("clone sound ID must differ from source")
    if clone_player_slot not in PLAYER_STATE_OFFSETS:
        raise ValueError("clone player slot must be in 0..3")

    expected_probe_rom = build_probe(
        rom,
        source_sound_id=source_sound_id,
        clone_sound_id=clone_sound_id,
        clone_player_slot=clone_player_slot,
    )
    expected_probe_hash = hashlib.sha256(expected_probe_rom).hexdigest()
    captured_probe_hash = hashlib.sha256(captured_rom).hexdigest()

    base = compare_cgb_capture(rom, bank, decoded, capture)
    clone_owner = PLAYER_TRACK_BASES[clone_player_slot]
    source_owner = PLAYER_TRACK_BASES[source_slot]
    expected_owner = min(clone_owner, source_owner)
    losing_owner = max(clone_owner, source_owner)
    comparisons = []
    competition_observed = False
    captured_pcm = bytearray()
    capture_hashes_valid = True
    for invocation, row in enumerate(capture["captures"]):
        player_state = bytes.fromhex(row["player_state_hex"])
        clone_clock = struct.unpack_from(
            "<I", player_state, PLAYER_STATE_OFFSETS[clone_player_slot] + 0x0C
        )[0]
        source_clock = struct.unpack_from(
            "<I", player_state, PLAYER_STATE_OFFSETS[source_slot] + 0x0C
        )[0]
        cgb4 = bytes.fromhex(row["cgb_state_hex"])[
            CGB4_STATE_OFFSET:CGB4_STATE_OFFSET + 0x40
        ]
        status = cgb4[0]
        owner = struct.unpack_from("<I", cgb4, CHANNEL_TRACK_OFFSET)[0]
        active = bool(status & 0xC7)
        right = bytes.fromhex(row["right_hex"])
        left = bytes.fromhex(row["left_hex"])
        interleaved = bytes(
            sample
            for pair in zip(right, left)
            for sample in pair
        )
        captured_pcm.extend(interleaved)
        capture_hashes_valid &= (
            row.get("pcm_sha256") == hashlib.sha256(interleaved).hexdigest()
        )
        owner_match = not active or owner == expected_owner
        clocks_match = (
            clone_clock == invocation + 1
            and source_clock == invocation + 1
        )
        if active and clocks_match and owner == expected_owner:
            competition_observed = True
        comparisons.append({
            "invocation": invocation,
            "clone_player_clock": clone_clock,
            "source_player_clock": source_clock,
            "player_clocks_match": clocks_match,
            "channel_status": status,
            "channel_owner": f"0x{owner:08X}",
            "active_owner_match": owner_match,
        })

    clock_mismatches = [
        row for row in comparisons if not row["player_clocks_match"]
    ]
    owner_mismatches = [
        row for row in comparisons if not row["active_owner_match"]
    ]
    state_hashes_valid = capture_state_hashes_valid(capture)
    capture_hashes_valid &= (
        capture.get("combined_pcm_sha256")
        == hashlib.sha256(captured_pcm).hexdigest()
    )
    counter_sequence_valid = capture.get("counter_sequence_valid") is True
    result = {
        "format": "gba-naruto-mgba-cross-player-cgb-differential-v1",
        "source_sound_id": source_sound_id,
        "source_player_slot": source_slot,
        "clone_sound_id": clone_sound_id,
        "clone_player_slot": clone_player_slot,
        "clone_track_owner": f"0x{clone_owner:08X}",
        "source_track_owner": f"0x{source_owner:08X}",
        "expected_winning_track_owner": f"0x{expected_owner:08X}",
        "losing_track_owner": f"0x{losing_owner:08X}",
        "invocation_count": len(comparisons),
        "counter_sequence_valid": counter_sequence_valid,
        "capture_state_hashes_valid": state_hashes_valid,
        "capture_hashes_valid": capture_hashes_valid,
        "expected_probe_rom_sha256": expected_probe_hash,
        "captured_probe_rom_sha256": captured_probe_hash,
        "probe_rom_match": captured_rom == expected_probe_rom,
        "all_visible_registers_match": base["all_visible_registers_match"],
        "matched_visible_register_count": base["matched_visible_register_count"],
        "all_channel_statuses_match": base["all_channel_statuses_match"],
        "direct_fifo_silent": base["direct_fifo_silent"],
        "all_player_clocks_match": not clock_mismatches,
        "first_clock_mismatch_invocation": (
            clock_mismatches[0]["invocation"] if clock_mismatches else None
        ),
        "all_active_owners_match": not owner_mismatches,
        "first_owner_mismatch_invocation": (
            owner_mismatches[0]["invocation"] if owner_mismatches else None
        ),
        "competition_observed": competition_observed,
        "expected_nr44_trigger_writes": base["expected_nr44_trigger_writes"],
        "offline_engine_finished": base["offline_engine_finished"],
        "tie_break_boundary": (
            "Both priority-255 players advance on every invocation. Static allocator "
            "control flow uses old_owner >= new_owner for equal-priority replacement, "
            f"so the lower track address 0x{expected_owner:08X} is the stable owner; "
            "this capture verifies the final owner for the configured simultaneous "
            "request, not both possible temporal arrival orders."
        ),
        "comparisons": comparisons,
    }
    result["verification_passed"] = (
        result["all_visible_registers_match"]
        and result["all_channel_statuses_match"]
        and result["direct_fifo_silent"]
        and result["all_player_clocks_match"]
        and result["all_active_owners_match"]
        and result["competition_observed"]
        and result["capture_state_hashes_valid"]
        and result["capture_hashes_valid"]
        and result["counter_sequence_valid"]
        and result["probe_rom_match"]
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--source-sound-id", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--clone-sound-id", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--clone-player-slot", type=int, required=True)
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
    result = compare_cross_player_cgb_capture(
        args.rom.read_bytes(),
        json.loads(args.bank.read_text()),
        json.loads(args.decoded.read_text()),
        capture,
        source_sound_id=args.source_sound_id,
        clone_sound_id=args.clone_sound_id,
        clone_player_slot=args.clone_player_slot,
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
