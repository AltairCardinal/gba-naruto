#!/usr/bin/env python3
"""Z1 (wave 14): record the remake's settlement chain as a closed loop.

What this tool does
-------------------
The battle itself cannot be won on the current ROM -- the scene runs out of
OBJ palette colours at the round-2 dialogue (Butano's ``BPP8 palette create
failed. Colors count: 128``) and halts there, so the controller never reaches
``outcome`` by playing.  The settlement chain is therefore entered by
**poking the controller's state** (the phase byte and the outcome byte, both
read back and verified) and then walked **as a closed loop**:

    read the phase from the ROM's own telemetry -> decide -> press A

The chain is walked until the controller reaches ``complete``, so the number
of button presses is whatever the chain needs (the original's chain needed 8
presses, the remake's needs 16), not a hard coded count.

Every frame in the capture is a **real runtime frame**: the product code
renders it, the probe's Lua frame callback photographs it.  Nothing is drawn
by the tool.

Usage::

    python tools/s49_battle_balance/z1_settlement_chain.py \\
        --rom build/s49-package-y4-final/work/pinned-rom/measured.gba \\
        --out build/z1/chain-a
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

# The controller's phase byte and outcome byte, in the battle runtime scene's
# ``BN_DATA_EWRAM_BSS static battle_runtime_controller controller;``.
#
# The controller's base address comes from the ELF symbol table and the
# member offsets from the DWARF (``battle_scene_controller<12, 23, 32>``):
#
#   controller  0x0200C444
#   _phase      + 0x177FC  ->  0x02023C40
#   _outcome    + 0x17A24  ->  0x02023E68
#
# The probe parses a ``poke`` address as a **decimal** integer, so the
# addresses are written in base ten.
CONTROLLER_BASE = 0x0200C444
CONTROLLER_PHASE_OFFSET = 0x177FC
CONTROLLER_OUTCOME_OFFSET = 0x17A24
CONTROLLER_PHASE_ADDRESS = CONTROLLER_BASE + CONTROLLER_PHASE_OFFSET
CONTROLLER_OUTCOME_ADDRESS = CONTROLLER_BASE + CONTROLLER_OUTCOME_OFFSET

PHASE_OUTCOME = 13
PHASE_COMPLETE = 16
PHASE_TRAINING = 19
PHASE_POST_BATTLE_DIALOGUE = 24
OUTCOME_WIN = 1

# The settlement chain's phases (battle_scene_phase ordinals).
SETTLEMENT_PHASES = {
    13: "outcome",
    14: "result",
    15: "level_up",
    19: "training",
    24: "post_battle_dialogue",
    25: "task_menu",
}

KEY_A = 0x001


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# The EWRAM .sbss window the battle runtime scene's statics live in
# (``battle_runtime_scene.o`` occupies 0x0200ab20..0x02025ee8 of the link
# map).  The controller's phase byte is looked up inside it.
EWRAM_SCAN_START = 0x0200A000
EWRAM_SCAN_END = 0x0202E700
EWRAM_CHUNK = 0x8000


def locate_phase_byte(probe: probe_module.Probe,
                      telemetry: x1_telemetry.Telemetry,
                      current_phase: int,
                      probe_value: int = PHASE_OUTCOME,
                      log=print) -> int:
    """Find the controller's ``_phase`` byte in EWRAM and prove it.

    The controller is a ``BN_DATA_EWRAM_BSS static`` in the battle runtime
    scene, so its address moves with every build; the link map gives the
    *object's* window but not the individual static's address.  The byte is
    therefore **found by its effect**: every byte in the window that currently
    holds the phase is poked with ``probe_value`` and the ROM's own telemetry
    is read back.  The byte the telemetry follows is the controller's phase.
    """
    candidates: list[int] = []
    for base in range(EWRAM_SCAN_START, EWRAM_SCAN_END, EWRAM_CHUNK):
        blob = telemetry._dump(base, min(EWRAM_CHUNK, EWRAM_SCAN_END - base))
        candidates.extend(base + offset for offset, value in enumerate(blob)
                          if value == current_phase)
    log(f"  {len(candidates)} bytes in the window hold {current_phase}")
    for address in candidates:
        probe.run(f"poke {address} {probe_value}")
        probe.run("frames 2 0x00000000")
        observed = telemetry.read()["phase"]
        if observed == probe_value:
            log(f"  the phase byte is 0x{address:08X}")
            return address
        probe.run(f"poke {address} {current_phase}")
    raise RuntimeError("the controller's phase byte was not found in EWRAM")


class ChainWalker:
    """Walks the settlement chain with the ROM's telemetry as the oracle."""

    def __init__(self, probe: probe_module.Probe,
                 telemetry: x1_telemetry.Telemetry,
                 out: pathlib.Path,
                 phase_address: int = 0,
                 skip_training: bool = False) -> None:
        self.probe = probe
        self.telemetry = telemetry
        self.out = out
        self.phase_address = phase_address
        self.skip_training = skip_training
        self.shots = out / "shots"
        self.shots.mkdir(parents=True, exist_ok=True)
        self.pages: list[dict[str, object]] = []
        self.frames = 0
        self.skipped_training = False

    # ------------------------------------------------------------- plumbing
    def run(self, frames: int, mask: int = 0) -> None:
        self.probe.run(f"frames {frames} 0x{mask:08X}")
        self.frames += frames

    def tap(self, key: int = KEY_A) -> None:
        """One button press with a released frame before and after it.

        The scene latches a confirmation until it has seen the button
        released (``script_confirmation_latched`` is only cleared on a frame
        where A is not held), and the probe's ``frames`` command releases the
        keys after the last frame it renders.  A press without a released
        frame in front of it is swallowed.
        """
        self.run(1, 0)
        self.run(4, key)
        self.run(2, 0)

    def state(self) -> dict[str, int]:
        return self.telemetry.read()

    def wait_idle(self, timeout: int = 1200, poll: int = 8) -> bool:
        """Wait until the scene is not busy.

        The scene's input dispatch gives a running presentation the frame
        (``else if(presentation_frame) { presentation.advance(); }`` comes
        before the button branch), so a button pressed while a presentation
        is running is **swallowed**.  The chain's last training page is
        exactly that case.
        """
        deadline = self.frames + timeout
        while self.frames < deadline:
            values = self.state()
            if (values["presentation_busy"] == 0 and
                    values["map_movement_active"] == 0):
                return True
            self.run(poll)
        return False

    def wait_stable(self, probe_shot: pathlib.Path, tries: int = 12,
                    gap: int = 20) -> str:
        """Wait until the rendered frame stops changing.

        The chain's first screen is drawn behind the battle-to-settlement
        black field, so a fixed wait photographs the fade instead of the
        screen.  Two identical frames in a row mean the picture has settled.
        """
        previous = ""
        for _ in range(tries):
            self.probe.run(f"shot {probe_shot}")
            current = sha256_file(probe_shot)
            if current == previous:
                return current
            previous = current
            self.run(gap)
        return previous

    @staticmethod
    def screen_key(values: dict[str, int]) -> tuple[int, ...]:
        """What identifies the screen the chain is showing.

        The phase alone is not enough: the training stage has six sub pages
        that all share one phase, so the sub page counter is part of the key.
        """
        return (values["phase"], values["training_detail_page"],
                values["result_participant_count"],
                values["result_total_experience"])

    # ------------------------------------------------------------- the chain
    def walk(self, settle_frames: int = 90, max_pages: int = 48) -> dict:
        """Walk the chain: read the screen -> decide -> press.

        The chain's stages do not all take the same button: the training
        stage swallows A on its last page.  The walker therefore **reads the
        rendered screen** (the probe's own screenshot) and, when a button
        leaves the screen unchanged, tries the next one.  The decision never
        uses a hard coded key sequence.

        The identity of a page is the sha256 of its rendered frame, so a
        stage that shows several pages under one phase (``training`` has
        six) is walked page by page.
        """
        result: dict[str, object] = {"pages": [], "presses": 0}
        keys = [("A", KEY_A), ("B", 0x002), ("Right", 0x010),
                ("Down", 0x080), ("Left", 0x020), ("Up", 0x040)]
        probe_shot = self.out / "probe.png"
        previous_sha: str | None = None
        key_index = 0
        for index in range(max_pages):
            values = self.state()
            phase = values["phase"]
            name = SETTLEMENT_PHASES.get(phase, x1_telemetry.phase_name(phase))
            if phase == PHASE_COMPLETE:
                result["final_phase"] = phase
                result["final_phase_name"] = "complete"
                break
            if phase not in SETTLEMENT_PHASES:
                result["final_phase"] = phase
                result["final_phase_name"] = name
                result["unexpected_phase"] = True
                break
            if self.skip_training and phase == PHASE_TRAINING:
                # The training stage crashes the remake on its last page
                # ("Invalid UTF-8 character", bn_utf8_character.h:91), so the
                # chain cannot be walked past it with the buttons.  The
                # controller's phase is moved to the next stage of the
                # chain instead; the pages that follow are still drawn by the
                # product code.
                self.probe.run(f"poke {self.phase_address} "
                               f"{PHASE_POST_BATTLE_DIALOGUE}")
                self.run(8)
                self.skipped_training = True
                result["skipped_training"] = True
                continue
            # Let the screen settle before the observation: the scene needs a
            # couple of frames to switch its UI layer, to finish the
            # dialogue's typewriter and to get the black field out of the way.
            self.run(settle_frames)
            values = self.state()
            phase = values["phase"]
            name = SETTLEMENT_PHASES.get(phase, x1_telemetry.phase_name(phase))
            if phase not in SETTLEMENT_PHASES:
                result["final_phase"] = phase
                result["final_phase_name"] = name
                break
            sha = self.wait_stable(probe_shot)
            if sha != previous_sha:
                path = self.shots / f"page-{index:03d}-{name}.png"
                path.write_bytes(probe_shot.read_bytes())
                entry = {
                    "index": index,
                    "file": path.name,
                    "phase": phase,
                    "phase_name": name,
                    "training_detail_page": values["training_detail_page"],
                    "outcome": values["condition_outcome"],
                    "round": values["round"],
                    "result_participant_count":
                        values["result_participant_count"],
                    "result_total_experience":
                        values["result_total_experience"],
                    "sha256": sha,
                }
                self.pages.append(entry)
                result["pages"].append(entry)
                print(f"page {index:03d}: {name} "
                      f"(detail {values['training_detail_page']}) -> "
                      f"{path.name} sha={sha[:16]}", flush=True)
                previous_sha = sha
                key_index = 0
            else:
                # The screen did not change: the last button did nothing.
                key_index += 1
                if key_index >= len(keys):
                    result["stuck_at"] = index
                    result["stuck_phase"] = phase
                    break
            key_name, key_mask = keys[key_index]
            self.wait_idle()
            self.tap(key_mask)
            result["presses"] += 1
            if self.pages and self.pages[-1].get("index") == index:
                self.pages[-1]["advanced_by"] = key_name
        values = self.state()
        result["final_phase"] = values["phase"]
        result["final_phase_name"] = x1_telemetry.phase_name(values["phase"])
        result["outcome"] = values["condition_outcome"]
        result["frames_run"] = self.frames
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path,
                        default=HERE.parents[1] / "build" / "mgba-probe-z1" /
                        "mgba-probe.exe")
    parser.add_argument("--settle-frames", type=int, default=90)
    parser.add_argument("--max-pages", type=int, default=48)
    parser.add_argument("--no-boot", action="store_true")
    parser.add_argument("--skip-training", action="store_true",
                        help="move the controller past the training stage, which crashes the remake")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    receipt: dict[str, object] = {
        "schema": "konoha.s49-z1-settlement-chain.v1",
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "out": str(args.out),
        "entry": {
            "method": "controller state poke (phase + outcome), then a "
                      "closed-loop walk of the chain",
            "controller_base": f"0x{CONTROLLER_BASE:08X}",
            "phase_address": f"0x{CONTROLLER_PHASE_ADDRESS:08X}",
            "outcome_address": f"0x{CONTROLLER_OUTCOME_ADDRESS:08X}",
        },
    }
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        if not args.no_boot:
            boot = w1_boot.Boot(probe, args.out / "boot")
            receipt["boot"] = boot.run()
        telemetry = x1_telemetry.Telemetry(probe)
        telemetry.locate()
        receipt["telemetry_address"] = f"0x{telemetry.address:08X}"
        walker = ChainWalker(probe, telemetry, args.out,
                             skip_training=args.skip_training)

        # ---- find the controller's phase byte -------------------------------
        phase_before = telemetry.read()["phase"]
        phase_address = locate_phase_byte(probe, telemetry, phase_before)
        walker.phase_address = phase_address
        receipt["entry"]["phase_address"] = f"0x{phase_address:08X}"
        receipt["entry"]["phase_address_source"] = (
            "found by effect: poked with 13 and confirmed through the ROM's "
            "own telemetry")
        # ``_outcome`` sits 0x228 bytes after ``_phase`` in
        # battle_scene_controller<12, 23, 32>.
        outcome_address = phase_address + 0x228
        receipt["entry"]["outcome_address"] = f"0x{outcome_address:08X}"
        receipt["entry"]["outcome_address_source"] = (
            "_outcome is 0x228 bytes after _phase in "
            "battle_scene_controller<12, 23, 32>")

        # ---- verify the controller's phase byte before poking it -----------
        raw = telemetry._dump(phase_address, 1)
        observed = telemetry.read()["phase"]
        receipt["phase_byte_before_poke"] = raw[0]
        receipt["phase_from_telemetry"] = observed
        if raw[0] != observed:
            raise RuntimeError(
                f"the byte at 0x{phase_address:08X} is {raw[0]}, "
                f"not the phase {observed}; the controller moved")
        outcome_before = telemetry._dump(outcome_address, 1)[0]
        receipt["outcome_byte_before_poke"] = outcome_before

        # ---- enter the chain ------------------------------------------------
        probe.run(f"poke {phase_address} {PHASE_OUTCOME}")
        probe.run(f"poke {outcome_address} {OUTCOME_WIN}")
        walker.run(4)
        values = telemetry.read()
        receipt["phase_after_poke"] = values["phase"]
        receipt["outcome_after_poke"] = values["condition_outcome"]
        receipt["outcome_byte_after_poke"] = telemetry._dump(
            outcome_address, 1)[0]
        if values["phase"] != PHASE_OUTCOME:
            raise RuntimeError(
                f"the phase after the poke is {values['phase']}, not "
                f"{PHASE_OUTCOME}")

        receipt["chain"] = walker.walk(args.settle_frames, args.max_pages)
        receipt["pages"] = walker.pages
        (args.out / "stderr.txt").write_text("\n".join(probe.stderr) + "\n",
                                             encoding="utf-8", newline="\n")
    receipt["wall_seconds"] = round(time.time() - started, 1)
    (args.out / "chain.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({key: value for key, value in receipt.items()
                      if key != "pages"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
