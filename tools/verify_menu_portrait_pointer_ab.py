#!/usr/bin/env python3
"""Independently verify one isolated menu graphics-pointer runtime A/B."""
from __future__ import annotations

import argparse
import io
from functools import lru_cache
import json
from pathlib import Path
import struct
import sys
import tarfile
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.inspect_mgba_savestate import load_gba_state
from tools.render_mode0_checkpoint import render_checkpoint
from tools.rom_small_cfg_callback_gaps_independent_verifier import canonical, read_regular, sha
from tools.verify_menu_portrait_pixel_ab_evidence import _catalog_contract, _portrait, _rebuild_rom, _diff, _pixel_changes
from tools.verify_menu_portrait_writeback_audit import _encode_lz77

SCHEMA = "menu-portrait-gfx-pointer-verification-v1"
CONTRACT = "tools/data/menu-gfx-pointer-contract-v1.json"
CONTRACT_SHA = "ec6a3d46f77fe4c3ce4a43bfb5814d8859fbc7dc891c73568403dcac53727552"
BANK = "sequel/content/menu-ui/bank.json"
ROM_SHAS = {
    "baseline": "5e1c7a4d3c00a9d506b5ba81fd2cf0fbd174675a9aa31f4dbba5b66ae7ac4323",
    "candidate": "c8e707b8484782934cc07e9497219eec4028cf761123b3ae4ba3d14978e63442",
}
PARENT_SHAS = {
    "baseline": "202301cc0bcb246269e200db3c5ced1aa3ec8e7547e2f21c26d81df5db95fc3a",
    "candidate": "26a08a91628c4fc511a796db27a29518c7303e8a7294665afbf21b99dce42311",
}
PARENT_MANIFEST_SHA = "1b2ec1560b5492ef90c354646f44a5f9ba872384ae3e6831984030474811bd69"
BINARY_SHA = "ef2386a58364932504b082fb5097340268c2b5b7b202bbf8201b0ce69271d54b"
LIBRARY_SHA = "0f84fde81a26843207dcac5080da014e38fa0d66726498bc3a6b6d6b5c925b0b"
COMMIT = "c16c3ff55585e71bee83c95539c2ecde15d728c8"
INPUT_STATE = "artifacts/runtime-checkpoints/scenario-41-postbattle-dialogue-9.ss9"
INPUT_SHA = "5635916176865f63b12154ea1c68e202393baaf6e1427473fb6be8a84b18eba8"
CASES = (("zero-baseline-1", "baseline", False), ("zero-baseline-2", "baseline", False),
         ("zero-candidate", "candidate", False), ("input-baseline", "baseline", True),
         ("input-candidate", "candidate", True))
MEMBERS = ("audit.json", "sentinel.json", "guard.json", "guard.json.done.json", "launch.json",
           "residue.json", "frame80.ss9", "frame80.png")
RAW_FILES = {"build-manifest.json", "plan.json", "preflight-result.json"} | {
    f"runtime/{name}/{member}" for name, _, _ in CASES for member in MEMBERS}
DOMAINS = (("IO", 0x04000000, 0x400), ("PRAM", 0x05000000, 0x400),
           ("VRAM", 0x06000000, 0x18000), ("OAM", 0x07000000, 0x400),
           ("IWRAM", 0x03000000, 0x8000), ("EWRAM", 0x02000000, 0x40000))
