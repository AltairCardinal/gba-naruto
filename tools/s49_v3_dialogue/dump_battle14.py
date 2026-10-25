"""Scratch: dump battle 14's selector instructions and evaluate them.

Answers one question: how many script cases (and therefore how many dialogue
pages) does the battle entry of scenario 49 chain together?

The reverse line's inventory gives one definition per battle; the definition
lists the selector instructions, which append one selector per case.  The
remake plays every case the selector list holds, one after the other.

Usage:
    python tools/s49_v3_dialogue/dump_battle14.py [battle_id]
"""
from __future__ import annotations

import pathlib
import re
import sys

HEADER = pathlib.Path(
    "D:/Shell/Github/gba-naruto-butano/butano-sequel/game/include/konoha/"
    "generated_battle_presentation_content.h")

OPCODE_NAMES = {
    0x00: "end",
    0x01: "render_text",
    0x02: "show_portrait",
    0x03: "hide_portrait",
    0x04: "update_portrait",
    0x07: "goto",
    0x08: "select_speaker",
    0x0F: "wait_frames",
    0x11: "set_portrait_focus",
    0x12: "init_portrait_pair",
    0x17: "animate_portrait",
    0x20: "render_param_text",
    0x32: "selector_dispatch",
    0x33: "append_selector",
    0x34: "cond_round_side",
    0x35: "cond_relationship",
    0x36: "cond_unit_query",
    0x37: "set_script_flag",
    0x38: "cond_script_flag",
    0x39: "cond_battle_state",
}


def parse_definitions(text: str):
    body = text.split("battle_presentation_definitions = {{", 1)[1].split("}};", 1)[0]
    out = []
    for match in re.finditer(r"battle_presentation_definition\{ ([^}]*)\}", body):
        parts = [part.strip() for part in match.group(1).split(",")]
        out.append({
            "battle_id": int(parts[0]),
            "selector_root": int(parts[1]),
            "selector_offset": int(parts[2]),
            "selector_count": int(parts[3]),
            "case_offset": int(parts[4]),
            "case_count": int(parts[5]),
        })
    return out


def parse_instructions(text: str):
    body = text.split("battle_presentation_selector_instructions = {{", 1)[1].split("}};", 1)[0]
    out = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("battle_presentation_selector_instruction{"):
            continue
        source = line[len("battle_presentation_selector_instruction{"):].rstrip("}").strip()
        opcode = int(re.search(r"static_cast<battle_presentation_script_opcode>\(0x([0-9A-Fa-f]+)\)",
                               source).group(1), 16)
        operands = re.search(r"\{\{ ([^}]*)\}\}", source).group(1)
        operand_values = [int(value.strip()) for value in operands.split(",")]
        tail = source.split("}},")[-1].replace("}", "")
        numbers = [int(value.strip()) for value in tail.split(",") if value.strip()]
        out.append({
            "source": source.split(",")[0].strip(),
            "opcode": opcode,
            "operands": operand_values,
            "fallthrough": numbers[0] if numbers else 0xFFFF,
            "branch": numbers[1] if len(numbers) > 1 else 0xFFFF,
            "dispatch_offset": numbers[2] if len(numbers) > 2 else 0,
            "dispatch_count": numbers[3] if len(numbers) > 3 else 0,
        })
    return out


def parse_cases(text: str):
    body = text.split("battle_presentation_cases = {{", 1)[1].split("}};", 1)[0]
    out = []
    for match in re.finditer(r"battle_presentation_case\{ ([^}]*)\}", body):
        parts = [part.strip() for part in match.group(1).split(",")]
        out.append({
            "source": parts[0],
            "command_offset": int(parts[1]),
            "command_count": int(parts[2]),
            "selector": int(parts[3]),
        })
    return out


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
            "source": source.split(",")[0].strip(),
            "opcode": opcode,
            "operands": operand_values,
            "text_offset": numbers[0] if numbers else 0,
            "text_length": numbers[1] if len(numbers) > 1 else 0,
        })
    return out


def parse_dispatch_cases(text: str):
    body = text.split("battle_presentation_selector_dispatch_cases = {{", 1)[1].split("}};", 1)[0]
    out = []
    for match in re.finditer(r"battle_presentation_selector_dispatch_case\{ ([^}]*)\}", body):
        parts = [part.strip() for part in match.group(1).split(",")]
        out.append({"selector": int(parts[0]), "instruction_index": int(parts[1])})
    return out


