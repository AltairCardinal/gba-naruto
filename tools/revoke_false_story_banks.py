#!/usr/bin/env python3
"""Replace five false story-table slices with durable disproved tombstones."""
from __future__ import annotations

import json
from pathlib import Path

from extract_audio_resource_sets import extract

ROOT = Path(__file__).resolve().parent.parent
# story/story-b were later reassigned to the proven chapter-flow tables at
# 0x60C74/0x60D54. Never revoke those live slugs again.
MAPPING = {"story-c": 8, "story-d": 11, "story-e": 14}


def build_tombstone(slug: str, descriptor: dict) -> dict:
    false_offset = descriptor["descriptor_offset"] + 4
    return {
        "version": 3,
        "description": f"Disproved tombstone: {slug} was a +4 slice of audio song descriptor for sound ID {descriptor['sound_id']}, not a story/chapter table.",
        "structure_kind": "disproved-story-table",
        "table_offset": false_offset,
        "table_offset_hex": f"0x{false_offset:06X}",
        "entry_count": 0,
        "entry_size": 4,
        "entry_format": {"description": "No story entries. Former u32 pointers are the sequence pointer followed by per-track pointers in one song descriptor."},
        "verification": "disproved",
        "verification_method": "0x0809AAC0 indexes 0x08465B70 by sound ID and calls audio track initializer 0x0809B1F4. Descriptor byte 0 is track_count; +4 is sequence_ptr; +8 begins track_ptrs.",
        "former_claim": {"kind": "story/chapter pointer table", "offset": false_offset},
        "actual_container": {
            "master_table_offset": 0x465B70,
            "master_index": descriptor["sound_id"],
            "descriptor_offset": descriptor["descriptor_offset"],
            "track_count": descriptor["track_count"],
            "priority": descriptor["priority"],
        },
        "writeback": "disabled",
        "entries": [],
    }


def main() -> int:
    descriptors = {item["sound_id"]: item for item in extract((ROOT / "rom/base.gba").read_bytes())["entries"]}
    for slug, index in MAPPING.items():
        path = ROOT / "sequel/content" / slug / "bank.json"
        path.write_text(json.dumps(build_tombstone(slug, descriptors[index]), indent=2) + "\n", encoding="utf-8")
        print(f"revoked {slug}: master index {index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
