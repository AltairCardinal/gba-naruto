#!/usr/bin/env python3
"""Resolve the true base of a legacy content bank from the ROM's own literal index.

Why this tool exists
--------------------
Twenty-three legacy content banks under ``sequel/content/*/bank.json`` declare
a ``table_offset`` that the ROM never names -- not as a literal load, not as a
data pointer.  ``tools/completion_audit.py`` calls those "基址无效，需重新定位"
(*rebase*).

Every bank that has been resolved so far turned out to have the **same** shape:

    the declared base is a *skewed window into a real table*.

The decisive evidence is always a triple:

  1. a **live literal** ``L`` -- an address the game's own code loads with
     ``LDR Rn, [pc, #imm]`` -- that sits at or below the declared base;
  2. the relation ``declared_base = L + k*stride + field_offset``, where
     ``stride`` is *derived* from the reader's dataflow, never guessed;
  3. ``L + count*stride`` lands **exactly** on another known structure's base.

    | bank              | declared  | true base | relation                  | landing                       |
    |-------------------|-----------|-----------|---------------------------|-------------------------------|
    | character-stats   | 0x54507A  | 0x545068  | +1*16 + 2                 | 0x545068+63*16 == 0x545458    |
    | levels            | 0x5459D4  | 0x5459C8  | +1*12 + 0                 | 0x5459C8+45*12 == 0x545BE4    |
    | items / skills    | 0x546100  | 0x545BE4  | +81*16 + 12               | 0x545BE4+94*16 == 0x5461C4    |
    | battle-encounters | 0x542384  | 0x54229C  | +14*16 + 8                | 0x54229C+24*16 == 0x54241C    |

This tool makes that search *mechanical*:

  * it builds the **whole-ROM literal index**
    (``tools.consumer_locate.LiteralIndex`` -- 18051 values, 1196 of them
    pointing into the ROM image), not the audited 54-table subset, so no
    candidate is silently missing;
  * for every live literal near the declared base it re-derives the stride
    **from the consumer's own dataflow** by reusing the symbolic pass in
    ``tools/legacy_rebase.py`` (``analyze_reader``), aggregated over *all*
    readers of that literal instead of only the first one;
  * it checks the relation ``declared = L + k*stride + field_offset``;
  * it checks whether ``L + count*stride`` lands exactly on a known
    structure (the known-structure list lives in this file, seeded from
    ``tools/table_registry.py::TABLES``) or on the next live literal base;
  * for the winning candidate it prints a **record-shape check**: what the
    entries actually are, how many of them are coherent, and whether the
    table's end coincides with the next structure.

The ROM digest is verified against a pinned SHA-256 before anything else
runs; a mismatch is a hard error (exit 3), because every address this tool
prints is only meaningful for the ROM it was derived from.

Usage:
    python tools/rebase_resolve.py rom/base.gba --target 0x53E6D8
    python tools/rebase_resolve.py rom/base.gba --target 0x53E6D8 --window 0x400
    python tools/rebase_resolve.py rom/base.gba --bank battle-handlers
    python tools/rebase_resolve.py rom/base.gba --target 0x53E6D8 --json build/rebase.json

Exit codes:
    0  ok
    2  bad usage, missing ROM, missing bank
    3  the ROM digest does not match the pinned SHA-256
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import consumer_locate as cl  # noqa: E402
import legacy_rebase as lr  # noqa: E402
import table_registry as tr  # noqa: E402

ROM_BASE = cl.ROM_BASE
DEFAULT_ROM = REPO / "rom" / "base.gba"
CONTENT_ROOT = REPO / "sequel" / "content"

# The digest of rom/base.gba this tool's conclusions were derived from.
# Every address printed below is meaningless for any other ROM, so the check
# is not optional: a mismatch aborts before the index is even built.
EXPECTED_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_DIGEST = 3


# --------------------------------------------------------------------------
# known structures
# --------------------------------------------------------------------------
# The landing test needs a list of structures whose base address is known.
# It is seeded from ``tools/table_registry.py::TABLES`` -- the registry is the
# single source of truth for verified bases -- and extended below with the
# bases this investigation established on 2026-10-21 (see
# notes/evidence/rebase-resolve-20261021.md).
#
# Keys are **ROM file offsets**, like the registry and like every
# ``table_offset`` in a content bank.  The literal index works in ROM
# addresses (0x08xxxxxx); the two are converted at the boundary.
SESSION_FINDINGS: dict[int, str] = {
    0x53E698: "battle-handler dispatch table (8-byte records: 2 code pointers, "
              "256 entries; ends exactly on sprite_frame_descriptors)",
    0x53E496: "font byte table A (256 bytes; ends exactly on font byte table B)",
    0x53E596: "font byte table B (256 bytes; ends 2 bytes before 0x53E698)",
    0x53D5F0: "function-pointer u32 array (13 slots; slots 1..11 are the "
              "Thumb code pointers, slots 0 and 12 are 0xFFFFFFFF)",
    0x5A143C: "data pointer table A (46 u32 ROM pointers; ends on 0x5A14F4)",
    0x5A2034: "data pointer table B (90 u32 ROM pointers; ends on 0x5A219C)",
    0x5A320C: "tile-group record table (68-byte records, +12 field holds the "
              "6 u32 tile pointers; 79 records, ends at 0x5A4708)",
    0x5A4DEC: "portrait table (40-byte rows, id*40 + expr*8, 63 rows; ends "
              "exactly on the 12-byte palette-source table)",
    0x5A57C4: "12-byte palette-source record table",
    # 2026-10-22: the old base 0x596F0C was a +0x240 window of the
    # sprite-action table and its only native reference (0x0807B220) sits
    # in unreachable code -- so the bank is re-pointed at the base a live
    # reader loads (0x596CCC).  See
    # notes/evidence/resource-pointers-deadcode-20261022.md
    0x596CCC: "sprite-action table (18-byte records); the old 0x596F0C bank "
              "is its +0x240 window and has no live reader",
}


def known_structures() -> dict[int, str]:
    """``file offset -> name`` for every structure whose base is known."""
    out: dict[int, str] = {}
    for name, (addr, verified, _note) in tr.TABLES.items():
        if not verified:
            continue
        out[addr] = name
    out.update(SESSION_FINDINGS)
    return out


def verified_registry_count() -> int:
    """How many registry entries are marked verified."""
    return sum(1 for _n, (_a, verified, _note) in tr.TABLES.items() if verified)


# --------------------------------------------------------------------------
# address helpers
# --------------------------------------------------------------------------
def to_file_offset(address: int) -> int:
    """ROM address or file offset -> file offset."""
    if ROM_BASE <= address < ROM_BASE + 0x600000:
        return address - ROM_BASE
    return address


def parse_address(text: str) -> int:
    """A target given as a file offset or as a 0x08xxxxxx ROM address."""
    value = int(text, 0)
    if value >= ROM_BASE:
        return value - ROM_BASE
    return value


def u32_at(rom: bytes, offset: int) -> int:
    return struct.unpack_from("<I", rom, offset)[0]


# --------------------------------------------------------------------------
# candidate analysis
# --------------------------------------------------------------------------
def analyse_candidate(rom: bytes, index: cl.LiteralIndex,
                      literal: int, known: dict[int, str],
                      declared: int, live_offsets: list[int],
                      legacy_span: int | None = None) -> dict:
    """Everything the tool can say about one candidate base ``literal``.

    ``literal`` is a ROM address (the value the game loads).
    ``legacy_span`` is the byte length of the legacy bank's recorded window,
    when it is known: the window must fit *inside* the candidate table, which
    is what separates a real skew from a coincidental address match.
    """
    base = to_file_offset(literal)
    readers = sorted(set(index.readers_of(literal)))

    analyses = [lr.analyze_reader(rom, addr, mode, literal)
                for addr, mode in readers]

    strides = sorted({a["stride"] for a in analyses if a["stride"]})
    usages = sorted({a["usage"] for a in analyses})

    # the next live literal above this candidate: if the table ends exactly
    # there, that is a structural anchor that needs no registry entry.
    position = bisect.bisect_right(live_offsets, base)
    next_live = live_offsets[position] if position < len(live_offsets) else None

    # every known structure above this candidate, closest first
    above = sorted((t for t in known if t > base), key=lambda t: t - base)
    nearest_known = above[0] if above else None

    record = {
        "literal": f"0x{literal:08X}",
        "file_offset": f"0x{base:08X}",
        "delta": base - declared,
        "readers": len(readers),
        "reader_list": [f"0x{a:08X}" for a, _ in readers],
        "usages": usages,
        "strides": strides,
        "relations": [],
        "landings": [],
        "nearest_known": (f"0x{nearest_known:08X} ({known[nearest_known]})"
                          if nearest_known is not None else None),
        "next_live": f"0x{next_live:08X}" if next_live is not None else None,
    }

    for stride in strides:
        # --- relation: declared = L + k*stride + field_offset ---------------
        # declared - L = k*stride + field_offset, field_offset in [0, stride)
        delta = declared - base
        k = delta // stride
        field = delta - k * stride
        relation = {
            "stride": stride,
            "k": k,
            "field_offset": field,
            "exact": field == 0,
            "declared_inside_table": k >= 0,
        }
        record["relations"].append(relation)

        # --- landing: L + count*stride on a known structure -----------------
        # The *closest* known structure reachable with this stride wins; a
        # closer but unreachable structure is reported as ``nearest_known`` so
        # the gap stays visible instead of being hidden.
        for target in above:
            gap = target - base
            if gap % stride:
                continue
            count = gap // stride
            entry = {
                "stride": stride,
                "count": count,
                "target": f"0x{target:08X}",
                "target_name": known[target],
                "declared_inside_table": 0 <= k < count,
                "legacy_window_fits": None,
            }
            if legacy_span is not None:
                table_end = base + count * stride
                entry["legacy_window_fits"] = (
                    base <= declared
                    and declared + legacy_span <= table_end)
            record["landings"].append(entry)
            break

        # --- landing on the next live literal base -------------------------
        if next_live is not None:
            gap = next_live - base
            if gap % stride == 0:
                count = gap // stride
                entry = {
                    "stride": stride,
                    "count": count,
                    "target": f"0x{next_live:08X}",
                    "target_name": "(next live literal base)",
                    "declared_inside_table": 0 <= k < count,
                    "legacy_window_fits": None,
                }
                if legacy_span is not None:
                    entry["legacy_window_fits"] = (
                        base <= declared
                        and declared + legacy_span <= base + count * stride)
                record["landings"].append(entry)

    return record


def record_shape(rom: bytes, base: int, stride: int, count: int,
                 entry_size: int = 4) -> dict:
    """Classify the entries of a candidate table.

    The check answers "does the content look like one table of this shape?",
    not "does it look nice": pointers must point into the ROM, zero runs must
    be contiguous, and the table must not run off the end of the ROM.

    ``stride`` is the record stride, so the *value* width is ``min(stride, 4)``
    bytes: a byte table must be classified byte by byte, not as a run of
    overlapping u32 reads.
    """
    kinds = {"code_ptr": 0, "rom_ptr": 0, "ram_ptr": 0, "zero": 0,
             "small": 0, "other": 0}
    value_size = max(1, min(stride, 4))
    words = []
    for i in range(count):
        off = base + i * stride
        if off + value_size > len(rom):
            break
        value = int.from_bytes(rom[off:off + value_size], "little")
        if value == 0:
            kinds["zero"] += 1
        elif ROM_BASE <= value < ROM_BASE + len(rom):
            if value & 1:
                kinds["code_ptr"] += 1
            else:
                kinds["rom_ptr"] += 1
        elif 0x02000000 <= value < 0x04000000:
            kinds["ram_ptr"] += 1
        elif value < 0x1000:
            kinds["small"] += 1
        else:
            kinds["other"] += 1
        words.append(value)
    pointer_like = kinds["code_ptr"] + kinds["rom_ptr"]
    return {
        "entries": len(words),
        "value_bytes": value_size,
        "kinds": kinds,
        "pointer_fraction": (round(pointer_like / len(words), 3)
                             if words else 0.0),
        "first_words": [f"0x{w:0{value_size * 2}X}" for w in words[:16]],
        "last_words": [f"0x{w:0{value_size * 2}X}" for w in words[-8:]],
        "nonzero_entries": sum(1 for w in words if w),
    }


# --------------------------------------------------------------------------
# legacy bank cross-check
# --------------------------------------------------------------------------
def load_bank(name: str) -> dict | None:
    path = CONTENT_ROOT / name / "bank.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def check_legacy_content(rom: bytes, bank: dict, offset: int) -> dict:
    """Do the bank's recorded entries equal the ROM bytes at ``offset``?

    A bank whose *content* is right but whose *base* is wrong is exactly the
    skewed-window case, so this separates the two failure modes.
    """
    entries = bank.get("entries") or []
    size = int(bank.get("entry_size") or 4)
    matched = 0
    for entry in entries:
        raw = entry.get("_raw_offset")
        if raw is None:
            continue
        off = raw - to_file_offset(0)
        if off < 0 or off + size > len(rom):
            continue
        blob = rom[off:off + size]
        keys = set(entry)
        if size == 1:
            want = entry.get("char_width")
        elif "handler_ptr" in keys:
            want = entry.get("handler_ptr")
        elif "func_ptr" in keys:
            want = entry.get("func_ptr")
        elif "tile_ptr" in keys:
            want = entry.get("tile_ptr")
        elif "data_ptr" in keys:
            want = entry.get("data_ptr")
        elif "ui_ptr" in keys:
            want = entry.get("ui_ptr")
        else:
            want = None
        if want is None:
            continue
        if size == 1:
            got = blob[0]
        else:
            got = struct.unpack_from("<I", blob, 0)[0]
        if got == want:
            matched += 1
    total = sum(1 for e in entries if e.get("_raw_offset") is not None)
    return {
        "entries": total,
        "matching_rom_bytes": matched,
        "all_match": total > 0 and matched == total,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom", nargs="?", type=pathlib.Path, default=DEFAULT_ROM,
                    help="ROM image (default: rom/base.gba)")
    ap.add_argument("--target", action="append", default=[],
                    help="declared base to triage (file offset or 0x08xxxxxx); "
                         "may be repeated")
    ap.add_argument("--bank", action="append", default=[],
                    help="legacy content bank name under sequel/content/; "
                         "may be repeated")
    ap.add_argument("--window", type=lambda t: int(t, 0), default=0x200,
                    help="search radius in bytes (default 0x200)")
    ap.add_argument("--expect-sha256", default=EXPECTED_SHA256,
                    help="digest the ROM must have (default: the pinned "
                         "rom/base.gba digest)")
    ap.add_argument("--json", type=pathlib.Path, default=None,
                    help="also write the report as JSON")
    args = ap.parse_args()

    if not args.rom.exists():
        print(f"error: ROM not found: {args.rom}", file=sys.stderr)
        return EXIT_USAGE

    rom = args.rom.read_bytes()
    digest = hashlib.sha256(rom).hexdigest()
    if digest != args.expect_sha256:
        print(f"error: ROM digest mismatch\n"
              f"       rom      : {digest}\n"
              f"       expected : {args.expect_sha256}\n"
              "       every address this tool prints belongs to one specific "
              "ROM; refusing to continue.", file=sys.stderr)
        return EXIT_DIGEST

    targets: list[tuple[str, int]] = []
    for text in args.target:
        targets.append((text, parse_address(text)))
    for name in args.bank:
        bank = load_bank(name)
        if bank is None:
            print(f"error: no such content bank: {name}", file=sys.stderr)
            return EXIT_USAGE
        targets.append((name, int(bank["table_offset"])))
    if not targets:
        print("nothing to do: pass --target and/or --bank", file=sys.stderr)
        return EXIT_USAGE

    index = cl.LiteralIndex(rom)
    live = lr.live_literals(index)
    live_offsets = sorted(to_file_offset(v) for v in live)
    known = known_structures()
    verified_count = verified_registry_count()

    report = {
        "rom": str(args.rom),
        "rom_sha256": digest,
        "window": args.window,
        "indexed_values": len(index.readers),
        "live_rom_literals": len(live),
        "known_structures": len(known),
        "targets": [],
    }

    for label, declared in targets:
        bank = load_bank(label) if label in {b for b in args.bank} else None
        legacy_span = None
        legacy_entry_size = None
        if bank is not None:
            legacy_entry_size = int(bank.get("entry_size") or 4)
            legacy_span = int(bank.get("entry_count") or 0) * legacy_entry_size

        candidates = []
        for literal in live:
            base = to_file_offset(literal)
            if abs(base - declared) > args.window:
                continue
            candidates.append(analyse_candidate(rom, index, literal, known,
                                                 declared, live_offsets,
                                                 legacy_span))
        candidates.sort(key=lambda c: (-c["readers"], abs(c["delta"])))

        entry = {
            "name": label,
            "declared": f"0x{declared:08X}",
            "declared_is_live": len(index.readers_of(
                ROM_BASE + declared)) > 0,
            "legacy_span": legacy_span,
            "candidates": candidates,
            "legacy_content": None,
        }
        if bank is not None:
            entry["legacy_content"] = check_legacy_content(rom, bank, declared)

        # --- pick the winner ------------------------------------------------
        # A candidate qualifies when
        #   (a) it has an exact landing on a known structure,
        #   (b) the declared base lies *inside* its table (record index k is
        #       smaller than the table's own record count).
        # It is *preferred* when the legacy bank's recorded window also fits
        # inside that table -- but a bank whose own entry_count is too large
        # must not be allowed to hide the real base, so a failing fit only
        # costs priority, it does not disqualify.
        # Among the qualifying candidates the tightest table wins: a landing
        # 256 records away is a real table edge, one 1920 records away would
        # swallow half the ROM's data area.  A stride that matches the
        # legacy bank's own entry size wins ties.
        best = None
        for candidate in candidates:
            for landing in candidate["landings"]:
                for relation in candidate["relations"]:
                    if landing["stride"] != relation["stride"]:
                        continue
                    if not (0 <= relation["k"] < landing["count"]):
                        continue
                    fit_rank = 0 if landing["legacy_window_fits"] is True \
                        else (1 if landing["legacy_window_fits"] is None else 2)
                    stride_penalty = (0 if legacy_entry_size ==
                                      landing["stride"] else 1)
                    key = (fit_rank, stride_penalty, landing["count"],
                           -candidate["readers"])
                    if best is None or key < best[0]:
                        best = (key, candidate, landing)
        if best is not None:
            _key, winner, landing = best
            base = int(winner["file_offset"], 16)
            entry["winner"] = {
                "file_offset": winner["file_offset"],
                "literal": winner["literal"],
                "readers": winner["readers"],
                "strides": winner["strides"],
                "landing": landing,
                "record_shape": record_shape(rom, base, landing["stride"],
                                             landing["count"]),
            }
        report["targets"].append(entry)

    if args.json:
        from tools.lib.io import write_json
        write_json(args.json, report)

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"ROM        : {args.rom}")
    print(f"sha256     : {digest}")
    print(f"index      : {len(index.readers)} literal values, "
          f"{len(live)} of them point into the ROM image")
    print(f"known      : {len(known)} structures "
          f"({verified_count} verified registry entries + "
          f"{len(SESSION_FINDINGS)} session findings)")
    print()

    for entry in report["targets"]:
        print(f"=== {entry['name']}  declared {entry['declared']} ===")
        if entry["declared_is_live"]:
            print("  the declared base IS live (the ROM names it)")
        else:
            print("  the declared base is NOT live: the ROM never names it")
        if entry["legacy_content"]:
            lc = entry["legacy_content"]
            print(f"  legacy content: {lc['matching_rom_bytes']}/"
                  f"{lc['entries']} recorded entries match the ROM bytes at "
                  f"the declared base")
        print(f"  {'delta':>9}  {'literal':10} {'rd':>3}  {'stride':>6}  "
              f"{'k':>4} {'field':>5}  landing")
        for candidate in entry["candidates"]:
            for relation in candidate["relations"]:
                landings = " | ".join(
                    f"{l['count']}*{l['stride']} -> {l['target']} "
                    f"({l['target_name']})"
                    + ("" if l["legacy_window_fits"] is not False
                       else " [legacy window does NOT fit]")
                    for l in candidate["landings"]
                    if l["stride"] == relation["stride"])
                print(f"  {candidate['delta']:+#9x}  {candidate['literal']:10} "
                      f"{candidate['readers']:>3}  {relation['stride']:>6}  "
                      f"{relation['k']:>4} {relation['field_offset']:>5}  "
                      f"{landings or '-'}")
        if "winner" in entry:
            winner = entry["winner"]
            shape = winner["record_shape"]
            print(f"  WINNER {winner['file_offset']}  readers={winner['readers']}"
                  f"  stride={winner['strides']}")
            print(f"         landing: {winner['landing']['count']} * "
                  f"{winner['landing']['stride']} -> "
                  f"{winner['landing']['target']} "
                  f"({winner['landing']['target_name']})")
            fit = winner["landing"]["legacy_window_fits"]
            if fit is False:
                print("         WARNING: the legacy bank's recorded window "
                      "does NOT fit inside this table "
                      f"(declared {entry['declared']} + "
                      f"{entry['legacy_span']} bytes > table end)")
            print(f"         shape  : {shape['entries']} entries, "
                  f"non-zero {shape['nonzero_entries']}, "
                  f"pointer fraction {shape['pointer_fraction']}")
            print(f"         kinds  : {shape['kinds']}")
            print(f"         first  : {' '.join(shape['first_words'])}")
            print(f"         last   : {' '.join(shape['last_words'])}")
        else:
            print("  no candidate satisfies (relation + exact landing)")
        print()

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
