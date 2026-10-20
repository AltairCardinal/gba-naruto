#!/usr/bin/env python3
"""Drive the original S49 battle to victory with verifiable recorded segments.

Every segment is one ``tools/butano/capture_s49_advance.py`` run (which calls
``tools/run_guarded.py`` itself), so the guard's heavy lock and timeouts apply.
Each segment directory holds its own ``inputs.json`` / ``steps.json`` contract
and the savestate the next segment resumes from, which makes the whole chain
reproducible and citable.

The driver only ever *reads* the game state out of the mGBA savestates:

* unit pool  : ``0x020240C0``, stride ``0x1D4`` (positions, side, acting flag)
* HP array   : ``0x020242A0``, stride ``0x1D4`` (one byte per unit slot)

Both were verified against the known values of the battle-14 entry savestate
(138 / 104 / 110 / 40 / 25 x5).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from butano.read_rom_unit_pool import (  # noqa: E402
    POOL_ADDRESS,
    POOL_STRIDE,
    load_state,
    read_pool,
)

HP_ARRAY_ADDRESS = 0x020242A0
HP_STRIDE = 0x1D4
UNIT_COUNT = 9
NARUTO = 1
SAKURA = 3
SASUKE = 2
BEE_SLOTS = (5, 6, 7, 8, 9)
CROSS_RANGE = 3  # 十字手里剑 距離 3 直


def read_state(path: Path) -> dict:
    """Return positions, sides, acting flags and HP for one savestate."""
    savestate = load_state(path)
    units = read_pool(savestate)
    memory = savestate.read_memory(0x02000000, 0x40000)
    offset = HP_ARRAY_ADDRESS - 0x02000000
    hp = {slot + 1: memory[offset + slot * HP_STRIDE] for slot in range(UNIT_COUNT)}
    by_slot = {}
    for unit in units:
        by_slot[unit["slot"]] = unit
    return {
        "units": by_slot,
        "hp": hp,
        "acting": sorted(u["slot"] for u in units if u.get("acting")),
    }


def run_segment(out_dir: Path, state: Path, keys: str, settle: int,
                zero_input: int = 90, hold: int = 4) -> tuple[Path, dict]:
    """Record one segment and return (last savestate, steps.json payload)."""
    if out_dir.exists():
        raise SystemExit(f"segment directory already exists: {out_dir}")
    command = [
        sys.executable, str(ROOT / "tools/butano/capture_s49_advance.py"),
        "--out-dir", str(out_dir),
        "--rom", str(ROOT / "rom/base.gba"),
        "--state", str(state),
        "--keys", keys,
        "--zero-input-frames", str(zero_input),
        "--settle-frames", str(settle),
        "--hold-frames", str(hold),
        "--label", out_dir.name,
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(
            f"segment {out_dir.name} failed with exit {completed.returncode}: "
            f"{completed.stderr.strip()[:400]}")
    steps = json.loads((out_dir / "steps.json").read_text(encoding="utf-8"))
    last = out_dir / steps["steps"][-1]["state"]
    return last, steps


def direction_keys(frm: tuple[int, int], to: tuple[int, int]) -> list[str]:
    """Cursor presses that walk one cell at a time from frm to to."""
    keys: list[str] = []
    dx = to[0] - frm[0]
    dy = to[1] - frm[1]
    while dx > 0:
        keys.append("Right")
        dx -= 1
    while dx < 0:
        keys.append("Left")
        dx += 1
    while dy > 0:
        keys.append("Down")
        dy -= 1
    while dy < 0:
        keys.append("Up")
        dy += 1
    return keys


def pick_retreat(state: dict) -> tuple[int, tuple[int, int]] | None:
    """Nearest bee and the cell 3 steps toward it (瞬身术 距離 3 直)."""
    naruto = state["units"][NARUTO]
    origin = (naruto["x"], naruto["y"])
    best = None
    for slot in BEE_SLOTS:
        bee = state["units"].get(slot)
        if bee is None:
            continue
        target = (bee["x"], bee["y"])
        distance = abs(target[0] - origin[0]) + abs(target[1] - origin[1])
        score = (distance, state["hp"][slot], slot)
        if best is None or score < best[0]:
            best = (score, slot, target)
    if best is None:
        return None
    _, slot, target = best
    dx = target[0] - origin[0]
    dy = target[1] - origin[1]
    if abs(dx) >= abs(dy):
        step = 3 if dx > 0 else -3
        destination = (min(15, max(0, origin[0] + step)), origin[1])
    else:
        step = 3 if dy > 0 else -3
        destination = (origin[0], min(15, max(0, origin[1] + step)))
    if destination == origin:
        return None
    return slot, destination


def pick_target(state: dict) -> tuple[int, tuple[int, int]] | None:
    """Nearest bee that 十字手里剑 can reach: same row or column, <= 3 cells."""
    naruto = state["units"][NARUTO]
    origin = (naruto["x"], naruto["y"])
    best = None
    for slot in BEE_SLOTS:
        bee = state["units"].get(slot)
        if bee is None:
            continue
        target = (bee["x"], bee["y"])
        dx = target[0] - origin[0]
        dy = target[1] - origin[1]
        if (dx == 0) == (dy == 0):
            continue
        distance = abs(dx) + abs(dy)
        if distance > CROSS_RANGE:
            continue
        score = (state["hp"][slot], distance, slot)
        if best is None or score < best[0]:
            best = (score, slot, target)
    if best is None:
        return None
    return best[1], best[2]


def key_spec(keys: list[str]) -> str:
    """Compress a key list into the tool's ``A*3`` syntax."""
    parts: list[str] = []
    index = 0
    while index < len(keys):
        run = 1
        while index + run < len(keys) and keys[index + run] == keys[index]:
            run += 1
        parts.append(keys[index] if run == 1 else f"{keys[index]}*{run}")
        index += run
    return ",".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=Path, required=True)
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=8)
    parser.add_argument("--enemy-settle", type=int, default=2400)
    args = parser.parse_args()

    out_root: Path = args.out_root
    out_root.mkdir(parents=True, exist_ok=True)
    chain: list[dict] = []
    current: Path = args.start
    index = 0

    def record(tag: str, keys: str, settle: int) -> Path:
        nonlocal current, index
        index += 1
        name = f"s{index:02d}-{tag}"
        target_dir = out_root / name
        last, steps = run_segment(target_dir, current, keys, settle)
        chain.append({
            "segment": name,
            "keys": keys,
            "settle_frames": settle,
            "resumed_from": str(current),
            "resumed_from_sha256": steps["steps"][0].get("state_sha256"),
            "last_state": str(last),
            "last_state_sha256": steps["steps"][-1]["state_sha256"],
        })
        (out_root / "chain.json").write_text(
            json.dumps(chain, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        current = last
        return current

    for round_number in range(1, args.rounds + 1):
        state = read_state(current)
        if NARUTO not in state["acting"]:
            print(json.dumps({
                "status": "naruto-turn-not-ready",
                "round": round_number,
                "acting": state["acting"],
                "hp": state["hp"],
            }, ensure_ascii=False))
            return 1
        target = pick_target(state)
        if target is None:
            retreat = pick_retreat(state)
            if retreat is None:
                record(f"r{round_number}-stuck", "L", 600)
                continue
            _, destination = retreat
            naruto = state["units"][NARUTO]
            moves = direction_keys((naruto["x"], naruto["y"]), destination)
            record(f"r{round_number}-teleport-aim",
                   key_spec(["A", "Down", "A", "A"] + moves + ["A"]), 240)
            record(f"r{round_number}-teleport-exec", "A", 900)
            record(f"r{round_number}-teleport-turn-end", "A,A", 300)
        else:
            slot, position = target
            naruto = state["units"][NARUTO]
            moves = direction_keys((naruto["x"], naruto["y"]), position)
            keys = ["A", "Down", "A", "Down", "Down", "Down", "A"] + moves
            record(f"r{round_number}-naruto-aim", key_spec(keys), 90)
            after = read_state(current)
            acting = after["acting"]
            if slot not in acting:
                print(json.dumps({
                    "status": "aim-mismatch",
                    "round": round_number,
                    "expected_target": slot,
                    "acting": acting,
                    "hp": after["hp"],
                }, ensure_ascii=False))
                return 1
            record(f"r{round_number}-naruto-fire", "A,A,A", 900)
            record(f"r{round_number}-naruto-turn-end", "A,A,A", 300)
        record(f"r{round_number}-skip-sakura", "A,Down*4,A,A,A,A", 150)
        record(f"r{round_number}-skip-sasuke", "A,Down*4,A,A,A,A", 150)
        for attempt in range(3):
            record(f"r{round_number}-enemy-phase-{attempt}", "L", args.enemy_settle)
            state = read_state(current)
            if NARUTO in state["acting"]:
                break
        state = read_state(current)
        print(json.dumps({
            "status": "round-done",
            "round": round_number,
            "hp": state["hp"],
            "acting": state["acting"],
        }, ensure_ascii=False))
        if not all(state["hp"][slot] == 0 for slot in BEE_SLOTS):
            break
    print(json.dumps({"status": "finished", "segments": len(chain)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