FIELDS = [f"{role}_ptr_{i}" for i in range(5) for role in ("gfx", "palette")]


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
def _independent_build(root, identity):
    base = read_regular(root / "rom/base.gba")
    _, palette = _catalog_contract(root, base)
    before, source_palette = _portrait(root / "artifacts/menu-portraits-v1/portrait_01_variant_0.png", palette)
    parent = _rebuild_rom(base, before, source_palette)
    if sha(parent) != PARENT_SHAS["baseline"] or source_palette != palette:
        raise ValueError("parent reconstruction identity changed")
    after = bytearray(before)
    after[5184] = 14
    encoded = _encode_lz77(bytes(after))
    donor = _rebuild_rom(base, bytes(after), palette)
    if sha(donor) != PARENT_SHAS["candidate"] or len(encoded) != 3306 or parent[0xA80D6C:0xA81A56] != b"\xFF" * 3306:
        raise ValueError("independent graphics donor changed")
    baseline = bytearray(parent)
    baseline[0xA80D6C:0xA81A56] = encoded
    candidate = bytearray(baseline)
    struct.pack_into("<I", candidate, 0x5A4E14, 0x08A80D6C)
    if sha(baseline) != ROM_SHAS["baseline"] or sha(candidate) != ROM_SHAS["candidate"]:
        raise ValueError("independent variant reconstruction changed")
    expected = {
        "schema": "menu-portrait-gfx-pointer-ab-build-v1", "source_rom_sha256": dict(identity)["rom/base.gba"],
        "bank_sha256": dict(identity)[BANK], "parent_manifest_sha256": PARENT_MANIFEST_SHA,
        "parent_rom_sha256": PARENT_SHAS,
        "edit": {"record_id": "1", "variant": 0, "field": "gfx_ptr_0", "resource_id": 0,
                 "offset": 0x5A4E14, "before_pointer": 0x08A80000, "after_pointer": 0x08A80D6C},
        "allocation": {"offset": 0xA80D6C, "size": 3306, "region": "menu-portraits",
                       "region_owner": "menu_portrait_resources", "encoded_sha256": sha(encoded),
                       "decompressed_sha256": sha(bytes(after)), "shared_by_both_variants": True,
                       "stream_byte_offset": 5184, "before_index": 52, "after_index": 14},
        "isolation": {"changed_rom_offsets": [0x5A4E14, 0x5A4E15], "other_bytes_equal": True},
        "variants": {n: {"rom_path": f"{n}/{n}.gba", "rom_sha256": ROM_SHAS[n], "rom_size": 0x1000000} for n in ROM_SHAS},
        "runtime_verified": False,
    }
    return expected, before, bytes(after), palette


