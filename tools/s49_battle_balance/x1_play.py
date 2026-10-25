#!/usr/bin/env python3
"""X1 (wave 12): the closed-loop battle driver for the remake ROM.

Why a closed loop
-----------------
W1 (wave 11) replayed U2's **open loop** key script on the remake ROM and the
battle never finished: the script's fixed frame budgets do not line up with
the ROM's own phase sequence (every presentation and every animation has to
be waited out on the machine), so the keys land one phase off and the game
loops between the command menu and the preparation scene.

This driver reads the ROM's own battle telemetry
(``konoha_battle_runtime_telemetry``) and presses a key **only when the ROM
is in the phase that key belongs to**.  The route that is replayed is U2's
offline route, which was computed with the *same* controller the ROM runs, so
the two phase sequences agree step by step.

Settlement chain
----------------
When the battle is won the driver walks the settlement chain by pressing A
in every settlement phase (``outcome`` -> ``result`` -> ``level_up`` ->
``training`` -> ``post_battle_dialogue`` -> ``task_menu`` -> ``complete``) and
takes a PNG of every page it sees.

Usage::

    python tools/s49_battle_balance/x1_play.py \\
        --rom build/s49-wictory-capture/....gba \\
        --route build/s49-battle-balance/u2/routeX.json \\
        --out build/x1/run-current
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import w1_boot  # noqa: E402
import w1_probe as probe_module  # noqa: E402
import x1_telemetry  # noqa: E402

KEYS = dict(w1_boot.KEYS)

# The settlement chain's phases (battle_scene_phase ordinals).
PHASE_OUTCOME = 13
PHASE_RESULT = 14
PHASE_LEVEL_UP = 15
PHASE_TRAINING = 19
PHASE_POST_BATTLE_DIALOGUE = 24
PHASE_TASK_MENU = 25
PHASE_COMPLETE = 16
PHASE_SCRIPT_BLOCKED = 18

SETTLEMENT_PHASES = (
    PHASE_OUTCOME, PHASE_RESULT, PHASE_LEVEL_UP, PHASE_TRAINING,
    PHASE_POST_BATTLE_DIALOGUE, PHASE_TASK_MENU)


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class Driver:
    """Drives the remake ROM's battle with the ROM's own telemetry as oracle."""

    def __init__(self, probe: probe_module.Probe,
                 telemetry: x1_telemetry.Telemetry,
                 out: pathlib.Path,
                 verbose: bool = True) -> None:
        self.probe = probe
        self.telemetry = telemetry
        self.out = out
        self.shots = out / "shots"
        self.shots.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
        self.frames = 0
        self.keys = 0
        self.trace: list[dict[str, object]] = []
        self.captures: list[dict[str, object]] = []
        self.errors: list[str] = []
        self.last_script_fingerprint: tuple[int, ...] | None = None
        self.shot_steps = False

    # ------------------------------------------------------------- plumbing
    def log(self, text: str) -> None:
        if self.verbose:
            print(text, flush=True)

    def state(self) -> dict[str, int]:
        return self.telemetry.read()

    def wait(self, frames: int) -> None:
        if frames > 0:
            self.probe.run(f"frames {frames} 0x00000000")
            self.frames += frames

    def press(self, key: str, hold: int = 4) -> None:
        if key not in KEYS:
            raise KeyError(key)
        self.probe.run(f"frames {hold} 0x{KEYS[key]:08X}")
        self.frames += hold
        self.keys += 1

    def press_until(self, key: str, predicate, max_frames: int = 900,
                   poll: int = 4) -> bool:
        """Hold a key down until the ROM accepts it.

        The dialogue's typewriter **swallows** a key press: the runtime only
        accepts the confirmation once the typewriter has revealed the whole
        line, so a press that arrives too early is dropped (that is why the
        open loop script lost a page).  Holding the key down until the ROM
        reacts removes the race: the key stays down until the confirmation
        lands.
        """
        if key not in KEYS:
            raise KeyError(key)
        self.probe.run(f"key 0x{KEYS[key]:08X}")
        accepted = False
        deadline = self.frames + max_frames
        try:
            while self.frames < deadline:
                self.probe.run(f"run {poll}")
                self.frames += poll
                if predicate(self.state()):
                    accepted = True
                    break
        finally:
            self.probe.run("keyoff")
        self.keys += 1
        return accepted

    def shot(self, tag: str) -> pathlib.Path:
        index = len(self.captures) + 1
        path = self.shots / f"shot-{index:03d}-{tag}.png"
        self.probe.run(f"shot {path}")
        return path

    def wait_idle(self, timeout: int = 6000, poll: int = 8) -> bool:
        """Wait until no presentation and no map movement is running."""
        deadline = self.frames + timeout
        while self.frames < deadline:
            values = self.state()
            if (values["presentation_busy"] == 0 and
                    values["map_movement_active"] == 0):
                return True
            self.wait(poll)
        return False

    # ------------------------------------------------------------- the gate
    @staticmethod
    def script_fingerprint(values: dict[str, int]) -> tuple[int, ...]:
        return (values["script_phase"], values["script_command_index"],
                values["script_text_address"], values["script_selector"],
                values["script_portrait_0_id"], values["script_portrait_1_id"])

    def wait_phase(self, want: int, timeout: int = 4000,
                   poll: int = 8) -> dict[str, int] | None:
        """Wait until the ROM is in ``want`` and is idle enough to take input."""
        deadline = self.frames + timeout
        while self.frames < deadline:
            values = self.state()
            if (values["phase"] == want and
                    values["presentation_busy"] == 0 and
                    values["map_movement_active"] == 0):
                return values
            self.wait(poll)
        return None

    def wait_script_advance(self, timeout: int = 3000,
                            poll: int = 8) -> dict[str, int] | None:
        """Wait until the dialogue has moved on to the next script block."""
        deadline = self.frames + timeout
        while self.frames < deadline:
            values = self.state()
            if values["phase"] != PHASE_SCRIPT_BLOCKED:
                return values
            if (self.last_script_fingerprint is not None and
                    self.script_fingerprint(values) !=
                    self.last_script_fingerprint):
                return values
            self.wait(poll)
        return None

    # --------------------------------------------------------- the battle
    def play_route(self, route: dict[str, object],
                   max_steps: int = 0) -> bool:
        steps = route["steps"]
        if max_steps:
            steps = steps[:max_steps]
        for index, step in enumerate(steps):
            key = step["key"]
            phase = int(step.get("phase", -1))
            if key == "":
                # A pure wait.  The ROM drives the enemy turn and the
                # script's wait_frames blocks on its own, so the driver only
                # has to let the presentation finish.
                if phase < 0:
                    self.wait_idle(timeout=6000)
                else:
                    deadline = self.frames + 1500
                    while self.frames < deadline:
                        if self.state()["phase"] != phase:
                            break
                        self.wait(8)
                continue
            if phase >= 0:
                values = self.wait_phase(phase)
                if values is None:
                    now = self.state()
                    self.errors.append(
                        f"step {index} ({key}, phase {phase}): the ROM never "
                        f"reached phase {phase}; it is in "
                        f"{x1_telemetry.phase_name(now['phase'])} "
                        f"(round {now['round']})")
                    self.trace.append({"step": index, "key": key,
                                       "want_phase": phase, "result": "timeout",
                                       "now_phase": now["phase"],
                                       "now_round": now["round"],
                                       "frame": self.frames})
                    return False
            if phase == PHASE_SCRIPT_BLOCKED:
                # The dialogue swallows a press that arrives while the
                # typewriter is still running, so the key is held down until
                # the script block changes.
                before = self.script_fingerprint(self.state())
                accepted = self.press_until(
                    key,
                    lambda values: (
                        values["phase"] != PHASE_SCRIPT_BLOCKED or
                        self.script_fingerprint(values) != before),
                    max_frames=1500)
                if not accepted:
                    self.errors.append(
                        f"step {index} ({key}, phase {phase}): the dialogue "
                        f"never advanced")
                    return False
            else:
                self.press(key, int(step.get("hold", 4)))
            self.wait(min(int(step["settle"]), 300))
            values = self.state()
            if self.shot_steps:
                self.shot(f"step{index:03d}-{key or 'wait'}")
            self.trace.append({
                "step": index, "key": key, "want_phase": phase,
                "phase": values["phase"], "round": values["round"],
                "command": values["selected_command"],
                "action_index": values["action_index"],
                "action_count": values["action_count"],
                "action_id": values["selected_action_id"],
                "action_kind": values["selected_action_kind"],
                "selected_unit": values["selected_unit"],
                "char_id": values["selected_character_id"],
                "cursor": (values["cursor_x"], values["cursor_y"]),
                "frame": self.frames,
            })
            if values["phase"] in SETTLEMENT_PHASES:
                self.log(f"  step {index}: reached settlement phase "
                         f"{x1_telemetry.phase_name(values['phase'])}")
                return True
        return False

    # -------------------------------------------------- the settlement chain
    def play_settlement(self, settle_frames: int = 90,
                        max_pages: int = 40) -> dict[str, object]:
        """Walk the settlement chain and photograph every page."""
        result: dict[str, object] = {"pages": [], "final_phase": None}
        for _ in range(max_pages):
            values = self.state()
            phase = values["phase"]
            if phase not in SETTLEMENT_PHASES:
                result["final_phase"] = phase
                break
            self.wait(settle_frames)
            values = self.state()
            phase = values["phase"]
            if phase not in SETTLEMENT_PHASES:
                result["final_phase"] = phase
                break
            path = self.shot(x1_telemetry.phase_name(phase))
            self.captures.append({
                "file": path.name,
                "phase": phase,
                "phase_name": x1_telemetry.phase_name(phase),
                "round": values["round"],
                "outcome": values["condition_outcome"],
                "result_participant_count": values["result_participant_count"],
            })
            result["pages"].append(self.captures[-1])
            self.log(f"  settlement page: {x1_telemetry.phase_name(phase)} "
                     f"-> {path.name}")
            self.press("A", 4)
            self.wait(settle_frames)
        values = self.state()
        result["final_phase"] = values["phase"]
        result["outcome"] = values["condition_outcome"]
        result["round"] = values["round"]
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--route", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path,
                        default=HERE.parents[1] / "build" / "mgba-probe-x1" /
                        "mgba-probe.exe")
    parser.add_argument("--boot", action="store_true",
                        help="run the closed-loop boot before the route")
    parser.add_argument("--state", type=pathlib.Path, default=None,
                        help="load this savestate instead of booting")
    parser.add_argument("--max-frames", type=int, default=600000)
    parser.add_argument("--settle-frames", type=int, default=90)
    parser.add_argument("--timeout-minutes", type=float, default=90.0)
    parser.add_argument("--max-steps", type=int, default=0,
                        help="only replay this many route steps (testing)")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--shot-steps", action="store_true",
                        help="take a PNG after every route step")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    route = json.loads(args.route.read_text(encoding="utf-8"))
    started = time.time()
    receipt: dict[str, object] = {
        "schema": "konoha.s49-x1-closed-loop-play.v1",
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "route": str(args.route),
        "route_sha256": sha256_file(args.route),
        "out": str(args.out),
    }
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        driver = Driver(probe, x1_telemetry.Telemetry(probe), args.out,
                        verbose=not args.quiet)
        driver.shot_steps = args.shot_steps
        if args.state:
            probe.load(args.state)
            driver.frames = 0
        elif args.boot:
            boot = w1_boot.Boot(probe, args.out / "boot")
            receipt["boot"] = boot.run()
        else:
            probe.run("frames 120 0x00000000")
            driver.frames = 120
        driver.log(f"telemetry at 0x{driver.telemetry.locate(verbose=True):08X}")
        reached = driver.play_route(route, args.max_steps)
        settlement: dict[str, object] = {}
        if reached:
            settlement = driver.play_settlement(args.settle_frames)
        else:
            values = driver.state()
            settlement = {"final_phase": values["phase"],
                          "outcome": values["condition_outcome"],
                          "round": values["round"], "pages": []}
        receipt.update({
            "reached_settlement": reached,
            "frames_run": driver.frames,
            "keys_pressed": driver.keys,
            "errors": driver.errors,
            "settlement": settlement,
            "captures": driver.captures,
        })
        stderr = probe.stderr
        (args.out / "stderr.txt").write_text("\n".join(stderr) + "\n",
                                              encoding="utf-8", newline="\n")
        receipt["stderr_tail"] = stderr[-40:]
        (args.out / "trace.json").write_text(
            json.dumps(driver.trace, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n")
    receipt["wall_seconds"] = round(time.time() - started, 1)
    (args.out / "play.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({key: value for key, value in receipt.items()
                      if key not in ("trace", "captures")},
                     ensure_ascii=False, indent=1))
    return 0 if reached_ok(receipt) else 1


def reached_ok(receipt: dict[str, object]) -> bool:
    settlement = receipt.get("settlement") or {}
    return (receipt.get("reached_settlement") is True and
            settlement.get("final_phase") == PHASE_COMPLETE)


if __name__ == "__main__":
    raise SystemExit(main())
