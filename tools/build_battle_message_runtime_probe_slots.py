#!/usr/bin/env python3
"""Build the multi-slot battle-message selector probe and read back its slots.

The legacy single-slot probe (``tools/build_battle_message_runtime_probe.py``)
is frozen by ``artifacts/data-table-b-message0-pointer-pixel-ab-v1/manifest.json``
and must not change, so this is a separate tool.  It keeps the legacy 36-byte
scratch byte-for-byte compatible and appends a per-message-ID slot table, so a
single run can record every message ID the battle-message selector actually
touched instead of only the last one.

Memory safety
-------------
The slot table lives in EWRAM.  Its address is not a guess: it was measured
against four archived mGBA save states (the scenario-50 input checkpoint plus
the archived baseline/candidate outputs), whose EWRAM images agree on a common
zero region at 0x0203F173..0x0203FD60.  The table is placed 4-byte aligned
inside that region and never overlaps the legacy scratch at 0x0203FD60.

The probe only records what the game itself selected; it never claims a
message ID was reached that the run did not actually touch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

try:
    from tools.build_chapter_script_probe import BASE_SHA1
    from tools.build_save_state_runtime_probe import encode_thumb_bl
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from build_chapter_script_probe import BASE_SHA1
    from build_save_state_runtime_probe import encode_thumb_bl


ROM_BASE = 0x08000000
HOOK = 0x080985E2
EXPECTED_HOOK = bytes.fromhex("327c0221")  # ldrb r2,[r6,#0x10]; movs r1,#2
STUB = 0x0809E900
STUB_OFFSET = STUB - ROM_BASE
SCRATCH = 0x0203FD60
SCRATCH_SIZE = 36
MAGIC = 0x52504D42  # "BMPR"
MESSAGE_TABLE = 0x5A2034
MESSAGE_TABLE_BUS = ROM_BASE + MESSAGE_TABLE
MESSAGE_COUNT = 79

# Slot table placement: 4-byte aligned inside the measured common-zero EWRAM
# region 0x0203F173..0x0203FD60 (3053 B).  79 slots * 16 B = 1264 B, so the
# table spans 0x0203F174..0x0203F664 and never reaches the legacy scratch.
SLOT_TABLE = 0x0203F174
SLOT_SIZE = 16
SLOT_COUNT = MESSAGE_COUNT
SLOT_TABLE_SIZE = SLOT_SIZE * SLOT_COUNT
SAFE_REGION_START = 0x0203F173
SAFE_REGION_END = 0x0203FD60

# Stub region must be zero in the base ROM; the measured zero run at STUB is
# 570 bytes, which is the growth budget for the appended slot code.
STUB_ZERO_RUN = 570


# --- Thumb encoders (ARMv4T) ---------------------------------------------
def _t_ldr_literal(rt: int, imm8: int) -> int:
    """LDR rt, [PC, #imm8*4]."""
    if not 0 <= imm8 <= 255:
        raise ValueError(f"literal offset out of range: {imm8}")
    return 0x4800 | (rt << 8) | imm8


def _t_ldr_imm(rt: int, rn: int, imm5: int) -> int:
    """LDR rt, [rn, #imm5*4]."""
    if not 0 <= imm5 <= 31:
        raise ValueError(f"load offset out of range: {imm5}")
    return 0x6800 | (imm5 << 6) | (rn << 3) | rt


def _t_str_imm(rt: int, rn: int, imm5: int) -> int:
    """STR rt, [rn, #imm5*4]."""
    if not 0 <= imm5 <= 31:
        raise ValueError(f"store offset out of range: {imm5}")
    return 0x6000 | (imm5 << 6) | (rn << 3) | rt


def _t_ldrb(rt: int, rn: int, imm5: int) -> int:
    """LDRB rt, [rn, #imm5]."""
    if not 0 <= imm5 <= 31:
        raise ValueError(f"byte offset out of range: {imm5}")
    return 0x7800 | (imm5 << 6) | (rn << 3) | rt


def _t_lsls_imm(rd: int, rm: int, imm5: int) -> int:
    """LSLS rd, rm, #imm5."""
    if not 0 <= imm5 <= 31:
        raise ValueError(f"shift amount out of range: {imm5}")
    return 0x0000 | (imm5 << 6) | (rm << 3) | rd


def _t_adds_imm(rd: int, imm8: int) -> int:
    """ADDS rd, #imm8."""
    if not 0 <= imm8 <= 255:
        raise ValueError(f"immediate out of range: {imm8}")
    return 0x3000 | (rd << 8) | imm8


def _t_adds_reg(rd: int, rn: int, rm: int) -> int:
    """ADDS rd, rn, rm."""
    return 0x1800 | (rm << 6) | (rn << 3) | rd


class _Stub:
    """Thumb stub builder with an auto-resolved literal pool.

    Literal loads are emitted as placeholders and patched once the pool offset
    is known, so PC-relative offsets are derived instead of hand-written.
    """

    def __init__(self) -> None:
        self._code: list[int] = []
        self._literals: list[int] = []
        self._literal_slots: list[tuple[int, int]] = []

    def emit(self, *halfwords: int) -> None:
        for halfword in halfwords:
            self._code.append(halfword)

    def emit_literal_load(self, rt: int) -> None:
        """Emit LDR rt, [PC, #imm] and remember which literal it targets."""
        self._code.append(_t_ldr_literal(rt, 0))  # offset patched in assemble()
        self._literal_slots.append((len(self._code) - 1, len(self._literals)))
        self._literals.append(0)  # placeholder value

    def set_literal(self, index: int, value: int) -> None:
        self._literals[index] = value

    def assemble(self) -> bytes:
        pool_offset = len(self._code) * 2
        for instruction_index, literal_index in self._literal_slots:
            target = pool_offset + 4 * literal_index
            pc = (instruction_index * 2 + 4) & ~3
            if target < pc or (target - pc) % 4:
                raise ValueError("literal pool is not reachable")
            instruction = self._code[instruction_index]
            rt = (instruction >> 8) & 0x7
            self._code[instruction_index] = _t_ldr_literal(rt, (target - pc) // 4)
        body = struct.pack(f"<{len(self._code)}H", *self._code)
        pool = struct.pack(f"<{len(self._literals)}I", *self._literals)
        return body + pool


def _legacy_stub(slot_code: bool) -> bytes:
    """Rebuild the legacy stub, optionally appending the per-ID slot code.

    The legacy halfword sequence is copied verbatim from
    ``tools/build_battle_message_runtime_probe.py``; only the three literal
    offsets change, because the literal pool moves when the slot code is
    appended.  The literal offsets are resolved by :class:`_Stub`, never typed
    by hand.
    """
    stub = _Stub()
    # push {r0-r3}
    stub.emit(0xB40F)
    # r2 = SCRATCH
    stub.emit_literal_load(2)
    stub.set_literal(0, SCRATCH)
    # r1 = MAGIC
    stub.emit_literal_load(1)
    stub.set_literal(1, MAGIC)
    # [scratch+0] = MAGIC
    stub.emit(_t_str_imm(1, 2, 0))
    # r1 = [scratch+4]; r1 += 1; [scratch+4] = r1   (global hit counter)
    stub.emit(_t_ldr_imm(1, 2, 1), _t_adds_imm(1, 1), _t_str_imm(1, 2, 1))
    # r1 = r6[0] (message id); [scratch+8] = r1
    stub.emit(_t_ldrb(1, 6, 0), _t_str_imm(1, 2, 2))
    # r1 = r6[0] again; r1 = r1 << 2; r3 = MESSAGE_TABLE_BUS; r1 += r3
    stub.emit(_t_ldrb(1, 6, 0), _t_lsls_imm(1, 1, 2))
    stub.emit_literal_load(3)
    stub.set_literal(2, MESSAGE_TABLE_BUS)
    stub.emit(_t_adds_reg(1, 1, 3), _t_str_imm(1, 2, 3))
    # [scratch+16] = r0 (selected pointer)
    stub.emit(_t_str_imm(0, 2, 4))
    # [scratch+20..36] = 16 target bytes taken from the selected pointer
    stub.emit(
        _t_ldr_imm(1, 0, 0), _t_str_imm(1, 2, 5),
        _t_ldr_imm(1, 0, 1), _t_str_imm(1, 2, 6),
        _t_ldr_imm(1, 0, 2), _t_str_imm(1, 2, 7),
        _t_ldr_imm(1, 0, 3), _t_str_imm(1, 2, 8),
    )
    if slot_code:
        # slot = SLOT_TABLE + (id << 4)
        stub.emit(_t_ldrb(1, 6, 0), _t_lsls_imm(1, 1, 4))
        stub.emit_literal_load(3)
        stub.set_literal(3, SLOT_TABLE)
        stub.emit(_t_adds_reg(1, 1, 3))
        # slot.hit_count += 1
        stub.emit(_t_ldr_imm(2, 1, 0), _t_adds_imm(2, 1), _t_str_imm(2, 1, 0))
        # slot.selected_pointer = r0
        stub.emit(_t_str_imm(0, 1, 1))
        # slot.target_prefix = 8 bytes taken from the selected pointer
        stub.emit(
            _t_ldr_imm(2, 0, 0), _t_str_imm(2, 1, 2),
            _t_ldr_imm(2, 0, 1), _t_str_imm(2, 1, 3),
        )
    # pop {r0-r3}; re-execute the replaced originals; bx lr; align
    stub.emit(0xBC0F, 0x7C32, 0x2102, 0x4770, 0x46C0)
    return stub.assemble()


def legacy_stub_bytes() -> bytes:
    """The legacy stub without slot code, for the equivalence self-check."""
    return _legacy_stub(slot_code=False)


def slot_stub_bytes() -> bytes:
    """The multi-slot stub."""
    return _legacy_stub(slot_code=True)


def build_probe(
    base: bytes,
    *,
    message_id: int | None = None,
    replacement_id: int | None = None,
) -> bytes:
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    if (message_id is None) != (replacement_id is None):
        raise ValueError("message ID and replacement ID must be provided together")
    for label, value in (("message ID", message_id), ("replacement ID", replacement_id)):
        if value is not None and not 0 <= value < MESSAGE_COUNT:
            raise ValueError(f"{label} must be in 0..{MESSAGE_COUNT - 1}")

    hook_offset = HOOK - ROM_BASE
    if base[hook_offset:hook_offset + 4] != EXPECTED_HOOK:
        raise ValueError("battle-message selector bytes do not match")
    stub = slot_stub_bytes()
    if len(stub) > STUB_ZERO_RUN:
        raise ValueError("battle-message probe stub exceeds the measured zero run")
    if any(base[STUB_OFFSET:STUB_OFFSET + len(stub)]):
        raise ValueError("battle-message probe stub region is not zero-filled")

    rom = bytearray(base)
    rom[hook_offset:hook_offset + 4] = encode_thumb_bl(HOOK, STUB)
    rom[STUB_OFFSET:STUB_OFFSET + len(stub)] = stub
    if message_id is not None and replacement_id is not None:
        target = MESSAGE_TABLE + message_id * 4
        source = MESSAGE_TABLE + replacement_id * 4
        rom[target:target + 4] = base[source:source + 4]
    return bytes(rom)


def read_slots(state: Any) -> list[dict[str, Any]]:
    """Read the slot table out of an mGBA save state.

    ``state`` is anything exposing ``read_memory(address, size)``; the repo's
    ``tools.inspect_mgba_savestate.load_gba_state`` result satisfies that.
    """
    raw = state.read_memory(SLOT_TABLE, SLOT_TABLE_SIZE)
    if len(raw) != SLOT_TABLE_SIZE:
        raise ValueError("slot table read is short")
    slots: list[dict[str, Any]] = []
    for index in range(SLOT_COUNT):
        chunk = raw[index * SLOT_SIZE:(index + 1) * SLOT_SIZE]
        hit_count, pointer = struct.unpack_from("<II", chunk, 0)
        target_prefix = chunk[8:16]
        if hit_count == 0 and pointer == 0 and target_prefix == b"\x00" * 8:
            continue
        slots.append(
            {
                "message_id": index,
                "hit_count": hit_count,
                "selected_pointer": pointer,
                "target_prefix_hex": target_prefix.hex(),
            }
        )
    return slots


def read_legacy_scratch(state: Any) -> dict[str, Any]:
    """Read the legacy 36-byte scratch so slot data can be cross-checked."""
    raw = state.read_memory(SCRATCH, SCRATCH_SIZE)
    magic, hit_count, message_id, entry_address, pointer = struct.unpack_from(
        "<5I", raw, 0
    )
    return {
        "magic": magic,
        "hit_count": hit_count,
        "message_id": message_id,
        "entry_address": entry_address,
        "selected_pointer": pointer,
        "target_prefix_hex": raw[20:36].hex(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--message-id", type=int)
    parser.add_argument("--replacement-id", type=int)
    args = parser.parse_args()
    output = build_probe(
        args.base_rom.read_bytes(),
        message_id=args.message_id,
        replacement_id=args.replacement_id,
    )
    args.output_rom.write_bytes(output)
    print(
        json.dumps(
            {
                "output_rom": str(args.output_rom),
                "sha256": hashlib.sha256(output).hexdigest(),
                "slot_table": SLOT_TABLE,
                "slot_size": SLOT_SIZE,
                "slot_count": SLOT_COUNT,
                "stub_bytes": len(slot_stub_bytes()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
