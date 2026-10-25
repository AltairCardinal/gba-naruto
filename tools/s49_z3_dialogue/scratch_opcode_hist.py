"""Scratch: opcode histogram over every battle presentation command."""
from __future__ import annotations

import collections
import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location(
    "sd", pathlib.Path(__file__).with_name("scratch_script_dump.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

text = module.HEADER.read_text(encoding="utf-8")
commands = module.parse_commands(text)
histogram = collections.Counter(command["opcode"] for command in commands)
for opcode, count in sorted(histogram.items()):
    name = module.OPCODE_NAMES.get(opcode, "?")
    print(f"opcode {opcode:#04x} {name:<20} count={count}")
waits = [command for command in commands if command["opcode"] == 0x0F]
print(f"wait_frames commands: {len(waits)}")
for wait in waits[:30]:
    print("  ", wait)
