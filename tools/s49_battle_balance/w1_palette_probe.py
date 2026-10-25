#!/usr/bin/env python3
"""W1 (wave 15): measure the OBJ palette bank budget of the battle scene.

What it answers
---------------
*How many of Butano's sixteen hardware sprite palette banks does the battle
scene hold at once, and which cohort leaks them?*

The battle scene's portrait renderer owns a **BPP8** palette of 128 colours,
that is eight hardware banks, and Butano only lets a BPP8 palette live at the
**front** of the sprite palette bank (``palettes_bank::create_bpp_8`` refuses
to allocate it when a BPP4 palette already sits below index 8).  Every BPP4
palette that is alive at that moment therefore takes a bank away from the
portrait, and the ROM aborts with

    ERROR in bn_palettes_bank.cpp.h / create_bpp_8:265
    BPP8 palette create failed. Colors count: 128

whenever too many BPP4 palettes are alive.

The instrument reads Butano's own palette bank state out of the emulator's
memory (the EWRAM block of ``bn::palettes_manager``) and decodes it with the
layout of ``bn::palettes_bank``, so the numbers are the ROM's own, not an
estimate.

Usage::

    python tools/s49_battle_balance/w1_palette_probe.py \\
        --rom build/w1/rom-w1a.gba \\
        --route build/s49-battle-balance/u2/routeY.json \\
        --out build/w1/palette-a
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import w1_boot  # noqa: E402
import w1_palette_state as palette_state  # noqa: E402
import w1_probe as probe_module  # noqa: E402
import x1_telemetry  # noqa: E402
import y1_play  # noqa: E402


class PaletteDriver(y1_play.Driver):
    """The Y1 closed loop driver plus a palette bank sample per wait."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.samples: list[dict[str, object]] = []
        self.sample_period = 60

    def sample(self, tag: str) -> dict[str, object]:
        raw = self.probe.run(
            f"dump 0x{palette_state.SPRITE_BANK_ADDRESS:08X} "
            f"{palette_state.PALETTES_BANK_SIZE * 2}")
        hex_text = "".join(line for line in raw
                           if not line.startswith("DUMP") and line != "ENDDUMP")
        data = bytes.fromhex(hex_text)
        if tag == "final":
            (self.out / "final-bank.hex").write_text(
                hex_text, encoding="ascii", newline="\n")
        sprite = palette_state.decode_bank(
            data[:palette_state.PALETTES_BANK_SIZE], "sprite")
        bg = palette_state.decode_bank(
            data[palette_state.PALETTES_BANK_SIZE:], "bg")
        values = self.state()
        entry = {
            "tag": tag,
            "frame": self.frames,
            "phase": values["phase"],
            "phase_name": x1_telemetry.phase_name(values["phase"]),
            "round": values["round"],
            "sprite_used_banks": sprite["used_banks"],
            "sprite_first_bpp4_index": sprite["first_bpp4_index"],
            "bg_used_banks": bg["used_banks"],
            "sprite_slots": [
                {"index": slot.index, "usages": slot.usages,
                 "slots_count": slot.slots_count, "bpp_8": slot.bpp_8}
                for slot in sprite["slots"] if slot.usages  # type: ignore[index]
            ],
        }
        self.samples.append(entry)
        return entry

    def wait(self, frames: int) -> None:
        super().wait(frames)
        if frames and self.frames % self.sample_period < frames:
            self.sample("wait")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--route", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path,
                        default=HERE.parents[1] / "build" / "mgba-probe-w1" /
                        "mgba-probe.exe")
    parser.add_argument("--boot", action="store_true")
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--sample-period", type=int, default=60)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    route = json.loads(args.route.read_text(encoding="utf-8"))
    started = time.time()
    receipt: dict[str, object] = {
        "schema": "konoha.s49-w1-palette-probe.v1",
        "rom": str(args.rom),
        "rom_sha256": y1_play.sha256_file(args.rom),
        "route": str(args.route),
        "sprite_bank_address": palette_state.SPRITE_BANK_ADDRESS,
        "bg_bank_address": palette_state.BG_BANK_ADDRESS,
    }
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        driver = PaletteDriver(probe, x1_telemetry.Telemetry(probe), args.out,
                               verbose=not args.quiet)
        driver.sample_period = args.sample_period
        if args.boot:
            boot = w1_boot.Boot(probe, args.out / "boot")
            receipt["boot"] = boot.run()
        else:
            probe.run("frames 120 0x00000000")
            driver.frames = 120
        driver.log(f"telemetry at 0x{driver.telemetry.locate(verbose=True):08X}")
        reached = driver.play_route(route, args.max_steps)
        settlement: dict[str, object] = {}
        if reached:
            settlement = driver.play_settlement(90)
        else:
            values = driver.state()
            settlement = {"final_phase": values["phase"],
                          "final_phase_name":
                              x1_telemetry.phase_name(values["phase"]),
                          "outcome": values["condition_outcome"],
                          "round": values["round"], "pages": []}
        final = driver.sample("final")
        shot = driver.shot("final")
        receipt.update({
            "reached_settlement": reached,
            "frames_run": driver.frames,
            "keys_pressed": driver.keys,
            "errors": driver.errors,
            "settlement": settlement,
            "final_sample": final,
            "final_shot": str(shot),
            "max_sprite_banks": max((entry["sprite_used_banks"]
                                     for entry in driver.samples),
                                    default=0),
            "samples": driver.samples,
        })
        (args.out / "stderr.txt").write_text(
            "\n".join(probe.stderr) + "\n", encoding="utf-8", newline="\n")
    receipt["wall_seconds"] = round(time.time() - started, 1)
    (args.out / "palette.json").write_text(
        json.dumps(receipt, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({key: value for key, value in receipt.items()
                      if key != "samples"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
