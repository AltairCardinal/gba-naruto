#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from import_dialogue import import_dialogue

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class BuildContext:
    project_path: Path
    project: dict
    base_rom_path: Path
    output_rom_path: Path
    report_path: Path


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_context(project_path: Path) -> BuildContext:
    project = json.loads(project_path.read_text(encoding="utf-8"))
    base_rom_path = ROOT / project["base_rom"]["path"]
    output_rom_path = ROOT / project["build"]["output_rom"]
    report_path = ROOT / project["build"]["report"]
    return BuildContext(
        project_path=project_path,
        project=project,
        base_rom_path=base_rom_path,
        output_rom_path=output_rom_path,
        report_path=report_path,
    )


def apply_bytes_patch(data: bytearray, patch: dict) -> dict:
    offset = int(patch["offset"])
    before = bytes.fromhex(patch["before_hex"])
    after = bytes.fromhex(patch["after_hex"])
    actual = bytes(data[offset : offset + len(before)])
    if actual != before:
        raise ValueError(
            f"patch {patch['id']} mismatch at 0x{offset:X}: expected {before.hex()} got {actual.hex()}"
        )
    data[offset : offset + len(before)] = after
    return {
        "id": patch["id"],
        "type": patch["type"],
        "offset": offset,
        "before_hex": before.hex(),
        "after_hex": after.hex(),
        "length": len(after),
    }


def resolve_dialogue_patch(patch: dict) -> dict:
    bank = ROOT / patch["bank"]
    content = ROOT / patch["content"]
    entries = import_dialogue(bank, content)
    entry_map = {item["source_entry"]: item for item in entries}
    entry_id = patch["entry_id"]
    if entry_id not in entry_map:
        raise ValueError(f"dialogue entry {entry_id} missing from imported content")
    entry = dict(entry_map[entry_id])
    entry["id"] = patch["id"]
    entry["type"] = "dialogue"
    entry["bank"] = str(bank.relative_to(ROOT))
    entry["content"] = str(content.relative_to(ROOT))
    return entry


def build(project_path: Path) -> dict:
    ctx = load_context(project_path)
    expected_sha1 = ctx.project["base_rom"]["sha1"]
    actual_sha1 = sha1_file(ctx.base_rom_path)
    if actual_sha1 != expected_sha1:
        raise ValueError(
            f"base ROM sha1 mismatch: expected {expected_sha1} got {actual_sha1}"
        )

    manifest_path = ROOT / ctx.project["patch_manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    data = bytearray(ctx.base_rom_path.read_bytes())
    applied = []
    for patch in manifest["patches"]:
        if not patch.get("enabled", True):
            continue
        patch_type = patch["type"]
        if patch_type == "bytes":
            applied.append(apply_bytes_patch(data, patch))
        elif patch_type == "dialogue":
            resolved = resolve_dialogue_patch(patch)
            applied.append(
                apply_bytes_patch(data, resolved)
                | {
                    "type": "dialogue",
                    "text": resolved["text"],
                    "encoding": resolved["encoding"],
                    "bank": resolved["bank"],
                    "content": resolved["content"],
                    "source_entry": resolved["source_entry"],
                }
            )
        else:
            raise ValueError(f"unsupported patch type: {patch_type}")

    ctx.output_rom_path.parent.mkdir(parents=True, exist_ok=True)
    ctx.output_rom_path.write_bytes(data)
    built_sha1 = sha1_file(ctx.output_rom_path)

    report = {
        "project": ctx.project["project_id"],
        "base_rom": {
            "path": str(ctx.base_rom_path.relative_to(ROOT)),
            "sha1": actual_sha1,
        },
        "output_rom": {
            "path": str(ctx.output_rom_path.relative_to(ROOT)),
            "sha1": built_sha1,
            "size": len(data),
        },
        "applied_patches": applied,
        "patch_manifest": str(manifest_path.relative_to(ROOT)),
    }
    ctx.report_path.parent.mkdir(parents=True, exist_ok=True)
    ctx.report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build sequel development ROM from the project manifest."
    )
    parser.add_argument(
        "--project",
        default="sequel/project.json",
        help="Project metadata JSON path relative to repo root.",
    )
    args = parser.parse_args()

    report = build(ROOT / args.project)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
