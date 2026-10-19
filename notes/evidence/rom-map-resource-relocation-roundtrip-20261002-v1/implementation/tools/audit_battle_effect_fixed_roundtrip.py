"""Audit the fixed battle-effect import/build/readback matrix.

Run inside the repository's resource guard and an initialized active experiment.
The fixture deliberately has no editor database or allocation/relocation path.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.rom_small_cfg_callback_gaps_independent_verifier import canonical, read_regular, sha
from tools import verify_battle_effect_resource_writeback_audit as independent

SCHEMA = "battle-effect-fixed-roundtrip-verification-v1"
CONTRACT = "tools/data/battle-effect-fixed-roundtrip-contract-v1.json"
CONTRACT_SHA = "d01f10b1467ff16da2e423a25d7396952284dda0d163a3367f8c41d96298ec31"
SCRIPT = "tools/audit_battle_effect_fixed_roundtrip.py"
CATALOG = "artifacts/battle-effect-resource-pairs-v1/manifest.json"
TOOLCHAIN = (
    "tools/build_mod.py", "tools/import_battle_effect_resources.py", "tools/patch_safety.py",
    "tools/rom_layout.py", "tools/extract_tileset.py", "tools/gba_image_export.py",
)
TABLE = 0x59911C
TABLE_SIZE = 19 * 8


def _inputs(root):
    raw = read_regular(root / CONTRACT)
    if sha(raw) != CONTRACT_SHA:
        raise ValueError("roundtrip contract identity mismatch")
    contract = json.loads(raw)
    if contract["schema"] != "battle-effect-fixed-roundtrip-inputs-v1":
        raise ValueError("roundtrip contract schema mismatch")
    inputs = {name: read_regular(root / name) for name in contract["inputs"]}
    for name, value in inputs.items():
        if sha(value) != contract["inputs"][name]:
            raise ValueError(f"roundtrip input identity mismatch: {name}")
    return contract, inputs


def _managed_run(root, run):
    run = Path(run).absolute()
    try:
        relative = run.relative_to(root / "build/experiments/active")
    except ValueError as error:
        raise ValueError("output must be an initialized managed active run") from error
    if len(relative.parts) != 2 or ".." in relative.parts:
        raise ValueError("output must be an initialized managed active run")
    metadata = json.loads(read_regular(run / ".experiment.json"))
    if (metadata.get("status") != "active" or metadata.get("task") != relative.parts[0]
            or metadata.get("run_id") != relative.parts[1]):
        raise ValueError("output run must be initialized and active")
    return run


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical(value))


def _build_cli(fixture, name, edits):
    case = fixture / "cases" / name
    case.mkdir(parents=True, exist_ok=True)
    spec = {"schema": "battle-effect-resource-import-v1", "source_catalog": CATALOG, "edits": edits}
    _write(case / "spec.json", spec)
    _write(case / "manifest.json", {"patches": [{"id": name, "type": "battle_effect_resource",
                                                "spec": f"cases/{name}/spec.json"}]})
    _write(case / "project.json", {
        "project_id": name,
        "base_rom": {"path": "rom/base.gba", "sha1": "26f60795fa5e63b4f0264b84e453beffd56b9f7d"},
        "patch_manifest": f"cases/{name}/manifest.json",
        "build": {"output_rom": f"cases/{name}/output.gba", "report": f"cases/{name}/build-report.json"},
    })
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C", "LC_ALL": "C",
                   "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(fixture),
                   "DB_PATH": str(fixture / "sequel/absent-editor.db")}
    completed = subprocess.run(
        [sys.executable, str(fixture / "tools/build_mod.py"), "--project", f"cases/{name}/project.json"],
        cwd=fixture, env=environment, capture_output=True, text=True, timeout=45, check=False,
    )
    (case / "stdout.txt").write_text(completed.stdout)
    (case / "stderr.txt").write_text(completed.stderr)
    return completed, case


def _edit(row, source):
    return {"id": f"{row['resource_type']}-{row['resource_sha256']}",
            "resource_type": row["resource_type"], "resource_sha256": row["resource_sha256"],
            "source_file": source,
            "expected": {"decompressed_size": row["decompressed_size"],
                         "physical_offsets": [s["file_offset"] for s in row["physical_slots"]]}}


def _fixture_inputs(fixture, inputs, names):
    """Materialize validated bytes, without reading any unbound source path."""
    for name in names:
        target = fixture / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(inputs[name])


def run_roundtrip(root, run):
    root = Path(root).resolve(strict=True)
    contract, inputs = _inputs(root)
    run = _managed_run(root, run)
    artifact = root / contract["capacity_artifact"]
    checked = independent.verify_battle_effect_resource_writeback_audit(root, artifact)
    if checked["verified"] is not True:
        raise ValueError(f"independent capacity proof rejected: {checked}")
    capacity = independent._expected_payload(root)
    if json.loads(inputs[f"{contract['capacity_artifact']}/battle-effect-resource-writeback.json"]) != capacity:
        raise ValueError("capacity payload reconstruction mismatch")
    work = run / "roundtrip"
    work.mkdir(mode=0o700, exist_ok=False)
    fixture = work / "fixture"
    fixture.mkdir()
    _fixture_inputs(fixture, inputs, (*TOOLCHAIN, "rom/base.gba", CATALOG))
    rows = capacity["resources"]
    resource_ids = [f"{r['resource_type']}:{r['resource_sha256']}" for r in rows]
    if len(rows) != 34 or len(set(resource_ids)) != 34:
        raise ValueError("fixed resource denominator mismatch")
    baseline = inputs["rom/base.gba"]
    original_edits = []
    for row in rows:
        for source in row["source_files"]:
            name = f"artifacts/battle-effect-resource-pairs-v1/{source}"
            _fixture_inputs(fixture, inputs, (name,))
            if sha(inputs[name]) != row["resource_sha256"]:
                raise ValueError("exported resource identity mismatch")
        original_edits.append(_edit(row, f"artifacts/battle-effect-resource-pairs-v1/{row['source_files'][0]}"))
    noop, noop_case = _build_cli(fixture, "all-resource-noop", original_edits)
    if noop.returncode != 0:
        raise ValueError(f"no-op build CLI failed: {noop.stderr}")
    noop_rom = read_regular(noop_case / "output.gba")
    noop_report = json.loads(read_regular(noop_case / "build-report.json"))
    if noop_rom != baseline or noop_report["applied_patches"] != []:
        raise ValueError("all-resource no-op build must preserve the entire base ROM")
    observed = []
    accepted = rejected = written_slots = written_references = 0
    for index, row in enumerate(rows):
        role = row["resource_type"]
        offsets = [s["file_offset"] for s in row["physical_slots"]]
        content = independent._decompress(baseline, offsets[0])
        if content != inputs[f"artifacts/battle-effect-resource-pairs-v1/{row['source_files'][0]}"]:
            raise ValueError("independent extraction differs from exported source")
        original_encoding = independent._encode(content)
        if independent._decompress(original_encoding, 0) != content:
            raise ValueError("original independent codec roundtrip failed")
        mutation = bytearray(content)
        mutation[2 if role == "palette" else 0] ^= 1
        mutation = bytes(mutation)
        encoded = independent._encode(mutation)
        if (sha(encoded) != row["mutation_encoded_sha256"]
                or independent._decompress(encoded, 0) != mutation):
            raise ValueError("independent mutation codec roundtrip failed")
        name = f"mutation-{index:02d}"
        case = fixture / "cases" / name
        case.mkdir()
        (case / "edited.bin").write_bytes(mutation)
        completed, case = _build_cli(fixture, name, [_edit(row, f"cases/{name}/edited.bin")])
        output_present = (case / "output.gba").exists()
        report_present = (case / "build-report.json").exists()
        item = {"resource_id": resource_ids[index], "resource_type": role,
                "physical_offsets": offsets, "logical_aliases": row["logical_aliases"],
                "original_codec_roundtrip": True, "mutation_encoded_sha256": sha(encoded),
                "mutation_encoded_size": len(encoded), "mutation_decompressed_sha256": sha(mutation),
                "base_rom_unchanged": read_regular(fixture / "rom/base.gba") == baseline,
                "build_exit_code": completed.returncode,
                "mutation_accepted": row["mutation_fit_all_aliases"],
                "output_rom_present": output_present, "output_report_present": report_present}
        if not item["base_rom_unchanged"]:
            raise ValueError("build CLI changed its immutable base")
        if row["mutation_fit_all_aliases"]:
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
                address = int.from_bytes(actual[alias["table_pointer_offset"]:alias["table_pointer_offset"] + 4], "little")
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
                    or "does not fit every physical slot" not in reason):
                raise ValueError("overflow was not atomically rejected before output publication")
            rejected += 1
            item["rejection_reason"] = reason.removeprefix("ValueError: ")
        _write(case / "readback.json", item)
        observed.append(item)
    if (accepted, rejected, written_slots, written_references) != (23, 11, 24, 24):
        raise ValueError("fixed mutation outcome denominator mismatch")
    for name, digest in contract["inputs"].items():
        if sha(read_regular(root / name)) != digest:
            raise ValueError("roundtrip input identity drift during build")
    result = {
        "schema": SCHEMA, "verified": True, "scope": contract["scope"],
        "contract_sha256": CONTRACT_SHA, "input_sha256": contract["inputs"],
        "implementation_sha256": sha(read_regular(root / SCRIPT)),
        "resource_ids_total": resource_ids, "resource_ids_checked": resource_ids, "rows": observed,
        "summary": {"resources": 34, "physical_slots": 35, "logical_references": 36,
                    "mutation_accepted_resources": accepted, "mutation_rejected_resources": rejected,
                    "mutation_written_slots": written_slots, "mutation_written_logical_references": written_references,
                    "actual_build_cli_cases": 35, "all_resource_noop_patches": 0},
        "all_resource_noop_rom_exact": True, "fixed_mutation_matrix_complete": True,
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
