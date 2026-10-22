#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    project = json.loads((ROOT / "sequel/project.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / project["patch_manifest"]).read_text(encoding="utf-8")
    )
    base_rom = ROOT / project["base_rom"]["path"]
    build_rom = ROOT / project["build"]["output_rom"]
    report = ROOT / project["build"]["report"]

    story_files = sorted((ROOT / "sequel/content/story").glob("*.json"))
    map_files = sorted((ROOT / "sequel/content/maps").glob("*.json"))
    unit_files = sorted((ROOT / "sequel/content/units").glob("*.json"))
    text_files = sorted((ROOT / "sequel/content/text").glob("*"))

    status = {
        "project": project["project_id"],
        "base_rom_exists": base_rom.exists(),
        "base_rom_sha1": sha1_file(base_rom) if base_rom.exists() else None,
        "expected_base_rom_sha1": project["base_rom"]["sha1"],
        "build_rom_exists": build_rom.exists(),
        "build_report_exists": report.exists(),
        "enabled_patch_count": sum(
            1 for p in manifest["patches"] if p.get("enabled", True)
        ),
        "story_specs": [str(p.relative_to(ROOT)) for p in story_files],
        "map_specs": [str(p.relative_to(ROOT)) for p in map_files],
        "unit_specs": [str(p.relative_to(ROOT)) for p in unit_files],
        "text_specs": [str(p.relative_to(ROOT)) for p in text_files],
        "key_findings": [
            "Dialogue scene uses BG3 tilemap rendering",
            "WRAM 0x00A900-0x00AA4A is the strongest dialogue tilemap work buffer candidate",
            "VRAM 0x1800+ matches BG3 screen block region",
            "VRAM 0x2000+ is a likely glyph/tile upload region",
            "WRAM dialogue writer is now stably captured at 0x08066D74",
            "VRAM glyph writer is now stably captured at 0x08065F50",
            "0x08096168 and 0x08096238 now read as RAM record-preparation helpers",
            "Opening-story runtime tracing currently narrows the live caller branch to 0x080968A0",
        ],
        "next_engineering_targets": [
            "Recover the enclosing function and upstream caller around runtime lr=0x08096633",
            "Walk backward from 0x080968A0 through the compact record-state transition cluster",
            "Locate chapter flow and battle condition script format",
            "Expand patch manifest from proof-of-write patches to real content imports",
        ],
    }
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
