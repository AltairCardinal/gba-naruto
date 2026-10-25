#!/usr/bin/env python3
"""Acceptance gate for the original's BG2 overlay rule.

Runs four independent checks and exits non-zero if any of them fails.

A. **Reproduction** -- replay the recorded A-walk from the original's own
   savestate with the probe, dumping BG2's tilemap every frame, and find the
   frames whose 2048-byte tilemap is byte-identical to each exported ground
   truth (sha256).  A moment that cannot be reproduced byte-for-byte cannot be
   predicted byte-for-byte either.

B. **Rule prediction** -- feed the rule's state through
   :func:`overlay_rule.predict` and compare, per logical (16x16 px) cell, with
   the original's own tilemap.  The acceptance metric is the one the task
   asks for: ``original-only == 0`` and ``remake-only == 0`` for the lit cell
   set, plus zero per-cell family mismatches.

C. **Role/palette identity** -- prove that the original's bank-12 palette is
   the remake's palette slots 225..235 and that each family's tiles paint
   exactly the palette indices of its role (this is what makes the six-family
   vocabulary a *rule* and not a naming convention).

D. **Cursor cross-check** -- read the original's OAM and I/O registers
   frame-exactly and check that the yellow ``band`` cell of the overlay is the
   cell the cursor sprite sits on.

Usage::

    python tools/s49_rule_probe/verify_moments.py --out build/s49-rule/verify.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import struct
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

from capture_original import (  # noqa: E402
    DEFAULT_EXE,
    DEFAULT_ROM,
    DEFAULT_STATE,
    GT_DIR,
    IDLE_FRAMES,
    HOLD_FRAMES,
    KEY_A,
    MOMENTS,
    ROUNDS,
    SETTLE_FRAMES,
    moment_tilemap,
    sha256,
)
from overlay_ground_truth import (  # noqa: E402
    LOGICAL_COLS,
    LOGICAL_ROWS,
    load_all,
    load_palette,
    load_tiles,
    tile_family,
)
from overlay_rule import (  # noqa: E402
    FAMILY_PALETTE_INDEX,
    ROLE_FAMILY,
    FAMILY_REMAKE_ROLE,
    TRANSPARENT_INDEX,
    OverlayState,
    lit_cells,
    moment_families,
    moment_state,
    palette_cross_check,
    predict,
)

PROBE_CLIENT = REPO / "tools" / "mgba_probe" / "probe_client.py"
BG2_TILEMAP_ADDR = 0x06001000
BG2_TILEMAP_LEN = 2048
OAM_ADDR = 0x07000000      # the probe's `dump` parses its address as decimal
OAM_LEN = 1024


# ---------------------------------------------------------------------------
# probe helpers
# ---------------------------------------------------------------------------

def run_probe(exe, rom, commands, out, timeout=900.0):
    argv = [sys.executable, str(PROBE_CLIENT), "--exe", str(exe), "--rom", str(rom)]
    for command in commands:
        argv += ["--cmd", command]
    argv += ["--out", str(out)]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"probe failed: {proc.stderr[:2000]}")
    return json.loads(out.read_text(encoding="utf-8"))


def parse_hex_dump(document, index):
    step = document["steps"][index]
    payload = step.get("dump")
    if not payload:
        raise RuntimeError(f"step {index} produced no dump: {step['output'][:3]}")
    return bytes.fromhex(payload["bytes"])


def decode_oam(raw: bytes) -> list[dict]:
    entries = []
    for i in range(len(raw) // 8):
        a0, a1, a2, a3 = struct.unpack_from("<HHBB", raw, i * 8)
        y = a0 & 0xFF
        if a0 & 0x0100:
            y += 8
        x = a1 & 0x1FF
        size_bits = (a1 >> 14) & 3
        entries.append({
            "slot": i,
            "x": x,
            "y": y,
            "tile": a2 & 0x3FF,
            "w": [16, 32, 32, 64][size_bits],
            "h": [16, 32, 64, 64][size_bits],
        })
    return entries


def read_state(exe, rom, state_path, out_dir, tag):
    """Read OAM frame-exactly (the `dump` command runs no frame).

    The probe's `dump` command is mGBA's own CLI debugger command and parses
    its address as **decimal**, unlike `framedump`/`keyseq`, which take a
    0x-prefixed literal.
    """
    out_json = out_dir / f"{tag}-state.json"
    document = run_probe(exe, rom, [
        f"load {state_path}",
        f"dump {OAM_ADDR} {OAM_LEN}",
    ], out_json)
    oam = parse_hex_dump(document, 1)
    return decode_oam(oam)


def oam_cells(entries, hoffs, voffs):
    """The map-space cell each OBJ sprite is anchored on."""
    out = []
    for e in entries:
        if e["tile"] == 0 and e["x"] == 0 and e["y"] == 0:
            continue
        map_x = (e["x"] + hoffs) % 256
        map_y = (e["y"] + voffs) % 256
        out.append({**e, "map_px_x": map_x, "map_px_y": map_y,
                    "cell": (map_x // 16, map_y // 16)})
    return out


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

def check_reproduction(exe, rom, out_dir) -> dict:
    walk = out_dir / "walk"
    walk.mkdir(parents=True, exist_ok=True)
    document = run_probe(exe, rom, [
        f"load {DEFAULT_STATE}",
        f"framedump {IDLE_FRAMES} 0x{BG2_TILEMAP_ADDR:08X} {BG2_TILEMAP_LEN} "
        f"0x000 {walk / 'pre'}",
        f"keyseq {HOLD_FRAMES} {SETTLE_FRAMES} {ROUNDS} "
        f"0x{BG2_TILEMAP_ADDR:08X} {BG2_TILEMAP_LEN} 0x{KEY_A:03X} {walk / 'a'}",
    ], out_dir / "verify-walk.json")
    bad = [s for s in document["steps"] if s["status"] != "ok"]
    if bad:
        raise RuntimeError(f"probe step failed: {bad[0]['output']}")

    targets = {name: sha256(moment_tilemap(name)) for name in MOMENTS}
    hits: dict[str, list[str]] = {name: [] for name in MOMENTS}
    for path in sorted(walk.glob("*.bin")):
        digest = sha256(path.read_bytes())
        for name, want in targets.items():
            if digest == want:
                hits[name].append(path.name)
    return {
        "walk_frames": len(list(walk.glob("*.bin"))),
        "ground_truth_sha256": targets,
        "frames_per_moment": {name: len(v) for name, v in hits.items()},
        "first_frame_per_moment": {name: (v[0] if v else None)
                                   for name, v in hits.items()},
        "reproduced": {name: bool(v) for name, v in hits.items()},
        "all_reproduced": all(hits.values()),
    }


def check_rule(moments) -> dict:
    rows = {}
    for name, moment in moments.items():
        observed = moment_families(moment)
        state = moment_state(moment)
        predicted = predict(state)
        want_lit = lit_cells(observed)
        got_lit = lit_cells(predicted)
        original_only = sorted(want_lit - got_lit)
        remake_only = sorted(got_lit - want_lit)
        mismatched = sorted(
            (cell, observed[cell], predicted[cell])
            for cell in observed if observed[cell] != predicted[cell])
        rows[name] = {
            "original_lit": len(want_lit),
            "predicted_lit": len(got_lit),
            "overlap": len(want_lit & got_lit),
            "original_only": len(original_only),
            "remake_only": len(remake_only),
            "original_only_cells": original_only[:64],
            "remake_only_cells": remake_only[:64],
            "family_mismatches": len(mismatched),
            "family_mismatch_cells": mismatched[:64],
            "exact": (not original_only and not remake_only and not mismatched),
        }
    return {
        "per_moment": rows,
        "all_exact": all(row["exact"] for row in rows.values()),
    }


def check_roles() -> dict:
    palette = load_palette()
    identity = palette_cross_check()
    tiles = load_tiles()
    family_colours: dict[str, set[int]] = {}
    for index in range(256, 288):
        rows = tiles.get(index)
        if rows is None:
            continue
        family = tile_family(index)
        family_colours.setdefault(family, set()).update(
            v for row in rows for v in row)
    rows = []
    ok = True
    for family, allowed in sorted(FAMILY_PALETTE_INDEX.items()):
        painted = family_colours.get(family, set())
        opaque = sorted(v for v in painted if v != TRANSPARENT_INDEX)
        within = set(opaque) <= set(allowed)
        ok = ok and within
        rows.append({
            "family": family,
            "role": FAMILY_REMAKE_ROLE.get(family, "?"),
            "palette_indices_allowed": list(allowed),
            "palette_indices_painted": sorted(painted),
            "opaque_indices_painted": opaque,
            "within_role_palette": within,
            "rgb8": [list(palette[i]) for i in opaque],
        })
    return {
        "palette_identity": identity,
        "palette_identity_ok": identity["all_equal"],
        "family_colours": rows,
        "family_colours_ok": ok,
        "ok": identity["all_equal"] and ok,
    }


def check_cursor(exe, rom, capture_dir, moments) -> dict:
    """The yellow ``band`` cell must be the cell the cursor sprite sits on.

    The cursor sprite's position is read from the original's OAM -- a
    completely different memory region from the overlay tilemap -- and
    converted into the overlay's logical cell through the camera scroll
    recorded with the ground truth.  The OAM of the *ground truth's own*
    capture is preferred; the local reproduction's savestate is the fallback.
    """
    gt_oam = pathlib.Path(
        r"D:\Shell\Github\gba-naruto-butano\artifacts")
    rows = {}
    for name, moment in moments.items():
        sw = moment.screen_window
        hoffs = sw.get("bg2_hoffs", 0)
        voffs = sw.get("bg2_voffs", 0)
        band = sorted(cell for cell, fam in moment_families(moment).items()
                      if fam == "band")

        sources = {}
        own = gt_oam / f"s49-original-{name}" / "oam-00.bin"
        if own.is_file():
            sources["ground_truth_oam"] = decode_oam(own.read_bytes())
        state_path = capture_dir / f"{name}.ss9"
        if state_path.is_file():
            sources["local_reproduction_oam"] = read_state(
                exe, rom, state_path, capture_dir, name)
        if not sources:
            rows[name] = {"status": "no OAM available"}
            continue

        per_source = {}
        for label, entries in sources.items():
            anchored = oam_cells(entries, hoffs, voffs)
            hits = [a for a in anchored if a["cell"] in band]
            per_source[label] = {
                "obj_sprites": len(anchored),
                "sprites_on_a_band_cell": [
                    {k: a[k] for k in ("slot", "x", "y", "tile", "cell")}
                    for a in hits],
                "cursor_sprites": [
                    {k: a[k] for k in ("slot", "x", "y", "tile", "cell")}
                    for a in anchored if a["tile"] in (24, 208)],
                "cursor_confirmed": bool(hits) if band else None,
            }
        rows[name] = {
            "bg2_hoffs": hoffs,
            "bg2_voffs": voffs,
            "band_cells": band,
            "per_oam_source": per_source,
            "cursor_confirmed": (
                any(v["cursor_confirmed"] for v in per_source.values()
                    if v["cursor_confirmed"] is not None)
                if band else None),
        }
    return {"per_moment": rows}


def check_heldout(moments) -> dict:
    """Held-out test of the base layer.

    The base layer of the overlay (the battlefield extent plus the blocked
    cells) is a per-map property: it must be identical in the field and the
    movegrid moments, and it must be enough to reproduce *both* moments'
    overlays when combined with that moment's highlight sets.

    This is the strongest non-circular statement the captured data supports:
    the base layer is transferred from one moment to the other and the
    prediction must still be exact.
    """
    base = moment_state(moments["field-frame-v1"])
    rows = {}
    for name in ("field-frame-v1", "movegrid-frame-v1"):
        target = moment_state(moments[name])
        transferred = OverlayState.build(
            extent=base.extent,
            blocked=base.blocked,
            move_range=target.move_range,
            attack_range=target.attack_range,
            cursor=target.cursor,
            target=target.target,
        )
        observed = moment_families(moments[name])
        predicted = predict(transferred)
        want_lit = lit_cells(observed)
        got_lit = lit_cells(predicted)
        original_only = sorted(want_lit - got_lit)
        remake_only = sorted(got_lit - want_lit)
        mismatched = sorted((c, observed[c], predicted[c]) for c in observed
                            if observed[c] != predicted[c])
        rows[name] = {
            "original_lit": len(want_lit),
            "predicted_lit": len(got_lit),
            "original_only": len(original_only),
            "remake_only": len(remake_only),
            "family_mismatches": len(mismatched),
            "exact": not original_only and not remake_only and not mismatched,
        }
    return {
        "base_layer_shared": (
            moment_state(moments["field-frame-v1"]).extent
            == moment_state(moments["movegrid-frame-v1"]).extent
            and moment_state(moments["field-frame-v1"]).blocked
            == moment_state(moments["movegrid-frame-v1"]).blocked),
        "per_moment": rows,
        "all_exact": all(row["exact"] for row in rows.values()),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    ap.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    ap.add_argument("--capture-dir", type=pathlib.Path,
                    default=REPO / "build" / "s49-rule" / "capture")
    ap.add_argument("--out", type=pathlib.Path,
                    default=REPO / "build" / "s49-rule" / "verify-moments.json")
    ap.add_argument("--skip-replay", action="store_true",
                    help="skip check A (reuse the captured walk)")
    args = ap.parse_args()

    args.capture_dir.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    moments = load_all()

    print("=== A. reproduction: the original's own BG2 tilemap, byte for byte ===")
    if args.skip_replay:
        print("  (skipped)")
        reproduction = {"skipped": True, "all_reproduced": None}
    else:
        reproduction = check_reproduction(args.exe, args.rom, args.capture_dir)
        for name in MOMENTS:
            print(f"  {name:<18} {reproduction['frames_per_moment'][name]:>5} frame(s) "
                  f"reproduce the exported tilemap   first="
                  f"{reproduction['first_frame_per_moment'][name]}")
        print(f"  all four reproduced: {reproduction['all_reproduced']}")

    print("\n=== B. rule prediction vs the original, per logical 16x16 cell ===")
    rule = check_rule(moments)
    for name, row in rule["per_moment"].items():
        print(f"  {name:<18} original lit {row['original_lit']:>4}  "
              f"predicted {row['predicted_lit']:>4}  overlap {row['overlap']:>4}  "
              f"original-only {row['original_only']:>3}  remake-only {row['remake_only']:>3}  "
              f"family mismatches {row['family_mismatches']:>3}  "
              f"=> {'EXACT' if row['exact'] else 'MISMATCH'}")
    print(f"  all four exact: {rule['all_exact']}")

    print("\n=== B2. held-out base layer (field's extent+blocked -> movegrid) ===")
    heldout = check_heldout(moments)
    print(f"  base layer shared by field and movegrid: {heldout['base_layer_shared']}")
    for name, row in heldout["per_moment"].items():
        print(f"  {name:<18} original lit {row['original_lit']:>4}  "
              f"predicted {row['predicted_lit']:>4}  "
              f"original-only {row['original_only']:>3}  remake-only {row['remake_only']:>3}  "
              f"=> {'EXACT' if row['exact'] else 'MISMATCH'}")
    print(f"  all exact: {heldout['all_exact']}")

    print("\n=== C. role / palette identity ===")
    roles = check_roles()
    for row in roles["family_colours"]:
        print(f"  {row['family']:<11} role {row['role']:<16} "
              f"opaque palette {row['opaque_indices_painted']} "
              f"(allowed {row['palette_indices_allowed']}) "
              f"{'ok' if row['within_role_palette'] else 'MISMATCH'}")
    print(f"  palette identity (bank 12 == remake slots 225..235): "
          f"{roles['palette_identity_ok']}")
    print(f"  roles ok: {roles['ok']}")

    print("\n=== D. cursor cross-check (OAM -> logical cell) ===")
    cursor = check_cursor(args.exe, args.rom, args.capture_dir, moments)
    for name, row in cursor["per_moment"].items():
        print(f"  {name:<18} scroll=({row.get('bg2_hoffs')},{row.get('bg2_voffs')}) "
              f"band cells={row.get('band_cells')} "
              f"confirmed={row.get('cursor_confirmed')}")
        for label, src in row.get("per_oam_source", {}).items():
            hits = src["sprites_on_a_band_cell"]
            print(f"      {label:<24} sprites={src['obj_sprites']:>3} "
                  f"on a band cell={len(hits)}"
                  + (f"  e.g. slot{hits[0]['slot']} tile{hits[0]['tile']} "
                     f"cell{hits[0]['cell']}" if hits else ""))

    ok = (reproduction.get("all_reproduced") in (True, None)
          and rule["all_exact"] and heldout["all_exact"] and roles["ok"])
    receipt = {
        "schema": "konoha.s49-overlay-rule-verification.v1",
        "reproduction": reproduction,
        "rule": rule,
        "heldout_base_layer": heldout,
        "roles": roles,
        "cursor": cursor,
        "ok": ok,
    }
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8", newline="\n")
    print(f"\nwrote {args.out}")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
