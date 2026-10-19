#!/usr/bin/env python3
"""Independently verify the fixed Cutscene OBJ secondary-pointer runtime A/B."""

from __future__ import annotations

from functools import lru_cache
import argparse
import io
import json
from pathlib import Path
import struct
import sys
import tarfile
import tempfile

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_cutscene_obj_id1_pixel_ab import build_pair as build_parent
from tools.inspect_mgba_savestate import load_gba_state
from tools.render_mode0_checkpoint import render_checkpoint
from tools.rom_small_cfg_callback_gaps_independent_verifier import canonical, read_regular, sha
from tools.verify_cutscene_obj_primary_ptr_ab import EXPECTED_REGIONS, _lz77

SCHEMA = "cutscene-obj-secondary-ptr-verification-v1"
CONTRACT = "tools/data/cutscene-secondary-ptr-contract-v1.json"
CONTRACT_SHA = "86886cace99036319a4b3ccfda5be7ac67b0cd96b5e5177d8d7962933e7010ba"
BANK = "sequel/content/cutscene-scripts/bank.json"
PARENT_SHA = "4da5caf8e6aedf78182b13e75829931398dfb61aee7b7f5f45cd6ec324a33c16"
PARENT_MANIFEST_SHA = "34e8cf88ed9d57ff6a6e5c4148d3a3af8f055c50923b7e62f0e369e3dc356e3f"
ROM_SHAS = {
    "baseline": "762ea6794d93eb7bac79f2d1ccd58bfe8f67a625d3ff4be2aff2ddf8aefa5816",
    "candidate": "76974bcda32477926fe2397b4a48b87bdf956eacc5af7db4f41966026ce67c9d",
}
BINARY_SHA = "ef2386a58364932504b082fb5097340268c2b5b7b202bbf8201b0ce69271d54b"
LIBRARY_SHA = "0f84fde81a26843207dcac5080da014e38fa0d66726498bc3a6b6d6b5c925b0b"
COMMIT = "c16c3ff55585e71bee83c95539c2ecde15d728c8"
INPUT_STATE = "artifacts/runtime-checkpoints/scenario-41-combat-popup.ss9"
INPUT_SHA = "01f478cfafa2796cbe1652007c16e54480d2a289d1e6f54068ace8adc970300a"
CASES = (
    ("zero-baseline-1", "baseline", False),
    ("zero-baseline-2", "baseline", False),
    ("zero-candidate", "candidate", False),
    ("input-baseline", "baseline", True),
    ("input-candidate", "candidate", True),
)
MEMBERS = ("audit.json", "sentinel.json", "guard.json", "guard.json.done.json",
           "launch.json", "residue.json", "frame512.ss9", "frame512.png")
RAW_FILES = {"build-manifest.json", "plan.json", "preflight-result.json"} | {
    f"runtime/{name}/{member}" for name, _, _ in CASES for member in MEMBERS
}
DOMAINS = (("IO", 0x04000000, 0x400), ("PRAM", 0x05000000, 0x400),
           ("VRAM", 0x06000000, 0x18000), ("OAM", 0x07000000, 0x400),
           ("IWRAM", 0x03000000, 0x8000), ("EWRAM", 0x02000000, 0x40000))


def load_contract(root):
    raw = read_regular(root / CONTRACT)
    if sha(raw) != CONTRACT_SHA:
        raise ValueError("input contract identity changed")
    contract = json.loads(raw)
    for name, digest in contract["inputs"].items():
        if sha(read_regular(root / name)) != digest:
            raise ValueError(f"repository input identity changed: {name}")
    return contract


