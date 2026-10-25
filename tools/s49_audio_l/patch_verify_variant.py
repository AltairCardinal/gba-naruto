#!/usr/bin/env python3
"""Bisect helper: patch the isolated verification tree's audio runtime.

Stream L.  The verification ROM (HEAD + only stream L's audio changes) crashes
during the input walk, while the earlier build of the same tree without the
sound handle in the trace did not.  This script applies a named variant to the
verification tree so the cause can be isolated with one incremental build per
variant.

Variants
--------
``no-handle``  : the sound handle is no longer read out of the Maxmod mixer
                 (the trace keeps the 8 byte entry, the director restructure and
                 the battle BGM override stay).
``no-sfx``     : play_battle_sound() goes back to the semantic no-op, the
                 handle stays in the trace for the music path only.
``full``       : restore the current product code (no patch).
"""
from __future__ import annotations

import pathlib
import sys

TREE = pathlib.Path(
    r"D:\Github\gba-naruto\build\remake-audio-verify\butano-sequel")
RUNTIME = TREE / "game" / "include" / "konoha" / "battle_audio_runtime.h"

CURRENT = """inline void play_battle_sound(int cue)
{
    const int handle = play_battle_sound_item(cue);
    battle_audio_trace_record(
            battle_audio_trace_kind::sound,
            cue,
            handle);
}"""

NO_HANDLE = """inline void play_battle_sound(int cue)
{
    battle_audio_trace_record(
            battle_audio_trace_kind::sound,
            cue);
    play_battle_sound_item(cue);
}"""

NO_SFX = """inline void play_battle_sound(int cue)
{
    battle_audio_trace_record(
            battle_audio_trace_kind::sound,
            cue);
}"""


def main() -> int:
    variant = sys.argv[1] if len(sys.argv) > 1 else "full"
    text = RUNTIME.read_text(encoding="utf-8")
    bodies = {"full": CURRENT, "no-handle": NO_HANDLE, "no-sfx": NO_SFX}
    target = bodies[variant]
    if target in text:
        print(f"variant {variant!r} already applied")
        return 0
    applied = None
    for name, body in bodies.items():
        if body in text:
            applied = name
            break
    if applied is None:
        raise SystemExit("ERR no known play_battle_sound() body was found")
    RUNTIME.write_text(text.replace(bodies[applied], target),
                       encoding="utf-8", newline="\n")
    print(f"applied variant {variant!r} to {RUNTIME} (was {applied!r})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
