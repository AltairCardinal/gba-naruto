"""Scratch: parse the remake's generated battle presentation content.

Prints the commands of one battle id's cases, decoding the Shift-JIS text of
every rendered line and flagging the wait frames opcode.
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
    for match in re.finditer(
            r"battle_presentation_definition\{ ([^}]*)\}", body):
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
        operand_values = [int(value.strip())
                          for value in operands.split(",")]
        tail = source.split("}},")[-1].replace("}", "")
        numbers = [int(value.strip())
                   for value in tail.split(",") if value.strip()]
        out.append({
            "source": source.split(",")[0].strip(),
            "opcode": opcode,
            "operands": operand_values,
            "text_offset": numbers[0] if numbers else 0,
            "text_length": numbers[1] if len(numbers) > 1 else 0,
        })
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


def main() -> int:
    battle_id = int(sys.argv[1])
    text = HEADER.read_text(encoding="utf-8")
    definitions = parse_definitions(text)
    cases = parse_cases(text)
    commands = parse_commands(text)
    script_text = parse_text(text)
    definition = next(item for item in definitions
                      if item["battle_id"] == battle_id)
    print(f"battle {battle_id}: case_offset={definition['case_offset']} "
          f"case_count={definition['case_count']}")
    for case in cases[definition["case_offset"]:
                      definition["case_offset"] + definition["case_count"]]:
        print(f"  case sel={case['selector']} "
              f"cmd={case['command_offset']}..{case['command_offset'] + case['command_count']}"
              f" src={case['source']}")
        for command in commands[case["command_offset"]:
                                case["command_offset"] + case["command_count"]]:
            name = OPCODE_NAMES.get(command["opcode"],
                                     f"op{command['opcode']:#04x}")
            extra = ""
            if command["opcode"] in (0x01, 0x20):
                raw = script_text[command["text_offset"]:
                                  command["text_offset"] + command["text_length"]]
                extra = f" text={decode(raw)!r}"
            if command["opcode"] == 0x0F:
                extra = f" WAIT={command['operands'][0]} frames"
            print(f"    {command['source']:>12} {name:<18} "
                  f"ops={command['operands']} off={command['text_offset']} "
                  f"len={command['text_length']}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
