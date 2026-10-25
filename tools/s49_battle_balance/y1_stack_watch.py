#!/usr/bin/env python3
"""Y1 (wave 13): catch the stack overflow with a write watchpoint.

The GBA user stack lives at 0x03007F00 (``__sp_usr``) and the IWRAM data
ends at 0x03002BD8, so only ~21 kB of stack exist.  A **write watchpoint**
just above that boundary breaks the debugger at the exact instruction that
overflows the stack, and the backtrace at that moment is still intact.

Usage::

    python tools/s49_battle_balance/y1_stack_watch.py \\
        --rom build/y1/rom-fixed.gba --out build/y1/stackwatch
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import w1_boot  # noqa: E402
import w1_probe as probe_module  # noqa: E402
import x1_telemetry  # noqa: E402
import y1_play  # noqa: E402

# The bottom of the user stack: __sp_usr (0x03007F00) minus the IWRAM data
# that ends at 0x03002BD8.
STACK_GUARD = 0x03002BD8


class WatchDriver(y1_play.Driver):
    """Drives to the action confirm, then arms the watchpoint."""

    def __init__(self, *args, guard: int = STACK_GUARD,
                 guard_size: int = 16, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.guard = guard
        self.guard_size = guard_size

    def action_and_target(self, prefer_index=None):  # type: ignore[override]
        values = self.state()
        count = max(1, values["action_count"])
        for action_index in range(count):
            self.select_action_index(action_index)
            break
        self.report(f"watch-range/w {self.guard} "
                    f"{self.guard + self.guard_size}")
        self.press("A", 4)
        self.wait(240)
        self.report("backtrace 40")
        self.report("print/x r13")
        self.report("print/x r15")
        return False

    def report(self, command: str) -> None:
        try:
            lines = self.probe.run(command)
        except Exception as error:  # noqa: BLE001
            lines = [f"<{error}>"]
        print(f"---- {command} ----", flush=True)
        for line in lines:
            print(f"    {line}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--route", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path,
                        default=HERE.parents[1] / "build" / "mgba-probe-y1" /
                        "mgba-probe.exe")
    parser.add_argument("--guard", type=lambda value: int(value, 0),
                        default=STACK_GUARD)
    parser.add_argument("--guard-size", type=int, default=16)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    route = json.loads(args.route.read_text(encoding="utf-8"))
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        driver = WatchDriver(probe, x1_telemetry.Telemetry(probe), args.out,
                             guard=args.guard, guard_size=args.guard_size)
        boot = w1_boot.Boot(probe, args.out / "boot")
        boot.run()
        driver.telemetry.locate(verbose=True)
        driver.play_route(route)
        (args.out / "stderr.txt").write_text("\n".join(probe.stderr) + "\n",
                                             encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