def _provenance(root, name, variant, with_input, objects, contract):
    def get(member):
        return json.loads(objects[f"runtime/{name}/{member}"])
    guard, launch, audit = get("guard.json"), get("launch.json"), get("audit.json")
    marker, residue = get("guard.json.done.json"), get("residue.json")
    capture_root = guard["cwd"]
    command = guard["command"]
    script = "tools/mgba_single_input_replay.lua" if with_input else "tools/mgba_checkpoint_replay.lua"
    folder = f"{capture_root}/build/experiments/active/menu-portrait-pointer-ab/runtime-20261001-v1/runtime/{name}"
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
    if run_id != f"menu-gfx-ptr-20261001-{name}":
        raise ValueError("runtime run identity changed")
    if marker != {"run_id": run_id, "capture_frame": 80, "status": "capture-complete"}:
        raise ValueError("completion marker changed")
    inputs = [{"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}] if with_input else []
    expected = {"run_id": run_id, "frame": 80, "capture_frame": 80, "inputs": inputs,
                "success": True, "status": "capture-complete", "input_state": f"{capture_root}/{INPUT_STATE}",
                "input_state_sha256": INPUT_SHA, "rom_sha256": ROM_SHAS[variant],
                "output_state": f"{folder}/frame80.ss9", "output_png": f"{folder}/frame80.png",
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
    expected, before, after, palette = _independent_build(root, tuple(sorted(contract["inputs"].items())))
    if json.loads(objects["build-manifest.json"]) != expected:
        raise ValueError("build manifest differs from independent raw reconstruction")
    plan, preflight = json.loads(objects["plan.json"]), json.loads(objects["preflight-result.json"])
    if (plan["binary_sha256"] != BINARY_SHA or plan["library_sha256"] != LIBRARY_SHA or plan["source_commit"] != COMMIT
            or plan["input_state_sha256"] != INPUT_SHA or plan["capture_frame"] != 80
            or preflight["library_sha256"] != LIBRARY_SHA or preflight["source_commit"] != COMMIT
            or preflight["exported_git_commit"] != COMMIT or preflight["dlopen_verified"] is not True
            or preflight["source_tree_clean"] is not True):
        raise ValueError("runtime toolchain identity changed")
    if (plan["cases"] != [{"name": n, "variant": v, "input": i} for n, v, i in CASES]
            or plan["variants"] != expected["variants"] or plan["build_manifest_sha256"] != sha(objects["build-manifest.json"])
            or plan["input_state"] != INPUT_STATE or plan["input_state_version"] != "0x01000007"
            or plan["expected_output_state_version"] != "0x0100000B" or plan["bank_cells_total"] != 630
            or plan["requested_cell"] != {"record_id": "1", "field_id": "gfx_ptr_0"}
            or plan["required_heavy_lock"] != "build/experiments/heavy.lock" or plan["global_exhaustive_claim"] is not False
            or plan["repository_inputs"] != {p: contract["inputs"][p] for p in contract["capture_input_paths"]}
            or plan["scripts"] != {p: contract["inputs"][p] for p in
                                   ("tools/mgba_checkpoint_replay.lua", "tools/mgba_single_input_replay.lua")}):
        raise ValueError("runtime plan scope changed")
    bank = json.loads(read_regular(root / BANK))
    if (bank["entry_count"] != 63 or bank["entry_size"] != 40
            or [r["name"] for r in bank["entry_format"]["fields"]] != FIELDS
            or bank["table_offset"] + 40 != 0x5A4E14):
        raise ValueError("bank denominator changed")
    input_state = load_gba_state(root / INPUT_STATE)
    base = read_regular(root / "rom/base.gba")
    if (input_state.version_magic != 0x01000007 or input_state.read_u32(0x030011F0) != 0x08031F42
            or base.find(bytes.fromhex("02000100"), 0x31F42, 0x32000) != 0x31F6E
            or input_state.read_memory(0x06010000, 6400) in (before, after)):
        raise ValueError("natural pre-load boundary changed")
    rgbs, domains = {}, {}
    for name, variant, with_input in CASES:
        launch = _provenance(root, name, variant, with_input, objects, contract)
        if (launch["DYLD_LIBRARY_PATH"] != plan["DYLD_LIBRARY_PATH"]
                or plan["DYLD_LIBRARY_PATH"] != str(Path(preflight["library"]).parent)
                or launch["command"][0] != plan["binary"]):
            raise ValueError("library/binary selection changed")
        path = source / f"runtime/{name}/frame80.ss9"
        state = load_gba_state(path)
        if state.version_magic != 0x0100000B:
            raise ValueError("snapshot version changed")
        with Image.open(source / f"runtime/{name}/frame80.png") as image:
            if image.size != (240, 160):
                raise ValueError("pixels dimensions changed")
            rgb = image.convert("RGB").tobytes()
        if render_checkpoint(path)[0] != rgb:
            raise ValueError("renderer does not reproduce captured pixels")
        rgbs[name] = rgb
        domains[name] = {n: state.read_memory(a, size) for n, a, size in DOMAINS}
        if with_input:
            stream = before if variant == "baseline" else after
            if (state.read_memory(0x06010000, 6400) != stream
                    or state.read_memory(0x02002900, 6272) != stream[128:]
                    or sha(state.read_memory(0x02002880, 128)) != "963fe19839f2b2692d60b90eaae9b85ca5cebefc5a93d78e26e193b061def29e"
                    or state.read_memory(0x05000200, 128) != palette):
                raise ValueError("natural graphics memory domain route changed")
    zeros = [r[0] for r in CASES if not r[2]]
    if any(domains[n] != domains[zeros[0]] or rgbs[n] != rgbs[zeros[0]] for n in zeros[1:]):
        raise ValueError("zero input control differs")
    left, right = domains["input-baseline"], domains["input-candidate"]
    differences = {n: _diff(left[n], right[n]) for n, *_ in DOMAINS}
    if differences != {"IO": [], "PRAM": [], "VRAM": [0x11440], "OAM": [], "IWRAM": [], "EWRAM": [0x3CC0]}:
        raise ValueError("runtime memory domain isolation changed")
    a, b = rgbs["input-baseline"], rgbs["input-candidate"]
    if (sha(a) != "aada62ba20f1629f42db886114b96fd17c05c73cb7ee58f137628913747a22bc"
            or sha(b) != "f4ffd0cee4f4aa889b3598c4707b88dd7dd0ab67e40dc6bd96045cb49c8a79ed"):
        raise ValueError("final pixels identity changed")
    changes = _pixel_changes(a, b)
    if changes != [{"x": 56, "y": 48, "before_rgb": [239, 189, 165], "after_rgb": [99, 74, 57]}]:
        raise ValueError("final pixels attribution changed")
    return {"schema": SCHEMA, "verified": True, "bank": "menu-ui", "bank_sha256": contract["inputs"][BANK],
            "record_ids_total": [str(i) for i in range(63)], "record_ids_covered": ["1"],
            "field_ids_total": FIELDS, "field_ids_covered": ["gfx_ptr_0"], "cells_total": 630,
            "cells_covered": [{"record_id": "1", "field_id": "gfx_ptr_0"}],
            "changed_pixel_count": 1, "bbox_inclusive": [56, 48, 56, 48], "pixel_changes": changes,
            "memory_differences": differences, "zero_input_sample_count": 3,
            "natural_show_portrait_load": True, "isolated_pointer_field_ab": True,
            "scratch_prefix_semantics_verified": False,
            "exhaustive": False, "physical_gba_verified": False,
            "raw_sha256": {name: sha(data) for name, data in objects.items()}, "contract_sha256": CONTRACT_SHA}


def verify_source(root, source):
    try:
        return _verify_source(root, source)
    except (OSError, KeyError, TypeError, IndexError) as error:
        raise ValueError(f"invalid runtime source: {error}") from error


ARTIFACT_PATH = "build/experiments/active/menu-portrait-pointer-ab/contract-20261001-v1/final"
SCRIPT_PATH = "tools/verify_menu_portrait_pointer_ab.py"
ARTIFACT_FILES = {"raw.tar", "evidence.json", "baseline.png", "candidate.png"}
IMPLEMENTATION_PATHS = (
    "tools/build_menu_portrait_pointer_ab.py", "tests/test_build_menu_portrait_pointer_ab.py",
    "tools/export_menu_portrait_pointer_ab.py", SCRIPT_PATH,
    "tests/test_menu_portrait_pointer_ab.py", "tests/test_menu_portrait_pointer_publication.py",
)
LIMITATIONS = [
    "Only record 1 gfx_ptr_0 has isolated natural ShowPortrait(0,1,0) load evidence.",
    "Other 629 cells and portrait transitions are unverified; null row 0 and special variant 5 are not promoted.",
    "Scratch prefix semantics, arbitrary navigation and physical GBA execution remain unverified.",
    "No ROM-byte classification, live catalog or release gate is promoted by this packet.",
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
            if data[f"{variant}.png"] != objects[f"runtime/input-{variant}/frame80.png"]:
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
    uncovered = [{"record_id": str(i), "field_id": field} for i in range(63)
                 for field in FIELDS
                 if {"record_id": str(i), "field_id": field} not in covered]
    return {
        "catalog_classification": "runtime_verified", "bank_sha256": result["bank_sha256"],
        "coverage": {"status": "artifact_verified_natural_show_portrait_load", "records_total": 63, "records_covered": 1,
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
