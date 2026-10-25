#!/usr/bin/env python3
"""Apply the wave 24 / G1 presentation-state edits to the lane copy.

UTF-8, LF, no BOM.  Each replacement is checked: the script refuses to
write when a pattern is missing or ambiguous.
"""

from __future__ import annotations

import pathlib
import sys

TARGET = pathlib.Path(
    r"D:\Github\gba-naruto\build\w20-e1\butano-sequel\game\src"
    r"\battle_runtime_scene.cpp")

EDITS = [
    # 1. the message window: the empty box must be visible during the
    #    cutscene's entry beat (the original's `step-12`).
    (
        """        bool presentation_busy,
        battle_presentation_message_window_runtime_renderer&
                renderer)
{
    renderer.update(
            state.phase ==
                            battle_scene_phase::
                                    script_blocked &&
                    ! presentation_busy &&
                    state.script.message_window_visible);
}""",
        """        bool presentation_busy,
        bool cutscene_entry,
        battle_presentation_message_window_runtime_renderer&
                renderer)
{
    // The original shows the **empty** dialogue box from the moment the
    // cutscene's scene is on the screen, that is before the first line of
    // the script has spoken (the original's `step-12` beat).  The script's
    // own `message_window_visible` only rises when the script reaches its
    // first text command, so the cutscene's entry beat would show no box at
    // all.
    renderer.update(
            state.phase ==
                            battle_scene_phase::
                                    script_blocked &&
            (state.script.message_window_visible ||
             (cutscene_entry && ! presentation_busy)));
}""",
    ),
    # 2. the first call site of the message window.
    (
        """    update_script_message_window(
            state,
            presentation.busy(),
            message_window_renderer);""",
        """    update_script_message_window(
            state,
            presentation.busy(),
            initial_cutscene_entry_background,
            message_window_renderer);""",
    ),
    # 3. the second call site of the message window.
    (
        """        update_script_message_window(
                state,
                presentation.busy(),
                message_window_renderer);""",
        """        update_script_message_window(
                state,
                presentation.busy(),
                cutscene_entry_background,
                message_window_renderer);""",
    ),
    # 4. the initial background request: the cutscene's entry background.
    (
        """    const bool initial_dialogue_background_requested =
            config.battle_id == 14 &&
            state.phase ==
                    battle_scene_phase::script_blocked &&
            state.script.selector == 1 &&
            ! presentation.busy();""",
        """    const bool initial_cutscene_entry_background =
            battle_cutscene_entry_background(state, config.battle_id);
    const bool initial_dialogue_background_requested =
            config.battle_id == 14 &&
            state.phase ==
                    battle_scene_phase::script_blocked &&
            (initial_cutscene_entry_background ||
             (state.script.selector == 1 && ! presentation.busy()));""",
    ),
    # 5. the initial background renderer call.
    (
        """    dialogue_background_renderer.update(
            initial_dialogue_background_requested,
            map);""",
        """    dialogue_background_renderer.update(
            initial_dialogue_background_requested,
            initial_cutscene_entry_background,
            map);""",
    ),
    # 6. the per frame background request.
    (
        """        const bool dialogue_background_requested =
                config.battle_id == 14 &&
                state.phase ==
                        battle_scene_phase::
                                script_blocked &&
                state.script.selector == 1 &&
                ! presentation.busy();""",
        """        const bool cutscene_entry_background =
                battle_cutscene_entry_background(state, config.battle_id);
        const bool dialogue_background_requested =
                config.battle_id == 14 &&
                state.phase ==
                        battle_scene_phase::
                                script_blocked &&
                (cutscene_entry_background ||
                 (state.script.selector == 1 && ! presentation.busy()));""",
    ),
    # 7. the per frame background renderer call.
    (
        """        dialogue_background_renderer.update(
                dialogue_background_requested,
                map);""",
        """        dialogue_background_renderer.update(
                dialogue_background_requested,
                cutscene_entry_background,
                map);""",
    ),
]


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    for index, (old, new) in enumerate(EDITS, start=1):
        count = text.count(old)
        if count != 1:
            print(f"ERR edit {index}: pattern found {count} times")
            return 1
        text = text.replace(old, new)
        print(f"ok edit {index}")
    with TARGET.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
