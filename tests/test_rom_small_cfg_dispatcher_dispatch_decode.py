import hashlib
import struct
import unittest
from pathlib import Path

from tools import rom_small_cfg_dispatch_decode as dispatch_decode


ROM_BASE = 0x08000000
PACKET = Path(__file__).resolve().parent
REAL_ROM = Path(__file__).resolve().parents[1] / "rom/base.gba"
REAL_ROOT = 0x07DCB8


def _put16(buf, offset, value):
    buf[offset : offset + 2] = struct.pack("<H", value)


def _put32(buf, offset, value):
    buf[offset : offset + 4] = struct.pack("<I", value)


def _u16(buf, offset):
    return int.from_bytes(buf[offset : offset + 2], "little")


def _encode_bhi(source, target):
    displacement = target - (source + 4)
    if displacement % 2 or not -256 <= displacement <= 254:
        raise ValueError("synthetic BHI displacement is not Thumb-1 encodable")
    return 0xD800 | ((displacement >> 1) & 0xFF)


def _literal_imm(source, target):
    base = (source + 4) & ~3
    delta = target - base
    if delta % 4 or not 0 <= delta // 4 <= 0xFF:
        raise ValueError("synthetic literal is not encodable")
    return delta // 4


def _synthetic_fixture(
    *,
    root=0x40,
    state_literal=0x80,
    table_literal=0x84,
    table_start=0x120,
    default_target=0xA0,
    state_base=0x03001234,
    state_pointer_field=5,
    command_field=3,
    subtract=5,
    maximum=2,
    targets=(0x180, 0x182, 0x184),
    size=0x220,
):
    rom = bytearray(size)
    prefix = [
        0xB5F0,
        0x4800 | _literal_imm(root + 2, state_literal),
        0x3000 | state_pointer_field,
        0x6800,
        0x7800 | (command_field << 6),
        0x3800 | subtract,
        0x2800 | maximum,
        _encode_bhi(root + 14, default_target),
        0x0080,
        0x4900 | _literal_imm(root + 18, table_literal),
        0x1840,
        0x6800,
        0x4687,
    ]
    for index, opcode in enumerate(prefix):
        _put16(rom, root + index * 2, opcode)
    _put32(rom, state_literal, state_base)
    _put32(rom, table_literal, ROM_BASE + table_start)
    for slot, target in enumerate(targets):
        _put32(rom, table_start + slot * 4, ROM_BASE + target)
    return rom


