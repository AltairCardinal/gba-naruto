#!/usr/bin/env python3
"""U2: scale every ``settle`` value of a U2 key script.

The offline controller and the ROM do not run at the same speed, so a key
script that works offline can lose inputs on the ROM when the ROM's
animations are slower.  Scaling the waits is the cheapest way to give the
ROM more room; the key *sequence* itself is unchanged.

Usage::

    python tools/s49_battle_balance/u2_scale_settle.py \\
        --script build/s49-battle-balance/u2/routeA.json \\
        --factor 2 --out build/s49-battle-balance/u2/routeA-x2.json
"""

from __future__ import annotations

import argparse
import json
import pathlib


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", type=pathlib.Path, required=True)
    parser.add_argument("--factor", type=float, default=2.0)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--minimum", type=int, default=0)
    args = parser.parse_args()

    script = json.loads(args.script.read_text(encoding="utf-8"))
    for step in script.get("steps", []):
        settle = int(round(int(step.get("settle", 90)) * args.factor))
        step["settle"] = max(settle, args.minimum)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(script, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n")
    print(f"wrote {args.out} (factor {args.factor})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
