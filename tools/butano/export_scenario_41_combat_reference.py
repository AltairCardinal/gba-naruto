#!/usr/bin/env python3
"""Export hash-bound scenario 41 combat UI and dialogue boundaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.butano.export_scenario_41_reference import Checkpoint, export_reference  # noqa: E402


CHECKPOINT_ROOT = REPO_ROOT / "artifacts/runtime-checkpoints"


def _checkpoint(name: str, state_hash: str, screen_hash: str) -> Checkpoint:
    return Checkpoint(CHECKPOINT_ROOT / f"scenario-41-{name}.ss9", state_hash, screen_hash)


COMBAT_CHECKPOINTS = {
    "action-menu-0": _checkpoint(
        "action-menu-0",
        "863737740529a3fbd74931acdbc6eca822e4d01c09772e11a5800ab0097537ab",
        "8d4c2eaf7af6e2d908bfde1ee50838999be25ed0418046615238d1ed0a349679",
    ),
    "action-menu-1": _checkpoint(
        "action-menu-1",
        "21601d4d031b8c8d1147afd457267735fc42080a545fc5be16708d9f79f03d5b",
        "bfed5a83260ecf0c2fa591a1149497627ed3e4b88ceb571e541227dfccefea7a",
    ),
    "end-confirmation": _checkpoint(
        "end-confirmation",
        "6ddd7ada5ac3e58f7b3b634f40b87dbae31273487d2d31a4f37f26e739601b4a",
        "3469468b79070b6f88e9ca862094278554413c3e565a3b491e09b8b965e23a3d",
    ),
    "defense-confirmation": _checkpoint(
        "defense-confirmation",
        "695d14e7828251b6c908f8dc57a5f0e8951fc9cc877c22525479e2a687323fa3",
        "41c4c5c8e246e129653916e837bc694daa4370b88637ed357777cbae7be40c36",
    ),
    "target-select": _checkpoint(
        "target-select",
        "fee59b98fa22b1f05d083f490566aaa690406c73ead0bd808522cc660497eafc",
        "03b5baa399ffadd1a0c922706edd725b33c63864fa20ccf99e1b2c8f8e14da41",
    ),
    "attack-confirmation": _checkpoint(
        "attack-confirmation",
        "544cffbaea182a55d1963447965d95750984a915cae9877d66d6bc3aebbd560f",
        "fb30e74f8dcac135db659cd12e4539d6ff277540653898d166c048c024aaaf26",
    ),
    "combat-dialogue": _checkpoint(
        "combat-dialogue",
        "3741a385a4473919243e9f3220f9cbdf79d590b8002107f71e22f67e6b74ab1c",
        "4eaa2e010dcbe9ac7f025d51175dee4eb61ed80b63f2f052746c49fe326659b0",
    ),
    "combat-popup": _checkpoint(
        "combat-popup",
        "01f478cfafa2796cbe1652007c16e54480d2a289d1e6f54068ace8adc970300a",
        "c61889f77df91f4f5b4e336b479bf4d9929ad0c878b1415798901bb6d52e85a4",
    ),
}


def export_combat_reference(rom: Path, output: Path) -> dict[str, object]:
    return export_reference(rom, output, COMBAT_CHECKPOINTS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = export_combat_reference(args.rom, args.output)
    print(
        json.dumps(
            {"output": str(args.output), "boundary_count": len(manifest["boundaries"])},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