class DispatchDecodeTests(unittest.TestCase):
    def test_relocated_synthetic_case_has_unsigned_u8_domain(self):
        rom = _synthetic_fixture()
        payload = dispatch_decode.decode_dispatch(bytes(rom), 0x40)

        self.assertEqual(
            set(payload),
            {
                "root",
                "prefix_range",
                "instructions",
                "literal_bindings",
                "state_base_value",
                "state_pointer_field_offset",
                "command_field_offset",
                "subtract",
                "maximum_index",
                "default_target",
                "table_range",
                "table_sha256",
                "table_entries",
                "input_domain",
            },
        )
        self.assertEqual(payload["root"], 0x40)
        self.assertEqual(payload["prefix_range"], [0x40, 0x5A])
        self.assertEqual(payload["state_base_value"], 0x03001234)
        self.assertEqual(payload["state_pointer_field_offset"], 5)
        self.assertEqual(payload["command_field_offset"], 3)
        self.assertEqual(payload["subtract"], 5)
        self.assertEqual(payload["maximum_index"], 2)
        self.assertEqual(payload["default_target"], 0xA0)
        self.assertEqual(payload["table_range"], [0x120, 0x12C])
        self.assertEqual(
            payload["table_sha256"],
            hashlib.sha256(bytes(rom[0x120:0x12C])).hexdigest(),
        )
        self.assertEqual(
            [entry["target"] for entry in payload["table_entries"]],
            [0x180, 0x182, 0x184],
        )
        self.assertEqual(
            payload["input_domain"][0],
            {
                "command": 0,
                "index_u32": (0 - 5) & 0xFFFFFFFF,
                "slot_index": None,
                "target": 0xA0,
            },
        )
        self.assertEqual(payload["input_domain"][5]["slot_index"], 0)
        self.assertEqual(payload["input_domain"][7]["slot_index"], 2)
        self.assertIsNone(payload["input_domain"][8]["slot_index"])

    def test_real_rom_matches_frozen_dispatch_oracle(self):
        rom = REAL_ROM.read_bytes()
        payload = dispatch_decode.decode_dispatch(rom, REAL_ROOT)

        self.assertEqual(payload["root"], REAL_ROOT)
        self.assertEqual(payload["prefix_range"], [REAL_ROOT, REAL_ROOT + 26])
        self.assertEqual(payload["state_base_value"], 0x02026BE0)
        self.assertEqual(payload["state_pointer_field_offset"], 0xC4)
        self.assertEqual(payload["command_field_offset"], 4)
        self.assertEqual(payload["subtract"], 36)
        self.assertEqual(payload["maximum_index"], 19)
        self.assertEqual(payload["default_target"], 0x07DD42)
        self.assertEqual(payload["table_range"], [0x07DCDC, 0x07DD2C])
        self.assertEqual(len(payload["instructions"]), 13)
        self.assertEqual(len(payload["table_entries"]), 20)
        self.assertEqual(
            [entry["target"] for entry in payload["table_entries"]],
            [
                0x07DD2C,
                0x07DD2C,
                0x07DD42,
                0x07DD34,
                0x07DD34,
                0x07DD42,
                0x07DD42,
                0x07DD42,
                0x07DD42,
                0x07DD42,
                0x07DD42,
                0x07DD42,
                0x07DD42,
                0x07DD42,
                0x07DD42,
                0x07DD42,
                0x07DD42,
                0x07DD42,
                0x07DD42,
                0x07DD3C,
            ],
        )
        self.assertEqual(
            payload["literal_bindings"],
            [
                [0x07DCBA, 0x07DCD4, "e06b0202"],
                [0x07DCCA, 0x07DCD8, "dcdc0708"],
            ],
        )
        self.assertEqual(payload["input_domain"][36]["slot_index"], 0)
        self.assertEqual(payload["input_domain"][55]["slot_index"], 19)
        self.assertIsNone(payload["input_domain"][56]["slot_index"])
        self.assertEqual(payload["input_domain"][56]["target"], 0x07DD42)

    def test_rejects_every_frozen_negative_shape(self):
        cases = []

        def mutate(name, fn):
            rom = _synthetic_fixture()
            fn(rom)
            cases.append((name, bytes(rom), 0x40))

        mutate("bls", lambda rom: _put16(rom, 0x4E, 0xD900 | (_u16(rom, 0x4E) & 0xFF)))
        mutate("wrong-flag-register", lambda rom: _put16(rom, 0x4C, 0x2902))
        mutate("wrong-scale", lambda rom: _put16(rom, 0x50, 0x00C0))
        mutate("wrong-loadb-register", lambda rom: _put16(rom, 0x48, 0x7901))
        mutate("wrong-pc-write-mode", lambda rom: _put16(rom, 0x58, 0x4700))
        mutate("subtract-plus-maximum-wrap", lambda rom: (_put16(rom, 0x4A, 0x38FA), _put16(rom, 0x4C, 0x280A)))
        mutate("default-enters-prefix", lambda rom: _put16(rom, 0x4E, _encode_bhi(0x4E, 0x40)))
        mutate("table-pointer-outside-rom", lambda rom: _put32(rom, 0x84, 0xFFFFFFFF))
        mutate("odd-target", lambda rom: _put32(rom, 0x120, ROM_BASE | 0x181))
        mutate("target-enters-prefix", lambda rom: _put32(rom, 0x120, ROM_BASE | 0x40))
        mutate("target-enters-literal", lambda rom: _put32(rom, 0x120, ROM_BASE | 0x80))
        mutate("target-enters-table", lambda rom: _put32(rom, 0x120, ROM_BASE | 0x120))
        mutate("duplicate-literals", lambda rom: _put16(rom, 0x52, 0x4900 | _literal_imm(0x52, 0x80)))
        mutate("overlapping-table", lambda rom: _put32(rom, 0x84, ROM_BASE | 0x80))

        for name, rom, root in cases:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    dispatch_decode.decode_dispatch(rom, root)

        with self.assertRaises(ValueError):
            dispatch_decode.decode_dispatch(bytes(_synthetic_fixture())[:0x59], 0x40)
        with self.assertRaises(ValueError):
            dispatch_decode.decode_dispatch(bytes(_synthetic_fixture()), 0x41)


if __name__ == "__main__":
    unittest.main()
