#!/usr/bin/env python3
"""Rebuild `sequel/editor.db` from the repository content.

Why this tool exists
--------------------
`sequel/editor.db` is **gitignored** (it is a binary SQLite database, and
`*.db` is in `.gitignore`).  That is fine for a working copy, but it means
that on a **clean checkout** the editor -> build override chain is idle:
`tools/build_db_patches.py` finds no `editor.db`, every generator returns an
empty list, and the build silently produces no overrides at all.  Nobody
notices, because "no overrides" is also what a correct build looks like.

This tool makes the database **derivable** instead of hand-carried:

  1. create the editor schema (`web-editor/backend/database.py::init_db`),
  2. create + fill the ROM tables from `sequel/content/*/bank.json`
     (`web-editor/backend/rom_models.py`),
  3. import the editable rows (units / dialogues / skills / story beats /
     chapters / battle configs / audio files / unit positions) from the same
     content banks (`tools/import_rom_to_editor.py`),
  4. prove the chain is no longer idle: run `tools/build_db_patches.py` over
     the fresh database and require it to produce **at least one** override
     patch.

Usage
-----
    python tools/build_editor_db.py                 # build (or refresh) it
    python tools/build_editor_db.py --check         # only verify the chain
    python tools/build_editor_db.py --db PATH       # use another database

Exit codes
----------
    0   the database exists and the override chain produces patches
    1   the chain is still idle (no overrides) -- the database is not usable
    2   the database could not be built
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tools"), str(ROOT / "web-editor" / "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DEFAULT_DB = ROOT / "sequel" / "editor.db"

# The editor's own tables, in the order the import tool fills them.
EDITABLE_TABLES = ("units", "dialogues", "skills", "story_beats",
                   "chapters", "battle_configs", "audio_files",
                   "unit_positions")


def build(db_path: pathlib.Path) -> int:
    import database  # web-editor/backend/database.py
    import rom_models  # web-editor/backend/rom_models.py
    import import_rom_to_editor as ire

    db_path.parent.mkdir(parents=True, exist_ok=True)
    # `init_db` and the rom tables use the DB path from the environment, so
    # point it at the requested file for the whole build.
    os.environ["DB_PATH"] = str(db_path)
    database.DB_PATH = str(db_path)

    database.init_db()
    conn = sqlite3.connect(str(db_path))
    try:
        rom_models.init_rom_tables(conn)
        rom_models.populate_rom_tables(conn)
    finally:
        conn.close()

    conn = sqlite3.connect(str(db_path))
    try:
        for fn in (ire.import_units, ire.import_dialogues, ire.import_skills,
                   ire.import_story_beats, ire.import_chapters,
                   ire.import_battle_configs, ire.import_audio_files,
                   ire.import_unit_positions):
            fn(conn)
    finally:
        conn.close()
    print(f"built {db_path}")
    return 0


def counts(db_path: pathlib.Path) -> dict[str, int]:
    conn = sqlite3.connect(str(db_path))
    try:
        out = {}
        for table in EDITABLE_TABLES:
            try:
                out[table] = conn.execute(
                    f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.Error:
                out[table] = -1
        return out
    finally:
        conn.close()


def chain_patches(db_path: pathlib.Path) -> list:
    """Run **every** override generator over `db_path` and collect its output.

    The generator set is read out of `tools/build_db_patches.py` itself, so
    a generator that is added there later is covered automatically.

    Each generator's patches are split into *applied* and *rejected*: a
    generator whose base or column no longer matches the content bank
    rejects **every** row, and that must be visible rather than counted as
    success.
    """
    import build_db_patches as bdp
    out = []
    names = sorted(n for n in dir(bdp) if n.startswith("generate_"))
    for name in names:
        fn = getattr(bdp, name)
        try:
            produced = fn(db_path)
        except Exception as exc:  # a generator that raises is a failure
            raise RuntimeError(f"{name} raised {type(exc).__name__}: {exc}")
        if isinstance(produced, dict):
            produced = list(produced.values())
        applied = 0
        rejected = 0
        for patch in produced or []:
            kind = str(patch.get("type", "")) if isinstance(patch, dict) else ""
            if ("error" in kind or "unmapped" in kind or "reject" in kind
                    or "skipped" in kind):
                rejected += 1
            else:
                applied += 1
        if applied or rejected:
            out.append((name, applied, rejected))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=pathlib.Path, default=DEFAULT_DB)
    parser.add_argument("--check", action="store_true",
                        help="only verify the chain, do not rebuild")
    args = parser.parse_args(argv)

    db_path = args.db
    if not args.check:
        rc = build(db_path)
        if rc:
            return rc

    if not db_path.is_file():
        print(f"FAIL: {db_path} does not exist", file=sys.stderr)
        return 1

    table_counts = counts(db_path)
    print("editor.db tables:")
    for table, n in table_counts.items():
        print(f"  {table:18s} {n:>6d}")

    try:
        patches = chain_patches(db_path)
    except Exception as exc:
        print(f"FAIL: the override chain raised: {exc}", file=sys.stderr)
        return 1

    total = sum(n for _, n, _ in patches)
    rejected_total = sum(r for _, _, r in patches)
    print("override chain:")
    for name, n, r in patches:
        flag = "  <-- rejects everything" if n == 0 and r else ""
        print(f"  {name:34s} applied {n:>6d}  rejected {r:>5d}{flag}")
    print(f"  {'TOTAL':34s} applied {total:>6d}  rejected {rejected_total:>5d}")

    if total == 0:
        print("FAIL: the override chain is idle -- the editor -> build link "
              "produces nothing", file=sys.stderr)
        return 1
    print(f"OK: the editor -> build override chain produces {total} patch(es)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
