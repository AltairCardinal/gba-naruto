#!/usr/bin/env python3
"""Compare mGBA-visible CGB channel-4 state with the offline MP2K engine."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from tools.m4a_song_engine import M4ASongEngine
    from tools.m4a_scheduler import BUFFER_FRAMES
except ModuleNotFoundError:
    from m4a_song_engine import M4ASongEngine
    from m4a_scheduler import BUFFER_FRAMES


CGB_IO_SIZE = 0x30
CGB_STATE_SIZE = 0x100
CGB4_STATE_OFFSET = 0xC0
IDLE_VISIBLE_REGISTERS = {
    "NR41": 0x00,
    "NR42": 0x08,
    "NR43": 0x00,
    "NR51": 0x00,
}


def _visible_registers(io: bytes) -> dict[str, int]:
    if len(io) != CGB_IO_SIZE:
        raise ValueError("CGB IO capture must contain 0x30 bytes")
    return {
        "NR41": io[0x18],
        "NR42": io[0x19],
        "NR43": io[0x1C],
        "NR51": io[0x21],
    }


def _expected_registers(channel) -> dict[str, int]:
    if not channel.registers:
        return dict(IDLE_VISIBLE_REGISTERS)
    return {
        name: channel.registers[name]
        for name in ("NR41", "NR42", "NR43", "NR51")
    }


def compare_cgb_capture(rom: bytes, bank: dict, decoded: dict, capture: dict) -> dict:
    if capture.get("timed_out"):
        raise ValueError("mGBA capture timed out")
    if capture.get("error"):
        raise ValueError(f"mGBA capture failed: {capture['error']}")
    sound_id = capture["sound_id"]
    engine = M4ASongEngine.from_bank(
        rom, bank, decoded, sound_id=sound_id
    )
    comparisons = []
    trigger_invocations = []
    previous_allocations = 0
    direct_fifo_silent = True
    for invocation, row in enumerate(capture["captures"]):
        if row["invocation"] != invocation:
            raise ValueError("capture invocations must be contiguous from zero")
        engine.advance_soundmain()
        channel = engine.channels.cgb[3]
        allocation_count = sum(
            allocation.kind == "cgb" and allocation.channel_index == 3
            for runner in engine.runners
            for allocation in runner.allocations
        )
        if allocation_count > previous_allocations:
            trigger_invocations.extend(
                [invocation] * (allocation_count - previous_allocations)
            )
        previous_allocations = allocation_count

        io = bytes.fromhex(row["cgb_io_hex"])
        cgb_state = bytes.fromhex(row["cgb_state_hex"])
        if len(cgb_state) != CGB_STATE_SIZE:
            raise ValueError("CGB state capture must contain 0x100 bytes")
        actual_registers = _visible_registers(io)
        expected_registers = _expected_registers(channel)
        actual_status = cgb_state[CGB4_STATE_OFFSET]
        expected_status = channel.status
        right = bytes.fromhex(row["right_hex"])
        left = bytes.fromhex(row["left_hex"])
        if len(right) != BUFFER_FRAMES or len(left) != BUFFER_FRAMES:
            raise ValueError("captured FIFO planes must contain exactly 264 bytes")
        fifo_silent = not any(right) and not any(left)
        direct_fifo_silent &= fifo_silent
        comparisons.append({
            "invocation": invocation,
            "visible_registers_match": actual_registers == expected_registers,
            "captured_visible_registers": actual_registers,
            "expected_visible_registers": expected_registers,
            "channel_status_match": actual_status == expected_status,
            "captured_channel_status": actual_status,
            "expected_channel_status": expected_status,
            "direct_fifo_silent": fifo_silent,
        })

    register_mismatches = [
        row for row in comparisons if not row["visible_registers_match"]
    ]
    status_mismatches = [
        row for row in comparisons if not row["channel_status_match"]
    ]
    return {
        "format": "gba-naruto-mgba-cgb-differential-v1",
        "sound_id": sound_id,
        "invocation_count": len(comparisons),
        "counter_sequence_valid": capture.get("counter_sequence_valid"),
        "matched_visible_register_count": (
            len(comparisons) - len(register_mismatches)
        ),
        "all_visible_registers_match": not register_mismatches,
        "first_register_mismatch_invocation": (
            register_mismatches[0]["invocation"]
            if register_mismatches else None
        ),
        "matched_channel_status_count": (
            len(comparisons) - len(status_mismatches)
        ),
        "all_channel_statuses_match": not status_mismatches,
        "first_status_mismatch_invocation": (
            status_mismatches[0]["invocation"] if status_mismatches else None
        ),
        "direct_fifo_silent": direct_fifo_silent,
        "expected_nr44_trigger_writes": trigger_invocations,
        "nr44_readback_boundary": (
            "NR44 bit 7 is a trigger write and reads back as zero in mGBA; "
            "the comparison therefore records expected trigger invocations and "
            "compares NR41/NR42/NR43/NR51 plus channel-4 status directly."
        ),
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
    result = compare_cgb_capture(
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
    success = (
        result["all_visible_registers_match"]
        and result["all_channel_statuses_match"]
        and result["direct_fifo_silent"]
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
