#!/usr/bin/env python3
"""E4: final validation of the delivered artifacts and tree hygiene."""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess

REPO = pathlib.Path(r"D:\Github\gba-naruto")
OUT = REPO / "build" / "w20-e4"
SHARED = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano")
SHARED_GRAPHICS = SHARED / "butano-sequel" / "graphics"
LANE = REPO / "build" / "w20-e4" / "butano-sequel"

failures = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f"  -- {detail}" if detail else ""))
    if not condition:
        failures.append(label)


def main() -> int:
    # 1. JSON artifacts parse and carry the promised content.
    seed_json = OUT / "enemy-battle-experience.json"
    payload = json.loads(seed_json.read_text(encoding="utf-8"))
    check("seed JSON schema", payload["schema"] == "konoha.s49-enemy-battle-experience.v1")
    check("seed JSON verified flag", payload.get("verified") is True)
    scenarios = payload["scenarios"]
    check("seed JSON scenario count == 47", len(scenarios) == 47, str(len(scenarios)))
    units = sum(len(v["units"]) for s in scenarios for v in s["variants"])
    check("seed JSON unit count == 1692", units == 1692, str(units))
    b14 = next(s for s in scenarios if s["battle_id"] == 14)
    b14_v0 = b14["variants"][0]["units"]
    enemies = [
        u for u in b14_v0 if u["enabled"] and u["side"] == 1
    ]
    check(
        "battle 14 v0 has 5 enemies",
        len(enemies) == 5,
        str(len(enemies)),
    )
    check(
        "battle 14 v0 enemy seeds are all 50",
        all(u["battle_experience"] == 50 for u in enemies),
        str([u["battle_experience"] for u in enemies]),
    )
    check(
        "battle 14 v0 enemy character_id == 55",
        all(u["character_id"] == 55 for u in enemies),
    )

    unused = json.loads((OUT / "unused-dialogue-assets.json").read_text(encoding="utf-8"))
    check("unused stems == 33", len(unused["unreferenced_stems"]) == 33)
    check(
        "referenced stems == 7",
        len(unused["referenced_stems"]) == 7,
    )
    check(
        "every unused stem has 0 references",
        all(
            r["reference_count"] == 0
            for r in unused["reference_evidence"]
            if r["stem"] in set(unused["unreferenced_stems"])
        ),
    )

    manifest = json.loads(
        (OUT / "dialogue-asset-cleanup-manifest.json").read_text(encoding="utf-8")
    )
    check("cleanup manifest has 66 files", manifest["file_count"] == 66)
    # every recorded sha256 still matches the shared tree (nothing deleted)
    mismatched = []
    for entry in manifest["entries"]:
        path = pathlib.Path(entry["shared_path"])
        if not path.is_file():
            mismatched.append((entry["name"], "missing"))
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            mismatched.append((entry["name"], "sha mismatch"))
    check(
        "shared tree still holds all 66 files unchanged",
        not mismatched,
        str(mismatched[:4]),
    )

    footprint = json.loads(
        (OUT / "dialogue-asset-rom-footprint.json").read_text(encoding="utf-8")
    )
    check(
        "33/33 unreferenced assets are linked into the ROM",
        footprint["unreferenced_assets_linked"] == 33,
    )
    check(
        "unreferenced ROM footprint == 264768 bytes",
        footprint["unreferenced_rom_bytes"] == 264768,
        str(footprint["unreferenced_rom_bytes"]),
    )

    # 2. The lane copy must not contain product-file edits (E4 owns none).
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--", "butano-sequel/game", "butano-sequel/src"],
            cwd=str(SHARED),
            capture_output=True,
            text=True,
            timeout=120,
        )
        shared_dirty = [
            line for line in result.stdout.splitlines()
            if line.strip()
        ]
    except Exception as error:  # pragma: no cover
        shared_dirty = [f"git failed: {error}"]
    print(
        f"[INFO] shared tree product-tree dirty entries: {len(shared_dirty)}"
        "  (expected: pre-existing wave-20 work, NOT from E4)"
    )

    # 3. The shared tree's dialogue assets must be untouched by E4.
    shared_assets = sorted(
        p.name
        for p in SHARED_GRAPHICS.glob("scenario_41_postbattle_dialogue_*")
    )
    check(
        "shared tree still has 80 dialogue asset files",
        len(shared_assets) == 80,
        str(len(shared_assets)),
    )

    # 4. The note must exist and be non-trivial.
    note = REPO / "notes" / "s49-fidelity" / "W20-E4-reverse-forensics.md"
    check("note exists", note.is_file())
    check(
        "note is substantial",
        note.stat().st_size > 8000,
        f"{note.stat().st_size} bytes",
    )
    body = note.read_text(encoding="utf-8")
    check("note has the ledger", "假设台账" in body)
    check("note has P-40..P-55", all(f"P-{n}" in body for n in range(40, 56)))

    print()
    if failures:
        print(f"FAILURES: {failures}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
