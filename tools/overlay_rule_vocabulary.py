#!/usr/bin/env python3
"""Extract the original overlay's rule vocabulary from the exported ground truth.

The Butano line exported the original game's second background layer for four
moments of the S49 battle (field / movegrid / grid16 / banner).  Each export
labels every one of the 1,024 tilemap cells with a `family` (blank / solid /
edge variants), the palette bank, and the tile index.

This script prints:

* the family vocabulary and, per family, the distinct tile indices used;
* the per-moment cell counts;
* the geometry summary;
* the still-open questions recorded in the export.

That is the input a remake-side implementation needs: it says which cell
families exist, which tile each family uses, and how many cells each moment
lights -- without anyone having to re-derive it from pixels.
"""

from __future__ import annotations

import json
import pathlib
from collections import Counter, defaultdict

GT = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\s49-original-movegrid-tilemap-v1"
)
MOMENTS = ("field-frame-v1", "movegrid-frame-v1", "grid16-frame-v1", "banner-frame-v1")


def main() -> int:
    if not GT.is_dir():
        print(f"ERR missing {GT}")
        return 2

    family_tiles: dict[str, Counter] = defaultdict(Counter)
    family_cells: dict[str, Counter] = defaultdict(Counter)
    banks: Counter = Counter()
    lit_total: Counter = Counter()
    unknown_text: dict[str, str] = {}

    for moment in MOMENTS:
        path = GT / f"{moment}.bg2-tilemap.json"
        if not path.is_file():
            print(f"!! missing {path.name}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))

        for cell in data.get("cells", []):
            family = cell.get("family")
            family_cells[family][moment] += 1
            banks[cell.get("palette_bank")] += 1
        for cell in data.get("lit_cells", []):
            family = cell.get("family")
            family_tiles[family][cell.get("tile")] += 1
            lit_total[moment] += 1

        counts = data.get("counts", {})
        geometry = data.get("geometry", {})
        print(f"=== {moment} ===")
        print(f"  counts  : {json.dumps(counts, ensure_ascii=False)}")
        print(f"  geometry: {json.dumps(geometry, ensure_ascii=False)[:600]}")
        print(f"  registers: {json.dumps(data.get('registers', {}), ensure_ascii=False)[:300]}")
        print(f"  screen_window: {json.dumps(data.get('screen_window', {}), ensure_ascii=False)[:400]}")
        print(f"  overlay_tile_set: {json.dumps(data.get('overlay_tile_set', {}), ensure_ascii=False)[:400]}")
        for key, value in (data.get("unknowns") or {}).items():
            unknown_text[key] = str(value)
        print()

    print("=== family vocabulary (all moments) ===")
    for family in sorted(family_cells, key=lambda f: -sum(family_cells[f].values())):
        per_moment = {m: family_cells[family].get(m, 0) for m in MOMENTS}
        tiles = dict(family_tiles.get(family, {}))
        print(f"  {family:<12} cells={per_moment}  tiles={tiles}")

    print("\n=== palette banks used ===")
    for bank, count in banks.most_common():
        print(f"  bank {bank}: {count} cells")

    print("\n=== lit cell counts per moment ===")
    for moment in MOMENTS:
        print(f"  {moment}: {lit_total.get(moment, 0)}")

    print("\n=== still-open questions recorded by the exporter ===")
    for key, value in unknown_text.items():
        print(f"  {key}: {value[:400]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
