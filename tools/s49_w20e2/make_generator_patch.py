#!/usr/bin/env python3
"""W20-E2: build the generator seed-assertion patch (a wiring request).

The generator lives in the shared remake tree
(``D:\\Shell\\Github\\gba-naruto-butano\\tools\\generate_butano_battle_scenario_content.py``)
which this stream must not modify.  This script writes a *modified copy* next
to the lane receipts plus a unified diff, so the parent can apply the change
with ``git apply``.

The change adds one thing: a post-load assertion that the formation seeds the
fidelity work depends on are still present, so a future regeneration from a
stale data source fails loudly instead of silently zeroing them.
"""

from __future__ import annotations

import difflib
import pathlib

SOURCE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\tools\generate_butano_battle_scenario_content.py"
)
OUT_DIR = pathlib.Path(r"D:\Github\gba-naruto\build\w20-e2\gen")

ASSERTION = '''
# The formation ``battle_experience`` seeds the settlement screen depends on.
# They are read from the ROM formation table (0x5461C4 + group*0x1AAC +
# variant*0x08E4 + 4 + record*0x0B8, field +0x0C, u16 little endian) by the
# reverse line and land here through ``positions/bank.json``.  If the artifact
# is ever regenerated from a stale data source these silently fall back to 0
# and the settlement screen loses its 「戰鬥分」row without any test failing,
# so they are pinned here.
EXPECTED_BATTLE_EXPERIENCE = {
    # battle_id, variant, record -> seed
    (14, 0, 4): 50,
    (14, 0, 5): 50,
    (14, 0, 6): 50,
    (14, 0, 7): 50,
    (14, 0, 8): 50,
    (14, 2, 4): 75,
    (14, 2, 5): 75,
    (14, 2, 6): 75,
    (14, 2, 7): 75,
    (14, 2, 8): 75,
    (41, 0, 1): 50,
}


def _assert_expected_battle_experience(
        scenarios: list[dict[str, Any]]) -> None:
    for (battle_id, variant_id, record_id), expected in (
            sorted(EXPECTED_BATTLE_EXPERIENCE.items())):
        actual = scenarios[battle_id]["variants"][variant_id][record_id][
            "battle_experience"]
        if actual != expected:
            raise ValueError(
                f"formation seed mismatch at battle {battle_id} variant "
                f"{variant_id} record {record_id}: {actual} != {expected}"
            )

'''

ANCHOR = "def _load_json(path: Path) -> dict[str, Any]:"
MAIN_ANCHOR = "    scenarios = load_scenario_content(root)\n"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    original = SOURCE.read_text(encoding="utf-8")
    modified = original.replace(ANCHOR, ASSERTION.lstrip("\n") + "\n" + ANCHOR, 1)
    modified = modified.replace(
        MAIN_ANCHOR,
        MAIN_ANCHOR + "    _assert_expected_battle_experience(scenarios)\n",
        1,
    )
    if modified == original:
        print("ERROR: no anchor found; the shared generator changed shape")
        return 2
    new_path = OUT_DIR / "generate_butano_battle_scenario_content.py"
    new_path.write_text(modified, encoding="utf-8", newline="\n")
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        modified.splitlines(keepends=True),
        fromfile="a/tools/generate_butano_battle_scenario_content.py",
        tofile="b/tools/generate_butano_battle_scenario_content.py",
        n=3,
    )
    patch = "".join(diff)
    patch_path = OUT_DIR / "generator-seed-assertion.patch"
    patch_path.write_text(patch, encoding="utf-8", newline="\n")
    print("->", new_path)
    print("->", patch_path)
    print(f"patch lines: {len(patch.splitlines())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
