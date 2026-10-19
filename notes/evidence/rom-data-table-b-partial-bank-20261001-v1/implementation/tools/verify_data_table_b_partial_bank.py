"""Portable archived-sample verifier for the fixed 79-cell message bank.

Recorded launch paths remain frozen provenance, never filesystem dependencies.
This offline replay does not launch mGBA or supply missing zero-input controls.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import verify_data_table_b_message0_pointer_ab as legacy
from tools.rom_small_cfg_callback_gaps_independent_verifier import read_regular, sha

SCHEMA = "data-table-b-partial-bank-verification-v1"
CONTRACT = "tools/data/data-table-b-partial-bank-contract-v1.json"
CONTRACT_SHA = "c8f736cd52ff52bea19625304a47fb06f31f7e97baf0e233835e803811374fab"
BANK = "sequel/content/data-table-b/bank.json"
ARTIFACT = "artifacts/data-table-b-message0-pointer-pixel-ab-v1"
SCRIPT = "tools/verify_data_table_b_partial_bank.py"
LIMITATIONS = [
    "Only message 0 text_ptr has legacy archived natural action-7 pointer A/B evidence.",
    "The two captures lack a verified zero-input control and recorded shared-lock identity.",
    "Replay is offline; current emulator execution and its external attestation are not verified.",
    "Messages 1..78, language decoding, exhaustive bank semantics and physical GBA remain unverified.",
]


def load_contract(root):
    raw = read_regular(root / CONTRACT)
    if sha(raw) != CONTRACT_SHA:
        raise ValueError("contract identity mismatch")
    value = json.loads(raw)
    if value["schema"] != "data-table-b-partial-bank-inputs-v1":
        raise ValueError("contract schema mismatch")
    for name, digest in value["inputs"].items():
        if sha(read_regular(root / name)) != digest:
            raise ValueError(f"input identity mismatch: {name}")
    return value


def verify_archive_contents(root, source):
    """Rebuild the frozen evidence using actual ROM, state, image and raw audits.