@lru_cache(maxsize=1)
def _independent_build(root, input_identity):
    # Every caller rehashes frozen inputs before using the cached parent rebuild.
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "parent"
        parent = build_parent(root, output)
        original = (output / "baseline/baseline.gba").read_bytes()
        if sha(original) != PARENT_SHA or sha((output / "build-manifest.json").read_bytes()) != PARENT_MANIFEST_SHA:
            raise ValueError("parent reconstruction identity changed")
    allocations = [r for r in parent["variants"]["baseline"]["patch_ledger"] if r["kind"] == "allocation"]
    end = max(r["offset"] + r["size"] for r in allocations)
    if (end + 3) & ~3 != 0xBA12F0:
        raise ValueError("parent allocation boundary changed")
    encoded = bytes.fromhex("10200000004003e07fd65aad35088410e003f001e003")
    baseline = bytearray(original)
    if baseline[0xBA12F0:0xBA1306] != b"\xFF" * 22:
        raise ValueError("declared allocation collides")
    baseline[0xBA12F0:0xBA1306] = encoded
    candidate = bytearray(baseline)
    struct.pack_into("<I", candidate, 0x53DF7C, 0x08BA12F0)
    roms = {"baseline": bytes(baseline), "candidate": bytes(candidate)}
    if any(sha(data) != ROM_SHAS[name] for name, data in roms.items()):
        raise ValueError("independent variant reconstruction changed")
    before = _lz77(roms["baseline"], 0x08BA0964)
    after = _lz77(roms["candidate"], 0x08BA12F0)
    if len(before) != 32 or len(after) != 32 or before[:2] != after[:2] or before[4:] != after[4:] or after[2:4] != b"\xE0\x7F":
        raise ValueError("independent palette reconstruction changed")
    expected = {
        "schema": "cutscene-obj-id1-secondary-ptr-ab-build-v1",
        "source_rom_sha256": dict(input_identity)["rom/base.gba"],
        "parent_baseline_sha256": PARENT_SHA, "parent_manifest_sha256": PARENT_MANIFEST_SHA,
        "edit": {"record_id": "1", "resource_id": 1, "field": "secondary_ptr",
                 "offset": 0x53DF7C, "before_pointer": 0x08BA0964, "after_pointer": 0x08BA12F0},
        "allocation": {"offset": 0xBA12F0, "size": 22, "region": "cutscene-obj-bundle",
                       "region_owner": "cutscene_obj_resources", "encoded_sha256": sha(encoded),
                       "decompressed_sha256": sha(after), "shared_by_both_variants": True,
                       "palette_color_index": 1, "before_color": 0x7FFF, "after_color": 0x7FE0},
        "isolation": {"changed_rom_offsets": [0x53DF7C, 0x53DF7D], "other_bytes_equal": True},
        "variants": {n: {"rom_path": f"{n}/{n}.gba", "rom_sha256": ROM_SHAS[n], "rom_size": 0x1000000} for n in ROM_SHAS},
        "runtime_verified": False,
    }
    return expected, before, after


