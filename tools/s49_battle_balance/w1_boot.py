#!/usr/bin/env python3
"""W1 (wave 11): closed-loop boot of the remake ROM up to the battle dialogue.

Why a closed loop
-----------------
U2 (wave 10) could not drive the remake's power-on flow with an open-loop key
script: the pre-battle screens are interactive and they eat the script's keys.
This tool walks the boot **with the screen as the oracle**:

1. the preparation scene's root menu -- ``Down Down`` puts the cursor on
   开始任务 (the remake's own ``battle_preparation_flow`` starts on
   队伍·装备, and ``move(+1)`` walks the four options);
2. ``A`` confirms 开始任务吗？ -> yes;
3. ``A`` confirms the nine deployment units and the 开始 title;
4. the black field that separates the deployment from the battle is **the
   phase marker**: it is the only moment the screen is black;
5. the battle's opening dialogue follows.

The tool stops on the first dialogue page whose typewriter has finished and
saves a savestate there.  The victory key script starts with exactly three
``script_blocked`` confirms and one turn-banner confirm, so the dialogue has
to start on its **first** page for the script to line up.

Usage::

    python tools/s49_battle_balance/w1_boot.py \\
        --out build/s49-battle-balance/w1/boot \\
        --state build/s49-battle-balance/w1/boot/dialogue1.ss9
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import w1_probe as probe_module  # noqa: E402

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

KEY_NAMES = {value: name for name, value in KEYS.items()}


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def mean_luma(path: pathlib.Path) -> float:
    from PIL import Image
    with Image.open(path) as image:
        gray = image.convert("L")
        values = list(gray.getdata())
    return sum(values) / len(values)


class Boot:
    """The closed-loop boot driver."""

    def __init__(self, probe: probe_module.Probe, out: pathlib.Path):
        self.probe = probe
        self.out = out
        self.shots = out / "shots"
        self.shots.mkdir(parents=True, exist_ok=True)
        self.index = 0
        self.trace: list[dict[str, object]] = []

    # ------------------------------------------------------------- helpers
    def wait(self, frames: int) -> None:
        if frames > 0:
            self.probe.run(f"frames {frames} 0x00000000")

    def press(self, key: str, hold: int = 4, settle: int = 60) -> None:
        self.probe.run(f"frames {hold} 0x{KEYS[key]:08X}")
        self.wait(settle)

    def shot(self, tag: str) -> pathlib.Path:
        self.index += 1
        path = self.shots / f"boot-{self.index:04d}-{tag}.png"
        self.probe.run(f"shot {path}")
        return path

    def record(self, entry: dict[str, object]) -> None:
        self.trace.append(entry)
        (self.out / "boot-log.json").write_text(
            json.dumps(self.trace, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n")

    # ---------------------------------------------------------------- boot
    def run(self, black_luma: float = 60.0, max_presses: int = 24,
            deploy_settle: int = 30, poll_frames: int = 5,
            stable_frames: int = 30, stable_tries: int = 30) -> dict[str, object]:
        self.wait(120)
        # The preparation scene's root menu: move the cursor from 队伍·装备 to
        # 开始任务 (the remake's own flow walks four options with move(+1)).
        self.press("Down", settle=90)
        self.press("Down", settle=90)
        self.record({"do": "root-menu", "option": "start_battle"})

        # A until the black field appears.  The black field is the only phase
        # where the screen goes black, so it is the phase marker that proves
        # the deployment was confirmed.
        black_seen = False
        presses = 0
        for presses in range(1, max_presses + 1):
            self.press("A", settle=deploy_settle)
            path = self.shot(f"a{presses:02d}")
            luma = mean_luma(path)
            self.record({"do": "press-A", "index": presses, "luma": round(luma, 2),
                         "shot": path.name})
            if luma < black_luma:
                black_seen = True
                break
        if not black_seen:
            raise RuntimeError("the black field never appeared; the boot did "
                               "not reach the battle")

        # Wait until the black field is over: that is the first dialogue page.
        dialogue_frame = None
        for _ in range(200):
            self.wait(poll_frames)
            path = self.shot("dialog")
            luma = mean_luma(path)
            if luma >= black_luma:
                dialogue_frame = path
                self.record({"do": "dialogue", "luma": round(luma, 2),
                             "shot": path.name})
                break
        if dialogue_frame is None:
            raise RuntimeError("the black field never ended")

        # Wait for the typewriter to finish: two identical samples mean the
        # screen stopped changing.
        previous = dialogue_frame.read_bytes()
        stable = False
        for _ in range(stable_tries):
            self.wait(stable_frames)
            path = self.shot("stable")
            blob = path.read_bytes()
            if blob == previous:
                stable = True
                self.record({"do": "stable", "shot": path.name})
                break
            previous = blob
        return {"presses": presses, "dialogue_shot": str(dialogue_frame),
                "stable": stable}

    def save(self, path: pathlib.Path) -> pathlib.Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.probe.run(f"save {path}")
        return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--state", type=pathlib.Path, default=None,
                        help="where to save the savestate")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    state_path = args.state or (args.out / "dialogue1.ss9")
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        boot = Boot(probe, args.out)
        result = boot.run()
        boot.save(state_path)

    receipt = {
        "schema": "konoha.s49-w1-boot.v1",
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "state": str(state_path),
        "state_sha256": sha256_file(state_path),
        "out": str(args.out),
        **result,
    }
    (args.out / "boot.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
