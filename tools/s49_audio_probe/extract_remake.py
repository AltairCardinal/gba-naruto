#!/usr/bin/env python3
"""Stream J / remake side: export the Maxmod audio-event sequence of the S49
battle, and the static cue table that drives it.

Two kinds of evidence are combined:

1. STATIC -- `battle_audio_director.h` is a pure constexpr table
   (event -> list of (kind, cue)); it is parsed out of the header so the
   table in the report is generated, not hand-copied.  `battle_audio_runtime.h`
   decides which of those cues actually reach the sound engine.  The dispatch
   call sites in the product code are located so that the events that can
   fire at all are known.

2. RUNTIME -- the built remake ROM is driven by the headless mGBA probe from
   power-on (Down, Down, A x 32) and the sound / DMA register block is dumped
   every frame, so the frames in which the remake's sound hardware is
   actually doing something are known.

Usage:
    python tools/s49_audio_probe/extract_remake.py --out build/s49-audio
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import psg_state  # noqa: E402
from probe_driver import (  # noqa: E402
    KEY_A, KEY_DOWN, Probe, framedump_command, keyseq_command,
    read_dump_series, sha256_file, write_json,
)

REPO = pathlib.Path(__file__).resolve().parents[2]

REMAKE_ROOT = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\butano-sequel")
DEFAULT_ROM = REMAKE_ROOT / "butano-sequel.gba"
DIRECTOR_HEADER = REMAKE_ROOT / "game" / "include" / "konoha" / "battle_audio_director.h"
RUNTIME_HEADER = REMAKE_ROOT / "game" / "include" / "konoha" / "battle_audio_runtime.h"
SOURCE_DIR = REMAKE_ROOT / "game" / "src"

ZERO_INPUT_FRAMES = 600
HOLD_FRAMES = 4
SETTLE_FRAMES = 90
A_ROUNDS = 32
TAIL_FRAMES = 300

CASE_RE = re.compile(
    r"case\s+battle_audio_event::\s*(\w+)\s*:(.*?)(?=case\s+battle_audio_event::|return\s*\{\s*\};)",
    re.S)
COMMAND_RE = re.compile(r"kind::play_(music|sound)\s*,\s*(\d+)")
ARM_RE = re.compile(r"_(single|pair)\s*\(")


def _arm_commands(text: str) -> list[dict]:
    """Commands inside one `_single(...)` / `_pair(...)` expression."""
    commands = [{"kind": kind, "cue": int(cue)}
                for kind, cue in COMMAND_RE.findall(text)]
    # a `_pair` contributes two commands; the regex already sees both.
    return commands


def _split_ternary(body: str) -> tuple[str, str]:
    """Split a case body into the special_combination true/false arms."""
    marker = body.find("special_combination")
    if marker < 0:
        return "", body
    question = body.find("?", marker)
    if question < 0:
        return "", body
    # find the ':' that separates the two arms: the first ':' at the same
    # nesting depth after the '?' that is not inside parentheses.
    depth = 0
    index = question + 1
    while index < len(body):
        char = body[index]
        if char in "({":
            depth += 1
        elif char in ")}":
            depth -= 1
        elif char == ":" and depth == 0:
            break
        index += 1
    return body[question + 1:index], body[index + 1:]


def parse_director_table(header: pathlib.Path) -> dict[str, dict]:
    """event -> {default: [...], special: [...]} from battle_audio_director.h.

    `special_combination` selects a second command list (the ninja-combination
    presentation); both arms are reported so the table is not lossy.
    """
    text = header.read_text(encoding="utf-8")
    table: dict[str, dict] = {}
    for match in CASE_RE.finditer(text):
        event = match.group(1)
        body = match.group(2)
        true_arm, false_arm = _split_ternary(body)
        default = _arm_commands(false_arm) if true_arm else _arm_commands(body)
        special = _arm_commands(true_arm) if true_arm else []
        table[event] = {"default": default, "special": special}
    return table


def parse_music_wiring(header: pathlib.Path) -> dict:
    """Which cue IDs reach bn::music_items / bn::sound_items."""
    text = header.read_text(encoding="utf-8")
    music = {int(cue): item for cue, item in re.findall(
        r"case\s+(\d+)\s*:\s*bn::music_items::(\w+)\.play\(\)", text)}
    sound_calls = re.findall(r"bn::sound_items::(\w+)\.play\(\)", text)
    music_body = re.search(
        r"inline\s+void\s+play_battle_music\s*\(.*?\n\}", text, re.S)
    sound_body = re.search(
        r"inline\s+void\s+play_battle_sound\s*\(.*?\n\}", text, re.S)
    sound_noop = bool(sound_body) and not sound_calls
    return {
        "music_cue_to_item": {str(k): v for k, v in sorted(music.items())},
        "sound_items_called": sorted(set(sound_calls)),
        "play_battle_sound_is_noop": sound_noop,
        "play_battle_sound_body": sound_body.group(0) if sound_body else "",
        "play_battle_music_body": music_body.group(0) if music_body else "",
    }


def find_dispatch_sites(source_dir: pathlib.Path) -> dict[str, list[str]]:
    """event -> ["file:line", ...] of dispatch_battle_audio call sites.

    The event name can be split across lines by the formatter
    (`battle_audio_event::\n    action_confirmed`), so the scan works on the
    whole file text and maps a match back to its line number.
    """
    sites: dict[str, list[str]] = {}
    pattern = re.compile(r"battle_audio_event::\s*(\w+)")
    for path in sorted(source_dir.rglob("*.cpp")):
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            sites.setdefault(match.group(1), []).append(f"{path.name}:{line}")
    return sites


def capture_remake(out_dir: pathlib.Path, rom: pathlib.Path) -> dict:
    psg_dir = out_dir / "remake-psg"
    psg_dir.mkdir(parents=True, exist_ok=True)
    with Probe(rom, cwd=psg_dir) as probe:
        probe.run(f"frames {ZERO_INPUT_FRAMES} 0x000")
        probe.run(keyseq_command(HOLD_FRAMES, SETTLE_FRAMES, 1,
                                  psg_state.PSG_BASE, psg_state.PSG_LENGTH,
                                  KEY_DOWN, "d"))
        probe.run(keyseq_command(HOLD_FRAMES, SETTLE_FRAMES, 1,
                                  psg_state.PSG_BASE, psg_state.PSG_LENGTH,
                                  KEY_DOWN, "e"))
        probe.run(keyseq_command(HOLD_FRAMES, SETTLE_FRAMES, A_ROUNDS,
                                  psg_state.PSG_BASE, psg_state.PSG_LENGTH,
                                  KEY_A, "a"))
        probe.run(framedump_command(TAIL_FRAMES, psg_state.PSG_BASE,
                                    psg_state.PSG_LENGTH, 0x000, "z"))
    series = (read_dump_series(psg_dir, "d") + read_dump_series(psg_dir, "e")
              + read_dump_series(psg_dir, "a") + read_dump_series(psg_dir, "z"))
    return {"psg": series}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(REPO / "build" / "s49-audio"))
    parser.add_argument("--rom", default=str(DEFAULT_ROM))
    parser.add_argument("--decode-only", action="store_true")
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out)
    rom = pathlib.Path(args.rom)
    if not rom.is_file():
        raise SystemExit(f"ERR remake ROM missing: {rom}")

    table = parse_director_table(DIRECTOR_HEADER)
    wiring = parse_music_wiring(RUNTIME_HEADER)
    sites = find_dispatch_sites(SOURCE_DIR)

    if args.decode_only:
        psg_dir = out_dir / "remake-psg"
        series = (read_dump_series(psg_dir, "d") + read_dump_series(psg_dir, "e")
                  + read_dump_series(psg_dir, "a") + read_dump_series(psg_dir, "z"))
    else:
        print(f"capturing remake ... rom={rom.name}")
        series = capture_remake(out_dir, rom)["psg"]
    print(f"  psg frames: {len(series)}")

    states = [psg_state.decode(buffer) for buffer in series]
    signatures = [psg_state.activity_signature(state) for state in states]
    audible = [psg_state.is_audible(state) for state in states]
    episodes = psg_state.episodes(signatures, audible)
    audible_frames = sum(1 for flag in audible if flag)

    print(f"  frames with the sound hardware enabled: {audible_frames}")
    print(f"  audible episodes: {len(episodes)}")
    for episode in episodes[:20]:
        print(f"    f{episode['start_frame']}..{episode['end_frame']} "
              f"({episode['frames']}f) nr51=0x{episode['signature']['nr51']:04X} "
              f"nr52=0x{episode['signature']['nr52']:04X} "
              f"psg_ch=0x{episode['signature']['nr51'] & 0xF:X}")

    write_json(out_dir / "remake_events.json", {
        "side": "remake",
        "rom": str(rom),
        "rom_sha256": sha256_file(rom),
        "director_header": str(DIRECTOR_HEADER),
        "director_table": table,
        "runtime_wiring": wiring,
        "dispatch_sites": sites,
        "walk": {
            "zero_input_frames": ZERO_INPUT_FRAMES,
            "keys": ["Down", "Down"] + ["A"] * A_ROUNDS,
            "hold_frames": HOLD_FRAMES,
            "settle_frames": SETTLE_FRAMES,
            "tail_frames": TAIL_FRAMES,
        },
        "frame_count": len(series),
        "audible_frame_count": audible_frames,
        "audible_episodes": episodes,
        "events": [
            {
                "frame": episode["start_frame"],
                "phase": "walk",
                "kind": "audio_active",
                "frames": episode["frames"],
                "signature": episode["signature"],
            }
            for episode in episodes
        ],
    })
    print(f"wrote {out_dir / 'remake_events.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
