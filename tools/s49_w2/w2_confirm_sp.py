#!/usr/bin/env python3
"""W2 (wave 18): what exactly happens when the player presses A on "はい"?

The symptom (U4) is that the 「可以嗎?」 dialog cannot be confirmed: the product
either prints ``CANNOT SELECT`` and then stops, or stops outright.

This instrument answers three questions with data instead of impressions:

1. **Is the dialog itself alive?**  The scene is left alone at phase 20
   (``target_confirmation``) for a fixed number of frames.  If ``scene_frame``
   keeps advancing, the dialog is only *waiting* and the freeze is caused by
   the A press, not by the dialog.
2. **What is the rejection criterion?**  The remake publishes the scene's own
   error codes in its telemetry struct (``last_control_error``,
   ``last_player_error``, ``selected_action_error``).  They are read right
   after the A press.
3. **Did the user stack overflow?**  The user stack grows down from
   ``__sp_usr`` (0x03007F00) to 0x03002BC4; the devkitARM ``IRQ_VectorTable``
   lives at 0x03002880, i.e. **832 bytes below the stack bottom**, so a stack
   overflow scribbles over it.  The table is dumped before and after the A
   press, and a hardware breakpoint is planted on the deepest frame of the
   attack-confirmation chain so the **minimum sp** of that chain can be read
   out of the live machine.

Usage::

    python tools/s49_w2/w2_confirm_sp.py --rom <rom> --out build/w18-w2/run/sp
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
BALANCE = REPO / "tools" / "s49_battle_balance"
if str(BALANCE) not in sys.path:
    sys.path.insert(0, str(BALANCE))

import w1_boot  # noqa: E402
import w1_probe as probe_module  # noqa: E402
import x1_telemetry  # noqa: E402
import v1_battle  # noqa: E402
import v1_truth  # noqa: E402

# The devkitARM interrupt vector table (14 entries x 4 bytes).
IRQ_TABLE = 0x03002880
IRQ_TABLE_WORDS = 16
# The user stack bottom (the lowest IWRAM data block is mm_fetch at 0x03002A34,
# so the stack may reach 0x03002BC4) and the user stack top.
STACK_BOTTOM = 0x03002BC4
STACK_TOP = 0x03007F00

# Breakpoints on the attack-confirmation chain (addresses taken from
# build/w18-w2/butano-sequel/build/butano-sequel.map, i.e. from *this* ROM).
BP_POINTS = {
    # battle_scene_controller::_confirm_target
    "confirm": 0x08030764,
    # battle_action_resolver::resolve_area_draft_in_place
    "area": 0x0802E840,
    # battle_action_resolver::resolve_draft_in_place
    "draft": 0x0802F3B8,
    # battle_action_resolver::_resolve_battlefield_object_event_in_place
    "obj_in_place": 0x0802D1DC,
    # battle_action_resolver::resolve_battlefield_object_event, after
    # `add sp, r4` (r4 = -8068): the lowest sp of the deepest frame
    "deepest": 0x0802D646,
}
BP_CONFIRM_TARGET = BP_POINTS["confirm"]
BP_DEEPEST = BP_POINTS["deepest"]


class BoundedProbe(probe_module.Probe):
    """A probe whose stderr is counted, not accumulated.

    ``w1_probe.Probe`` keeps every stderr line in a list.  A ROM that spins in
    the BIOS illegal-instruction handler emits millions of lines, which costs
    hundreds of megabytes of RAM.  This subclass keeps only the tail.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.stderr_lines = 0
        self.stderr_tail: list[str] = []

    def _drain_stderr(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        for line in self._proc.stderr:
            self.stderr_lines += 1
            self.stderr_tail.append(line.rstrip("\r\n"))
            if len(self.stderr_tail) > 60:
                del self.stderr_tail[:30]


def words(blob: bytes, base: int) -> list[str]:
    return [f"{base + offset:08X}:{int.from_bytes(blob[offset:offset + 4], 'little'):08X}"
            for offset in range(0, len(blob) - 3, 4)]


def registers(probe: BoundedProbe) -> dict[str, int]:
    """Read the CPU registers out of mGBA's own debugger.

    mGBA prints them as ``r13: 03007FE8`` -- the name and the value are two
    separate tokens, so the value has to be taken from the token *after* the
    colon, not from the colon token itself.
    """
    out: dict[str, int] = {}
    for line in probe.run("status"):
        tokens = line.split()
        for index, token in enumerate(tokens):
            if not token.endswith(":"):
                continue
            name = token[:-1]
            if not (name.startswith("r") and name[1:].isdigit()):
                continue
            if index + 1 >= len(tokens):
                continue
            try:
                out[name] = int(tokens[index + 1], 16)
            except ValueError:
                continue
    return out


def parse_cell(text: str) -> tuple[int, int]:
    x, _, y = text.partition(",")
    return int(x), int(y)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--truth", type=pathlib.Path,
                        default=REPO / "build" / "v1" / "battle-truth.json")
    parser.add_argument("--move-cell", type=str, default="9,6")
    parser.add_argument("--action-index", type=int, default=3)
    parser.add_argument("--target", type=str, default="6,6")
    parser.add_argument("--control-frames", type=int, default=120,
                        help="frames left alone at phase 20 before the A press")
    parser.add_argument("--bp", type=str, default="deepest",
                        choices=sorted(BP_POINTS) + ["none"],
                        help="which breakpoint of the chain to arm")
    parser.add_argument("--watch", type=str, default="",
                        help="address of a write watchpoint (e.g. 0x03002880)")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    truth = v1_truth.load(args.truth)
    move_cell = parse_cell(args.move_cell)
    target = parse_cell(args.target)
    record: dict[str, object] = {
        "rom": str(args.rom),
        "rom_sha256": v1_battle.y1_play.sha256_file(args.rom),
        "move_cell": list(move_cell),
        "action_index": args.action_index,
        "target": list(target),
        "stack_bottom": f"0x{STACK_BOTTOM:08X}",
        "stack_top": f"0x{STACK_TOP:08X}",
        "irq_table": f"0x{IRQ_TABLE:08X}",
    }

    with BoundedProbe(args.rom, exe=args.exe) as probe:
        boot = w1_boot.Boot(probe, args.out / "boot")
        boot.run()
        telemetry = x1_telemetry.Telemetry(probe)
        driver = v1_battle.Battle(probe, telemetry, args.out, verbose=False,
                                  truth=truth)

        # ---- drive the turn up to the action list ----------------------
        for _ in range(200):
            values = telemetry.read()
            if values["phase"] == 6:
                break
            if values["phase"] == 18:
                driver.advance_dialogue()
            elif values["phase"] == 23:
                driver.press("A", 4)
                driver.wait(30)
                driver.settle()
            elif values["phase"] == 1:
                driver.select_actor()
            elif values["phase"] == 3:
                driver.do_command()
            elif values["phase"] == 2:
                driver.plan = {"path": [(values["cursor_x"], values["cursor_y"]),
                                        move_cell],
                               "cell": move_cell}
                driver.do_move()
            else:
                driver.wait(30)

        for _ in range(args.action_index):
            driver.press("Down", 2)
            driver.wait(8)

        # action selection -> target selection -> target preview -> the
        # 「可以嗎?」 dialog (phase 20 = target_confirmation).
        driver.press("A", 4)
        driver.wait(30)
        driver.place_cursor(target)
        driver.press("A", 4)
        driver.wait(30)
        driver.press("A", 4)
        driver.wait(30)

        values = telemetry.read()
        record["at_phase20"] = dict(values)
        print("at-phase20  phase={phase} frame={scene_frame} "
              "cursor=({cursor_x},{cursor_y}) ctrl={last_control_error} "
              "player={last_player_error} act_err={selected_action_error}"
              .format(**values), flush=True)

        # ---- 1. control: leave the dialog alone ------------------------
        before = telemetry.read()["scene_frame"]
        driver.wait(args.control_frames)
        after = telemetry.read()["scene_frame"]
        record["control"] = {"frames": args.control_frames,
                             "scene_frame_before": before,
                             "scene_frame_after": after,
                             "advanced": after > before}
        print(f"control     frame {before} -> {after} "
              f"(advanced={after > before})", flush=True)

        # ---- 2. the state right before the A press ---------------------
        table_before = telemetry._dump(IRQ_TABLE, IRQ_TABLE_WORDS * 4)
        regs_before = registers(probe)
        record["irq_table_before"] = words(table_before, IRQ_TABLE)
        record["registers_before"] = {k: f"0x{v:08X}"
                                      for k, v in regs_before.items()}
        print("irq-before  " + " ".join(record["irq_table_before"][:6]),
              flush=True)
        print("sp-before   0x%08X  pc 0x%08X"
              % (regs_before.get("r13", 0), regs_before.get("r15", 0)),
              flush=True)

        # ---- 3. plant the breakpoints and press A ----------------------
        armed = BP_POINTS[args.bp] if args.bp != "none" else 0
        bp_out = []
        if armed:
            bp_out = probe.run(f"break {armed:#010x}")
            print("breakpoint  " + " | ".join(bp_out)
                  + f"  (at {armed:#010x})", flush=True)
        record["breakpoints"] = bp_out
        record["breakpoint_address"] = f"0x{armed:08X}" if armed else ""

        # A write watchpoint on the interrupt vector table: it fires on the
        # very first write to 0x03002880, which is the moment the user stack
        # overflows into it.  The program counter then names the writer and
        # the stack pointer gives the chain's low-water mark.
        watch_out = []
        if args.watch:
            watch_out = probe.run(f"watch/w {int(args.watch, 0):#010x}")
            print("watchpoint  " + " | ".join(watch_out)
                  + f"  (at {int(args.watch, 0):#010x})", flush=True)
        record["watchpoint"] = watch_out

        # The A press itself, so that the probe's answer to "did a breakpoint
        # fire?" is visible.
        probe.run("frames 1 0x00000000")
        press_out = probe.run("frames 4 0x00000001")
        print("press       " + " | ".join(press_out), flush=True)
        record["press"] = press_out

        hits: list[dict[str, object]] = []
        regs = registers(probe)
        pc = regs.get("r15", 0)
        sp = regs.get("r13", 0)
        fired = any("Hit breakpoint" in line or "Hit watchpoint" in line
                    for line in press_out)
        print("pc=%08X sp=%08X lr=%08X fired=%s"
              % (pc, sp, regs.get("r14", 0), fired), flush=True)
        if fired:
            hits.append({"pc": f"0x{pc:08X}",
                         "sp": f"0x{sp:08X}",
                         "lr": f"0x{regs.get('r14', 0):08X}",
                         "breakpoint": f"0x{armed:08X}",
                         "sp_below_stack_bottom": sp < STACK_BOTTOM,
                         "bytes_below_stack_bottom": STACK_BOTTOM - sp})
            print("HIT         pc=%s sp=%s (%+d bytes vs the stack "
                  "bottom 0x%08X)" % (hits[-1]["pc"], hits[-1]["sp"],
                                      hits[-1]["bytes_below_stack_bottom"],
                                      STACK_BOTTOM), flush=True)
            for line in probe.run("listb"):
                token = line.split(":")[0].strip().split()
                if token and token[-1].isdigit():
                    try:
                        probe.run(f"delete {token[-1]}")
                    except Exception:  # noqa: BLE001
                        pass
            for line in probe.run("listw"):
                token = line.split(":")[0].strip().split()
                if token and token[-1].isdigit():
                    try:
                        probe.run(f"delete {token[-1]}")
                    except Exception:  # noqa: BLE001
                        pass
            probe.run("frames 2 0x00000000")
        record["hits"] = hits

        # ---- 4. let the machine settle into whatever it becomes ---------
        for step in range(10):
            probe.run("frames 30 0x00000000")
            values_after = telemetry.read()
            print("post        phase=%d frame=%d ctrl=%d player=%d act_err=%d"
                  % (values_after["phase"], values_after["scene_frame"],
                     values_after["last_control_error"],
                     values_after["last_player_error"],
                     values_after["selected_action_error"]), flush=True)
        regs_after = registers(probe)
        table_after = telemetry._dump(IRQ_TABLE, IRQ_TABLE_WORDS * 4)
        values_after = telemetry.read()
        record["irq_table_after"] = words(table_after, IRQ_TABLE)
        record["registers_after"] = {k: f"0x{v:08X}"
                                     for k, v in regs_after.items()}
        record["after"] = dict(values_after)
        print("irq-after   " + " ".join(record["irq_table_after"][:6]),
              flush=True)
        print("sp-after    0x%08X  pc 0x%08X"
              % (regs_after.get("r13", 0), regs_after.get("r15", 0)),
              flush=True)
        print("after       phase={phase} frame={scene_frame} "
              "ctrl={last_control_error} player={last_player_error} "
              "act_err={selected_action_error}".format(**values_after),
              flush=True)

        probe.run(f"shot {args.out / 'after-a.png'}")
        record["stderr_lines"] = probe.stderr_lines
        record["stderr_tail"] = probe.stderr_tail[-20:]
        print(f"stderr      {probe.stderr_lines} lines", flush=True)

    (args.out / "w2-confirm-sp.json").write_text(
        json.dumps(record, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
