import hashlib
import importlib
import unittest
from pathlib import Path

from tools.thumb_branch import decode_thumb_bl, encode_thumb_bl
from tests.thumb_observer_machine import MachineState


ROOT = Path(__file__).resolve().parent.parent

try:
    probe_builder = importlib.import_module("tools.build_action_submit_runtime_probe")
except ModuleNotFoundError:
    probe_builder = None


def execute_stub(stub, *, registers=None, memory=None):
    """Execute the compact MOVEDONE wrapper and record every data read."""
    values = {f"r{index}": 0 for index in range(13)}
    values.update({"sp": 0x03007F00, "lr": 0x08000005})
    values.update(registers or {})
    state = MachineState(values, {})
    state.reads = []
    for address, value in (memory or {}).items():
        for index in range(4):
            state.memory[address + index] = (value >> (index * 8)) & 0xFF

    def read_u32(address):
        state.reads.append(address)
        return state.read_u16(address) | (state.read_u16(address + 2) << 16)

    pc = 0
    zero = carry = False
    for _ in range(128):
        instruction = int.from_bytes(stub[pc:pc + 2], "little")
        next_pc = pc + 2
        if instruction & 0xFE00 == 0xB400:
            mask = instruction & 0xFF
            pushed = [index for index in range(8) if mask & (1 << index)]
            new_sp = state.registers["sp"] - 4 * len(pushed)
            for slot, index in enumerate(pushed):
                state.write_u32(new_sp + 4 * slot, state.registers[f"r{index}"])
            state.registers["sp"] = new_sp
        elif instruction & 0xFE00 == 0xBC00:
            mask = instruction & 0xFF
            popped = [index for index in range(8) if mask & (1 << index)]
            for slot, index in enumerate(popped):
                state.registers[f"r{index}"] = read_u32(state.registers["sp"] + 4 * slot)
            state.registers["sp"] += 4 * len(popped)
        elif instruction & 0xF800 == 0x4800:
            target = ((pc + 4) & ~3) + ((instruction & 0xFF) * 4)
            register = (instruction >> 8) & 7
            state.registers[f"r{register}"] = int.from_bytes(stub[target:target + 4], "little")
        elif instruction & 0xF800 == 0x6800:
            offset = ((instruction >> 6) & 0x1F) * 4
            base = (instruction >> 3) & 7
            destination = instruction & 7
            state.registers[f"r{destination}"] = read_u32(state.registers[f"r{base}"] + offset)
        elif instruction & 0xF800 == 0x6000:
            offset = ((instruction >> 6) & 0x1F) * 4
            base = (instruction >> 3) & 7
            source = instruction & 7
            state.write_u32(state.registers[f"r{base}"] + offset,
                            state.registers[f"r{source}"])
        elif instruction & 0xF800 in (0xC000, 0xC800):
            load = instruction & 0x0800
            base = (instruction >> 8) & 7
            address = state.registers[f"r{base}"]
            for register in range(8):
                if instruction & (1 << register):
                    if load:
                        state.registers[f"r{register}"] = read_u32(address)
                    else:
                        state.write_u32(address, state.registers[f"r{register}"])
                    address += 4
            state.registers[f"r{base}"] = address
        elif instruction & 0xF800 == 0x0000:
            shift = (instruction >> 6) & 0x1F
            source = (instruction >> 3) & 7
            destination = instruction & 7
            state.registers[f"r{destination}"] = (
                state.registers[f"r{source}"] << shift) & 0xFFFFFFFF
        elif instruction & 0xF800 == 0x0800:
            shift = (instruction >> 6) & 0x1F
            source = (instruction >> 3) & 7
            destination = instruction & 7
            state.registers[f"r{destination}"] = state.registers[f"r{source}"] >> shift
        elif instruction & 0xFE00 == 0x1800:
            right = (instruction >> 6) & 7
            left = (instruction >> 3) & 7
            destination = instruction & 7
            state.registers[f"r{destination}"] = (
                state.registers[f"r{left}"] + state.registers[f"r{right}"]
            ) & 0xFFFFFFFF
        elif instruction & 0xFE00 == 0x1C00:
            immediate = (instruction >> 6) & 7
            source = (instruction >> 3) & 7
            destination = instruction & 7
            state.registers[f"r{destination}"] = (
                state.registers[f"r{source}"] + immediate
            ) & 0xFFFFFFFF
        elif instruction & 0xFFC0 == 0x4340:
            source = (instruction >> 3) & 7
            destination = instruction & 7
            state.registers[f"r{destination}"] = (
                state.registers[f"r{destination}"] * state.registers[f"r{source}"]
            ) & 0xFFFFFFFF
        elif instruction & 0xF800 == 0x2800:
            left = state.registers[f"r{(instruction >> 8) & 7}"]
            right = instruction & 0xFF
            zero = left == right
            carry = left >= right
        elif instruction & 0xFFC0 == 0x4280:
            left = state.registers[f"r{instruction & 7}"]
            right = state.registers[f"r{(instruction >> 3) & 7}"]
            zero = left == right
            carry = left >= right
        elif instruction & 0xF000 == 0xD000:
            condition = (instruction >> 8) & 0xF
            take = {0: zero, 1: not zero, 3: not carry, 8: carry and not zero}[condition]
            if take:
                immediate = instruction & 0xFF
                if immediate & 0x80:
                    immediate -= 0x100
                next_pc = pc + 4 + immediate * 2
        elif instruction & 0xF800 == 0x2000:
            state.registers[f"r{(instruction >> 8) & 7}"] = instruction & 0xFF
        elif instruction & 0xF800 == 0x3000:
            destination = (instruction >> 8) & 7
            state.registers[f"r{destination}"] = (
                state.registers[f"r{destination}"] + (instruction & 0xFF)
            ) & 0xFFFFFFFF
        elif instruction == 0x46A4:
            state.registers["r12"] = state.registers["r4"]
        elif instruction == 0x4760:
            state.branch_target = state.registers["r12"]
            return state
        else:
            raise AssertionError(f"unsupported Thumb opcode 0x{instruction:04X} at +0x{pc:X}")
        pc = next_pc
    raise AssertionError("observer stub did not tail-branch")


