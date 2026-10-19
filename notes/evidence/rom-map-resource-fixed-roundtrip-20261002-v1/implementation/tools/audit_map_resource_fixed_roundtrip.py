"""Audit the fixed map-resource import/build/readback matrix.

Run inside the repository's resource guard and an initialized active experiment.
The fixture deliberately has no editor database or allocation/relocation path.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.rom_small_cfg_callback_gaps_independent_verifier import read_regular, sha
from tools import verify_map_resource_writeback_audit as independent
from tools.fixed_resource_roundtrip import _managed_run, _write, _fixture_inputs, _edit, build_cli as _build_cli

SCHEMA = "map-resource-fixed-roundtrip-verification-v1"
CONTRACT = "tools/data/map-resource-fixed-roundtrip-contract-v1.json"
CONTRACT_SHA = "04bc6b6aa47fc4f8e924e9f203cb69bbf5e239ba430b5be17bc222efbe58dc78"
SCRIPT = "tools/audit_map_resource_fixed_roundtrip.py"
CATALOG = "artifacts/map-canvases-v1/manifest.json"
TOOLCHAIN = (
    "tools/build_mod.py", "tools/import_map_resources.py", "tools/patch_safety.py",
    "tools/rom_layout.py", "tools/extract_tileset.py", "tools/gba_image_export.py",
)
TABLE = 0x53D910
TABLE_SIZE = 47 * 32
RECIPE = {"catalog": CATALOG, "spec_schema": "map-resource-import-v1", "patch_type": "map_resource"}


def _inputs(root):
    raw = read_regular(root / CONTRACT)
    if sha(raw) != CONTRACT_SHA:
        raise ValueError("roundtrip contract identity mismatch")
    contract = json.loads(raw)
    if contract["schema"] != "map-resource-fixed-roundtrip-inputs-v1":
        raise ValueError("roundtrip contract schema mismatch")
    inputs = {name: read_regular(root / name) for name in contract["inputs"]}
    for name, value in inputs.items():
        if sha(value) != contract["inputs"][name]:
            raise ValueError(f"roundtrip input identity mismatch: {name}")
    return contract, inputs


def linked_domain(catalog, contents, replacements=None):
    """Check every linked map independently of the importer and its decoder.

    Inputs are identity-checked decompressed bytes. Layout halves index 8-byte
    metatiles; each metatile u16 selects a tile and palette bank. Flip flags
    are masked out, rather than being mistaken for an index.
    """
    replacements = replacements or {}
    errors = []
    for entry in catalog["entries"]:
        map_id = entry["map_id"]
        sources = entry["resources"]

        def content(role):
            key = (role, sources[role]["sha256"])
            return replacements[key] if key in replacements else contents[key]

        width, height = entry["dimensions_tiles"]
        cells = (width // 4) * (height // 2)
        graphics, palette = content("tile_graphics"), content("bg_palette")
        metatiles = content("metatile_definitions")
        if len(content("collision_grid")) != cells * 2:
            errors.append({"map_id": map_id, "kind": "collision-size"})
        for role in ("primary_layout", "alternate_layout"):
            if sources.get(role) is None:
                continue
            layout = content(role)
            if len(layout) != cells * 4:
                errors.append({"map_id": map_id, "kind": "layout-size", "role": role})
                continue
            for index, (value,) in enumerate(struct.iter_unpack("<H", layout)):
                if value >= len(metatiles) // 8:
                    errors.append({"map_id": map_id, "kind": "layout-metatile-index",
                                   "role": role, "half_index": index, "value": value,
                                   "bound": len(metatiles) // 8})
        for index, (value,) in enumerate(struct.iter_unpack("<H", metatiles)):
            tile, bank = value & 1023, value >> 12
            if tile >= len(graphics) // 32:
                errors.append({"map_id": map_id, "kind": "metatile-tile-index",
                               "index": index, "value": tile, "bound": len(graphics) // 32})
            if bank >= len(palette) // 32:
                errors.append({"map_id": map_id, "kind": "metatile-palette-bank",
                               "index": index, "value": bank, "bound": len(palette) // 32})
    return errors


def rejection_matches(domain_errors, reason):
    if not domain_errors:
        return "does not fit every physical slot" in reason
    kinds = {"collision-size": "collision grid size", "layout-size": " size ",
             "layout-metatile-index": "metatile index", "metatile-tile-index": "metatile tile index",
             "metatile-palette-bank": "metatile palette bank"}
    return any(f"map {e['map_id']} " in reason and kinds[e["kind"]] in reason for e in domain_errors)


def _source_path(row):
    return f"artifacts/map-canvases-v1/{row['source_file']}"


def run_roundtrip(root, run):
    root = Path(root).resolve(strict=True)
    contract, inputs = _inputs(root)
    run = _managed_run(root, run)
    artifact = root / contract["capacity_artifact"]
    checked = independent.verify_map_resource_writeback_audit(root, artifact)
    if checked["verified"] is not True:
        raise ValueError(f"independent capacity proof rejected: {checked}")
    capacity = independent._expected_payload(root)
    if json.loads(inputs[f"{contract['capacity_artifact']}/map-resource-writeback.json"]) != capacity:
        raise ValueError("capacity payload reconstruction mismatch")
    work = run / "roundtrip"
    work.mkdir(mode=0o700, exist_ok=False)
    fixture = work / "fixture"
    fixture.mkdir()
    _fixture_inputs(fixture, inputs, (*TOOLCHAIN, "rom/base.gba", CATALOG))
    rows = capacity["resources"]
    resource_ids = [f"{r['resource_type']}:{r['resource_sha256']}" for r in rows]
    if len(rows) != 166 or len(set(resource_ids)) != 166:
        raise ValueError("fixed resource denominator mismatch")
    baseline = inputs["rom/base.gba"]
    original_edits = []
    for row in rows:
        name = _source_path(row)
        _fixture_inputs(fixture, inputs, (name,))
        if sha(inputs[name]) != row["resource_sha256"]:
            raise ValueError("exported resource identity mismatch")
        original_edits.append(_edit(row, _source_path(row)))
    noop, noop_case = _build_cli(fixture, "all-resource-noop", original_edits, **RECIPE)
    if noop.returncode != 0:
        raise ValueError(f"no-op build CLI failed: {noop.stderr}")
    noop_rom = read_regular(noop_case / "output.gba")
    noop_report = json.loads(read_regular(noop_case / "build-report.json"))
    if noop_rom != baseline or noop_report["applied_patches"] != []:
        raise ValueError("all-resource no-op build must preserve the entire base ROM")
    observed = []
    accepted = rejected = domain_rejected = written_slots = written_references = 0
    catalog = json.loads(inputs[CATALOG])
    contents = {(row["resource_type"], row["resource_sha256"]):
                inputs[_source_path(row)] for row in rows}
    if linked_domain(catalog, contents):
        raise ValueError("base map linked domain is invalid")
    for index, row in enumerate(rows):
        role = row["resource_type"]
        offsets = [s["file_offset"] for s in row["physical_slots"]]
        content = independent._decompress(baseline, offsets[0])
        if content != inputs[_source_path(row)]:
            raise ValueError("independent extraction differs from exported source")
        original_encoding = independent._encode(content)
        if independent._decompress(original_encoding, 0) != content:
            raise ValueError("original independent codec roundtrip failed")
        mutation = bytearray(content)
        mutation[row["mutation"]["offset"]] ^= 1
        mutation = bytes(mutation)
        encoded = independent._encode(mutation)
        if (sha(encoded) != row["mutation_encoded_sha256"]
                or independent._decompress(encoded, 0) != mutation):
            raise ValueError("independent mutation codec roundtrip failed")
        domain_errors = linked_domain(catalog, contents, {(role, row["resource_sha256"]): mutation})
        domain_valid = not domain_errors
        name = f"mutation-{index:03d}"
        case = fixture / "cases" / name
        case.mkdir()
        (case / "edited.bin").write_bytes(mutation)
        completed, case = _build_cli(fixture, name, [_edit(row, f"cases/{name}/edited.bin")], **RECIPE)
        output_present = (case / "output.gba").exists()
        report_present = (case / "build-report.json").exists()
        item = {"resource_id": resource_ids[index], "resource_type": role,
                "physical_offsets": offsets, "logical_aliases": row["logical_aliases"],
                "original_codec_roundtrip": True, "mutation_encoded_sha256": sha(encoded),
                "mutation_encoded_size": len(encoded), "mutation_decompressed_sha256": sha(mutation),
                "base_rom_unchanged": read_regular(fixture / "rom/base.gba") == baseline,
                "build_exit_code": completed.returncode,
                "mutation_accepted": domain_valid and row["mutation_fit_all_aliases"],
                "linked_domain_valid": domain_valid, "linked_domain_errors": domain_errors,
                "capacity_fit_all_aliases": row["mutation_fit_all_aliases"],
                "output_rom_present": output_present, "output_report_present": report_present}
        if not item["base_rom_unchanged"]:
            raise ValueError("build CLI changed its immutable base")
        if item["mutation_accepted"]:
            if completed.returncode != 0 or not output_present or not report_present:
                raise ValueError(f"bounded mutation build failed: {completed.stderr}")
            actual = read_regular(case / "output.gba")
            expected = bytearray(baseline)
            for slot in row["physical_slots"]:
                offset, size = slot["file_offset"], slot["slot_size"]
                if len(encoded) > size:
                    raise ValueError("accepted capacity witness overflows a physical slot")
                expected[offset:offset + size] = encoded + baseline[offset + len(encoded):offset + size]
                if independent._decompress(actual, offset) != mutation:
                    raise ValueError("actual output did not re-decode the target alias")
            if actual != bytes(expected) or actual[TABLE:TABLE + TABLE_SIZE] != baseline[TABLE:TABLE + TABLE_SIZE]:
                raise ValueError("output differs outside independently rebuilt fixed slots")
            report = json.loads(read_regular(case / "build-report.json"))
            if (len(report["applied_patches"]) != len(offsets)
                    or sorted(p["offset"] for p in report["applied_patches"]) != offsets):
                raise ValueError("build report does not bind all physical aliases")
            for alias in row["logical_aliases"]:
                address = int.from_bytes(actual[alias["header_pointer_offset"]:alias["header_pointer_offset"] + 4], "little")
                if (address != alias["physical_offset"] + 0x08000000
                        or independent._decompress(actual, address - 0x08000000) != mutation):
                    raise ValueError("logical alias pointer/readback mismatch")
            accepted += 1
            written_slots += len(offsets)
            written_references += len(row["logical_aliases"])
            changed = sum(a != b for slot in row["physical_slots"] for a, b in zip(
                baseline[slot["file_offset"]:slot["file_offset"] + slot["slot_size"]],
                actual[slot["file_offset"]:slot["file_offset"] + slot["slot_size"]], strict=True))
            if changed == 0:
                raise ValueError("accepted mutation did not modify any ROM byte")
            item.update({"output_rom_sha256": sha(actual), "changed_rom_bytes": changed,
                         "all_target_aliases_redecoded": True, "outside_target_slots_unchanged": True,
                         "pointer_table_unchanged": True})
        else:
            reason = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else ""
            if (completed.returncode == 0 or output_present or report_present
                    or not rejection_matches(domain_errors, reason)):
                raise ValueError("overflow was not atomically rejected before output publication")
            rejected += int(domain_valid)
            domain_rejected += int(not domain_valid)
            item["rejection_class"] = "capacity" if domain_valid else "linked-domain"
            item["rejection_reason"] = reason.removeprefix("ValueError: ")
        _write(case / "readback.json", item)
        observed.append(item)
    if (accepted, rejected, domain_rejected) != (70, 96, 0):
        raise ValueError("fixed mutation outcome denominator mismatch")
    for name, digest in contract["inputs"].items():
        if sha(read_regular(root / name)) != digest:
            raise ValueError("roundtrip input identity drift during build")
    result = {
        "schema": SCHEMA, "verified": True, "scope": contract["scope"],
        "contract_sha256": CONTRACT_SHA, "input_sha256": contract["inputs"],
        "implementation_sha256": sha(read_regular(root / SCRIPT)),
        "resource_ids_total": resource_ids, "resource_ids_checked": resource_ids, "rows": observed,
        "summary": {"resources": 166, "physical_slots": 217, "logical_references": 249,
                    "mutation_accepted_resources": accepted, "mutation_capacity_rejected_resources": rejected,
                    "mutation_domain_rejected_resources": domain_rejected,
                    "mutation_written_slots": written_slots, "mutation_written_logical_references": written_references,
                    "actual_build_cli_cases": 167, "all_resource_noop_patches": 0},
        "all_resource_noop_rom_exact": True, "fixed_mutation_matrix_complete": True, "linked_domain_independently_checked": True,
        "build_environment_isolated": True, "editor_db_connected": False,
        "arbitrary_edit_capacity_complete": False, "resource_relocation_complete": False,
        "pointer_rewrite_complete": False, "full_graphics_release_gate_complete": False,
        "runtime_executed": False, "physical_gba_verified": False,
        "provider": {"python": sys.version, "platform": platform.system()},
    }
    _write(work / "result.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_roundtrip(args.root, args.run)
    except (ValueError, OSError, KeyError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"schema": SCHEMA, "verified": False, "errors": [str(error)]}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
