#!/usr/bin/env python3
"""Export unfaded attack-animation bases from hashable mGBA GPU state."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.butano.render_scenario_41_gpu import render_mode0
from tools.inspect_mgba_savestate import load_gba_state


SOURCE_FRAMES = (56, 63)
EXPECTED_RGB_SHA256 = {
    56: "aa65f3a032c364d7dbb93aacdad175657093eab3177b7ebf853305f3dea43417",
    63: "a011d354d30a00b473ff1a400a44576188a021eacd907466aedc3bd28380fe23",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_gpu_bases(source: Path, output: Path) -> dict[str, object]:
    """Publish GPU dumps and no-brightness renders for both fade poses."""

    source = Path(source)
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    published = False
    manifest: dict[str, object] = {
        "schema_version": 1,
        "source_frames": list(SOURCE_FRAMES),
        "frames": {},
    }
    try:
        frame_records: dict[str, object] = manifest["frames"]  # type: ignore[assignment]
        for frame in SOURCE_FRAMES:
            state_path = source / f"state-{frame:04d}.ss9"
            state = load_gba_state(state_path)
            regions = {
                "io": state.read_memory(0x04000000, 0x400),
                "pram": state.read_memory(0x05000000, 0x400),
                "oam": state.read_memory(0x07000000, 0x400),
                "vram": state.read_memory(0x06000000, 0x18000),
            }
            rgb = render_mode0(
                regions["io"], regions["pram"], regions["oam"], regions["vram"]
            )
            rgb_sha256 = hashlib.sha256(rgb).hexdigest()
            if rgb_sha256 != EXPECTED_RGB_SHA256[frame]:
                raise ValueError(
                    f"frame {frame} unfaded RGB SHA-256 mismatch: {rgb_sha256}"
                )
            frame_dir = temporary / f"frame-{frame:04d}"
            frame_dir.mkdir()
            for name, payload in regions.items():
                (frame_dir / f"{name}.bin").write_bytes(payload)
            image_path = frame_dir / "unfaded.png"
            Image.frombytes("RGB", (240, 160), rgb).save(image_path)
            frame_records[str(frame)] = {
                "source_state": state_path.name,
                "source_state_sha256": _sha256(state_path),
                "rgb_sha256": rgb_sha256,
                "png_sha256": _sha256(image_path),
                "gpu_sha256": {
                    name: hashlib.sha256(payload).hexdigest()
                    for name, payload in regions.items()
                },
            }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(output)
        published = True
        return manifest
    finally:
        if not published and temporary.exists():
            shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = export_gpu_bases(args.source, args.output)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
