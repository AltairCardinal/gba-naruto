#!/usr/bin/env python3
"""Event queue budget for battle scene logic scripts.

The engine queues conditional dialogue events while a battle runs, and the
queue holds at most 16 entries at a time.  The third-party editor refuses to
compile a scene whose original events plus newly added events could exceed
that, using a static analysis of the scene's *logic* script.

This tool is our own implementation of that analysis, on top of our story
script VM (`tools/decode_story_script.py`).  It answers the question a sequel
author actually needs: **for this battle, how many conditional events can I
still add?**

How the count is derived
------------------------
Walk the logic script for every (turn, phase, sub) combination the script can
react to, and take the deepest chain of event-queueing instructions:

  * `0x00` end          -> return to the caller on the stack
  * `0x07` jump / `0x06` two-way branch -> take the worst of the branches
  * `0x13` call         -> descend into the sub-script
  * `0x34` turn/phase condition -> follow the taken or the not-taken side
  * `0x39` config check -> follow the matching or the other side
  * `0x33`              -> counts one queued event
  * anything else       -> counts 0, and continues with the worst of the
                           fall-through and the branch targets

Recursion deeper than 8 frames, or a cycle, is treated as "over budget".

Usage:
    python tools/event_queue_budget.py
    python tools/event_queue_budget.py --json build/queue_budget.json
    python tools/event_queue_budget.py --events my_events.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import decode_story_script as ds  # noqa: E402
from tools import text_codec  # noqa: E402

QUEUE_LIMIT = 16
MAX_DEPTH = 8

OP_END = 0x00
OP_CALL = 0x13
OP_JUMP = 0x07
OP_BRANCH2 = 0x06
OP_QUEUED = 0x33
OP_TURN_COND = 0x34
OP_CONFIG = 0x39

# Comparator semantics of 0x34 (+1): 0==, 1!=, 2>, 3>=, 4<, 5<=, 0xFF always.
def turn_matches(comparator: int, turn: int, target: int) -> bool:
    if comparator == 0xFF:
        return True
    if comparator == 0:
        return turn == target
    if comparator == 1:
        return turn != target
    if comparator == 2:
        return turn > target
    if comparator == 3:
        return turn >= target
    if comparator == 4:
        return turn < target
    if comparator == 5:
        return turn <= target
    return False


class AnalysisInconclusive(Exception):
    """Raised when the walk hits a cycle or exceeds the depth guard."""


def queue_depth(rom: bytes, nodes: dict, start: int, turn: int, phase: int,
                sub: int) -> int:
    """Deepest chain of queued events reachable in this (turn, phase, sub)."""
    memo: dict[str, int] = {}

    def walk(p: int, stack: tuple[int, ...]) -> int:
        key = f"{p}:{stack}"
        if key in memo:
            return memo[key]
        if p in stack or len(stack) > MAX_DEPTH:
            raise AnalysisInconclusive(
                f"cycle or depth > {MAX_DEPTH} at {p:#x}")
        node = nodes.get(p)
        if node is None:
            return 0
        nxt = p + node.length
        op = node.op
        if op == OP_END:
            value = walk(stack[-1], stack[:-1]) if stack else 0
        elif op == OP_CALL:
            value = walk(node.targets[0], stack + (nxt,)) if node.targets else 0
        elif op in (OP_JUMP, OP_BRANCH2):
            value = max((walk(t, stack) for t in node.targets), default=0)
        elif op == OP_TURN_COND:
            comparator = rom[p + 1]
            target_turn = rom[p + 2]
            phase_match = rom[p + 3] == phase
            taken = phase_match and turn_matches(comparator, turn, target_turn)
            value = walk(node.targets[0], stack) if taken else walk(nxt, stack)
        elif op == OP_CONFIG:
            taken = rom[p + 1] == sub
            value = walk(node.targets[0], stack) if taken else walk(nxt, stack)
        else:
            value = (1 if op == OP_QUEUED else 0) + max(
                [walk(nxt, stack)] + [walk(t, stack) for t in node.targets]
            )
        memo[key] = value
        return value

    return walk(start, ())


def budget_for_scene(rom: bytes, nodes: dict, start: int,
                     added: list[dict]) -> tuple[int | None, int | None, str | None]:
    """Return (baseline depth, depth including added events, inconclusive reason)."""
    turns = {0, 1, 255}
    for node in nodes.values():
        if node.op == OP_TURN_COND:
            for delta in (-1, 0, 1):
                t = rom[node.offset + 2] + delta
                if 0 <= t <= 255:
                    turns.add(t)
    for event in added:
        if event.get("type") == "turn":
            turns.add(event["turn"])
            if event["turn"] > 0:
                turns.add(event["turn"] - 1)

    baseline = 0
    with_added = 0
    for turn in sorted(turns):
        for phase in (0, 1):
            for sub in range(3):
                try:
                    depth = queue_depth(rom, nodes, start, turn, phase, sub)
                except AnalysisInconclusive as exc:
                    return None, None, str(exc)
                baseline = max(baseline, depth)
                extra = sum(
                    1 for e in added
                    if e.get("phase") == phase
                    and (e.get("sub", 0) == 3 or e.get("sub", 0) == sub)
                    and (e.get("type") != "turn" or turn >= e.get("turn", 0))
                )
                with_added = max(with_added, depth + extra)
    return baseline, with_added, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument(
        "--events",
        default=None,
        help="JSON file: {stage: [event, ...]} with fields "
             "type(turn|absent), repeat(once|phase), phase(0|1), sub(0..3), turn",
    )
    args = ap.parse_args()

    rom_path = text_codec.resolve_rom(args.rom)
    rom = rom_path.read_bytes()
    mapping, _ = text_codec.load_mapping(rom_path)

    added_by_stage: dict[int, list[dict]] = {}
    if args.events:
        raw = json.loads(pathlib.Path(args.events).read_text(encoding="utf-8"))
        added_by_stage = {int(k): v for k, v in raw.items()}

    rows = []
    for scene in range(1, 47):
        roots = ds.scene_roots(rom, scene)
        logic = roots.get("logic")
        if not logic:
            continue
        nodes, issues = ds.walk(rom, [logic], mapping)
        added = added_by_stage.get(scene, [])
        baseline, with_added, reason = budget_for_scene(rom, nodes, logic, added)
        # The static walk is an over-approximation: on original content it
        # reaches 17 on stage 20, so a depth above 16 does not mean the game
        # would overflow.  What matters for an author is the *marginal* cost
        # of the events they add.
        exceeds = bool(with_added is not None and with_added > QUEUE_LIMIT)
        rows.append({
            "stage": scene,
            "logic_offset": logic,
            "nodes": len(nodes),
            "decode_issues": len(issues),
            "baseline_depth": baseline,
            "added_events": len(added),
            "depth_with_added": with_added,
            "headroom": (QUEUE_LIMIT - with_added) if with_added is not None else None,
            "exceeds_limit": exceeds,
            "baseline_already_exceeds": bool(
                baseline is not None and baseline > QUEUE_LIMIT),
            "inconclusive": reason,
        })

    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps({"queue_limit": QUEUE_LIMIT, "scenes": rows},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"ROM: {rom_path.name}   queue limit: {QUEUE_LIMIT}")
    print(f"{'stage':>5} {'nodes':>6} {'base':>5} {'+added':>7} {'free':>5}  status")
    for r in rows:
        if r["inconclusive"]:
            status = "N/A"
            print(f"{r['stage']:>5} {r['nodes']:>6} {'-':>5} {'-':>7} {'-':>5}  "
                  f"N/A (analysis inconclusive: {r['inconclusive']})")
            continue
        status = "OVER" if r["exceeds_limit"] else "ok"
        if r["baseline_already_exceeds"] and not r["exceeds_limit"]:
            status = "ok*"
        print(f"{r['stage']:>5} {r['nodes']:>6} {r['baseline_depth']:>5} "
              f"{r['depth_with_added']:>7} {r['headroom']:>5}  {status}")
    analyzed = [r for r in rows if not r["inconclusive"]]
    worst = max(analyzed, key=lambda r: r["baseline_depth"]) if analyzed else None
    if worst:
        print()
        print(f"deepest original scene: stage {worst['stage']} "
              f"-> {worst['baseline_depth']} queued events, "
              f"free {QUEUE_LIMIT - worst['baseline_depth']}")
    over = [r["stage"] for r in analyzed if r["baseline_already_exceeds"]]
    if over:
        print(f"stages whose *original* static depth already exceeds {QUEUE_LIMIT}: "
              f"{over}  (static over-approximation, not a runtime overflow)")
    na = [r["stage"] for r in rows if r["inconclusive"]]
    if na:
        print(f"scenes where the static walk does not terminate: {na}")
    issues = sum(r["decode_issues"] for r in rows)
    print(f"decode issues across all logic scripts: {issues}")
    print()
    print("usage rule: a scene can take at most (16 - its own baseline depth)")
    print("new conditional events; the static depth is an upper bound.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
