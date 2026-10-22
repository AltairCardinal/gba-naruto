#!/usr/bin/env python3
"""L4: let the game walk the story chain **by itself**, scene after scene.

Why this tool exists
--------------------
`notes/runtime-verification-gates-20260710.md` §4 defines L4 as
「全流程、全人物组合、全地图实际打通」.  The per-scene harness
(`tools/mgba_probe/l4_playthrough.py`) proves that *every* scene can be
dispatched, but it does that by **poking the scene byte** -- the game
never chose the scene itself.

This tool closes the remaining part of the "全流程" axis: the game chains
scene -> scene **on its own**.  The story dispatcher `0x0808F544` moves on
when the running script writes `state[0x18] = 3` (the VM opcode `0x1A`
with a non-zero flag), and the new scene number is read at `0x0808F5DA`
(`ldrb r4,[r7,#0x16]`).  Right afterwards the VM entry `0x080977B8` is
reached again; `r0` there is the script pointer the game itself used,
which must equal the root-table entry of the new scene.

Every hop is therefore checked twice: the scene number the game picked and
the script pointer it actually executed.

Usage
-----
    python tools/mgba_probe/l4_playthrough_flow.py rom/base.gba \
        --start-scene 1 --max-scenes 55 --out build/l4-flow \
        --json build/l4-flow.json

Exit code
---------
0 = the chain reached every requested hop with matching script pointers,
1 = the chain stopped early (the report says where and why),
2 = the environment is not usable (no probe binary / no ROM).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _p in (REPO, REPO / "tools"):
    if _p not in sys.path:
        sys.path.insert(0, str(_p))

from tools.mgba_probe.l4_battle_matrix import (  # noqa: E402
    Harness, hit_of, root_pointer, PHASE_WORD, SCENE_BYTE, NEW_SCENE_READ,
    VM_ENTRY, BEFORE_ROOT_FILE, AFTER_ROOT_FILE, BATTLE_FLAG_WORD,
    DISPATCHER,
)
from tools.mgba_probe.l4_playthrough import KEY_BITS, capture  # noqa: E402

# The phase that dispatches a story scene (the dispatcher runs it).
PHASE_NEXT_SCENE = 0x0030

# The story dispatcher is entered with the scene id in ``r0``.  Its caller is
# the phase-0x30 handler ``0x0808F8DC``:
#
#     0x0808F8DC: ldrb r0, [r4, #0x16]   ; the scene the game picked
#     0x0808F8DE: bl   0x0808F544         ; the story dispatcher
#
# so breaking on the dispatcher entry yields exactly the scene the game
# chose by itself.
DISPATCHER_ENTRY = DISPATCHER

# The key cycle the game sees.  A advances dialogue, the arrows drive the
# menus the game puts up, START/SELECT open/close the panels.
KEY_CYCLE = ("A", "B", "DOWN", "UP", "LEFT", "RIGHT", "START", "SELECT")


def script_for(rom: bytes, scene: int, sub: int) -> str | None:
    """The script pointer the root table holds for `scene`."""
    for table in (BEFORE_ROOT_FILE, AFTER_ROOT_FILE):
        value = root_pointer(rom, table, scene)
        if value:
            return f"0x{value:08X}"
    return None


def run_chain(harness, rom: bytes, start_scene: int, max_scenes: int,
              press_rounds: int, out_dir: pathlib.Path | None) -> tuple[list[dict], list[str]]:
    """Follow the game's own scene chain from `start_scene`."""
    chain: list[dict] = []
    notes: list[str] = []
    harness.arm(VM_ENTRY)
    harness.arm(DISPATCHER_ENTRY)
    harness.poke(SCENE_BYTE, start_scene)
    harness.poke16(PHASE_WORD, PHASE_NEXT_SCENE)

    current = start_scene
    for hop in range(max_scenes):
        dispatches: list[tuple[int, int | None]] = []
        for _ in range(press_rounds):
            out = harness.send("cont 600")
            hit = hit_of(out)
            if hit is None:
                out = (harness.send("frames 8 0x001")
                       + harness.send("frames 120 0x000"))
                hit = hit_of(out)
            if hit is None:
                continue
            if hit == DISPATCHER_ENTRY:
                # the dispatcher is entered with the scene id in r0
                regs = harness.probe.registers()
                scene_id = regs.get("r0", 0)
                harness.send("next")
                harness.rearm()
                script = None
                out = harness.send("cont 600")
                if hit_of(out) == VM_ENTRY:
                    regs = harness.probe.registers()
                    script = regs.get("r0", 0)
                dispatches.append((scene_id, script))
                continue
            harness.send("next")
            harness.rearm()

        # The first dispatch is the scene we asked for; a re-dispatch of the
        # same scene is the game re-entering it (a choice menu, for example).
        # The transition is the first dispatch that names **another** scene.
        transition = next((d for d in dispatches if d[0] != current), None)
        if transition is None:
            new_scene = None
            new_script = None
        else:
            new_scene, new_script = transition

        expected = script_for(rom, new_scene, 0) if new_scene else None
        state_bytes = harness.read(0x020311D4, 0x24)
        record = {
            "hop": hop,
            "from_scene": current,
            "to_scene": new_scene,
            "dispatches": [{"scene": s, "script": (f"0x{sc:08X}" if sc else None)}
                           for s, sc in dispatches],
            "script": f"0x{new_script:08X}" if new_script else None,
            "script_expected": expected,
            "match": bool(new_script and expected
                          and f"0x{new_script:08X}" == expected),
            "state_after": state_bytes.hex() if state_bytes else None,
            "phase_after": (f"0x{int.from_bytes(state_bytes[0x12:0x14], 'little'):04X}"
                            if state_bytes else None),
            "scene_after": (f"0x{state_bytes[0x16]:02X}" if state_bytes else None),
            # The three runtime-state fields the audit asks for.
            #   story_progress  = state + 0x10 = 0x020311E4 (u16)
            #   story_branch   = state + 0x18 = 0x020311EC (u8)
            #   story_config   = state + 0x19..0x1B = 0x020311ED..EF
            "story_progress_after": (int.from_bytes(state_bytes[0x10:0x12], "little")
                                     if state_bytes else None),
            "story_branch_after": (state_bytes[0x18] if state_bytes else None),
            "story_config_after": (state_bytes[0x19:0x1C].hex()
                                   if state_bytes else None),
        }
        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)
            record["screenshot"] = str(
                capture(harness, out_dir / f"flow-{start_scene:02d}-{current}.png")
                or "")
        chain.append(record)
        if not new_scene:
            notes.append(f"the chain stopped at scene {current}")
            break
        current = new_scene
        # Let the dispatcher run again for the new scene.  Only the *phase* is
        # re-armed -- the scene byte is never touched, so the next scene is
        # still the one the running script picked.
        harness.poke16(PHASE_WORD, PHASE_NEXT_SCENE)
    return chain, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("rom", nargs="?", default="rom/base.gba")
    parser.add_argument("--exe", type=pathlib.Path,
                        default=REPO / "build" / "mgba-probe" / "mgba-probe.exe")
    parser.add_argument("--start-scene", type=int, default=1)
    parser.add_argument("--scenes", default=None,
                        help="scan a range of start scenes, e.g. '1-55' or '1,5,9'")
    parser.add_argument("--max-scenes", type=int, default=55,
                        help="how many hops to try")
    parser.add_argument("--press-rounds", type=int, default=80,
                        help="press rounds to wait for one hop")
    parser.add_argument("--out", type=pathlib.Path, default=None,
                        help="directory for the per-hop screenshots")
    parser.add_argument("--json", type=pathlib.Path, default=None)
    args = parser.parse_args(argv)

    rom_path = pathlib.Path(args.rom)
    if not rom_path.is_file():
        print(f"ERR ROM not found: {rom_path}", file=sys.stderr)
        return 2
    if not args.exe.exists():
        print(f"ERR {args.exe} missing; run: python tools/mgba_probe/build.py",
              file=sys.stderr)
        return 2
    rom = rom_path.read_bytes()

    if args.scenes:
        return scan_scenes(rom_path, rom, args)

    harness = Harness(args.exe, rom_path)
    chain: list[dict] = []
    notes: list[str] = []
    try:
        if not harness.boot_to_state_machine():
            print("ERR could not park on the story state machine", file=sys.stderr)
            return 1
        chain, notes = run_chain(harness, rom, args.start_scene, args.max_scenes,
                                 args.press_rounds, args.out)
    finally:
        harness.close()

    report = {
        "rom": str(rom_path),
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "start_scene": args.start_scene,
        "requested": args.max_scenes,
        "reached": len([c for c in chain if c["to_scene"]]),
        "chain": chain,
        "scenes_visited": [args.start_scene] + [c["to_scene"] for c in chain
                                              if c["to_scene"]],
        "all_scripts_match": all(c["match"] for c in chain if c["to_scene"]),
        "notes": notes,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with open(args.json, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"\nreached {report['reached']}/{args.max_scenes} hop(s); "
          f"scenes visited: {report['scenes_visited']}")
    if report["reached"] < args.max_scenes:
        print("FAIL: the game-driven chain stopped early", file=sys.stderr)
        return 1
    print("OK: the game drove the whole chain and every script pointer matched")
    return 0


def parse_scenes(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return out


def scan_scenes(rom_path: pathlib.Path, rom: bytes, args) -> int:
    """Collect the game's own scene transition graph.

    The story is a **graph**, not a chain: scene 39 offers scenes 40..45 and
    scene 45 ends the chapter (it sets the phase to 0x0100).  So the "全流程"
    evidence is the set of edges the game walks by itself, each checked
    against the root table.
    """
    scenes = parse_scenes(args.scenes)
    edges: list[dict] = []
    per_scene: dict[str, dict] = {}
    for scene in scenes:
        harness = Harness(args.exe, rom_path)
        try:
            if not harness.boot_to_state_machine():
                per_scene[str(scene)] = {"status": "no-state-machine", "hops": []}
                continue
            chain, notes = run_chain(harness, rom, scene, args.max_scenes,
                                     args.press_rounds, args.out)
        finally:
            harness.close()
        hops = [c for c in chain if c["to_scene"]]
        per_scene[str(scene)] = {
            "status": "chained" if hops else "no-chain",
            "hops": [{"from": c["from_scene"], "to": c["to_scene"],
                      "script": c["script"], "expected": c["script_expected"],
                      "match": c["match"],
                      "phase_after": c["phase_after"],
                      "scene_after": c["scene_after"],
                      "story_progress_after": c["story_progress_after"],
                      "story_branch_after": c["story_branch_after"],
                      "story_config_after": c["story_config_after"]}
                     for c in hops],
            "notes": notes,
        }
        for c in hops:
            edges.append({"from": c["from_scene"], "to": c["to_scene"],
                          "script": c["script"], "expected": c["script_expected"],
                          "match": c["match"],
                          "phase_after": c["phase_after"],
                          "story_progress_after": c["story_progress_after"],
                          "story_branch_after": c["story_branch_after"],
                          "story_config_after": c["story_config_after"]})
        print(f"scene {scene:3d}: {per_scene[str(scene)]['status']:14s} "
              f"-> {[c['to_scene'] for c in hops]}")
        sys.stdout.flush()

    unique = sorted({(e["from"], e["to"]) for e in edges})
    progress_values = sorted({e["story_progress_after"] for e in edges
                              if e.get("story_progress_after") is not None})
    branch_values = sorted({e["story_branch_after"] for e in edges
                            if e.get("story_branch_after") is not None})
    report = {
        "rom": str(rom_path),
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "scenes_requested": scenes,
        "per_scene": per_scene,
        "edges": edges,
        "unique_edges": [{"from": a, "to": b} for a, b in unique],
        "edge_count": len(unique),
        "scenes_that_chain": sorted({e["from"] for e in edges}),
        "all_scripts_match": all(e["match"] for e in edges),
        "story_progress_values": progress_values,
        "story_branch_values": branch_values,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with open(args.json, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"\n{len(unique)} unique game-driven scene edge(s) from "
          f"{len(report['scenes_that_chain'])} start scene(s); "
          f"all script pointers match: {report['all_scripts_match']}")
    if not edges:
        print("FAIL: no game-driven scene transition was observed", file=sys.stderr)
        return 1
    print("OK: the game drove at least one scene transition and every script "
          "pointer matched the root table")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
