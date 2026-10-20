#!/usr/bin/env python3
"""Replay every build_manifest producer against the FINAL ledger.

A producer that has already been promoted into the canonical ledger cannot be
replayed against that same ledger: its own current-unknown gate rejects the
call ("<label> is not current unknown" / "are no longer unknown" /
"promotion changed").  Any test that replays such a producer with the final
ledger therefore fails.

This probe enumerates the producers in production-chain order (parsed from
build_manifest), replays each one against the final ledger, and reports which
ones raise.  Read-only: it never writes to the repository.

Usage:
    /usr/local/bin/python3 probe_full_ledger_replay_20261020.py
"""

from __future__ import annotations

import inspect
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tools import audit_rom_byte_coverage as auditor  # noqa: E402

LEDGER = ROOT / "sequel/rom-byte-coverage.json"
ROM = ROOT / "rom/base.gba"
CALL_PATTERN = re.compile(r"claims \+= (_[a-z0-9_]+_claims)\(root, rom, claims\)")


def production_chain() -> list[tuple[int, str]]:
    source = inspect.getsource(auditor.build_manifest)
    found: list[tuple[int, str]] = []
    for offset, line in enumerate(source.splitlines(), start=1):
        match = CALL_PATTERN.search(line)
        if match:
            found.append((offset, match.group(1)))
    return found


def main() -> int:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    claims = ledger["claims"]
    rom = ROM.read_bytes()
    chain = production_chain()
    report = {
        "ledger_sha256_placeholder": None,
        "producer_count": len(chain),
        "raised": [],
        "ok": [],
    }
    for offset, name in chain:
        helper = getattr(auditor, name, None)
        if helper is None:
            report["raised"].append({"producer": name, "line": offset, "error": "absent"})
            continue
        started = time.monotonic()
        try:
            produced = helper(ROOT, rom, claims)
        except Exception as error:  # noqa: BLE001 - probe records every failure
            report["raised"].append(
                {
                    "producer": name,
                    "line": offset,
                    "error": f"{type(error).__name__}: {error}",
                    "seconds": round(time.monotonic() - started, 3),
                }
            )
        else:
            report["ok"].append(
                {
                    "producer": name,
                    "line": offset,
                    "claims": len(produced),
                    "seconds": round(time.monotonic() - started, 3),
                }
            )
    out = Path(__file__).resolve().parent / "full-ledger-replay-20261020.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"producers: {report['producer_count']}")
    print(f"raised against final ledger: {len(report['raised'])}")
    for row in report["raised"]:
        print(f"  RAISE {row['producer']}  ({row.get('seconds', '?')}s)  {row['error'][:140]}")
    print(f"replayed cleanly: {len(report['ok'])}")
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
