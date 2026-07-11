#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from patch_safety import PatchSafetyGate, with_base_precondition

ROOT = Path(__file__).resolve().parent.parent


def sync_rom_mirrors(db_path: Path) -> dict[str, int]:
    """Refresh read-only ``rom_*`` tables from their canonical bank files.

    Direct CLI builds do not pass through the web backend startup hook, so the
    build must perform the same idempotent mirror refresh before DB generators
    run. This keeps newly discovered structures such as ``rom_positions`` from
    silently producing no patches in command-line builds.
    """
    backend_dir = ROOT / "web-editor" / "backend"
    sys.path.insert(0, str(backend_dir))
    try:
        from rom_models import init_rom_tables, populate_rom_tables
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        try:
            init_rom_tables(conn)
            return populate_rom_tables(conn)
        finally:
            conn.close()
    finally:
        try:
            sys.path.remove(str(backend_dir))
        except ValueError:
            pass

# Optional env override: when the editor backend kicks off a build via
# subprocess, it sets BUILD_OUTPUT_DIR to a per-user/per-build subdir so
# concurrent users never overwrite each other's ROMs. When unset (e.g.
# running `python3 tools/build_mod.py` by hand) we fall back to the
# project.json `build.output_rom` path, preserving the historical behaviour.
_BUILD_OUTPUT_DIR_ENV = os.environ.get("BUILD_OUTPUT_DIR")


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
    report_path = ROOT / project["build"]["report"]

    if _BUILD_OUTPUT_DIR_ENV:
        # Per-build output dir from the editor backend.
        # Both ROM and report live side-by-side in this isolated dir so
        # concurrent users never share files.
        out_root = Path(_BUILD_OUTPUT_DIR_ENV)
        if not out_root.is_absolute():
            out_root = ROOT / out_root
        output_rom_path = out_root / "naruto-sequel-dev.gba"
        report_path = out_root / "naruto-sequel-build-report.json"
    else:
        # Legacy / standalone path — write to the path the project.json
        # declares.
        output_rom_path = ROOT / project["build"]["output_rom"]

    return BuildContext(
        project_path=project_path,
        project=project,
        base_rom_path=base_rom_path,
        output_rom_path=output_rom_path,
        report_path=report_path,
    )


def apply_bytes_patch(
    data: bytearray,
    patch: dict,
    *,
    gate: PatchSafetyGate | None = None,
    patch_class: str = "game_effective",
) -> dict:
    offset = int(patch["offset"])
    before = bytes.fromhex(patch["before_hex"])
    after = bytes.fromhex(patch["after_hex"])
    safety_result: dict[str, object] = {}
    if gate is not None:
        safety_result = gate.register(patch, patch_class=patch_class)
    else:
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
        "patch_class": patch_class,
        **safety_result,
    }


def apply_pointer_redirect_patch(
    data: bytearray, patch: dict, *, gate: PatchSafetyGate | None = None
) -> dict:
    ptr_offset = int(patch["pointer_table_offset"])
    new_ptr_bytes = bytes.fromhex(patch["new_pointer_hex"])
    normalized = {
        **patch,
        "offset": ptr_offset,
        "before_hex": patch["expected_pointer_hex"],
        "after_hex": patch["new_pointer_hex"],
    }
    safety_result: dict[str, object] = {}
    if gate is not None:
        safety_result = gate.register(normalized, patch_class="game_effective")
    else:
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
        "patch_class": "game_effective",
        **safety_result,
    }


def resolve_dialogue_patch(ctx_roots: tuple[Path, Path], patch: dict) -> list[dict]:
    from import_dialogue import import_dialogue

    bank = ROOT / patch["bank"]
    content = ROOT / patch["content"]
    # Pull any editor-db overrides for this bank so dialogue text created
    # via the editor (which lives in sequel/editor.db) replaces whatever is
    # hard-coded in dialogue-patches.json. The map is {entry_id: text}.
    overrides: dict[str, str] = {}
    editor_db_path = ROOT / "sequel" / "editor.db"
    if editor_db_path.exists():
        try:
            from build_db_patches import generate_editor_dialogue_overrides
            overrides = generate_editor_dialogue_overrides(editor_db_path)
        except Exception:
            overrides = {}
    entries = import_dialogue(bank, content, overrides=overrides)
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


def apply_patch(
    data: bytearray, patch: dict, *, gate: PatchSafetyGate | None = None
) -> dict:
    ptype = patch.get("sub_type", patch["type"])
    if ptype == "bytes":
        return apply_bytes_patch(data, patch, gate=gate)
    elif ptype == "pointer_redirect":
        return apply_pointer_redirect_patch(data, patch, gate=gate)
    else:
        raise ValueError(f"unsupported sub-patch type: {ptype}")


