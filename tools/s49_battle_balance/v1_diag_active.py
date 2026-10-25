#!/usr/bin/env python3
"""U4 (wave 17): does the in-range **active** attack hang, or is it slow?

Wave 16's V1 measured two symptoms of defect D4:

* the **ninja tool**, confirmed while a living enemy is inside its range,
  freezes the ROM (the scene frame stops advancing);
* a **plain attack**, confirmed in range, "kills the input" (the phase does
  not move and the keys stop working).

The driver only ever waited **30 frames** after the confirmation.  This tool
answers the question the driver actually needs answered: after confirming an
in-range plain attack, does the phase **ever** leave the action selection, or
does the scene really stop?

It plays the battle with the real driver (so the actor walks to a cell where
the plain attack is legal), then confirms the attack and **polls the ROM's
own telemetry** for thousands of frames, recording the phase, the scene frame
and the error codes at every poll.

Usage::

    python tools/s49_battle_balance/v1_diag_active.py \\
        --rom build/v1-u4/rom-pinned.gba --out build/v1-u4/diag-active
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import w1_boot  # noqa: E402
import w1_probe as probe_module  # noqa: E402
import x1_telemetry  # noqa: E402
import v1_battle  # noqa: E402
import v1_truth  # noqa: E402

REPO = HERE.parents[1]

PHASE_ACTION_SELECTION = 6


class Probe(v1_battle.Battle):
    """The driver with a long observation after the attack's confirmation."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.observation: dict | None = None

    def do_action(self) -> None:
        plan = self.plan or {}
        want = plan.get("chosen_attack")
        if want is None:
            # No attack is in reach yet: close the distance (the base driver).
            super().do_action()
            return
        values = self.state()
        count = max(1, values["action_count"])
        entry = self.walk_to_action(want, count)
        self.decisions.append({"do": "probe-action", "frame": self.frames,
                               "want": want, "chosen": entry,
                               "gap": plan.get("gap")})
        self.press("A", 4)
        polls = []
        left = False
        healthy = self.telemetry_window()
        for _ in range(self.observe_polls):
            self.wait(self.poll_frames)
            values = self.state()
            polls.append({
                "frame": self.frames,
                "phase": values["phase"],
                "phase_name": x1_telemetry.phase_name(values["phase"]),
                "scene_frame": values["scene_frame"],
                "action_error": values["selected_action_error"],
                "control_error": values["last_control_error"],
                "player_error": values["last_player_error"],
                "cursor": [values["cursor_x"], values["cursor_y"]],
            })
            if values["phase"] != PHASE_ACTION_SELECTION:
                left = True
                break
        broken = self.telemetry_window()
        self.wait(120)
        broken2 = self.telemetry_window()
        self.observation = {
            "want": want, "chosen": entry, "gap": plan.get("gap"),
            "polls": polls, "left_action_selection": left,
            "final_phase": values["phase"],
            "final_phase_name": x1_telemetry.phase_name(values["phase"]),
            "final_scene_frame": values["scene_frame"],
            "telemetry_before": healthy,
            "telemetry_after": broken,
            "telemetry_after_120f": broken2,
        }
        self.expect = "end"

    def telemetry_window(self) -> dict:
        """The telemetry struct's first words, as raw u32s.

        The struct starts with ``magic``, ``battle_id``, ``phase`` and
        ``round``; when the battle scene dies, the question is whether the
        corruption is a **contiguous** overwrite (a buffer overrun) or a
        single word.
        """
        address = self.telemetry.address
        if address is None:
            return {}
        blob = self.telemetry._dump(address, 32)
        words = [int.from_bytes(blob[index:index + 4], "little")
                 for index in range(0, len(blob), 4)]
        return {"address": address,
                "words": words,
                "labels": x1_telemetry.FIELDS[:len(words)]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path,
                        default=REPO / "build" / "mgba-probe-u4" /
                        "mgba-probe.exe")
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "v1-u4" / "diag-active")
    parser.add_argument("--truth", type=pathlib.Path,
                        default=REPO / "build" / "v1" / "battle-truth.json")
    parser.add_argument("--max-turns", type=int, default=12)
    parser.add_argument("--observe-polls", type=int, default=60)
    parser.add_argument("--poll-frames", type=int, default=50)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    truth = v1_truth.load(args.truth)
    record: dict[str, object] = {"rom": str(args.rom),
                                  "rom_sha256": v1_battle.y1_play.sha256_file(
                                      args.rom)}
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        boot = w1_boot.Boot(probe, args.out / "boot")
        boot.run()
        telemetry = x1_telemetry.Telemetry(probe)
        driver = Probe(probe, telemetry, args.out,
                       verbose=not args.quiet, truth=truth,
                       allow_tools=False)
        driver.observe_polls = args.observe_polls
        driver.poll_frames = args.poll_frames
        driver.play_battle(args.max_turns)
        record["observation"] = driver.observation
        record["decisions"] = driver.decisions
        record["roster"] = driver.roster_snapshot(driver.state())
    (args.out / "diag-active.json").write_text(
        json.dumps(record, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    observation = record["observation"]
    if observation:
        print(json.dumps({key: value for key, value in observation.items()
                          if key != "polls"}, indent=1, ensure_ascii=False))
        print("polls:")
        for poll in observation["polls"]:
            print("  ", json.dumps(poll, ensure_ascii=False))
    else:
        print("no attack was in range")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