def _provenance(root, name, variant, with_input, objects, contract):
    def get(member):
        return json.loads(objects[f"runtime/{name}/{member}"])
    guard, launch, audit = get("guard.json"), get("launch.json"), get("audit.json")
    marker, residue = get("guard.json.done.json"), get("residue.json")
    capture_root = guard["cwd"]
    command = guard["command"]
    script = "tools/mgba_single_input_replay.lua" if with_input else "tools/mgba_checkpoint_replay.lua"
    folder = f"{capture_root}/build/experiments/active/cutscene-secondary-ptr-ab/runtime-shared-lock-20261001-v1/runtime/{name}"
    if command[-1] != f"{folder}/staged.gba":
        raise ValueError("runtime case folder changed")
    if len(command) != 4 or command[1] != "--script" or command[2] != f"{capture_root}/{script}" or Path(command[0]).name != "mGBA":
        raise ValueError("runtime command provenance changed")
    gcmd = launch["guard_command"]
    if gcmd.count("--lock-file") != 1 or gcmd[gcmd.index("--lock-file") + 1] != f"{capture_root}/build/experiments/heavy.lock":
        raise ValueError("runtime requires shared heavy lock")
    flags = {"--summary": f"{folder}/guard.json", "--success-marker": f"{folder}/guard.json.done.json",
             "--cwd": capture_root, "--min-available-mib": "4096", "--max-tree-rss-mib": "1536",
             "--wall-timeout-s": "180", "--idle-timeout-s": "90"}
    if gcmd[1] != f"{capture_root}/tools/run_guarded.py" or gcmd[gcmd.index("--") + 1:] != command:
        raise ValueError("guard command provenance changed")
    for flag, value in flags.items():
        if gcmd.count(flag) != 1 or gcmd[gcmd.index(flag) + 1] != value:
            raise ValueError("guard limits/provenance changed")
    if (guard.get("reason") != "completed" or guard.get("exit_code") != 0
            or guard.get("completion_trigger") != "success-marker"
            or guard.get("protection_backend") != "posix-process-group"
            or guard.get("degraded") is not False or not 0 < guard["peak_tree_rss_mib"] <= 1536
            or "mgba_crash_reports" in guard):
        raise ValueError("guard result rejected")
    if (launch["command"] != command or launch["binary_sha256"] != BINARY_SHA
            or launch["library_sha256"] != LIBRARY_SHA or launch["script_sha256"] != contract["inputs"][script]
            or launch["input"] is not with_input):
        raise ValueError("runtime launch identity changed")
    expected_guard = [gcmd[0], f"{capture_root}/tools/run_guarded.py"]
    ordered_flags = ["--summary", "--success-marker", "--lock-file", "--cwd", "--min-available-mib",
                     "--max-tree-rss-mib", "--wall-timeout-s", "--idle-timeout-s"]
    flags["--lock-file"] = f"{capture_root}/build/experiments/heavy.lock"
    for flag in ordered_flags:
        expected_guard.extend([flag, flags[flag]])
    expected_guard.extend(["--", *command])
    if gcmd != expected_guard or not Path(gcmd[0]).name.startswith("python3"):
        raise ValueError("guard command contains unsupported options")
    run_id = launch["run_id"]
    if run_id != f"secondary-ptr-shared-lock-20261001-{name}":
        raise ValueError("runtime run identity changed")
    if marker != {"run_id": run_id, "capture_frame": 512, "status": "capture-complete"}:
        raise ValueError("completion marker changed")
    inputs = [{"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}] if with_input else []
    expected = {"run_id": run_id, "frame": 512, "capture_frame": 512, "inputs": inputs,
                "success": True, "status": "capture-complete", "input_state": f"{capture_root}/{INPUT_STATE}",
                "input_state_sha256": INPUT_SHA, "rom_sha256": ROM_SHAS[variant],
                "output_state": f"{folder}/frame512.ss9", "output_png": f"{folder}/frame512.png",
                "audit": f"{folder}/audit.json", "sentinel": f"{folder}/sentinel.json"}
    if with_input:
        expected.update({"automatic_inputs": [], "recovery_inputs": [], "evidence_mode": "single-input", "zero_input_verified": False})
    if audit != expected or get("sentinel.json") != expected:
        raise ValueError("runtime input protocol changed")
    if (residue.get("checked_pgid") != guard["child_pid"] or residue.get("pgid_clean") is not True
            or residue.get("mgba_listener_clean") is not True or residue.get("pgid_matching_rows") != []
            or residue.get("mgba_listener_rows") != [] or residue.get("lsof_exit_code") != 1):
        raise ValueError("runtime residue rejected")
    return launch


def _verify_source(root, source):
    root, source = Path(root).resolve(strict=True), Path(source).absolute()
    contract = load_contract(root)
    actual = {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()}
    if actual != RAW_FILES:
        raise ValueError("raw file set changed")
    objects = {name: read_regular(source / name) for name in sorted(RAW_FILES)}
    expected, before, after = _independent_build(root, tuple(sorted(contract["inputs"].items())))
    if json.loads(objects["build-manifest.json"]) != expected:
        raise ValueError("build manifest differs from independent raw reconstruction")
    plan, preflight = json.loads(objects["plan.json"]), json.loads(objects["preflight-result.json"])
    if (plan["binary_sha256"] != BINARY_SHA or plan["library_sha256"] != LIBRARY_SHA or plan["source_commit"] != COMMIT
            or plan["input_state_sha256"] != INPUT_SHA or plan["capture_frame"] != 512
            or preflight["library_sha256"] != LIBRARY_SHA or preflight["source_commit"] != COMMIT
            or preflight["exported_git_commit"] != COMMIT or preflight["dlopen_verified"] is not True
            or preflight["source_tree_clean"] is not True):
        raise ValueError("runtime toolchain identity changed")
    if (plan["cases"] != [{"name": n, "variant": v, "input": i} for n, v, i in CASES]
            or plan["variants"] != expected["variants"] or plan["build_manifest_sha256"] != sha(objects["build-manifest.json"])
            or plan["input_state"] != INPUT_STATE or plan["input_state_version"] != "0x01000007"
            or plan["required_heavy_lock"] != "build/experiments/heavy.lock"
            or plan["global_exhaustive_claim"] is not False
            or plan["scripts"] != {p: contract["inputs"][p] for p in
                                   ("tools/mgba_checkpoint_replay.lua", "tools/mgba_single_input_replay.lua")}
            or load_gba_state(root / INPUT_STATE).version_magic != 0x01000007):
        raise ValueError("runtime plan scope changed")
    bank = json.loads(read_regular(root / BANK))
    if bank["entry_count"] != 8 or [r["name"] for r in bank["entry_format"]["fields"]] != ["primary_ptr", "secondary_ptr"]:
        raise ValueError("bank denominator changed")
    rgbs, domain_bytes = {}, {}
    for name, variant, with_input in CASES:
        launch = _provenance(root, name, variant, with_input, objects, contract)
        if launch["DYLD_LIBRARY_PATH"] != plan["DYLD_LIBRARY_PATH"] or plan["DYLD_LIBRARY_PATH"] != str(Path(preflight["library"]).parent):
            raise ValueError("library selection changed")
        state_path = source / f"runtime/{name}/frame512.ss9"
        state = load_gba_state(state_path)
        if state.version_magic != 0x0100000B:
            raise ValueError("snapshot version changed")
        with Image.open(source / f"runtime/{name}/frame512.png") as image:
            if image.size != (240, 160):
                raise ValueError("pixels dimensions changed")
            rgb = image.convert("RGB").tobytes()
        if render_checkpoint(state_path)[0] != rgb:
            raise ValueError("renderer does not reproduce captured pixels")
        rgbs[name] = rgb
        domain_bytes[name] = {n: state.read_memory(a, size) for n, a, size in DOMAINS}
    zeros = [r[0] for r in CASES if not r[2]]
    if any(domain_bytes[n] != domain_bytes[zeros[0]] or rgbs[n] != rgbs[zeros[0]] for n in zeros[1:]):
        raise ValueError("zero input control differs")
    left, right = domain_bytes["input-baseline"], domain_bytes["input-candidate"]
    for name, *_ in DOMAINS:
        if sha(left[name]) != EXPECTED_REGIONS[name][2]:
            raise ValueError("baseline memory domain differs from natural victory reference")
        if name != "PRAM" and left[name] != right[name]:
            raise ValueError(f"non-palette memory domain changed: {name}")
    indices = [i for i, (a, b) in enumerate(zip(left["PRAM"], right["PRAM"], strict=True)) if a != b]
    if indices != [0x382] or left["PRAM"][0x380:0x3A0] != before or right["PRAM"][0x380:0x3A0] != after:
        raise ValueError("palette pointer does not select reconstructed stream")
    a, b = rgbs["input-baseline"], rgbs["input-candidate"]
    if sha(a) != "051162ea4f830febd94823d2e87d75ad474223f352867e63fa0965912dbe7bc8" or sha(b) != "a279454f9ea1f124e9522cdcfa3e8372cd06977474751645d384b5713139f41c":
        raise ValueError("final pixels identity changed")
    count = sum(a[i:i + 3] != b[i:i + 3] for i in range(0, len(a), 3))
    bbox = ImageChops.difference(Image.frombytes("RGB", (240, 160), a), Image.frombytes("RGB", (240, 160), b)).getbbox()
    if count != 778 or bbox != (42, 49, 196, 111):
        raise ValueError("final pixels count/bounds changed")
    return {"schema": SCHEMA, "verified": True, "bank": "cutscene-scripts",
            "bank_sha256": contract["inputs"][BANK], "record_ids_total": [str(i) for i in range(8)],
            "record_ids_covered": ["1"], "field_ids_total": ["primary_ptr", "secondary_ptr"],
            "field_ids_covered": ["secondary_ptr"], "cells_total": 16,
            "cells_covered": [{"record_id": "1", "field_id": "secondary_ptr"}],
            "changed_pixel_count": count, "bbox_inclusive": [42, 49, 195, 110],
            "pram_changed_offsets": indices, "zero_input_sample_count": 3,
            "natural_victory_load": True, "exhaustive": False, "physical_gba_verified": False,
            "raw_sha256": {name: sha(data) for name, data in objects.items()}, "contract_sha256": CONTRACT_SHA}


def verify_source(root, source):
    try:
        return _verify_source(root, source)
    except (OSError, KeyError, TypeError, IndexError) as error:
        raise ValueError(f"invalid runtime source: {error}") from error


ARTIFACT_PATH = "build/experiments/active/cutscene-secondary-ptr-contract/tier1-20261001-v1/final"
SCRIPT_PATH = "tools/verify_cutscene_obj_secondary_ptr_ab.py"
ARTIFACT_FILES = {"raw.tar", "evidence.json", "baseline.png", "candidate.png"}
IMPLEMENTATION_PATHS = (
    "tools/build_cutscene_obj_secondary_ptr_ab.py", "tests/test_build_cutscene_obj_secondary_ptr_ab.py",
    "tools/export_cutscene_obj_secondary_ptr_ab.py", SCRIPT_PATH,
    "tests/test_cutscene_obj_secondary_ptr_ab.py", "tests/test_cutscene_obj_secondary_ptr_publication.py",
)
LIMITATIONS = [
    "Only first-table record 1 secondary_ptr has isolated natural victory-load evidence.",
    "The other 15 record/field cells are outside this packet; second-table records have different semantics.",
    "Physical GBA execution, arbitrary navigation and exhaustive bank semantics are unverified.",
    "No ROM-byte classification, live bank catalog or release gate is promoted by this packet.",
]


def pack_raw(objects):
    """Canonical serialization only; semantic verification is independent of packing."""
    if set(objects) != RAW_FILES:
        raise ValueError("raw archive denominator changed")
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name in sorted(objects):
            row = tarfile.TarInfo(name)
            row.size, row.mode = len(objects[name]), 0o644
            archive.addfile(row, io.BytesIO(objects[name]))
    return output.getvalue()


def unpack_raw(raw, destination):
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("raw archive exceeds fixed packet bound")
    objects = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for row in archive:
            if row.name not in RAW_FILES or row.name in objects or not row.isfile() or row.size > 2 * 1024 * 1024:
                raise ValueError("raw archive unsafe member or denominator")
            stream = archive.extractfile(row)
            if stream is None:
                raise ValueError("raw archive member has no bytes")
            objects[row.name] = stream.read()
    if set(objects) != RAW_FILES or pack_raw(objects) != raw:
        raise ValueError("raw archive is not the canonical 43-member packet")
    for name, data in objects.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return objects


def intended_manifest(root, data, report=None):
    if set(data) != ARTIFACT_FILES:
        raise ValueError("artifact denominator changed")
    result = {
        "schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA,
        "artifact_status": "candidate" if report is None else "accepted",
        "public_contract_sha256": CONTRACT_SHA,
        "files": {name: {"size": len(raw), "sha256": sha(raw)} for name, raw in sorted(data.items())},
        "implementation_inputs": [{"path": p, "size": len(read_regular(root / p)),
                                   "sha256": sha(read_regular(root / p))} for p in IMPLEMENTATION_PATHS],
    }
    if report is not None:
        result["verifier"] = {"command": ["python3", SCRIPT_PATH, "--root", ".", "--artifact-dir", ARTIFACT_PATH],
                              "exit_code": 0, "report": report}
    return result


def verify_artifact(root, artifact, *, allow_candidate=False):
    try:
        root = Path(root).resolve(strict=True)
        directory = Path(artifact)
        directory = directory if directory.is_absolute() else root / directory
        if ".." in directory.parts or not directory.is_relative_to(root):
            raise ValueError("unsafe artifact path")
        if {p.name for p in directory.iterdir()} != ARTIFACT_FILES | {"manifest.json"}:
            raise ValueError("artifact denominator changed")
        data = {name: read_regular(directory / name) for name in ARTIFACT_FILES}
        manifest_raw = read_regular(directory / "manifest.json")
        manifest = json.loads(manifest_raw)
        if manifest_raw != canonical(manifest):
            raise ValueError("manifest JSON is not canonical")
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary).resolve() / "source"
            objects = unpack_raw(data["raw.tar"], source)
            expected = verify_source(root, source)
        if data["evidence.json"] != canonical(expected):
            raise ValueError("artifact evidence differs from independent raw replay")
        for variant in ("baseline", "candidate"):
            if data[f"{variant}.png"] != objects[f"runtime/input-{variant}/frame512.png"]:
                raise ValueError("artifact pixels differ from verified capture")
        report = {**expected, "contract_ok": True, "errors": []}
        accepted = manifest.get("artifact_status") == "accepted"
        if not accepted and not allow_candidate:
            raise ValueError("candidate artifact is not accepted")
        if manifest != intended_manifest(root, data, report if accepted else None):
            raise ValueError("artifact manifest contract changed")
        return report
    except (ValueError, OSError, KeyError, TypeError, IndexError, tarfile.TarError) as error:
        return {"schema": SCHEMA, "verified": False, "contract_ok": False, "errors": [str(error)]}


def _bank_contract_report(root, directory, result):
    evidence = (directory / "manifest.json").relative_to(root).as_posix()
    return {**result, "evidence_sha256": {evidence: sha(read_regular(root / evidence))}}


def proof_binding(root, artifact, result):
    """Return a partial proposal only; never alter the live catalog."""
    root = Path(root).resolve(strict=True)
    directory = Path(artifact)
    directory = directory if directory.is_absolute() else root / directory
    if result.get("verified") is not True or result != verify_artifact(root, directory):
        raise ValueError("result mismatch")
    evidence = (directory / "manifest.json").relative_to(root).as_posix()
    contract_result = _bank_contract_report(root, directory, result)
    covered = result["cells_covered"]
    uncovered = [{"record_id": str(i), "field_id": field} for i in range(8)
                 for field in ("primary_ptr", "secondary_ptr")
                 if {"record_id": str(i), "field_id": field} not in covered]
    return {
        "catalog_classification": "runtime_verified", "bank_sha256": result["bank_sha256"],
        "coverage": {"status": "artifact_verified_natural_victory_load", "records_total": 8, "records_covered": 1,
                     **{key: result[key] for key in ("record_ids_total", "record_ids_covered", "field_ids_total",
                                                     "field_ids_covered", "cells_total", "cells_covered")},
                     "cells_uncovered": uncovered},
        "evidence": [{"path": evidence, "sha256": sha(read_regular(root / evidence))}],
        "verifiers": [{"command": ["python3", SCRIPT_PATH, "--root", ".", "--artifact-dir", directory.relative_to(root).as_posix(), "--bank-contract"],
                       "script_sha256": sha(read_regular(root / SCRIPT_PATH)),
                       "contract": {"format": "json", "assertions": {f"/{key}": value for key, value in contract_result.items()}}}],
        "limitations": LIMITATIONS,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--bank-contract", action="store_true", help="Bind the actual artifact manifest in a partial bank report")
    args = parser.parse_args(argv)
    report = verify_artifact(args.root, args.artifact_dir)
    if args.bank_contract and report["verified"]:
        root = args.root.resolve(strict=True)
        directory = args.artifact_dir if args.artifact_dir.is_absolute() else root / args.artifact_dir
        report = _bank_contract_report(root, directory, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
