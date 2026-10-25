#!/usr/bin/env python3
"""Y1 (wave 13): get a debugger backtrace at the action-confirm crash.

The crash is a stack overflow: ``__sp_usr`` is 0x03007F00 and the IWRAM data
ends at 0x03002BD8, so only ~21 kB of stack exist, while the remake's scene
function alone has a 7 kB frame.  This script drives the ROM to the action
confirmation, presses A and then asks mGBA's debugger for the register state
and the stack backtrace.

Usage::

    python tools/s49_battle_balance/y1_crash_bt.py \\
        --rom build/y1/rom-fixed.gba --out build/y1/crash
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


class CrashDriver(y1_play.Driver):
    """Same driver, but the action confirm stops and asks the debugger."""

    def action_and_target(self, prefer_index=None):  # type: ignore[override]
        values = self.state()
        count = max(1, values["action_count"])
        order = list(range(count))
        if prefer_index is not None and prefer_index in order:
            order.remove(prefer_index)
            order.insert(0, prefer_index)
        for action_index in order:
            self.log(f"    trying action[{action_index}]")
            self.select_action_index(action_index)
            values = self.state()
            self.log(f"    action id={values['selected_action_id']} "
                     f"error={values['selected_action_error']}")
            break
        # The crash happens on this press.
        self.report("stack trace-only")
        self.press("A", 4)
        self.wait(120)
        self.report("backtrace 30")
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
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    route = json.loads(args.route.read_text(encoding="utf-8"))
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        driver = CrashDriver(probe, x1_telemetry.Telemetry(probe), args.out)
        boot = w1_boot.Boot(probe, args.out / "boot")
        boot.run()
        driver.telemetry.locate(verbose=True)
        driver.play_route(route)
        (args.out / "stderr.txt").write_text("\n".join(probe.stderr) + "\n",
                                             encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