The legacy top-level collector demands that the current checkout and binary
live at their original absolute paths. Here those exact recorded paths are
validated as capture provenance; no old path is opened or executed.
    """
    root = Path(root).resolve(strict=True)
    source = Path(source).resolve(strict=True)
    return _rebuild_evidence(root, source, load_contract(root))


def _rebuild_evidence(root, source, contract):
    captured = Path(contract["historical_capture_root"])
    captured_run = captured / contract["historical_capture_run"]
    checkpoint = legacy.INPUT_PATH.as_posix()
    if sha(read_regular(source / "input.ss9")) != legacy.INPUT_SHA256:
        raise ValueError("raw checkpoint identity mismatch")
    base = read_regular(root / "rom/base.gba")
    roms = {"baseline": legacy.build_probe(base),
            "candidate": legacy.build_probe(base, message_id=0, replacement_id=1)}
    changed = [i for i, (a, b) in enumerate(zip(roms["baseline"], roms["candidate"], strict=True)) if a != b]
    if changed != [legacy.MESSAGE_TABLE]:
        raise ValueError("ROM pointer isolation mismatch")
    pointers = dict(zip(("baseline", "candidate"), struct.unpack_from("<II", base, legacy.MESSAGE_TABLE)))
    runs, guards = {}, {}
    script_sha = contract["inputs"][legacy.SCRIPT_PATH.as_posix()]
    for variant in ("baseline", "candidate"):
        runtime = source / variant
        audit = legacy.read_json(runtime / "audit.json")
        sentinel = legacy.read_json(runtime / "sentinel.json")
        done = legacy.read_json(runtime / "done.json")
        guard = legacy.read_json(runtime / "guard.json")
        historical = captured_run / legacy.SOURCE_DIRS[variant]
        expected_command = [str(legacy.BINARY_PATH), "--script", str(captured / legacy.SCRIPT_PATH),
                            str(captured_run / "input" / legacy.ROM_NAMES[variant])]
        rom_sha = sha(roms[variant])
        if (audit != sentinel or audit.get("status") != "capture-complete"
                or audit.get("success") is not True or audit.get("frame") != 300
                or audit.get("capture_frame") != 300
                or audit.get("inputs") != [{"key": "A", "down_frame": 5, "up_frame": 13, "hold_frames": 8}]
                or audit.get("automatic_inputs") != [] or audit.get("recovery_inputs") != []
                or audit.get("evidence_mode") != "input-sequence"
                or audit.get("zero_input_verified") is not False
                or audit.get("input_state") != str(captured / checkpoint)
                or audit.get("input_state_sha256") != legacy.INPUT_SHA256
                or audit.get("rom_sha256") != rom_sha
                or any(audit.get(key) != str(historical / filename) for key, filename in (
                    ("output_state", "output.ss9"), ("output_png", "output.png"),
                    ("audit", "audit.json"), ("sentinel", "sentinel.json")))
                or done.get("status") != "capture-complete"
                or guard.get("reason") != "completed" or guard.get("exit_code") != 0
                or guard.get("completion_trigger") != "success-marker"
                or guard.get("protection_backend") != "posix-process-group"
                or guard.get("degraded") is not False or guard.get("command") != expected_command
                or guard.get("cwd") != str(captured)
                or type(guard.get("peak_tree_rss_mib")) not in (int, float)
                or not 0 < guard["peak_tree_rss_mib"] <= 512):
            raise ValueError(f"{variant} historical provenance mismatch")
        pointer = pointers[variant]
        expected_scratch = {"magic": legacy.MAGIC, "hit_count": 1, "message_id": 0,
                            "entry_address": legacy.MESSAGE_TABLE_BUS, "selected_pointer": pointer,
                            "target_prefix_hex": base[pointer - 0x08000000:pointer - 0x08000000 + 16].hex()}
        scratch = legacy._scratch(runtime / "output.ss9")
        if scratch != expected_scratch:
            raise ValueError(f"{variant} selector scratch mismatch")
        rgb_sha = legacy.validate_state_png_pair(runtime / "output.ss9", runtime / "output.png", variant)
        runs[variant] = {
            "rom_sha256": rom_sha, "rgb_sha256": rgb_sha, "scratch": scratch,
            "peak_tree_rss_mib": guard["peak_tree_rss_mib"],
            **{f"{key}_sha256": sha(read_regular(runtime / name)) for key, name in (
                ("audit", "audit.json"), ("done", "done.json"), ("sentinel", "sentinel.json"),
                ("state", "output.ss9"), ("png", "output.png"), ("guard", "guard.json"))},
        }
        guards[variant] = {"guard_sha256": runs[variant]["guard_sha256"], "rom_sha256": rom_sha,
                           "binary_command_path_sha256": sha(expected_command[0].encode()),
                           "script_command_path_sha256": sha(expected_command[2].encode())}
    launch = {"schema": "data-table-b-message0-pointer-launch-identity-v1",
              "binary": {"basename": "mGBA", "sha256": legacy.BINARY_SHA256, "source_commit": legacy.BINARY_COMMIT},
              "script": {"repository_path": legacy.SCRIPT_PATH.as_posix(), "sha256": script_sha},
              "guards": guards}
    if legacy.read_json(source / "launch-identity.json") != launch:
        raise ValueError("launch identity mismatch")
    count = legacy._different_pixels(source / "baseline/output.png", source / "candidate/output.png")
    if count != 928:
        raise ValueError("final pixel difference mismatch")
    return {
        "schema": "data-table-b-message0-pointer-pixel-ab-evidence-v1", "verified": True,
        "bank": {"rom_offset": legacy.MESSAGE_TABLE, "record_count": 79, "record_size": 4,
                 "end_offset_exclusive": legacy.MESSAGE_TABLE + 79 * 4},
        "natural_route": {"checkpoint": checkpoint, "checkpoint_sha256": legacy.INPUT_SHA256,
                          "action": "confirmed natural action 7 (shadow clone)",
                          "input": {"key": "A", "down_frame": 5, "up_frame": 13},
                          "selector_hook": f"0x{legacy.HOOK:08X}", "renderer": "0x08098290"},
        "edit": {"message_id": 0, "field": "text_ptr", "rom_offset": legacy.MESSAGE_TABLE,
                 "baseline_pointer": f"0x{pointers['baseline']:08X}", "candidate_donor_id": 1,
                 "candidate_pointer": f"0x{pointers['candidate']:08X}", "changed_rom_offsets": changed},
        "runtime_effect": {"selector_hit_count_each": 1, "selected_entry_address": f"0x{legacy.MESSAGE_TABLE_BUS:08X}",
                           "baseline_rgb_sha256": runs["baseline"]["rgb_sha256"],
                           "candidate_rgb_sha256": runs["candidate"]["rgb_sha256"],
                           "different_pixel_count": count, "visible_message_changed": True},
        "emulator": {"binary_sha256": legacy.BINARY_SHA256, "source_commit": legacy.BINARY_COMMIT,
                     "script_path": legacy.SCRIPT_PATH.as_posix(), "script_sha256": script_sha},
        "runs": runs,
        "scope": {"natural_action7_consumer_verified": True,
                  "message0_pointer_causal_visible_difference_verified": True,
                  "all_79_messages_naturally_exercised": False, "natural_language_decoding_claimed": False,
                  "external_cryptographic_attestation_claimed": False, "physical_gba_verified": False},
    }


def verify_partial_bank(root):
    root = Path(root).resolve(strict=True)
    contract = load_contract(root)
    inputs = contract["inputs"]
    bank = json.loads(read_regular(root / BANK))
    if (bank["entry_count"] != 79 or bank["entry_size"] != 4 or len(bank["entries"]) != 79
            or bank["entry_format"]["fields"] != [{"offset": 0, "size": 4, "name": "text_ptr", "type": "u32"}]):
        raise ValueError("fixed bank denominator mismatch")
    base = read_regular(root / "rom/base.gba")
    for index, entry in enumerate(bank["entries"]):
        offset = legacy.MESSAGE_TABLE + 4 * index
        if (entry["_index"] != index or entry["_raw_offset"] != offset
                or entry["text_ptr"] != struct.unpack_from("<I", base, offset)[0]):
            raise ValueError("bank ROM record identity mismatch")
    artifact = root / ARTIFACT
    manifest = legacy.read_json(artifact / "manifest.json")
    if (manifest["artifact_id"] != legacy.ARTIFACT_ID or manifest["artifact_schema"] != legacy.ARTIFACT_SCHEMA
            or manifest["schema"] != legacy.PROMOTION_SCHEMA or manifest["artifact_status"] != "accepted"
            or set(manifest["files"]) != {"baseline.png", "candidate.png", "evidence.json", "raw.tar"}
            or set(manifest["implementation"]) != legacy.IMPLEMENTATION_FILES
            or manifest["verifier"] != {"command": legacy.verifier_command(), "exit_code": 0}):
        raise ValueError("legacy manifest identity mismatch")
    for name, digest in manifest["files"].items():
        if inputs[f"{ARTIFACT}/{name}"] != digest:
            raise ValueError("legacy payload binding mismatch")
    for name, digest in manifest["implementation"].items():
        if inputs[name] != digest:
            raise ValueError("legacy implementation binding mismatch")
    with tempfile.TemporaryDirectory() as directory:
        raw = Path(directory).resolve(strict=True)
        legacy.extract_raw(artifact / "raw.tar", raw)
        evidence = _rebuild_evidence(root, raw, contract)
        for variant in ("baseline", "candidate"):
            if read_regular(artifact / f"{variant}.png") != read_regular(raw / variant / "output.png"):
                raise ValueError("artifact PNG binding mismatch")
    if legacy.read_json(artifact / "evidence.json") != evidence:
        raise ValueError("legacy evidence reconstruction mismatch")
    return {
        "schema": SCHEMA, "verified": True, "scope": "legacy_archived_natural_action7_pointer_ab",
        "bank": "data-table-b", "bank_sha256": inputs[BANK],
        "evidence_sha256": {f"{ARTIFACT}/manifest.json": inputs[f"{ARTIFACT}/manifest.json"]},
        "input_sha256": inputs, "contract_sha256": CONTRACT_SHA,
        "record_ids_total": [str(i) for i in range(79)], "record_ids_covered": ["0"],
        "field_ids_total": ["text_ptr"], "field_ids_covered": ["text_ptr"],
        "cells_total": 79, "cells_covered": [{"record_id": "0", "field_id": "text_ptr"}],
        "cells_uncovered": [{"record_id": str(i), "field_id": "text_ptr"} for i in range(1, 79)],
        "changed_pixel_count": evidence["runtime_effect"]["different_pixel_count"],
        "historical_captures": 2, "zero_input_control_verified": False,
        "historical_shared_lock_verified": False, "current_emulator_executed": False,
        "portable_offline_archive_replay": True, "physical_gba_verified": False,
        "exhaustive": False, "limitations": list(LIMITATIONS),
    }


def proof_binding(root, result):
    """Return a proposal only; never change the live catalog."""
    root = Path(root).resolve(strict=True)
    if result != verify_partial_bank(root):
        raise ValueError("result mismatch")
    return {
        "catalog_classification": "runtime_verified", "bank_sha256": result["bank_sha256"],
        "coverage": {"status": "artifact_verified_legacy_natural_pointer_ab", "records_total": 79,
                     "records_covered": 1, **{key: result[key] for key in (
                         "record_ids_total", "record_ids_covered", "field_ids_total", "field_ids_covered",
                         "cells_total", "cells_covered", "cells_uncovered")}},
        "evidence": [{"path": n, "sha256": s} for n, s in result["evidence_sha256"].items()],
        "verifiers": [{"command": ["python3", SCRIPT, "--root", "."],
                       "script_sha256": sha(read_regular(root / SCRIPT)),
                       "contract": {"format": "json", "assertions": {f"/{k}": v for k, v in result.items()}}}],
        "limitations": list(LIMITATIONS),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        result = verify_partial_bank(args.root)
    except (ValueError, OSError, KeyError) as error:
        print(json.dumps({"schema": SCHEMA, "verified": False, "errors": [str(error)]}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
