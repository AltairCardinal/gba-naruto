"""Scratch: check the glyph coverage of the remake's dialogue font.

Answers one question: are all the codes of a dialogue line present in the
remake's glyph table (``battle_presentation_glyph_codes``)?

The runtime draws a line glyph by glyph and bails out with an empty sprite
list as soon as one code is missing, so a missing code hides the whole line.

Usage:
    python tools/s49_v3_dialogue/check_glyph_coverage.py [battle_id ...]
"""
from __future__ import annotations

import pathlib
import re
import sys

HEADER = pathlib.Path(
    "D:/Shell/Github/gba-naruto-butano/butano-sequel/game/include/konoha/"
    "generated_battle_presentation_content.h")
GLYPHS = pathlib.Path(
    "D:/Shell/Github/gba-naruto-butano/butano-sequel/game/include/konoha/"
    "generated_battle_presentation_glyph_content.h")


def parse_text(text: str) -> bytes:
    body = text.split("battle_presentation_text = {{", 1)[1].split("}};", 1)[0]
    values = [int(value, 16) for value in re.findall(r"0x([0-9A-Fa-f]{2})", body)]
    return bytes(values)


def parse_commands(text: str):
    body = text.split("battle_presentation_commands = {{", 1)[1].split("}};", 1)[0]
    out = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("battle_presentation_command{"):
            continue
        source = line[len("battle_presentation_command{"):].rstrip("}").strip()
        opcode = int(re.search(r"0x([0-9A-Fa-f]+)\)", source).group(1), 16)
        operands = re.search(r"\{\{ ([^}]*)\}\}", source).group(1)
        operand_values = [int(value.strip()) for value in operands.split(",")]
        tail = source.split("}},")[-1].replace("}", "")
        numbers = [int(value.strip()) for value in tail.split(",") if value.strip()]
        out.append({
            "opcode": opcode,
            "operands": operand_values,
            "text_offset": numbers[0] if numbers else 0,
            "text_length": numbers[1] if len(numbers) > 1 else 0,
        })
    return out


def parse_definitions(text: str):
    body = text.split("battle_presentation_definitions = {{", 1)[1].split("}};", 1)[0]
    out = []
    for match in re.finditer(r"battle_presentation_definition\{ ([^}]*)\}", body):
        parts = [part.strip() for part in match.group(1).split(",")]
        out.append({
            "battle_id": int(parts[0]),
            "case_offset": int(parts[4]),
            "case_count": int(parts[5]),
        })
    return out


def parse_cases(text: str):
    body = text.split("battle_presentation_cases = {{", 1)[1].split("}};", 1)[0]
    out = []
    for match in re.finditer(r"battle_presentation_case\{ ([^}]*)\}", body):
        parts = [part.strip() for part in match.group(1).split(",")]
        out.append({
            "command_offset": int(parts[1]),
            "command_count": int(parts[2]),
            "selector": int(parts[3]),
        })
    return out


def parse_glyph_codes() -> set:
    text = GLYPHS.read_text(encoding="utf-8")
    body = text.split("battle_presentation_glyph_codes = {{", 1)[1].split("}};", 1)[0]
    return {int(value, 16) for value in re.findall(r"0x([0-9A-Fa-f]{4})", body)}


def main() -> int:
    battle_ids = [int(value) for value in sys.argv[1:]] or [14]
    text = HEADER.read_text(encoding="utf-8")
    script_text = parse_text(text)
    commands = parse_commands(text)
    definitions = parse_definitions(text)
    cases = parse_cases(text)
    known = parse_glyph_codes()
    print(f"glyph table holds {len(known)} codes")
    for battle_id in battle_ids:
        definition = next(item for item in definitions
                          if item["battle_id"] == battle_id)
        print(f"\n== battle {battle_id} ==")
        for case in cases[definition["case_offset"]:
                          definition["case_offset"] + definition["case_count"]]:
            for command in commands[case["command_offset"]:
                                    case["command_offset"] + case["command_count"]]:
                if command["opcode"] not in (0x01, 0x20):
                    continue
                raw = script_text[command["text_offset"]:
                                  command["text_offset"] + command["text_length"]]
                missing = []
                index = 0
                while index < len(raw):
                    lead = raw[index]
                    if lead == 0x0A:
                        index += 1
                        continue
                    code = (lead << 8) | raw[index + 1]
                    if code not in known:
                        missing.append(code)
                    index += 2
                print(f"  sel={case['selector']} off={command['text_offset']} "
                      f"len={command['text_length']} missing={len(missing)} "
                      f"{[hex(code) for code in missing[:8]]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
