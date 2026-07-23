#!/usr/bin/env python3
"""Export hash-bound scenario 41 result, growth and postbattle dialogue states."""

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


EXTENDED_CHECKPOINTS = {
    "result": _checkpoint(
        "result",
        "0c1d378246fe56211cf80168506ef64b62d508037d4ea88cdcdee5b2d446b7f6",
        "1d1ba6fc50371466154ecb0e7ece04483f83cb34f7755e310a4dd1f15818a20d",
    ),
    "level-up-1": _checkpoint(
        "level-up-1",
        "98102cba5d21a2f65346f90dff652b8099f0fab5409c152ebc8fa86e58da1cf4",
        "893383f034d33d8ed23d13be8f773162af061945ebd0df8d54d5003b3072563a",
    ),
    "level-up-2": _checkpoint(
        "level-up-2",
        "456e4d3bffc4ddac763cce5d5dd9f24af46183314999e7825520785f919d1036",
        "315942dc3e84edf2ac348c0c520469d982271b6d4b002993a516b8c50e5430f1",
    ),
}

_DIALOGUE_HASHES = (
    ("d8fef181a40b79b71999b85dbfc2aadeb8b04d479d43bfa1de73c52dbe0f00c9", "6095ef80772b0dda9eea3657651d8a423605e2baf74fa78ab8f6b4bfe424ad5f"),
    ("2dd6209a5605ed4c1e04d99c4d7db77fb993a53944b2ecb4a5b40a898b38bc63", "1a233810fed68c3e44efcd56971ea3260bf509d707e4b6666452003721729db2"),
    ("09df62b1aa0633023a7c2643f734bd4ddafac0e85a8fd0a5af0033fd74a80797", "513640213c9af3e4e91828e764c8d88c3759a7d054fef45cd63c43b27870f91c"),
    ("24c923d9db2212f056499e4846ac9f2c28ac7954a6dd7782f201d78da03b6432", "ff9d173bd814e937c6081f22aba9e847377b3373a9f9177e3248dac86771ad10"),
    ("9d68008dd469a0832a16f938fc2d45034673162d8a3a1186888bfb11e77bad89", "fd494ad28f23dbcfd05edb6ba8e2da8ce60be68345e76859e7d1a63eae81298f"),
    ("761c9f87299a8d9c5dfd5de930ac4ea3eb3a0c226af6f8d6db1b4f19c9cc658d", "fa93f4adfbf0ff6fef431bcadc1c3214b2897cb554731748a0b90ddca620579a"),
    ("c678be26972b859aba1ecd83aa5b4f773011bc5f0fba04e3e4bf3ffb4bf67d24", "1d74badc844a08e0450f09596497849af7ec1153b620342014ef4562c5024e27"),
    ("62adcd52b577f73ca1ffd6d2d4ec3b9fafa2a2b130ac644a6834e2a56a50d4d8", "e40cc06e62fdbada1d031cb0228af1d2b087e0277b4a3957c80b581e7942116f"),
    ("5635916176865f63b12154ea1c68e202393baaf6e1427473fb6be8a84b18eba8", "ddfd148774b09e10b7fc60f5c8e30b57e3dbf9ba05259535b5b852b868e4cbc6"),
    ("c2bb5b242ae773b4e9fb4ae509f486e99ed01d2e1ff362e5d95fe1acff54bed6", "ad10d07ba429064ac2425302d9cc546a63effcbec4a81393eac87e2642e39ec7"),
    ("bf821ecdd9945c123576ff7f26717c4d2018f07e623c36cb83dc2bb0fa569555", "561bd80e8d9ac6ec7ba2f98755b0ce804cba14bd43a8899897569f35069f4e38"),
)
for index, (state_hash, screen_hash) in enumerate(_DIALOGUE_HASHES, 1):
    name = f"postbattle-dialogue-{index}"
    EXTENDED_CHECKPOINTS[name] = _checkpoint(name, state_hash, screen_hash)


def export_extended_reference(rom: Path, output: Path) -> dict[str, object]:
    return export_reference(rom, output, EXTENDED_CHECKPOINTS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = export_extended_reference(args.rom, args.output)
    print(json.dumps({"output": str(args.output), "boundary_count": len(manifest["boundaries"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