@unittest.skipIf(probe_builder is None, "action-submit probe builder not implemented")
class ActionSubmitRuntimeProbeTests(unittest.TestCase):
    def setUp(self):
        self.base = (ROOT / "rom/base.gba").read_bytes()
        self.probe = probe_builder.build_probe(self.base)

    def test_base_rom_and_both_checked_calls_are_exact(self):
        self.assertEqual(hashlib.sha1(self.base).hexdigest(), probe_builder.BASE_SHA1)
        for site in probe_builder.OBSERVER_SITES:
            hook_offset = site.hook - probe_builder.ROM_BASE
            self.assertEqual(
                self.base[hook_offset : hook_offset + 4],
                encode_thumb_bl(site.hook, site.original),
            )
            self.assertEqual(
                self.probe[hook_offset : hook_offset + 4],
                encode_thumb_bl(site.hook, site.stub),
            )
            first = int.from_bytes(self.probe[hook_offset : hook_offset + 2], "little")
            second = int.from_bytes(self.probe[hook_offset + 2 : hook_offset + 4], "little")
            self.assertEqual(decode_thumb_bl(site.hook, first, second), site.stub)

        self.assertEqual(
            [(site.hook, site.original) for site in probe_builder.OBSERVER_SITES],
            [
                (0x0807443C, 0x080722A8),
                (0x08074918, 0x080722A8),
            ],
        )
        self.assertEqual(
            [site.stub for site in probe_builder.OBSERVER_SITES],
            [0x0809E800, 0x0809E880],
        )

    def test_sites_have_independent_records_events_and_shared_sequence(self):
        first, second = probe_builder.OBSERVER_SITES
        self.assertNotEqual(first.stub, second.stub)
        self.assertNotEqual(first.scratch, second.scratch)
        self.assertNotEqual(first.magic, second.magic)
        self.assertNotEqual(first.event_code, second.event_code)
        self.assertEqual(probe_builder.EVENT_COUNTER % 4, 0)
        self.assertTrue(0x02000000 <= probe_builder.EVENT_COUNTER < 0x02040000)

        for site in probe_builder.OBSERVER_SITES:
            stub_offset = site.stub - probe_builder.ROM_BASE
            stub = self.probe[stub_offset : stub_offset + probe_builder.STUB_SIZE]
            for literal in (
                site.scratch,
                site.magic,
                site.hook,
                probe_builder.EVENT_COUNTER,
                probe_builder.CURRENT_OBJECT,
                probe_builder.UNIT_RECORD_BASE,
                site.original | 1,
            ):
                self.assertIn(literal.to_bytes(4, "little"), stub)
            self.assertIn((0x2000 | site.event_code).to_bytes(2, "little"), stub)

    def test_hook_record_captures_current_object_and_resolved_unit_before_original(self):
        site = probe_builder.OBSERVER_SITES[0]
        memory = {
            probe_builder.CURRENT_OBJECT: 0x01000001,
            probe_builder.CURRENT_OBJECT + 4: 0x02024294,
            0x02024294: 0x0D0E0101,
            0x02024294 + 0xC0: 0x00000100,
            0x02024294 + 0xC4: 0x04000A04,
            0x02024294 + 0xC8: 0x3322110A,
            0x02024294 + 0xCC: 0x77665544,
            probe_builder.EVENT_COUNTER: 8,
        }
        initial = {
            **{f"r{index}": 0x11110000 + index for index in range(8)},
            "sp": 0x03007E00,
            "lr": site.hook + 5,
        }
        state = execute_stub(
            self.probe[
                site.stub - probe_builder.ROM_BASE:
                site.stub - probe_builder.ROM_BASE + probe_builder.STUB_SIZE
            ],
            registers=initial,
            memory=memory,
        )

        fields = (
            "magic", "hit_count", "sequence", "event_code", "source_hook", "object_word",
            "object_record_pointer", "record_address", "record_word_00", "record_word_c0",
            "record_word_c4", "record_word_c8", "record_word_cc",
        )
        record = {
            field: state.read_u32(site.scratch + index * 4)
            for index, field in enumerate(fields)
        }
        self.assertEqual(
            record,
            {
                "magic": site.magic,
                "hit_count": 1,
                "sequence": 9,
                "event_code": site.event_code,
                "source_hook": site.hook,
                "object_word": 0x01000001,
                "object_record_pointer": 0x02024294,
                "record_address": 0x02024294,
                "record_word_00": 0x0D0E0101,
                "record_word_c0": 0x00000100,
                "record_word_c4": 0x04000A04,
                "record_word_c8": 0x3322110A,
                "record_word_cc": 0x77665544,
            },
        )
        for register in (*[f"r{index}" for index in range(8)], "sp", "lr"):
            self.assertEqual(state.registers[register], initial[register])
        self.assertEqual(state.branch_target, site.original | 1)

    def test_invalid_current_unit_identity_fails_closed_before_record_dereference(self):
        invalid_cases = (
            ("slot zero", 0x00000001, 0x020240C0),
            ("slot above unit table", 0x15000001, 0x02025824),
            ("null pointer", 0x01000001, 0x00000000),
            ("ROM pointer", 0x01000001, 0x08024294),
            ("EWRAM past end", 0x01000001, 0x02040000),
            ("unaligned EWRAM pointer", 0x01000001, 0x02024295),
            ("slot pointer mismatch", 0x02000001, 0x02024294),
        )
        for site in probe_builder.OBSERVER_SITES:
            initial = {
                **{f"r{index}": 0x11110000 + index for index in range(8)},
                "sp": 0x03007E00,
                "lr": site.hook + 5,
            }
            for label, object_word, pointer in invalid_cases:
                with self.subTest(site=site.name, label=label):
                    memory = {
                        site.scratch: site.magic,
                        site.scratch + 4: 7,
                        probe_builder.EVENT_COUNTER: 8,
                        probe_builder.CURRENT_OBJECT: object_word,
                        probe_builder.CURRENT_OBJECT + 4: pointer,
                        pointer: 0xDEADBEEF,
                        pointer + 0xC0: 0xDEADBEEF,
                    }
                    state = execute_stub(
                        self.probe[
                            site.stub - probe_builder.ROM_BASE:
                            site.stub - probe_builder.ROM_BASE + probe_builder.STUB_SIZE
                        ],
                        registers=initial,
                        memory=memory,
                    )
                    self.assertEqual(state.read_u32(site.scratch), 0)
                    self.assertEqual(state.read_u32(site.scratch + 4), 7)
                    self.assertEqual(state.read_u32(probe_builder.EVENT_COUNTER), 8)
                    unit_reads = {pointer, pointer + 0xC0, pointer + 0xC4,
                                  pointer + 0xC8, pointer + 0xCC}
                    self.assertTrue(unit_reads.isdisjoint(state.reads))
                    for register in (*[f"r{index}" for index in range(8)], "sp", "lr"):
                        self.assertEqual(state.registers[register], initial[register])
                    self.assertEqual(state.branch_target, site.original | 1)

    def test_patch_is_confined_to_two_calls_and_two_zero_caves(self):
        allowed = set()
        for site in probe_builder.OBSERVER_SITES:
            allowed.update(range(site.hook - probe_builder.ROM_BASE, site.hook - probe_builder.ROM_BASE + 4))
            allowed.update(range(site.stub - probe_builder.ROM_BASE, site.stub - probe_builder.ROM_BASE + probe_builder.STUB_SIZE))
        changed = {index for index, (before, after) in enumerate(zip(self.base, self.probe)) if before != after}
        self.assertTrue(changed)
        self.assertTrue(changed <= allowed)

    def test_wrong_call_and_occupied_cave_fail_closed(self):
        wrong_call = bytearray(self.base)
        wrong_call[probe_builder.OBSERVER_SITES[0].hook - probe_builder.ROM_BASE] ^= 1
        with self.assertRaisesRegex(ValueError, "call-site bytes do not match"):
            probe_builder.build_probe(bytes(wrong_call), verify_sha1=False)

        occupied = bytearray(self.base)
        occupied[probe_builder.OBSERVER_SITES[1].stub - probe_builder.ROM_BASE] = 1
        with self.assertRaisesRegex(ValueError, "stub region is not zero-filled"):
            probe_builder.build_probe(bytes(occupied), verify_sha1=False)


class ActionSubmitRuntimeProbePresenceTests(unittest.TestCase):
    def test_action_submit_probe_builder_exists(self):
        self.assertIsNotNone(probe_builder, "missing tools.build_action_submit_runtime_probe")


if __name__ == "__main__":
    unittest.main()
