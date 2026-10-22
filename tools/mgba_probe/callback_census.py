#!/usr/bin/env python3
"""Census of the callback-table dispatch points: which of them does a route hit?

The L2 batch-4 structures were blocked because their native consumers are only
reached through ROM callback tables.  The dispatch points are now known at
instruction level (see
`notes/evidence/callback-dispatch-tables-20261021.md`), so the remaining
question is purely a *routing* question: which route -- if any -- makes the
game execute those instructions.

This tool arms a breakpoint on every known dispatch point and runs one route,
reporting which ones fire and what the registers held when they did.

Usage:
    python tools/mgba_probe/callback_census.py rom/base.gba --route battle
    python tools/mgba_probe/callback_census.py rom/base.gba --route save
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
for _p in (REPO, REPO / "tools", REPO / "tools" / "mgba_probe"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from navigate import Probe as _BaseProbe            # noqa: E402
from runtime_probe import parse_status              # noqa: E402

ROM_BASE = 0x08000000
DEFAULT_EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"
STATE_DIR = REPO / "build" / "l2-states"

STORY_STATE = 0x020311D4
SCENE_BYTE = STORY_STATE + 0x16
PHASE_WORD = STORY_STATE + 0x12
SUBCFG_BYTE = STORY_STATE + 0x19
STATE_LOOP = 0x0808F752
PHASE_BATTLE = 0x0110
PHASE_SAVE = 0x0018

PRESS_FRAMES = 8
SETTLE_FRAMES = 120
KEYS = (0x001, 0x002, 0x008, 0x040, 0x080, 0x020, 0x010)

HIT_RE = re.compile(r"(?:Hit breakpoint|Hit watchpoint)\s+#?(\d+)\s+at\s+(0x[0-9a-fA-F]+)")

# address -> (label, structure it would prove)
WATCH: dict[int, tuple[str, str]] = {
    0x0807F108: ("fonts 0x0853E596 (glyph width byte)", "fonts"),
    0x0807EEA8: ("glyph metrics 0x0853E328 (+0 width)", "font-metrics"),
    0x0807EEBE: ("glyph metrics 0x0853E328 (+1 bearing)", "font-metrics"),
    0x0807FD36: ("handler table 0x0853E698 (word0)", "battle-handlers"),
    0x0807FE62: ("object-type record 0x0853EF30 (+0 index)", "object-types"),
    0x0807FE7A: ("object-type record 0x0853EF30 (+0x04 slot)", "object-types"),
    0x0807FE80: ("spawn table 0x0859911C", "object-types"),
    0x08080B12: ("object descriptor table 0x0853F140", "map-sprites"),
    0x08080B32: ("unit slot remap 0x0853F298", "units"),
    0x08080B74: ("unit slot remap 0x0853F298 (decision)", "units"),
    0x080806BC: ("sprite frame descriptors 0x0853EE98", "sprite-frame-descriptors"),
    0x08080E44: ("spawn jump table 0x0853F310", "entity-spawn"),
    0x08080E5A: ("spawn jump table entry load", "entity-spawn"),
    0x0807EE50: ("glyph metrics reader fn", "font-metrics"),
    0x0807FE2C: ("object-type dispatch fn", "object-types"),
    0x08080B08: ("object descriptor reader fn", "map-sprites"),
    0x08080BA0: ("entity spawn fn", "entity-spawn"),
    0x08080E30: ("spawn entry fn", "entity-spawn"),
    # The exact decision points the L2 evidence note uses, so the census can
    # reach the same judgement with the same register values.  `fn 0x0806D964`
    # is the one function that reads *every* character table.
    0x0806D98E: ("character stats 0x08545068 (decision point)", "character-stats"),
    0x0806D9D8: ("character stats B 0x08545068 (decision point)", "character-stats-b"),
    0x0806DB1A: ("character perks 0x085459C8 (decision point)", "levels"),
    0x0806E1FE: ("battle formation 0x085461C4 (decision point)", "battle-config"),
    0x0806B770: ("sprite action table 0x08596CCC (decision point)", "sprite-animations"),
    0x0806D988: ("character template 0x0854241C (decision point)", "character-template"),
    0x080806BC: ("sprite frame descriptors 0x0853EE98", "sprite-frame-descriptors"),
    0x0807F108: ("font width table 0x0853E596", "fonts"),
    # The story battle's event switch: `case 0x4080` is the one that reads
    # the items / skills table (0x08545BE4) through fn 0x08070DF8 ->
    # fn 0x0806D910.  Which case fires depends on the battle's event stream,
    # so every group has to be tried.
    0x08074190: ("event case 0x4080 (items reader)", "items"),
    0x0807443C: ("event case 0x6000 (entity spawn)", "map-sprites"),
    0x0807425A: ("event case -> fn 0x080851F8", "items"),
    0x0806D91A: ("items table 0x08545BE4 (fn 0x0806D910)", "items"),
    0x0806D908: ("items table 0x08545BE4 decision point", "items"),
    0x080952C8: ("item list UI fn", "items"),
    0x08078E38: ("ninjutsu list UI fn", "ninjutsu-names"),
    # `fn 0x08061E98` is the choke point for "play sound id N": it reads the
    # sound-id table 0x08465B70 *and* the m4a SongHeader pointer table
    # 0x08465B40, so one hit proves both.
    0x08061EA6: ("sound id table 0x08465B70 (fn 0x08061E98)", "sound-id-table"),
    0x08061EB0: ("sound id table 0x08465B70 (decision point)", "sound-id-table"),
    # fn 0x0809AAC0 is what the *blip* helper (0x08061E6C) calls, so every
    # menu cursor sound reads the sound id table.  The decision point has to
    # be 0x0809AACC: the next instruction (0x0809AACE) overwrites r1, which
    # is the register that holds the table base.
    0x0809AACC: ("sound id table 0x08465B70 (blip path)", "sound-id-table"),
    0x0809AB9A: ("sound id table 0x08465B70 (stop path)", "sound-id-table"),
    # The dialogue pointer table (0x08461CE8) is loaded as 0x08461CE4
    # (base - 4) at 0x080917B0 and kept on the stack; the table itself has
    # no literal reader at all.
    0x080917B0: ("dialogue pointer table 0x08461CE8", "text-writeback"),
    # The cutscene block loader's table load (reached when the pointer at
    # 0x02026A80 is zero) and the story_config[0] write (which the game
    # clears one instruction later, so the breakpoint has to sit between).
    0x08072F0E: ("cutscene block table 0x0853DF70", "cutscene-scripts"),
    0x0808F5CA: ("story_config[0] write 0x020311ED", "runtime-state"),
    # The battle entry reads state[0x19] (the battle sub-config byte) into
    # r0 and copies it to ctrl[2] -- so r0 *is* story_config[0] here.
    0x0808F93E: ("story_config[0] read 0x020311ED", "runtime-state"),
    # The m4a play entry reads a SongHeader's fields when a song starts.
    # These are the three dereference readers of the sound-id table, so a hit
    # proves both the table and the SongHeader it points at.  The SongHeader
    # bases the game actually plays are:
    #   0x08536368 = story  (audio_song_1,  sound id 1)
    #   0x08536BC4 = story-b (audio_song_2,  sound id 2)
    #   0x08538FEC = story-c (audio_song_8,  sound id 8)
    #   0x0853AB74 = story-d (audio_song_11, sound id 11)
    #   0x0853C3BC = story-e (audio_song_14, sound id 14)
    0x0809B242: ("m4a play: SongHeader 0x08536368 / 0x08536BC4 / 0x08538FEC "
                 "/ 0x0853AB74", "story"),
    0x0809B25C: ("m4a play: SongHeader 0x08536368 / 0x08536BC4 / 0x08538FEC "
                 "/ 0x0853AB74", "story"),
    0x0809B282: ("m4a play: SongHeader 0x08536368 / 0x08536BC4 / 0x08538FEC "
                 "/ 0x0853AB74", "story"),
    # the event dispatcher: fn 0x080733A0 (the id switch) and its shell
    # fn 0x0807504E.  r6 carries the event id at the call site.
    0x080733A0: ("event id switch fn", "event-chain"),
    0x0807504E: ("event dispatch shell fn", "event-chain"),
    0x08075054: ("event dispatch call", "event-chain"),
    # the consumer points the earlier notes already named
    0x0807F414: ("battle event dispatcher fn", "battle-handlers"),
    0x0807F942: ("battle event dispatcher decision", "battle-handlers"),
    0x0807F936: ("0x0853E698 literal site A", "battle-handlers"),   # was pool 0x0807FA38, loaded by 0x0807F934
    0x0807FD36: ("0x0853E698 literal site B (word0)", "battle-handlers"),
    0x0807AA8C: ("map event setup fn", "map-events"),
    0x0807AB34: ("battle unit setup fn", "map-events"),
    0x0807AE04: ("sprite action window fn", "resource-pointers"),
    0x0807B220: ("resource pointer reader", "resource-pointers"),
    0x0806DF1E: ("battle unit creation call site", "map-events"),
    0x0807C6BE: ("sprite action call site", "resource-pointers"),
    # menu / item / skill / tile consumers
    0x0806F89C: ("ninjutsu list caller", "ninjutsu-names"),
    0x080794F4: ("ninjutsu names reader fn", "ninjutsu-names"),
    0x0806D910: ("item/skill table fn", "items"),
    0x0806D91A: ("item/skill record reader", "items"),
    0x0808AFE0: ("data table A fn", "data-table-a"),
    0x0808B420: ("data table A caller", "data-table-a"),
    0x0809880C: ("tile assets reader fn", "tile-assets"),
    0x08098E22: ("tile assets caller", "tile-assets"),
    0x08087C9C: ("battle encounter fn", "battle-encounters"),
    0x0808A69E: ("battle encounter thunk", "battle-encounters"),
    0x0808136C: ("mechanism effects fn", "mechanism-effects"),
    0x080874FE: ("mission text reader", "mission-text"),
    0x08087334: ("mission text fn", "mission-text"),
    0x080731DA: ("mission text reader B", "mission-text"),
    0x0808675C: ("mission text reader C", "mission-text"),
    0x0806E1B4: ("battle unit fn", "items"),
    0x0806E892: ("battle unit branch A", "items"),
    0x0806E8E4: ("battle unit branch B", "items"),
    0x0808FC28: ("item/skill reader A", "items"),
    0x0808FF78: ("item/skill reader B", "items"),
    0x0806E8E8: ("battle unit branch B inner", "items"),
    0x0806E830: ("battle unit branch A inner", "items"),   # was pool 0x0806E860, loaded by 0x0806E82E
    0x0806E4D0: ("battle unit fn head", "items"),
    0x0806D964: ("character stats fn", "items"),
    0x0806D6B8: ("character perk fn", "items"),
    0x08093070: ("character perk fn B", "items"),
    # every literal site that reads the remaining structures
    0x08078EFA: ("items table site C", "items"),   # was pool 0x08078F04, loaded by 0x08078EF8
    0x08078F0A: ("items table site D", "items"),   # was pool 0x08078FC0, loaded by 0x08078F08
    0x08095396: ("items table site E", "items"),   # was pool 0x080953A0, loaded by 0x08095394
    0x080953A6: ("items table site F", "items"),   # was pool 0x0809545C, loaded by 0x080953A4
    0x0806D91C: ("items table site G", "items"),   # was pool 0x0806D960, loaded by 0x0806D91A
    0x08087D02: ("battle encounter site A", "battle-encounters"),   # was pool 0x08087DB0, loaded by 0x08087D00
    0x08087DE2: ("battle encounter site B", "battle-encounters"),   # was pool 0x08087E24, loaded by 0x08087DE0
    0x08087DFE: ("tile assets 0x085A320C site A", "tile-assets"),   # was pool 0x08087E30, loaded by 0x08087DFC
    0x0809845E: ("tile assets 0x085A320C site B", "tile-assets"),   # was pool 0x0809851C, loaded by 0x0809845C
    0x08098820: ("tile assets 0x085A320C site C", "tile-assets"),   # was pool 0x08098840, loaded by 0x0809881E
    0x08098A94: ("tile assets 0x085A320C site D", "tile-assets"),   # was pool 0x08098AF0, loaded by 0x08098A92
    0x08098D4C: ("tile assets 0x085A320C site E", "tile-assets"),   # was pool 0x08098DB0, loaded by 0x08098D4A
    0x08098EF0: ("tile assets 0x085A320C site F", "tile-assets"),   # was pool 0x08098FC0, loaded by 0x08098EEE
    0x080990D4: ("tile assets 0x085A320C site G", "tile-assets"),   # was pool 0x08099464, loaded by 0x080990D2
    0x08099600: ("tile assets 0x085A320C site H", "tile-assets"),   # was pool 0x08099698, loaded by 0x080995FE
    0x08099CE6: ("tile assets 0x085A320C site I", "tile-assets"),   # was pool 0x08099D10, loaded by 0x08099CE4
    0x0808A6BC: ("data table A site A", "data-table-a"),   # was pool 0x0808A704, loaded by 0x0808A6BA
    0x0806F506: ("ninjutsu site A", "ninjutsu-names"),   # was pool 0x0806F524, loaded by 0x0806F504
    0x080796E6: ("ninjutsu site B", "ninjutsu-names"),   # was pool 0x08079700, loaded by 0x080796E4
    0x08079706: ("ninjutsu site C", "ninjutsu-names"),   # was pool 0x0807972C, loaded by 0x08079704
    0x08081644: ("ninjutsu site D", "ninjutsu-names"),   # was pool 0x080816BC, loaded by 0x08081642
    0x08081700: ("ninjutsu site E", "ninjutsu-names"),   # was pool 0x08081734, loaded by 0x080816FE
    0x0808E9FA: ("ninjutsu site F", "ninjutsu-names"),   # was pool 0x0808EAE4, loaded by 0x0808E9F8
    0x08090288: ("ninjutsu site G", "ninjutsu-names"),   # was pool 0x080902BC, loaded by 0x08090286
    0x08090352: ("ninjutsu site H", "ninjutsu-names"),   # was pool 0x080903A4, loaded by 0x08090350
    0x0809734E: ("ninjutsu site I", "ninjutsu-names"),   # was pool 0x080973A4, loaded by 0x0809734C
    0x080973E8: ("ninjutsu site J", "ninjutsu-names"),   # was pool 0x0809740C, loaded by 0x080973E6
    0x08081352: ("mechanism effects literal", "mechanism-effects"),   # was pool 0x08081368, loaded by 0x08081350
    # sanity checkpoints: these are known to fire in the battle route, so a
    # silent census is a broken harness, not a missing route.
    0x080732B4: ("SANITY battle wrapper", "sanity"),
    0x0808A588: ("SANITY battle entry", "sanity"),
    0x0806D98C: ("SANITY character stats reader", "sanity"),
    0x08069040: ("SANITY map loader reader", "sanity"),
}


class Probe(_BaseProbe):
    def registers(self) -> dict:
        raw = parse_status(self.send("status"))
        out = {f"r{i}": raw.get(f"r{i}", 0) for i in range(13)}
        out["sp"] = raw.get("r13", 0)
        out["lr"] = raw.get("r14", 0)
        out["pc"] = raw.get("r15", 0)
        return out


def arm(probe: Probe, address: int) -> int | None:
    for line in probe.send(f"b {address:#x}"):
        if "breakpoint #" in line:
            return int(line.split("#")[1].split()[0])
    return None


def hits_in(output: list[str]) -> list[tuple[int, int]]:
    out = []
    for line in output:
        m = HIT_RE.search(line)
        if m:
            out.append((int(m.group(1)), int(m.group(2), 16)))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", type=pathlib.Path)
    ap.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    ap.add_argument("--state-dir", type=pathlib.Path, default=STATE_DIR)
    ap.add_argument("--route", default="battle",
                    choices=["battle", "save", "sweep", "title"])
    ap.add_argument("--groups", default="0-7")
    ap.add_argument("--presses", type=int, default=12)
    ap.add_argument("--scenes", default="1-55")
    ap.add_argument("--max-hits", type=int, default=40)
    ap.add_argument("--json", type=pathlib.Path, default=None)
    ap.add_argument("--sites", default=None,
                    help="comma separated address list to watch instead of "
                         "the default set (keeping the list small matters: "
                         "extra breakpoints change the game's pacing)")
    ap.add_argument("--keys", default=None,
                    help="comma separated key names to cycle, e.g. 'DOWN,A'")
    args = ap.parse_args(argv)

    keys = list(KEYS)
    if args.keys:
        names = {"A": 0x001, "B": 0x002, "SELECT": 0x004, "START": 0x008,
                 "RIGHT": 0x010, "LEFT": 0x020, "UP": 0x040, "DOWN": 0x080}
        keys = [names[k.strip().upper()] for k in args.keys.split(",")
                if k.strip().upper() in names]

    watch = dict(WATCH)
    if args.sites:
        wanted = {int(s, 0) for s in args.sites.split(",")}
        watch = {a: WATCH.get(a, ("watched", "custom")) for a in sorted(wanted)}

    rom = args.rom.read_bytes()
    groups = []
    for part in args.groups.split(","):
        if "-" in part:
            lo, hi = part.split("-", 1)
            groups.extend(range(int(lo), int(hi) + 1))
        else:
            groups.append(int(part))

    probe = Probe(args.exe, args.rom, timeout=1800)
    armed: dict[int, int] = {}
    records: dict[int, list[dict]] = {}
    try:
        for addr in watch:
            ident = arm(probe, addr)
            if ident is not None:
                armed[ident] = addr
        if not armed:
            print("ERR: could not arm any breakpoint", file=sys.stderr)
            return 2

        def handle(found: list[tuple[int, int]]) -> None:
            # A single `frames` run can trip several breakpoints, but the
            # debugger only stops at the *first* one.  The register dump
            # therefore belongs to the stop, and the program counter says
            # which site that was: a genuine hit has |pc - addr| <= 4 (a
            # 16- or 32-bit Thumb instruction), anything else is a dump
            # taken at a different site and must not be filed under the
            # reported address.
            #
            # The dump must also be taken *immediately* after the `frames`
            # call that produced the hit -- issuing the next `frames` moves
            # the debugger to the next stop.
            for ident, addr in found:
                if ident not in armed:
                    continue
                regs = probe.registers()
                pc = regs.get("pc", 0)
                genuine = abs(pc - addr) <= 4
                site = addr if genuine else (pc - 2 if pc else -1)
                if not genuine and site not in watch:
                    slot = records.setdefault(-1, [])
                    if len(slot) < args.max_hits:
                        slot.append({"reported": f"0x{addr:08X}",
                                     "pc": f"0x{pc:08X}",
                                     "regs": {k: f"0x{v:08X}"
                                              for k, v in regs.items()}})
                    continue
                slot = records.setdefault(site, [])
                if len(slot) < args.max_hits:
                    slot.append({"reported": f"0x{addr:08X}",
                                 "pc": f"0x{pc:08X}",
                                 "genuine": genuine,
                                 "regs": {k: f"0x{v:08X}"
                                          for k, v in regs.items()}})
                probe.send("next")

        state = args.state_dir / f"{'battle' if args.route == 'save' else args.route}.ss9"
        if not state.is_file():
            print(f"ERR: missing savestate {state}", file=sys.stderr)
            return 2

        if args.route == "battle":
            for group in groups:
                probe.send(f"load {state}")
                for ident in list(armed):
                    probe.send(f"delete {ident}")
                armed.clear()
                for addr in watch:
                    ident = arm(probe, addr)
                    if ident is not None:
                        armed[ident] = addr
                probe.send(f"poke 0x{SCENE_BYTE:08X} {group}")
                probe.send(f"poke 0x{SUBCFG_BYTE:08X} 0")
                probe.send(f"poke16 0x{PHASE_WORD:08X} {PHASE_BATTLE}")
                for step in range(args.presses):
                    key = keys[step % len(keys)]
                    out = probe.send(f"frames {PRESS_FRAMES} {key:#05x}")
                    found = hits_in(out)
                    # The release must be unconditional.  It used to run
                    # only when no breakpoint fired, so on any route with
                    # a sentinel breakpoint the key stayed down forever,
                    # the game never saw a press edge, the battle intro
                    # never advanced and the unit slots stayed empty --
                    # which is what made every callback dispatch point
                    # look unreachable.
                    out = probe.send(f"frames {SETTLE_FRAMES} 0x000")
                    found = found + hits_in(out)
                    if found:
                        handle(found)
        elif args.route == "save":
            probe.send(f"load {state}")
            probe.send(f"poke16 0x{PHASE_WORD:08X} {PHASE_SAVE}")
            for step in range(args.presses):
                key = keys[step % len(keys)]
                out = probe.send(f"frames {PRESS_FRAMES} {key:#05x}")
                found = hits_in(out)
                # The release must be unconditional (see the note above).
                out = probe.send(f"frames {SETTLE_FRAMES} 0x000")
                found = found + hits_in(out)
                if found:
                    handle(found)
        elif args.route == "sweep":
            scenes = []
            for part in args.scenes.split(","):
                if "-" in part:
                    lo, hi = part.split("-", 1)
                    scenes.extend(range(int(lo), int(hi) + 1))
                else:
                    scenes.append(int(part))
            for scene in scenes:
                probe.send(f"load {state}")
                for ident in list(armed):
                    probe.send(f"delete {ident}")
                armed.clear()
                for addr in watch:
                    ident = arm(probe, addr)
                    if ident is not None:
                        armed[ident] = addr
                probe.send(f"poke 0x{SCENE_BYTE:08X} {scene}")
                # The state machine only dispatches the scene when the phase
                # says "next scene" (0x0030) -- poking the scene byte alone
                # does NOT start it.
                probe.send(f"poke16 0x{PHASE_WORD:08X} 0x0030")
                probe.send("next")
                for step in range(args.presses):
                    key = keys[step % len(keys)]
                    out = probe.send(f"frames {PRESS_FRAMES} {key:#05x}")
                    found = hits_in(out)
                    # The release must be unconditional.  It used to run
                    # only when no breakpoint fired, so on any route with
                    # a sentinel breakpoint the key stayed down forever,
                    # the game never saw a press edge, the battle intro
                    # never advanced and the unit slots stayed empty --
                    # which is what made every callback dispatch point
                    # look unreachable.
                    out = probe.send(f"frames {SETTLE_FRAMES} 0x000")
                    found = found + hits_in(out)
                    if found:
                        handle(found)
        else:
            print(f"route {args.route} not implemented yet", file=sys.stderr)
            return 2
    finally:
        probe.close()

    real = {a: v for a, v in records.items() if a in watch}
    report = {
        "rom": str(args.rom),
        "route": args.route,
        "watch": {f"0x{a:08X}": {"label": lab, "structure": st}
                  for a, (lab, st) in sorted(watch.items())},
        "hit_counts": {f"0x{a:08X}": len(v) for a, v in sorted(real.items())},
        "hits": {f"0x{a:08X}": v for a, v in sorted(real.items())},
        "fired": sorted(f"0x{a:08X}" for a in real),
        "silent": sorted(f"0x{a:08X}" for a in watch if a not in real),
        "unattributed": len(records.get(-1, [])),
    }
    print(json.dumps(report["hit_counts"], indent=1))
    print("fired:   ", ", ".join(report["fired"]) or "(none)")
    print("silent:  ", ", ".join(report["silent"]) or "(none)")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
