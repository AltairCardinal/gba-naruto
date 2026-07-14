"""Deterministic Thumb interpreter for the published-call observer stub subset."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MachineState:
    registers: dict[str, int]
    memory: dict[int, int]
    writes: list[tuple[int, int, int]] = field(default_factory=list)
    branch_target: int | None = None

    def read_u16(self, address: int) -> int:
        return self.memory.get(address, 0) | (self.memory.get(address + 1, 0) << 8)

    def read_u32(self, address: int) -> int:
        return self.read_u16(address) | (self.read_u16(address + 2) << 16)

    def write_u16(self, address: int, value: int) -> None:
        value &= 0xFFFF
        self.memory[address] = value & 0xFF
        self.memory[address + 1] = value >> 8
        self.writes.append((address, 2, value))

    def write_u32(self, address: int, value: int) -> None:
        value &= 0xFFFFFFFF
        for index in range(4):
            self.memory[address + index] = (value >> (index * 8)) & 0xFF
        self.writes.append((address, 4, value))


def execute_stub(
    stub: bytes,
    *,
    registers: dict[str, int] | None = None,
    memory: dict[int, int] | None = None,
) -> MachineState:
    """Execute exactly the instructions emitted by ``build_observer_stub``."""
    register_values = {f"r{index}": 0 for index in range(13)}
    register_values.update({"sp": 0x03007F00, "lr": 0x08000005})
    if registers:
        register_values.update(registers)
    state = MachineState(register_values, {})
    for address, value in (memory or {}).items():
        for index in range(4):
            state.memory[address + index] = (value >> (index * 8)) & 0xFF

    pc = 0
    zero = False
    for _ in range(128):
        instruction = int.from_bytes(stub[pc:pc + 2], "little")
        next_pc = pc + 2

        if instruction & 0xFE00 == 0xB400:  # push low registers
            mask = instruction & 0xFF
            pushed = [index for index in range(8) if mask & (1 << index)]
            new_sp = state.registers["sp"] - 4 * len(pushed)
            for slot, index in enumerate(pushed):
                state.write_u32(new_sp + 4 * slot, state.registers[f"r{index}"])
            state.registers["sp"] = new_sp
        elif instruction & 0xFE00 == 0xBC00:  # pop low registers
            mask = instruction & 0xFF
            popped = [index for index in range(8) if mask & (1 << index)]
            for slot, index in enumerate(popped):
                state.registers[f"r{index}"] = state.read_u32(
                    state.registers["sp"] + 4 * slot
                )
            state.registers["sp"] += 4 * len(popped)
        elif instruction & 0xF800 == 0x4800:  # ldr Rd, [pc, #imm]
            target = ((pc + 4) & ~3) + ((instruction & 0xFF) * 4)
            register = (instruction >> 8) & 7
            state.registers[f"r{register}"] = int.from_bytes(
                stub[target:target + 4], "little"
            )
        elif instruction & 0xF800 == 0x6800:  # ldr Rd, [Rb, #imm]
            offset = ((instruction >> 6) & 0x1F) * 4
            base = (instruction >> 3) & 7
            destination = instruction & 7
            state.registers[f"r{destination}"] = state.read_u32(
                state.registers[f"r{base}"] + offset
            )
        elif instruction & 0xF800 == 0x6000:  # str Rd, [Rb, #imm]
            offset = ((instruction >> 6) & 0x1F) * 4
            base = (instruction >> 3) & 7
            source = instruction & 7
            state.write_u32(
                state.registers[f"r{base}"] + offset,
                state.registers[f"r{source}"],
            )
        elif instruction & 0xF800 == 0x8000:  # strh Rd, [Rb, #imm]
            offset = ((instruction >> 6) & 0x1F) * 2
            base = (instruction >> 3) & 7
            source = instruction & 7
            state.write_u16(
                state.registers[f"r{base}"] + offset,
                state.registers[f"r{source}"],
            )
        elif instruction & 0xF800 == 0x9800:  # ldr Rd, [sp, #imm]
            destination = (instruction >> 8) & 7
            offset = (instruction & 0xFF) * 4
            state.registers[f"r{destination}"] = state.read_u32(
                state.registers["sp"] + offset
            )
        elif instruction & 0xFFC0 == 0x4280:  # cmp low registers
            left = instruction & 7
            right = (instruction >> 3) & 7
            zero = state.registers[f"r{left}"] == state.registers[f"r{right}"]
        elif instruction & 0xF000 == 0xD000:  # conditional branch
            condition = (instruction >> 8) & 0xF
            take = (condition == 0 and zero) or (condition == 1 and not zero)
            if condition not in (0, 1):
                raise AssertionError(f"unsupported Thumb condition: {condition}")
            if take:
                immediate = instruction & 0xFF
                if immediate & 0x80:
                    immediate -= 0x100
                next_pc = pc + 4 + immediate * 2
        elif instruction & 0xF800 == 0xE000:  # unconditional branch
            immediate = instruction & 0x7FF
            if immediate & 0x400:
                immediate -= 0x800
            next_pc = pc + 4 + immediate * 2
        elif instruction & 0xF800 == 0x2000:  # movs Rd, #imm
            destination = (instruction >> 8) & 7
            state.registers[f"r{destination}"] = instruction & 0xFF
        elif instruction & 0xF800 == 0x3000:  # adds Rd, #imm
            destination = (instruction >> 8) & 7
            state.registers[f"r{destination}"] = (
                state.registers[f"r{destination}"] + (instruction & 0xFF)
            ) & 0xFFFFFFFF
        elif instruction == 0x46A4:  # mov r12, r4
            state.registers["r12"] = state.registers["r4"]
        elif instruction == 0x4760:  # bx r12
            state.branch_target = state.registers["r12"]
            return state
        else:
            raise AssertionError(f"unsupported Thumb opcode 0x{instruction:04X} at +0x{pc:X}")
        pc = next_pc
    raise AssertionError("observer stub did not tail-branch within 128 instructions")
