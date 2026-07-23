#!/usr/bin/env python3
"""Export hash-bound scenario 41 save-state reference bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.inspect_mgba_savestate import (  # noqa: E402
    TASK_CONTEXT_BASE,
    TASK_CONTEXT_SIZE,
    load_gba_state,
    png_screen_fingerprint,
)


EXPECTED_ROM_SHA256 = (
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
)


@dataclass(frozen=True)
class Checkpoint:
    path: Path
    sha256: str
    screen_sha256: str | None = None


_CHECKPOINT_ROOT = REPO_ROOT / "artifacts/runtime-checkpoints"
CHECKPOINTS = {
    "player-turn": Checkpoint(
        _CHECKPOINT_ROOT / "scenario-41-player-turn.ss9",
        "ba411edee4ccf73c1b5a8392735d23dbbef6f8edce5240aef7acdcd76c436171",
        "2847f0d1c2c3a6ba7e67275811a0c1ef918d02d999a1acad4ea328088e3712ce",
    ),
    "first-movedone-facing": Checkpoint(
        _CHECKPOINT_ROOT / "scenario-41-first-movedone-facing.ss9",
        "1bc95c63cb11d469e4b2e80e8bae5a937f04ad40e18d7a15706fc261cb9ffb94",
        "54f5409df260ee24f35a4940069f32d4bb77b56e42acce566343b8814a73564f",
    ),
    "first-turn-technique-menu": Checkpoint(
        _CHECKPOINT_ROOT / "scenario-41-first-turn-technique-menu.ss9",
        "039030d6b754f66a07582356402c9eaf99832badaf0821939af4dbdc8e83c6c1",
        "17644dae174acd0e26b9b004f3e8a03b9fd9a43b523cb3dff40f978b4f9b6eef",
    ),
    "turn-1-complete": Checkpoint(
        _CHECKPOINT_ROOT / "scenario-41-turn-1-complete.ss9",
        "a9e255d86f983c0b6d062aee2467674d89685d8ca88896e2f2fefe6b3a7e5ae5",
        "fa0bb87531d63182e939cfda56b3f2d9dccc21a9308572bccf18b6cc77d5d186",
    ),
    "victory": Checkpoint(
        _CHECKPOINT_ROOT / "scenario-41-victory.ss9",
        "7a24a7a628c301493418d93e88ab239c0fbb6b77de139a67b91e8e0bcadf6200",
        "6fc3d928abd921413dc8603c094387afa9c0c0b297fe8d9a5d79d7211396ffa2",
    ),
    "postbattle": Checkpoint(
        _CHECKPOINT_ROOT / "scenario-41-postbattle.ss9",
        "950652381ae03ad60ad028f9063b9fc22f133ea532396fbafe7f5353d2553162",
        "298acd7711c13879ecb91cf3eb88563060b79584944289716a1811baa588e0ef",
    ),
}

REGIONS = {
    "io": (0x04000000, 0x00400),
    "pram": (0x05000000, 0x00400),
    "oam": (0x07000000, 0x00400),
    "vram": (0x06000000, 0x18000),
    "iwram": (0x03000000, 0x08000),
    "ewram": (0x02000000, 0x40000),
}
UNIT_POOL_ADDRESS = 0x020240C0
UNIT_POOL_SIZE = 21 * 0x1D4


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _task_2(state) -> dict[str, object]:
    address = TASK_CONTEXT_BASE + TASK_CONTEXT_SIZE
    raw = state.read_memory(address, TASK_CONTEXT_SIZE)
    lr = int.from_bytes(raw[8:12], "little")
    return {
        "type": raw[0],
        "delay": raw[1],
        "sp": f"0x{int.from_bytes(raw[4:8], 'little'):08X}",
        "lr": f"0x{lr:08X}",
        "resume_pc": f"0x{((lr - 1) if lr & 1 else lr):08X}",
    }


def _validated_sources(
    rom: Path, checkpoints: dict[str, Checkpoint] = CHECKPOINTS
) -> list[tuple[str, Checkpoint, object, dict]]:
    actual_rom_hash = _sha256_file(rom)
    if actual_rom_hash != EXPECTED_ROM_SHA256:
        raise ValueError(
            f"ROM SHA-256 mismatch: {actual_rom_hash}; expected {EXPECTED_ROM_SHA256}"
        )

    sources = []
    for name, checkpoint in checkpoints.items():
        actual_hash = _sha256_file(checkpoint.path)
        if actual_hash != checkpoint.sha256:
            raise ValueError(
                f"{name} checkpoint SHA-256 mismatch: {actual_hash}; "
                f"expected {checkpoint.sha256}"
            )
        state = load_gba_state(checkpoint.path)
        screen = png_screen_fingerprint(checkpoint.path)
        if (
            checkpoint.screen_sha256 is not None
            and screen["rgb_pixels_sha256"] != checkpoint.screen_sha256
        ):
            raise ValueError(f"{name} normalized screen SHA-256 mismatch")
        sources.append((name, checkpoint, state, screen))
    return sources


def export_reference(
    rom: Path,
    output_dir: Path,
    checkpoints: dict[str, Checkpoint] | None = None,
) -> dict[str, object]:
    """Create one immutable reference bundle; existing targets are never replaced."""

    rom = Path(rom)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"output already exists: {output_dir}")

    if checkpoints is None:
        checkpoints = CHECKPOINTS
    sources = _validated_sources(rom, checkpoints)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=output_dir.parent)
    )
    published = False
    try:
        manifest: dict[str, object] = {
            "schema_version": 1,
            "rom": _source_label(rom),
            "rom_sha256": EXPECTED_ROM_SHA256,
            "boundaries": {},
        }
        boundaries = manifest["boundaries"]
        assert isinstance(boundaries, dict)
        for name, checkpoint, state, screen in sources:
            boundary_dir = temporary / name
            boundary_dir.mkdir()
            region_manifest = {}
            for region_name, (address, size) in REGIONS.items():
                data = state.read_memory(address, size)
                filename = f"{region_name}.bin"
                (boundary_dir / filename).write_bytes(data)
                region_manifest[region_name] = {
                    "address": f"0x{address:08X}",
                    "file": filename,
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }

            unit_pool = state.read_memory(UNIT_POOL_ADDRESS, UNIT_POOL_SIZE)
            boundaries[name] = {
                "source": _source_label(checkpoint.path),
                "checkpoint_sha256": checkpoint.sha256,
                "screen": screen,
                "regions": region_manifest,
                "battle_control_0x02026804": state.read_memory(
                    0x02026804, 8
                ).hex(),
                "action_fields_0x0200A880": state.read_memory(
                    0x0200A880, 8
                ).hex(),
                "task_2": _task_2(state),
                "unit_pool": {
                    "address": f"0x{UNIT_POOL_ADDRESS:08X}",
                    "size": len(unit_pool),
                    "sha256": hashlib.sha256(unit_pool).hexdigest(),
                },
            }

        manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
        (temporary / "manifest.json").write_bytes(manifest_bytes)
        os.rename(temporary, output_dir)
        published = True
        return manifest
    finally:
        if not published and temporary.exists():
            shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = export_reference(args.rom, args.output)
    print(json.dumps({
        "output": str(args.output),
        "boundary_count": len(manifest["boundaries"]),
        "rom_sha256": manifest["rom_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