def parse_text(text: str):
    body = text.split("battle_presentation_text = {{", 1)[1].split("}};", 1)[0]
    values = [int(value, 16) for value in re.findall(r"0x([0-9A-Fa-f]{2})", body)]
    return bytes(values)


def decode(raw: bytes) -> str:
    try:
        return raw.decode("shift_jis")
    except Exception:
        return raw.decode("latin-1")


def evaluate(instructions, dispatch_cases, definition, round_index, side,
              battle_state, dispatch_selector):
    """Mirror of battle_presentation_selector::evaluate."""
    selectors = []
    index = definition["selector_root"]
    for _ in range(4096):
        if index >= len(instructions):
            return selectors, "out of range"
        instruction = instructions[index]
        opcode = instruction["opcode"]
        if opcode == 0x00:
            return selectors, "end"
        if opcode == 0x07:
            index = instruction["branch"]
            continue
        if opcode == 0x33:
            selectors.append(instruction["operands"][0])
            index = instruction["fallthrough"]
            continue
        if opcode == 0x32:
            index = instruction["fallthrough"]
            for candidate in dispatch_cases:
                if candidate["selector"] == dispatch_selector:
                    index = candidate["instruction_index"]
                    break
            continue
        if opcode == 0x34:
            condition = (side == instruction["operands"][2] and
                         _compare(round_index, instruction["operands"][0],
                                  instruction["operands"][1]))
            index = instruction["branch"] if condition else instruction["fallthrough"]
            continue
        if opcode == 0x36:
            # unit query: character id active on side
            condition = False
            index = instruction["branch"] if condition else instruction["fallthrough"]
            continue
        if opcode == 0x37:
            index = instruction["fallthrough"]
            continue
        if opcode == 0x38:
            index = instruction["fallthrough"]
            continue
        if opcode == 0x39:
            condition = battle_state == instruction["operands"][0]
            index = instruction["branch"] if condition else instruction["fallthrough"]
            continue
        if opcode in (0x01, 0x02, 0x08):
            index = instruction["fallthrough"]
            continue
        return selectors, f"unsupported opcode {opcode:#04x}"
    return selectors, "execution limit"


def _compare(left, comparison, right):
    if comparison == 0:
        return left == right
    if comparison == 1:
        return left != right
    if comparison == 2:
        return left > right
    if comparison == 3:
        return left >= right
    if comparison == 4:
        return left < right
    if comparison == 5:
        return left <= right
    return False


def main() -> int:
    battle_id = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    text = HEADER.read_text(encoding="utf-8")
    definitions = parse_definitions(text)
    instructions = parse_instructions(text)
    cases = parse_cases(text)
    commands = parse_commands(text)
    dispatch_cases = parse_dispatch_cases(text)
    script_text = parse_text(text)
    definition = next(item for item in definitions if item["battle_id"] == battle_id)

    print(f"battle {battle_id}: selector_root={definition['selector_root']} "
          f"selector_count={definition['selector_count']} "
          f"case_offset={definition['case_offset']} "
          f"case_count={definition['case_count']}")

    print("\n-- selector instructions --")
    for index in range(definition["selector_offset"],
                       definition["selector_offset"] +
                       definition["selector_count"]):
        instruction = instructions[index]
        name = OPCODE_NAMES.get(instruction["opcode"],
                                 f"op{instruction['opcode']:#04x}")
        print(f"  [{index:>4}] {instruction['source']:>12} {name:<18} "
              f"ops={instruction['operands']} "
              f"ft={instruction['fallthrough']} br={instruction['branch']}")

    selectors, reason = evaluate(instructions, dispatch_cases, definition,
                                  0, 0, 0, 0)
    print(f"\n-- selector list (round 0, side 0) -> {selectors} ({reason})")

    print("\n-- cases of this battle --")
    for case in cases[definition["case_offset"]:
                      definition["case_offset"] + definition["case_count"]]:
        pages = 0
        for command in commands[case["command_offset"]:
                                case["command_offset"] + case["command_count"]]:
            if command["opcode"] in (0x01, 0x20):
                pages += 1
        print(f"  case sel={case['selector']} "
              f"cmd={case['command_offset']}.."
              f"{case['command_offset'] + case['command_count']} "
              f"src={case['source']} text_pages={pages}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
