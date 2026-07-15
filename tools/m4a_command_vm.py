#!/usr/bin/env python3
"""Persistent per-track MP2K command-control VM for SoundMain scheduling."""

from __future__ import annotations

from collections import Counter
from typing import Callable


def _wait_ticks(name: str) -> int:
    return int(name[1:])


class MPlayTrackVM:
    """Execute one ROM track incrementally, exactly one MP2K tick at a time.

    The VM owns command pointer, WAIT, PATT and REPT control state. Consumers
    receive every interpreted command and retain musical/channel state without
    duplicating the decoded-command parser.
    """

    def __init__(self, start_offset: int, command_map: dict[int, dict]):
        self.pc = start_offset
        self.command_map = command_map
        self.wait = 0
        self.tick = 0
        self.running = True
        self.pattern_stack: list[int] = []
        self.repeat_state: dict[int, int] = {}
        self.command_counts: Counter[str] = Counter()

    def step_tick(
        self,
        *,
        on_gate_scan: Callable[[], None] | None = None,
        on_command: Callable[[dict], None] | None = None,
        on_lfo: Callable[[], None] | None = None,
        max_commands: int = 4096,
    ) -> None:
        if max_commands <= 0:
            raise ValueError("max_commands must be positive")
        if on_gate_scan:
            on_gate_scan()

        interpreted = 0
        while self.running and self.wait == 0:
            if interpreted >= max_commands:
                raise ValueError(
                    f"track control flow ran {max_commands} commands without WAIT"
                )
            command = self.command_map.get(self.pc)
            if command is None:
                raise ValueError(
                    f"execution target 0x{self.pc:X} is not a command boundary"
                )
            interpreted += 1
            name = command["name"]
            self.command_counts[name] += 1
            if on_command:
                on_command(command)
            next_pc = self.pc + command["size"]

            if name.startswith("W"):
                self.wait = _wait_ticks(name)
                self.pc = next_pc
                break
            if name == "FINE":
                self.running = False
                self.pc = next_pc
                break
            if name == "PATT":
                if len(self.pattern_stack) >= 16:
                    raise ValueError(f"pattern stack overflow at 0x{self.pc:X}")
                self.pattern_stack.append(next_pc)
                self.pc = command["target_offset"]
                continue
            if name == "PEND":
                if self.pattern_stack:
                    self.pc = self.pattern_stack.pop()
                    continue
                self.pc = next_pc
                continue
            if name == "GOTO":
                self.pc = command["target_offset"]
                continue
            if name == "REPT":
                remaining = self.repeat_state.setdefault(self.pc, command["count"])
                if remaining > 0:
                    self.repeat_state[self.pc] = remaining - 1
                    self.pc = command["target_offset"]
                    continue
                self.repeat_state.pop(self.pc, None)
                self.pc = next_pc
                continue

            self.pc = next_pc

        if self.wait:
            self.wait -= 1
        if on_lfo:
            on_lfo()
        self.tick += 1
