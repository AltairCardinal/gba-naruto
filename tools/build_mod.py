#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
        "type": patch.get("sub_type", patch["type"]),
        "offset": offset,
        "before_hex": before.hex(),
        "after_hex": after.hex(),
        "length": len(after),
    }


def apply_pointer_redirect_patch(data: bytearray, patch: dict) -> dict:
    ptr_offset = int(patch["pointer_table_offset"])
    new_ptr_bytes = bytes.fromhex(patch["new_pointer_hex"])
    actual = bytes(data[ptr_offset : ptr_offset + 4])
    if actual != bytes.fromhex(patch["expected_pointer_hex"]):
        raise ValueError(
            f"pointer_redirect {patch['id']} mismatch at 0x{ptr_offset:X}: "
            f"expected {patch['expected_pointer_hex']} got {actual.hex()}"
        )
    data[ptr_offset : ptr_offset + 4] = new_ptr_bytes

    return {
        "id": patch["id"],
        "type": "pointer_redirect",
        "pointer_table_offset": ptr_offset,
        "new_pointer_hex": patch["new_pointer_hex"],
        "expected_pointer_hex": patch["expected_pointer_hex"],
    }


def resolve_dialogue_patch(ctx_roots: tuple[Path, Path], patch: dict) -> list[dict]:
    from import_dialogue import import_dialogue

    bank = ROOT / patch["bank"]
    content = ROOT / patch["content"]
    entries = import_dialogue(bank, content)
    entry_map = {item["source_entry"]: item for item in entries}
    entry_id = patch["entry_id"]
    if entry_id not in entry_map:
        raise ValueError(f"dialogue entry {entry_id} missing from imported content")
    entry = dict(entry_map[entry_id])
    entry["id"] = patch["id"]
    entry["bank"] = str(bank.relative_to(ROOT))
    entry["content"] = str(content.relative_to(ROOT))
    return [entry]


def resolve_map_patch(ctx_roots: tuple[Path, Path], patch: dict) -> list[dict]:
    from import_map import resolve_map_patches

    spec = ROOT / patch["spec"]
    return resolve_map_patches(spec, patch["id"])


def resolve_battle_config_patch(ctx_roots: tuple[Path, Path], patch: dict) -> list[dict]:
    from import_battle_config import resolve_battle_config_patches

    units_path = ROOT / patch["units"]
    story_path = ROOT / patch["story"]
    return resolve_battle_config_patches(units_path, story_path, patch["id"])


def resolve_dialogue_var_patch(ctx_roots: tuple[Path, Path], patch: dict) -> list[dict]:
    from import_dialogue_var import import_dialogue_variable

    bank = ROOT / patch["bank"]
    content = ROOT / patch["content"]
    free_start = int(patch.get("free_space_start", "0x5DFBEC"), 0)
    return import_dialogue_variable(bank, content, free_start)


def apply_patch(data: bytearray, patch: dict) -> dict:
    ptype = patch.get("sub_type", patch["type"])
    if ptype == "bytes":
        return apply_bytes_patch(data, patch)
    elif ptype == "pointer_redirect":
        return apply_pointer_redirect_patch(data, patch)
    else:
        raise ValueError(f"unsupported sub-patch type: {ptype}")


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
    applied: list[dict] = []
    for patch in manifest["patches"]:
        if not patch.get("enabled", True):
            continue
        patch_type = patch["type"]
        if patch_type == "bytes":
            applied.append(apply_bytes_patch(data, patch))
        elif patch_type == "dialogue":
            resolved_list = resolve_dialogue_patch((ROOT, ROOT), patch)
            for resolved in resolved_list:
                sub_type = resolved.get("sub_type", resolved["type"])
                if sub_type == "pointer_redirect":
                    result = apply_pointer_redirect_patch(data, resolved)
                    result["strategy"] = resolved.get("strategy", "pointer_redirect")
                    result["text"] = resolved.get("text", "")
                    result["encoding"] = resolved.get("encoding", "")
                    applied.append(result)
                else:
                    result = apply_bytes_patch(data, resolved)
                    result["text"] = resolved.get("text", "")
                    result["encoding"] = resolved.get("encoding", "")
                    result["source_entry"] = resolved.get("source_entry", "")
                    result["strategy"] = resolved.get("strategy", "same_length")
                    applied.append(result)
        elif patch_type == "pointer_redirect":
            applied.append(apply_pointer_redirect_patch(data, patch))
        elif patch_type == "map":
            sub_patches = resolve_map_patch((ROOT, ROOT), patch)
            for sp in sub_patches:
                applied.append(apply_patch(data, sp))
        elif patch_type == "battle_config":
            sub_patches = resolve_battle_config_patch((ROOT, ROOT), patch)
            for sp in sub_patches:
                applied.append(apply_patch(data, sp))
        elif patch_type == "dialogue_var":
            sub_patches = resolve_dialogue_var_patch((ROOT, ROOT), patch)
            for sp in sub_patches:
                applied.append(apply_patch(data, sp))
        else:
            raise ValueError(f"unsupported patch type: {patch_type}")

    ctx.output_rom_path.parent.mkdir(parents=True, exist_ok=True)
    ctx.output_rom_path.write_bytes(data)
    built_sha1 = sha1_file(ctx.output_rom_path)

    report: dict[str, Any] = {
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
