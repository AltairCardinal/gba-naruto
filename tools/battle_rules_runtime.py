#!/usr/bin/env python3
"""Runtime capture of the win/lose rule dispatcher arms (types 2 and 3).

What this tool does
-------------------
The static analysis in ``notes/reward-and-rules-semantics-20261020.md`` proved
that the type-2 arm at ``0x08077904`` compares the battle turn limit
(``0x0202680A``) with one byte of the per-battle counter block
(``0x0202680C``) and never reads the rule record at all, while the type-3
arm at ``0x08077924`` scans the battle unit array for a character id.

This tool *executes that native code inside the headless mGBA probe* and
records what the CPU actually does:

1. it boots the real ROM in the probe,
2. it writes a controlled battle state into WRAM with the debugger's own
   ``w/1`` / ``w/4`` commands,
3. it enters the native rule dispatcher (``0x080777FC``) - the code reads
   the *ROM* rule table, so the type of every rule it evaluates comes from
   the ROM, not from the harness - and it records the registers at the
   type-2 / type-3 arms through real breakpoints,
4. it then re-enters each arm directly (a synthetic caller) and single
   steps through it, so the *decision* of the arm is observable as the
   branch it takes,
5. it arms a read watchpoint on the rule record of each arm, which proves
   that the type-2 arm never reads ``rule.a`` / ``rule.b`` while the type-3
   arm does.

Every claim the tool prints is falsifiable: the falsifier is always
"change exactly one input byte and the decision must flip / not flip".

Usage:
    python tools/battle_rules_runtime.py rom/base.gba
    python tools/battle_rules_runtime.py rom/base.gba --json build/battle-rules-runtime.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools", REPO / "tools" / "mgba_probe"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import mechanism_map as mm  # noqa: E402
import reward_rules_semantics as rrs  # noqa: E402

try:
    from runtime_probe import Probe, parse_status  # noqa: E402
except ImportError as exc:  # pragma: no cover
    raise SystemExit(f"ERR cannot import the probe client: {exc}")

ROM_BASE = 0x08000000

# --- WRAM landmarks (see notes/runtime-and-object-tables-20261020.md) ------
BATTLE_CTRL = 0x02026804        # battle control block
CTRL_STAGE = BATTLE_CTRL + 1    # stage id
CTRL_SUB = BATTLE_CTRL + 2      # sub id
CTRL_FLAG = BATTLE_CTRL + 0     # ctrl[0]: non-zero keeps the dispatcher off the UI path
CTRL_TURN_LIMIT = BATTLE_CTRL + 6   # 0x0202680A, turn limit
COUNTER_BLOCK = 0x0202680C      # per-battle counter block, byte 0 is the gate value
UNIT_ARRAY = 0x020240C0         # battle unit array
UNIT_STRIDE = 0x01D4
UNIT_ID_OFFSET = 0xBC           # unit + 0xBC : character id (read by the type-3 arm)
UNIT_FLAGS_OFFSET = 0xC0       # unit + 0xC0 : flags word, bit0 = side
SCRATCH_STACK = 0x0203FF00      # stack for the injected call
TRAP_ADDRESS = 0x08500000       # return trap (ROM data area, never executed)
# mGBA keeps the Thumb flag in CPSR bit 5; the debugger's `w/r cpsr` masks
# the value with 0xF00000FF, so 0x3F = "Thumb + system mode" has to be
# written before the PC, otherwise the core would decode ARM instructions.
CPSR_THUMB = 0x3F

# --- rule evaluation ------------------------------------------------------
RULES_TABLE = 0x594758
RULE_STAGE_STRIDE = 0xCC
RULE_SUB_STRIDE = 0x44
RULE_GROUP_STRIDE = 0x20        # 4 rules * 8 bytes
RULE_SIZE = 8

# decision addresses inside the dispatcher (see the disassembly in the note)
SATISFIED_PATH = 0x08077B28     # "this rule is satisfied" continuation
NEXT_RULE_PATH = 0x08077B3A     # "this rule is not satisfied" continuation
TYPE2_EQUAL_BRANCH = 0x0807791E
TYPE3_SATISFIED = 0x0807798E
TYPE3_NEXT = 0x0807798C

STATUS_ADDR_RE = re.compile(r"^([0-9A-Fa-f]{8}):")


def rule_entry_address(stage: int, sub: int) -> int:
    """ROM address of the rules entry of one (stage, sub) pair."""
    return ROM_BASE + RULES_TABLE + stage * RULE_STAGE_STRIDE + sub * RULE_SUB_STRIDE


def rule_record_address(stage: int, sub: int, group: int, index: int) -> int:
    """ROM address of one rule record (type, a, b, c, text pointer)."""
    return (rule_entry_address(stage, sub) + 4
            + group * RULE_GROUP_STRIDE + index * RULE_SIZE)


def parse_pc(lines: list[str]) -> int | None:
    """Address of the instruction the debugger is about to execute."""
    for line in reversed(lines):
        match = STATUS_ADDR_RE.match(line.strip())
        if match:
            return int(match.group(1), 16)
    return None


class ArmProbe:
    """Drives the headless probe and executes one arm at a time."""

    def __init__(self, exe: pathlib.Path, rom: pathlib.Path):
        self.probe = Probe(exe, rom)
        self.watch_hits: list[str] = []

    def close(self) -> None:
        self.probe.close()

    # -- memory ----------------------------------------------------------
    def write_bytes(self, address: int, data: bytes) -> None:
        for offset, byte in enumerate(data):
            self.probe.send(f"w/1 {address + offset:#010x} {byte}")

    def read_bytes(self, address: int, length: int) -> bytes:
        return self.probe.read_bytes(address, length)

    # -- registers -------------------------------------------------------
    def set_registers(self, registers: dict[str, int]) -> None:
        for name, value in registers.items():
            self.probe.send(f"w/r {name} {value:#x}")

    def status(self) -> dict[str, int]:
        return parse_status(self.probe.send("status"))

    # -- execution -------------------------------------------------------
    def step_to_branch(self, limit: int = 160) -> list[int]:
        """Execute instruction by instruction (branch granularity) and
        return the visited instruction addresses."""
        path: list[int] = []
        for _ in range(limit):
            out = self.probe.send("next")
            pc = parse_pc(out)
            if pc is None:
                break
            path.append(pc)
            if pc in (SATISFIED_PATH, NEXT_RULE_PATH):
                break
        return path

    def run_arm(self, arm: int, registers: dict[str, int],
                steps: int = 240) -> dict:
        """Jump into `arm` with `registers` and record what it does."""
        self.set_registers(registers)
        self.probe.send(f"w/r pc {arm:#x}")
        entry = self.status()
        path = self.step_to_branch(steps)
        terminal = path[-1] if path else None
        return {
            "arm": f"0x{arm:08X}",
            "entry_registers": {k: f"0x{v:08X}" for k, v in sorted(entry.items())},
            "path": [f"0x{pc:08X}" for pc in path],
            "terminal": f"0x{terminal:08X}" if terminal else None,
        }

    # -- breakpoints -----------------------------------------------------
    def arm_breakpoint(self, address: int) -> int | None:
        for line in self.probe.send(f"b {address:#x}"):
            if "breakpoint #" in line:
                return int(line.split("#")[1].split()[0])
        return None

    def arm_read_watch(self, address: int) -> None:
        self.probe.send(f"watch/r {address:#x}")

    def clear_watch_hits(self) -> None:
        self.watch_hits = []

    def collect_watch_hits(self, lines: list[str]) -> list[str]:
        hits = [line for line in lines if "Hit watchpoint" in line]
        self.watch_hits.extend(hits)
        return hits


# --------------------------------------------------------------------------
# experiments
# --------------------------------------------------------------------------
def stage_with_type2(rom: bytes) -> tuple[int, int, dict, dict]:
    """The first (stage, sub) whose rules contain a type-2 and a type-3 row."""
    rules = rrs.rules_entries(rom)
    type2 = [r for r in rules if r["type"] == 2]
    type3 = [r for r in rules if r["type"] == 3]
    if not type2 or not type3:
        raise SystemExit("ERR the ROM has no type-2 / type-3 rule row")
    row = type2[0]
    twin = None
    for other in type3:
        if (other["stage"], other["sub"]) == (row["stage"], row["sub"]):
            twin = other
            break
    return row["stage"], row["sub"], row, twin


def prepare_state(arm: ArmProbe, *, stage: int, sub: int, turn_limit: int,
                  counter: int, character: int | None, side: int) -> None:
    """Write the battle state the dispatcher expects into WRAM."""
    # battle control block
    arm.write_bytes(BATTLE_CTRL, bytes([
        1,            # +0 ctrl[0]: non-zero -> stay off the message/UI path
        stage,        # +1 stage id
        sub,          # +2 sub id
        0, 0, 0,
        turn_limit,   # +6 turn limit (0x0202680A)
        0,            # +7
    ]))
    # counter block: byte 0 is the value the type-2 arm compares against
    arm.write_bytes(COUNTER_BLOCK, bytes([counter]))
    # unit array slot 1: the character the type-3 arm looks for
    unit1 = UNIT_ARRAY + UNIT_STRIDE
    if character is None:
        arm.write_bytes(unit1, bytes(1))
        arm.write_bytes(unit1 + UNIT_ID_OFFSET, bytes(1))
        arm.write_bytes(unit1 + UNIT_FLAGS_OFFSET, bytes(1))
    else:
        # unit + 0x00 = character id (0 means "empty slot"),
        # unit + 0xBC = copy of the character id,
        # unit + 0xC0 = flags word, bit0 = side.
        arm.write_bytes(unit1, bytes([character]))
        arm.write_bytes(unit1 + UNIT_ID_OFFSET, bytes([character]))
        arm.write_bytes(unit1 + UNIT_FLAGS_OFFSET, bytes([side & 1]))


def arm_decision(result: dict) -> str:
    """Classify where the arm went.

    The dispatcher continues at 0x08077B28 when a rule is *satisfied* and at
    0x08077B3A when it is *not*, so the terminal address of the step path is
    the arm's decision.
    """
    terminal = result["terminal"]
    if terminal is None:
        return "unknown"
    value = int(terminal, 16)
    if value == SATISFIED_PATH:
        return "satisfied"
    if value == NEXT_RULE_PATH:
        return "not-satisfied"
    return f"other(0x{value:08X})"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom", type=pathlib.Path)
    ap.add_argument("--exe", type=pathlib.Path, default=None)
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args()

    exe = args.exe or (REPO / "build" / "mgba-probe" / "mgba-probe.exe")
    if not exe.exists():
        print(f"ERR {exe} missing; run: python tools/mgba_probe/build.py",
              file=sys.stderr)
        return 2

    rom = args.rom.read_bytes()
    capstone = mm.load_capstone()
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    md.detail = False

    # Re-derive the arms from the ROM instead of trusting a hand written
    # address: find the dispatcher and its jump table.
    dispatch = rrs.find_rule_dispatch(rom, md, ROM_BASE + RULES_TABLE)
    if not dispatch:
        print("ERR could not locate the rule dispatcher in this ROM",
              file=sys.stderr)
        return 2
    arms = dispatch["arms"]
    arm2 = arms[2]
    arm3 = arms[3]
    stage, sub, row2, row3 = stage_with_type2(rom)
    turn_limit = row2["turn_limit"]

    record2 = rule_record_address(stage, sub, row2["group"], row2["index"])
    record3 = (rule_record_address(stage, sub, row3["group"], row3["index"])
               if row3 else None)

    out: dict = {
        "rom": str(args.rom),
        "dispatch_table": f"0x{dispatch['table_addr']:08X}",
        "arms": {str(t): f"0x{addr:08X}" for t, addr in sorted(arms.items())},
        "stage": stage,
        "sub": sub,
        "turn_limit": turn_limit,
        "type2_rule": {
            "record": f"0x{record2:08X}",
            "group": row2["group"], "index": row2["index"],
            "a": row2["a"], "b": row2["b"], "c": row2["c"],
        },
        "type3_rule": ({"record": f"0x{record3:08X}", "group": row3["group"],
                        "index": row3["index"], "a": row3["a"], "b": row3["b"]}
                       if row3 else None),
        "experiments": [],
    }

    print(f"ROM                : {args.rom}")
    print(f"rule dispatcher    : table 0x{dispatch['table_addr']:08X}, "
          f"entry 0x{dispatch['dispatch_addr']:08X}")
    print(f"type 2 arm         : 0x{arm2:08X}")
    print(f"type 3 arm         : 0x{arm3:08X}")
    print(f"stage / sub        : {stage} / {sub}   (turn limit {turn_limit})")
    print(f"type-2 rule record : 0x{record2:08X}  a={row2['a']} b={row2['b']}")
    if row3:
        print(f"type-3 rule record : 0x{record3:08X}  a={row3['a']} b={row3['b']}")

    probe = ArmProbe(exe, args.rom)
    try:
        probe.probe.send("frames 300 0x000")

        # ---------------------------------------------------------------
        # 1. native dispatcher run: the ROM rule table decides the arm
        # ---------------------------------------------------------------
        prepare_state(probe, stage=stage, sub=sub, turn_limit=turn_limit,
                      counter=turn_limit, character=row2["b"], side=row2["a"])
        bp2 = probe.arm_breakpoint(arm2)
        bp3 = probe.arm_breakpoint(arm3)
        probe.set_registers({
            "r0": 1,                      # mode: settlement check
            "r8": record2 - ROM_BASE,     # rule pointer (the dispatcher recomputes it)
            "r5": record2,
            "sp": SCRATCH_STACK,
            "lr": TRAP_ADDRESS,
            "cpsr": CPSR_THUMB,
        })
        probe.probe.send(f"w/r pc {0x080777FC:#x}")
        out_lines = probe.probe.send("frames 20 0x000")
        dispatcher_hits = probe.collect_watch_hits(out_lines)
        regs = probe.status()
        out["dispatcher_run"] = {
            "entry": "0x080777FC",
            "mode": 1,
            "breakpoints": {"type2": bp2, "type3": bp3},
            "registers": {k: f"0x{v:08X}" for k, v in sorted(regs.items())},
            "watch_hits": dispatcher_hits,
        }
        print()
        print("== native dispatcher run (mode=1) ==")
        print(f"   registers at the stop: "
              f"{ {k: f'0x{v:08X}' for k, v in sorted(regs.items())} }")
        print(f"   ctrl[6] (turn limit) = "
              f"{probe.read_bytes(CTRL_TURN_LIMIT, 1)[0]}, "
              f"byte[0x0202680C] = {probe.read_bytes(COUNTER_BLOCK, 1)[0]}")
        for key in ("bp2", "bp3"):
            ident = out["dispatcher_run"]["breakpoints"][
                "type2" if key == "bp2" else "type3"]
            if ident is not None:
                probe.probe.send(f"delete {ident}")

        # ---------------------------------------------------------------
        # 2. arm level decision matrix
        # ---------------------------------------------------------------
        matrix = []
        cases = [
            ("type2 mode=1 limit=15 counter=15", arm2,
             dict(mode=1, turn_limit=turn_limit, counter=turn_limit),
             "satisfied"),
            ("type2 mode=1 limit=15 counter=14", arm2,
             dict(mode=1, turn_limit=turn_limit, counter=turn_limit - 1),
             "not-satisfied"),
            ("type2 mode=0 limit=15 counter=15", arm2,
             dict(mode=0, turn_limit=turn_limit, counter=turn_limit),
             "not-satisfied"),
            ("type2 mode=1 limit=0  counter=0", arm2,
             dict(mode=1, turn_limit=0, counter=0),
             "not-satisfied"),
            ("type2 mode=1 limit=15 counter=15, character absent", arm2,
             dict(mode=1, turn_limit=turn_limit, counter=turn_limit,
                  character=None),
             "satisfied"),
            ("type3 character present", arm3,
             dict(mode=1, turn_limit=turn_limit, counter=turn_limit,
                  character=row3["b"] if row3 else 31),
             "not-satisfied"),
            ("type3 character absent", arm3,
             dict(mode=1, turn_limit=turn_limit, counter=turn_limit,
                  character=None),
             "satisfied"),
        ]
        print()
        print("== arm decision matrix (native execution in the probe) ==")
        for label, arm, cfg, expected in cases:
            mode = cfg.pop("mode")
            turn = cfg.pop("turn_limit")
            counter = cfg.pop("counter")
            character = cfg.pop("character", row2["b"])
            prepare_state(probe, stage=stage, sub=sub, turn_limit=turn,
                          counter=counter, character=character, side=row2["a"])
            registers = {
                "r0": mode,
                "r8": mode,            # the dispatcher keeps the mode in r8
                "r5": record2 if arm == arm2 else (record3 or 0),
                "r6": BATTLE_CTRL,
                "sp": SCRATCH_STACK,
                "lr": TRAP_ADDRESS,
                "cpsr": CPSR_THUMB,
            }
            result = probe.run_arm(arm, registers)
            decision = arm_decision(result)
            ok = decision == expected
            result.update({"case": label, "mode": mode, "turn_limit": turn,
                           "counter": counter, "character": character,
                           "decision": decision, "expected": expected,
                           "agrees": ok})
            matrix.append(result)
            print(f"   {label:48s} -> {decision:14s} "
                  f"(expected {expected}, {'OK' if ok else 'MISMATCH'})")
            tail = result["path"][-8:]
            print(f"       path tail: {' -> '.join(tail)}")
            print(f"       r0={result['entry_registers'].get('r0')} "
                  f"r5={result['entry_registers'].get('r5')} "
                  f"r6={result['entry_registers'].get('r6')} "
                  f"r8={result['entry_registers'].get('r8')} "
                  f"pc={result['entry_registers'].get('r15')}")
        out["decision_matrix"] = matrix
    finally:
        probe.close()

    # ---------------------------------------------------------------
    # 3. does the arm read rule.a / rule.b ?
    #
    # Two independent tests:
    #  a) a read watchpoint on the rule record (plus a WRAM control that
    #     the arm is known to read, to prove the watchpoint works at all),
    #  b) a behavioural test: point r5 at a RAM buffer full of 0xFF and
    #     at the *other* arm's rule record; the decision must not move.
    # ---------------------------------------------------------------
    print()
    print("== does the arm read rule.a / rule.b ? ==")
    watch = []
    for label, arm, record, expect in (
            ("type 2 record", arm2, record2, "no hit"),
            ("type 3 record", arm3, record3, "hit"),
            ("WRAM control", arm2, COUNTER_BLOCK, "hit")):
        if record is None:
            continue
        session = ArmProbe(exe, args.rom)
        try:
            session.probe.send("frames 300 0x000")
            session.arm_read_watch(record)
            prepare_state(session, stage=stage, sub=sub, turn_limit=turn_limit,
                          counter=turn_limit, character=row2["b"], side=row2["a"])
            registers = {
                "r0": 1, "r8": 1, "r5": record, "r6": BATTLE_CTRL,
                "sp": SCRATCH_STACK, "lr": TRAP_ADDRESS, "cpsr": CPSR_THUMB,
            }
            result = session.run_arm(arm, registers)
            hits = list(session.watch_hits)
            watch.append({"case": label, "record": f"0x{record:08X}",
                          "expected": expect, "hits": hits,
                          "path_tail": result["path"][-6:]})
            print(f"   {label:16s} 0x{record:08X}: "
                  f"{len(hits)} watchpoint hit(s) - expected {expect}")
            for hit in hits:
                print(f"       {hit}")
        finally:
            session.close()
    out["read_watchpoints"] = watch

    # behavioural test: the type-2 arm must ignore whatever r5 points at
    behaviour = []
    for label, r5_value in (("rule record of the type-2 row", record2),
                            ("rule record of the type-3 row", record3 or 0),
                            ("RAM buffer full of 0xFF", 0x0203FF80)):
        session = ArmProbe(exe, args.rom)
        try:
            session.probe.send("frames 300 0x000")
            if r5_value == 0x0203FF80:
                session.write_bytes(r5_value, b"\xff" * 8)
            prepare_state(session, stage=stage, sub=sub, turn_limit=turn_limit,
                          counter=turn_limit, character=row2["b"], side=row2["a"])
            registers = {
                "r0": 1, "r8": 1, "r5": r5_value, "r6": BATTLE_CTRL,
                "sp": SCRATCH_STACK, "lr": TRAP_ADDRESS, "cpsr": CPSR_THUMB,
            }
            result = session.run_arm(arm2, registers)
            decision = arm_decision(result)
            behaviour.append({"case": label, "r5": f"0x{r5_value:08X}",
                              "decision": decision})
            print(f"   type-2 arm with r5 = {label:32s} -> {decision}")
        finally:
            session.close()
    out["type2_rule_pointer_independence"] = behaviour

    # ---------------------------------------------------------------
    # verdict
    # ---------------------------------------------------------------
    by_case = {row["case"]: row for row in matrix}
    control = [row for row in watch if row["case"] == "WRAM control"]
    watch_works = bool(control and control[0]["hits"])
    type2_hits = [row for row in watch if row["case"] == "type 2 record"]
    type2_hits = type2_hits[0]["hits"] if type2_hits else []
    behaviour_ok = all(row["decision"] == "satisfied" for row in behaviour)
    verdict = {
        "type2_compares": "battle turn limit (0x0202680A) vs counter byte "
                          "(0x0202680C)",
        "read_watchpoint_works_on_wram": watch_works,
        "type2_reads_rule_record": bool(type2_hits) if watch_works else None,
        "type2_ignores_rule_pointer": behaviour_ok,
        "type2_is_turn_limit_gate": (
            by_case["type2 mode=1 limit=15 counter=15"]["decision"] == "satisfied"
            and by_case["type2 mode=1 limit=15 counter=14"]["decision"]
            == "not-satisfied"),
        "type2_ignores_character": (
            by_case["type2 mode=1 limit=15 counter=15, character absent"]
            ["decision"] == "satisfied"),
        "type3_is_character_left_field": (
            by_case["type3 character present"]["decision"] == "not-satisfied"
            and by_case["type3 character absent"]["decision"] == "satisfied"),
        "type2_is_type3_inverse": False,
    }
    verdict["type2_is_type3_inverse"] = (
        verdict["type2_ignores_character"]
        and verdict["type2_ignores_rule_pointer"]
        and by_case["type3 character present"]["decision"] != "satisfied")
    out["verdict"] = verdict

    print()
    print("== verdict ==")
    print(f"   type-2 arm compares      : {verdict['type2_compares']}")
    print(f"   type-2 reads rule record : {verdict['type2_reads_rule_record']}"
          f"   (read watchpoint usable on WRAM: "
          f"{verdict['read_watchpoint_works_on_wram']})")
    print(f"   type-2 ignores rule ptr  : {verdict['type2_ignores_rule_pointer']}")
    print(f"   type-2 == turn limit gate: {verdict['type2_is_turn_limit_gate']}")
    print(f"   type-2 ignores character : {verdict['type2_ignores_character']}")
    print(f"   type-3 == left the field : {verdict['type3_is_character_left_field']}")
    print(f"   type-2 is type-3 inverse : {verdict['type2_is_type3_inverse']}")

    if args.json:
        from tools.lib.io import write_json
        write_json(args.json, out)

    failures = [row["case"] for row in matrix if not row["agrees"]]
    if failures:
        print(f"ERR unexpected arm decisions: {failures}", file=sys.stderr)
        return 1
    if not behaviour_ok:
        print("ERR the type-2 arm reacted to the rule pointer", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