def classify_db_patch(patch: dict) -> str:
    """Classify non-byte generator output without inflating effective writes."""
    return "game_effective" if patch.get("type") == "bytes" else "diagnostic"


def build(project_path: Path) -> dict:
    """Build the ROM. Reads patch_manifest.json and the editor DB."""
    # Editor DB patches fall into two buckets:
    #   1. Real ROM patches (battle_configs → 0x53F298, chapters → 0x53D914+i*32).
    #      These change actual game data and are applied alongside the manifest.
    #   2. Audit-trail patches written into a reserved region (0x5E0000..0x600000).
    #      Every editor.db row gets a 64-byte sentinel-tagged record here so we can
    #      verify the editor's data reached the ROM without depending on game semantics.
    editor_db_path = ROOT / "sequel" / "editor.db"
    db_real_patches: list[dict] = []
    db_audit_patches: list[dict] = []
    if editor_db_path.exists():
        sync_rom_mirrors(editor_db_path)
        from build_db_patches import (
            generate_db_patches,
            generate_battle_config_patches,
            generate_chapter_patches,
            generate_unit_patches,
            generate_skill_patches,
            generate_story_beat_patches,
            generate_audio_patches,
            generate_unit_position_patches,
            generate_map_patches,
            generate_level_patches,
            generate_character_stat_patches,
            generate_battle_config_data_patches,
            generate_encounter_zone_patches,
            generate_item_patches,
            generate_audio_event_patches,
            generate_battle_encounter_patches,
            generate_battle_handler_patches,
            generate_character_stats_b_patches,
            generate_cutscene_script_patches,
            generate_data_table_a_patches,
            generate_data_table_b_patches,
            generate_font_patches,
            generate_function_pointer_patches,
            generate_map_event_patches,
            generate_map_sprite_patches,
            generate_menu_ui_patches,
            generate_palette_patches,
            generate_resource_pointer_patches,
            generate_sappy_engine_patches,
            generate_save_state_patches,
            generate_sprite_animation_patches,
            generate_story_b_patches,
            generate_story_c_patches,
            generate_story_d_patches,
            generate_story_e_patches,
            generate_tile_asset_patches,
        )
        db_real_patches.extend(generate_battle_config_patches(editor_db_path))
        db_real_patches.extend(generate_chapter_patches(editor_db_path))
        db_real_patches.extend(generate_unit_patches(editor_db_path))
        db_real_patches.extend(generate_skill_patches(editor_db_path))
        db_real_patches.extend(generate_story_beat_patches(editor_db_path))
        db_real_patches.extend(generate_audio_patches(editor_db_path))
        db_real_patches.extend(generate_unit_position_patches(editor_db_path))
        db_real_patches.extend(generate_map_patches(editor_db_path))
        db_real_patches.extend(generate_level_patches(editor_db_path))
        db_real_patches.extend(generate_character_stat_patches(editor_db_path))
        db_real_patches.extend(generate_battle_config_data_patches(editor_db_path))
        db_real_patches.extend(generate_encounter_zone_patches(editor_db_path))
        db_real_patches.extend(generate_item_patches(editor_db_path))
        db_real_patches.extend(generate_audio_event_patches(editor_db_path))
        db_real_patches.extend(generate_battle_encounter_patches(editor_db_path))
        db_real_patches.extend(generate_battle_handler_patches(editor_db_path))
        db_real_patches.extend(generate_character_stats_b_patches(editor_db_path))
        db_real_patches.extend(generate_cutscene_script_patches(editor_db_path))
        db_real_patches.extend(generate_data_table_a_patches(editor_db_path))
        db_real_patches.extend(generate_data_table_b_patches(editor_db_path))
        db_real_patches.extend(generate_font_patches(editor_db_path))
        db_real_patches.extend(generate_function_pointer_patches(editor_db_path))
        db_real_patches.extend(generate_map_event_patches(editor_db_path))
        db_real_patches.extend(generate_map_sprite_patches(editor_db_path))
        db_real_patches.extend(generate_menu_ui_patches(editor_db_path))
        db_real_patches.extend(generate_palette_patches(editor_db_path))
        db_real_patches.extend(generate_resource_pointer_patches(editor_db_path))
        db_real_patches.extend(generate_sappy_engine_patches(editor_db_path))
        db_real_patches.extend(generate_save_state_patches(editor_db_path))
        db_real_patches.extend(generate_sprite_animation_patches(editor_db_path))
        db_real_patches.extend(generate_story_b_patches(editor_db_path))
        db_real_patches.extend(generate_story_c_patches(editor_db_path))
        db_real_patches.extend(generate_story_d_patches(editor_db_path))
        db_real_patches.extend(generate_story_e_patches(editor_db_path))
        db_real_patches.extend(generate_tile_asset_patches(editor_db_path))
        db_audit_patches = generate_db_patches(editor_db_path)
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
    base_data = bytes(data)
    safety_gate = PatchSafetyGate(base_data)
    applied: list[dict] = []
    for patch in manifest["patches"]:
        if not patch.get("enabled", True):
            continue
        patch_type = patch["type"]
        if patch_type == "bytes":
            applied.append(apply_bytes_patch(data, patch, gate=safety_gate))
        elif patch_type == "dialogue":
            resolved_list = resolve_dialogue_patch((ROOT, ROOT), patch)
            for resolved in resolved_list:
                sub_type = resolved.get("sub_type", resolved["type"])
                if sub_type == "pointer_redirect":
                    result = apply_pointer_redirect_patch(data, resolved, gate=safety_gate)
                    result["strategy"] = resolved.get("strategy", "pointer_redirect")
                    result["text"] = resolved.get("text", "")
                    result["encoding"] = resolved.get("encoding", "")
                    applied.append(result)
                else:
                    result = apply_bytes_patch(data, resolved, gate=safety_gate)
                    result["text"] = resolved.get("text", "")
                    result["encoding"] = resolved.get("encoding", "")
                    result["source_entry"] = resolved.get("source_entry", "")
                    result["strategy"] = resolved.get("strategy", "same_length")
                    applied.append(result)
        elif patch_type == "pointer_redirect":
            applied.append(apply_pointer_redirect_patch(data, patch, gate=safety_gate))
        elif patch_type == "map":
            sub_patches = resolve_map_patch((ROOT, ROOT), patch)
            for sp in sub_patches:
                applied.append(apply_patch(data, sp, gate=safety_gate))
        elif patch_type == "battle_config":
            sub_patches = resolve_battle_config_patch((ROOT, ROOT), patch)
            for sp in sub_patches:
                applied.append(apply_patch(data, sp, gate=safety_gate))
        elif patch_type == "dialogue_var":
            sub_patches = resolve_dialogue_var_patch((ROOT, ROOT), patch)
            for sp in sub_patches:
                applied.append(apply_patch(data, sp, gate=safety_gate))
        else:
            raise ValueError(f"unsupported patch type: {patch_type}")

    # Apply editor DB real ROM patches (battle_configs, chapters). These
    # use the same before-hex check as manifest bytes patches so we don't
    # silently overwrite unrelated game data.
    for patch in db_real_patches:
        if patch.get("type") != "bytes":
            applied.append({**patch, "patch_class": classify_db_patch(patch)})
            continue
        # A real patch precondition is always derived from the immutable base
        # ROM.  Reading the already-mutated buffer here would hide collisions.
        patch = with_base_precondition(base_data, patch)
        # Ensure id is present so apply_bytes_patch's report row has a stable key
        if "id" not in patch:
            patch["id"] = f"db_real_{patch.get('db_table', '?')}_{patch.get('db_row_id', '?')}"
        result = apply_bytes_patch(data, patch, gate=safety_gate)
        result["patch_source"] = "db_real"
        applied.append(result)

    # Apply editor DB audit-trail patches (these write to a reserved ROM
    # region so we can prove editor→DB→ROM flow end-to-end). DB audit
    # patches don't have before_hex — we just write the bytes directly
    # without a pre-check because the reserved region was 0xFF padding.
    for patch in db_audit_patches:
        if patch.get("type") == "db_overflow":
            applied.append({**patch, "patch_class": "audit"})
            continue
        offset = int(patch["offset"])
        after = bytes.fromhex(patch["after_hex"])
        audit_patch = {
            **patch,
            "id": f"db_{patch.get('db_table', '?')}_{patch.get('db_row_id', '?')}",
        }
        audit_safety_result = safety_gate.register(audit_patch, patch_class="audit")
        data[offset : offset + len(after)] = after
        applied.append({
            "id": audit_patch["id"],
            "type": "bytes",
            "offset": offset,
            "before_hex": "(reserved region — no pre-check)",
            "after_hex": patch["after_hex"],
            "length": len(after),
            "db_table": patch.get("db_table"),
            "db_row_id": patch.get("db_row_id"),
            "description": patch.get("description"),
            "patch_source": "db_audit",
            "patch_class": "audit",
            **audit_safety_result,
        })

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
        "patch_class_counts": {
            "game_effective": sum(
                p.get("patch_class") == "game_effective" for p in applied
            ),
            "audit": sum(p.get("patch_class") == "audit" for p in applied),
            "diagnostic": sum(
                p.get("patch_class") == "diagnostic" for p in applied
            ),
        },
        "patch_statistics": {
            "db_real": sum(p.get("patch_source") == "db_real" for p in applied),
            "db_audit": sum(p.get("patch_source") == "db_audit" for p in applied),
        },
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
