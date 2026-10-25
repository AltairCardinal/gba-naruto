#!/usr/bin/env python3
"""Find the EWRAM field that tells the original battle which screen it shows.

Why this tool exists
--------------------
Streams K, M, W3 and X3 all failed to reach the original victory screen for
the same reason: the driver had to *classify the screen* in order to decide
what to press, and the classifier (menu box pixels + a "menu level" byte) was
either ambiguous or one step behind the game.

The reverse engineering line left a **labelled corpus** of original-ROM
savestates, each of which is one known battle screen:

    scenario-41-action-menu-0/-1      the five entry action menu
    scenario-41-first-turn-technique-menu   the jutsu list
    scenario-41-target-select         the target cursor
    scenario-41-attack-confirmation   the attack forecast
    scenario-41-defense-confirmation  the defence question
    scenario-41-end-confirmation      the end-of-action question
    scenario-41-player-turn           the player unit selection phase
    scenario-41-victory               the 「胜利」 screen
    scenario-41-result                the settlement (EXP / power / turns)
    scenario-41-level-up-1/-2         the level up screen
    scenario-41-postbattle            the post battle screen

A savestate holds the whole EWRAM, so the screen-discriminating field can be
found **offline**: no emulator, no probe, no frame lag.  For every byte offset
the tool reports whether the value is constant inside each label and different
between the labels -- those offsets are candidate screen discriminators.

Usage::

    python tools/s49_victory_capture/screen_fingerprint.py \
        --out build/s49-victory-capture/w4/fingerprint
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import s49_state  # noqa: E402

REPO = HERE.parents[1]
CHECKPOINTS = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints")

# label -> checkpoint file names
CORPUS = {
    "action_menu": ["scenario-41-action-menu-0", "scenario-41-action-menu-1"],
    "jutsu_list": ["scenario-41-first-turn-technique-menu"],
    "target_select": ["scenario-41-target-select"],
    "attack_confirm": ["scenario-41-attack-confirmation"],
    "defense_confirm": ["scenario-41-defense-confirmation"],
    "end_confirm": ["scenario-41-end-confirmation"],
    "player_turn": ["scenario-41-player-turn"],
    "victory": ["scenario-41-victory"],
    "result": ["scenario-41-result"],
    "level_up": ["scenario-41-level-up-1", "scenario-41-level-up-2"],
    "postbattle": ["scenario-41-postbattle"],
    "battle14_move": ["scenario-49-battle-14-turn4-two-kills"],
    "battle14_entry": ["scenario-49-battle-14-entry"],
    "battle14_postbattle": ["scenario-49-battle-14-postbattle-task-menu"],
}

# addresses the previous streams already used (checked against the corpus)
KNOWN = {
    "menu_level_02026A8C": 0x02026A8C,
    "menu_cursor_0200A8BA": 0x0200A8BA,
    "cursor_02026A78": 0x02026A78,
    "action_tail_0200A880": 0x0200A880,
    "side_0202680E": 0x0202680E,
    "selected_slot_02026A41": 0x02026A41,
    "current_unit_ptr_02026810": 0x02026810,
    "battle_control_02026804": 0x02026804,
    "battle_state_02022E30": 0x02022E30,
}


def ewram(state: s49_state.GbaState) -> bytes:
    return state.read_memory(0x02000000, 0x40000)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "s49-victory-capture" / "w4" / "fingerprint")
    parser.add_argument("--limit", type=int, default=120,
                        help="how many discriminator offsets to report")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)

    labels: dict[str, list[bytes]] = {}
    for label, names in CORPUS.items():
        blobs = []
        for name in names:
            path = CHECKPOINTS / f"{name}.ss9"
            if not path.exists():
                print(f"!! missing {path}", file=sys.stderr)
                continue
            blobs.append(ewram(s49_state.load_state(path)))
        if blobs:
            labels[label] = blobs

    label_names = sorted(labels)
    # offsets that are constant inside every label
    consistent: list[int] = []
    for offset in range(0x40000):
        values = {}
        ok = True
        for label in label_names:
            seen = {blob[offset] for blob in labels[label]}
            if len(seen) != 1:
                ok = False
                break
            values[label] = seen.pop()
        if ok:
            consistent.append(offset)

    # among those, the ones whose value differs between the labels
    discriminators = []
    for offset in consistent:
        values = {label: labels[label][0][offset] for label in label_names}
        if len(set(values.values())) >= 2:
            discriminators.append((offset, values))

    # rank: prefer offsets that separate many label pairs
    def rank(entry):
        offset, values = entry
        distinct = len(set(values.values()))
        return (-distinct, offset)

    discriminators.sort(key=rank)

    document = {
        "schema": "konoha.s49-screen-fingerprint.v1",
        "checkpoint_dir": str(CHECKPOINTS),
        "labels": {label: [f"{name}.ss9" for name in CORPUS[label]]
                   for label in label_names},
        "known_addresses": {name: f"0x{address:08X}" for name, address in KNOWN.items()},
        "known_values": {
            name: {label: labels[label][0][address - 0x02000000] for label in label_names}
            for name, address in KNOWN.items()
        },
        "consistent_offsets": len(consistent),
        "discriminator_count": len(discriminators),
        "discriminators": [
            {"address": f"0x{0x02000000 + offset:08X}",
             "offset": offset,
             "values": {label: values[label] for label in label_names}}
            for offset, values in discriminators[:args.limit]
        ],
    }
    path = args.out / "fingerprint.json"
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")

    print(f"labels: {label_names}")
    print(f"consistent offsets: {len(consistent)}  discriminators: {len(discriminators)}")
    for name, address in KNOWN.items():
        values = document["known_values"][name]
        print(f"  {name:32s} " + " ".join(f"{label}={values[label]}" for label in label_names))
    print("--- top discriminators ---")
    for entry in document["discriminators"][:25]:
        print(f"  {entry['address']}  " +
              " ".join(f"{label}={entry['values'][label]}" for label in label_names))
    print(f"written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
