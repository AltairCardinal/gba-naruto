#!/usr/bin/env python3
"""W1 (wave 11): closed-loop driver for the remake ROM.

Why a closed loop
-----------------
U2 proved that the remake's power-on flow (title -> story -> briefing ->
deployment -> party list -> battle opening dialogue) is **interactive** and that
the offline key script alone cannot walk it: the script's keys are eaten by the
pre-battle screens, so the battle never receives its input.

This driver keeps the probe process alive and lets the caller decide, frame by
frame, which key to press -- either interactively (stdin REPL) or from a JSON
plan file.  Every action can leave a screenshot behind, so the decision is made
on the *actual* frame, not on a guess.

It is also the tool that produces the final receipts: the same plan file can be
replayed twice on the same ROM and compared byte for byte.

Usage (interactive)::

    python tools/s49_battle_balance/w1_drive.py \\
        --out build/s49-battle-balance/w1/explore

    press A
    wait 90
    shot
    save build/.../boot.ss9
    quit

Usage (plan)::

    python tools/s49_battle_balance/w1_drive.py \\
        --out build/s49-battle-balance/w1/runA \\
        --plan build/s49-battle-balance/w1/boot-plan.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
V4 = HERE.parent / "s49_victory_capture"
if str(V4) not in sys.path:
    sys.path.insert(0, str(V4))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import w1_probe as probe_module  # noqa: E402
import w1_boot  # noqa: E402

REPO = HERE.parents[1]
DEFAULT_EXE = REPO / "build" / "mgba-probe-w1" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba")

KEYS = {
    "A": 0x001,
    "B": 0x002,
    "Select": 0x004,
    "Start": 0x008,
    "Right": 0x010,
    "Left": 0x020,
    "Up": 0x040,
    "Down": 0x080,
    "R": 0x100,
    "L": 0x200,
}


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class Driver:
    """A live probe plus the bookkeeping the receipts need."""

    def __init__(self, rom: pathlib.Path, exe: pathlib.Path, out: pathlib.Path,
                 log_path: pathlib.Path | None = None):
        self.rom = rom
        self.exe = exe
        self.out = out
        self.shots = out / "shots"
        self.shots.mkdir(parents=True, exist_ok=True)
        self.log: list[dict[str, object]] = []
        self.log_path = log_path
        self.shot_index = 0
        self.probe = probe_module.Probe(rom, exe=exe)

    # ------------------------------------------------------------- lifecycle
    def start(self) -> None:
        self.probe.start()

    def close(self) -> None:
        self.probe.close()

    def _record(self, entry: dict[str, object]) -> None:
        self.log.append(entry)
        if self.log_path is not None:
            self.log_path.write_text(
                json.dumps(self.log, indent=1, ensure_ascii=False) + "\n",
                encoding="utf-8", newline="\n")

    # ---------------------------------------------------------------- verbs
    def wait(self, frames: int) -> None:
        """Run ``frames`` frames with no key held."""
        if frames > 0:
            self.probe.run(f"frames {frames} 0x00000000")

    def press(self, key: str, hold: int = 4, settle: int = 60) -> None:
        """Press ``key`` for ``hold`` frames, then let the game settle."""
        mask = KEYS[key]
        self.probe.run(f"frames {hold} 0x{mask:08X}")
        if settle > 0:
            self.probe.run(f"frames {settle} 0x00000000")

    def hold(self, key: str, frames: int) -> None:
        """Hold ``key`` down for ``frames`` frames (no release edge inside)."""
        mask = KEYS[key]
        self.probe.run(f"key 0x{mask:08X}")
        self.probe.run(f"frames {frames} 0x{mask:08X}")
        self.probe.run("keyoff")

    def shot(self, tag: str = "") -> pathlib.Path:
        self.shot_index += 1
        name = f"shot-{self.shot_index:04d}"
        if tag:
            name += f"-{tag}"
        path = self.shots / f"{name}.png"
        self.probe.run(f"shot {path}")
        return path

    def save(self, path: pathlib.Path) -> pathlib.Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.probe.run(f"save {path}")
        return path

    def load(self, path: pathlib.Path) -> None:
        self.probe.run(f"load {path}")

    def dump(self, address: int, length: int) -> bytes:
        return self.probe.dump(address, length)

    # ------------------------------------------------------------- scripting
    def run_action(self, action: dict[str, object]) -> dict[str, object]:
        kind = str(action.get("do", "")).lower()
        result: dict[str, object] = {"do": kind}
        if kind == "wait":
            frames = int(action.get("frames", 60))
            self.wait(frames)
            result["frames"] = frames
        elif kind == "press":
            key = str(action["key"])
            hold = int(action.get("hold", 4))
            settle = int(action.get("settle", 60))
            self.press(key, hold, settle)
            result.update({"key": key, "hold": hold, "settle": settle})
        elif kind == "hold":
            key = str(action["key"])
            frames = int(action.get("frames", 30))
            self.hold(key, frames)
            result.update({"key": key, "frames": frames})
        elif kind == "shot":
            tag = str(action.get("tag", ""))
            path = self.shot(tag)
            result["path"] = str(path)
        elif kind == "save":
            path = pathlib.Path(str(action["path"]))
            self.save(path)
            result["path"] = str(path)
        elif kind == "load":
            path = pathlib.Path(str(action["path"]))
            self.load(path)
            result["path"] = str(path)
        elif kind == "dump":
            address = int(str(action["address"]), 0)
            length = int(action.get("length", 12))
            blob = self.dump(address, length)
            result.update({"address": f"0x{address:08X}", "hex": blob.hex()})
        elif kind == "boot":
            boot = w1_boot.Boot(self.probe, self.out / "boot")
            result.update(boot.run())
        else:
            raise ValueError(f"unknown action {kind!r}")
        self._record(result)
        return result


def run_plan(driver: Driver, plan: list[dict[str, object]]) -> None:
    for action in plan:
        driver.run_action(action)


def repl(driver: Driver) -> None:
    print("W1 closed-loop driver. Commands: press <KEY> [hold] [settle] | "
          "wait <frames> | hold <KEY> <frames> | shot [tag] | "
          "save <path> | load <path> | dump <addr> [len] | quit")
    for line in sys.stdin:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        command = parts[0].lower()
        try:
            if command == "quit" or command == "exit":
                break
            if command == "press":
                key = parts[1]
                hold = int(parts[2]) if len(parts) > 2 else 4
                settle = int(parts[3]) if len(parts) > 3 else 60
                driver.press(key, hold, settle)
                print(f"OK press {key} hold={hold} settle={settle}")
            elif command == "wait":
                frames = int(parts[1])
                driver.wait(frames)
                print(f"OK wait {frames}")
            elif command == "hold":
                key = parts[1]
                frames = int(parts[2])
                driver.hold(key, frames)
                print(f"OK hold {key} {frames}")
            elif command == "shot":
                tag = parts[1] if len(parts) > 1 else ""
                print(f"OK shot {driver.shot(tag)}")
            elif command == "save":
                print(f"OK save {driver.save(pathlib.Path(parts[1]))}")
            elif command == "load":
                driver.load(pathlib.Path(parts[1]))
                print(f"OK load {parts[1]}")
            elif command == "dump":
                address = int(parts[1], 0)
                length = int(parts[2]) if len(parts) > 2 else 12
                print(f"OK dump {driver.dump(address, length).hex()}")
            else:
                print(f"ERR unknown command {command!r}")
        except Exception as error:  # noqa: BLE001 - the REPL must not die
            print(f"ERR {error}")
            if isinstance(error, probe_module.ProbeError):
                break
    sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--plan", type=pathlib.Path, default=None,
                        help="JSON file with a list of actions")
    parser.add_argument("--zero-frames", type=int, default=60,
                        help="frames to run before the first action")
    parser.add_argument("--repl", action="store_true",
                        help="read commands from stdin instead of a plan")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    driver = Driver(args.rom, args.exe, args.out,
                    log_path=args.out / "drive-log.json")
    driver.start()
    try:
        driver.wait(args.zero_frames)
        if args.repl:
            repl(driver)
        elif args.plan is not None:
            plan = json.loads(args.plan.read_text(encoding="utf-8"))
            run_plan(driver, plan)
        else:
            repl(driver)
    finally:
        driver.close()

    receipt = {
        "schema": "konoha.s49-w1-drive.v1",
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "exe": str(args.exe),
        "out": str(args.out),
        "actions": len(driver.log),
        "shots": len(list(driver.shots.glob("*.png"))),
    }
    (args.out / "drive.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
