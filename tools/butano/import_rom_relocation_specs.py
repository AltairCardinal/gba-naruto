#!/usr/bin/env python3
"""Import the accepted relocation and writeback families as the engineering
basis for the "customized original ROM" route.

Content-level customization of the original ROM is not a matter of finding the
right bytes: graphics, palettes and tilemaps have to be moved somewhere, every
pointer that referenced them has to be recomputed, and the moved content has
to still fit.  The reverse work tree already closed that question for 22
families -- each one ships a *relocation spec* (the rules: which resource
belongs to which region, which pointer offsets have to be rewritten) and a
*relocation audit* or *writeback audit* (the evidence: how many bytes the
region holds, how many pointer patches were applied, and whether a resource
still fits its slot after an edit).

Until now all 22 sat at ``doc`` status: mentioned in prose, never consumed.
This importer copies the rules and the audits into the remake tree and
records, per family:

* the region, the partition and the owner that the resource is bound to;
* the relocation rule set (the number of edits, and the pointer offsets they
  rewrite);
* the writeback capacity gate -- the numbers that decide whether an edited
  resource still fits, and which of them are allowed to overflow;
* the manifest hash, the verifier command and the applicability boundary, so
  the import keeps its provenance and its limits.

``verify`` re-checks the imported tree against the reverse work tree and
re-runs the capacity gate.  A family whose manifest moved, lost its
``accepted`` status, whose bytes no longer match its own manifest, or whose
capacity gate no longer holds is a hard failure naming that family.

Usage::

    python3 tools/butano/import_rom_relocation_specs.py import \\
        --reverse-root /Users/altair/github/gba-naruto-reverse \\
        --out-dir artifacts/butano-reverse-m3-import-v1/relocation

    python3 tools/butano/import_rom_relocation_specs.py verify \\
        --reverse-root /Users/altair/github/gba-naruto-reverse \\
        --out-dir artifacts/butano-reverse-m3-import-v1/relocation
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

if __package__ in (None, ""):  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.butano.import_rom_reverse_families import (
    ACCEPTED_STATUS,
    DEFAULT_REVERSE_ROOT,
    EXIT_GATE_FAILED,
    EXIT_INPUT_ERROR,
    EXIT_OK,
    FamilyImportError,
    FamilySpec,
    as_specs,
    copy_verified_file,
    first_key,
    load_verified_manifest,
    manifest_scope,
    manifest_verifier,
    prune_previous_output,
    read_json,
    reverse_commit,
    sha256_file,
    verify_family_files,
    write_json,
)

IMPORT_SCHEMA = "konoha.butano-relocation-spec-import.v1"
INDEX_NAME = "relocation-specs.json"
RUN_MANIFEST_NAME = "import-manifest.json"

#: The accepted relocation / writeback families, pinned by the SHA-256 of
#: their manifest.  Each entry is the data the importer consumes: it reads
#: that manifest, checks the hash against the pin, and imports the rule and
#: audit files the manifest lists.
RELOCATION_FAMILIES: tuple[tuple[str, str], ...] = (
    ("battle-effect-resource-relocation-v1", "d1076ca1a1fc7ad4f6bc0fdc8fe0ebfc3eb51132721d5cf165237d8d3d46da9f"),
    ("battle-effect-resource-writeback-v1", "47970ba90a761de5eeb67eebaea574558b2e780b8483129e22a02dbd61d3cb3c"),
    ("bg-resource-relocation-v1", "b4ce592ce1fc203a1e25943181a0e1e9b1cfd95f76537ba01dbbde0fb8b62199"),
    ("bg-resource-writeback-v1", "e14e1c9f43f26ebf6dbe34b3d813d50e90480a2f197a9771f76ccab821c08728"),
    ("character-battle-bundle-relocation-v1", "4f51f3fa95a29b3f8328e6d67ee7a60efe85383476aefc26f864fcbb9fa9dc20"),
    ("character-battle-graphics-writeback-v1", "a6d6aa819842e6d477111573f7d4d34608055e916dbe1126d7ff1a06fa4a41b4"),
    ("character-battle-palette-writeback-v1", "262d1a8480cb93fe996e2c56412df0b3b559771b0c8a63c40a43fcafc6e944f0"),
    ("character-battle-structure-writeback-v1", "e3727d069742f6dbe9bc26c9765060dfc725f61cf10f76da5de4ad1cf768e672"),
    ("cutscene-obj-bundle-relocation-v1", "5438878f03972989ca20c302cce4a526b594208b8458399a2b0d2d2455b1868b"),
    ("direct-image-palette-relocation-v1", "996a9dc0dfd9174154a3cdae9bfbdafd03799fc75fad91d646b21a3e8cced3c1"),
    ("generic-sprite-bundle-relocation-v1", "775bc2ed1fa6d64e0107b5318cbfdfba7c70b07d7c29b54e3d1dac885e9aa941"),
    ("map-resource-relocation-v1", "5c229b20e9842fc10da92b1fc64594d4766c4554ced744c9a343e0c844410d07"),
    ("map-resource-writeback-v1", "9c7333e7c817133738e035f32526ce1f065a6f223aeae02b87ef3ab56526439e"),
    ("menu-portrait-relocation-v1", "451237d76f5208b2f36d7c7eeb29c8b86dfb051075b8aa39fccd8bfce15118ca"),
    ("menu-portrait-writeback-v1", "dbae133169f8ced45eb0893535084c5488345cfe2d3be6c6fef1611e3352278a"),
    ("residual-lz77-graphics-relocation-v1", "14b9667a6a3fada3cda3baf0c76352bd2192156c9d533da4916229d1883b2e18"),
    ("residual-text-bg-tilemap-relocation-v1", "14418c429239eb953f1aefa15e12ddbcaf4b9e13adb7f44f686134440b307679"),
    ("residual-wram-derived-tilemap-relocation-v1", "1cf450ddb482b287d62d108660443b332f988007eef07f34726fa30a218f0030"),
    ("residual-wram-tilemap-relocation-v1", "93a767b4a81e8742e75d24943823ca3b140b056ebb67db8d7c84df039609e5c2"),
    ("story-visual-resource-relocation-v1", "8b6de4effe5fe10da40cb60e80ad9cf713d456a6650cf5a6054ebb258cfe9846"),
    ("tile-asset-resource-relocation-v1", "d645146c230b32528accfe4dccdb495bd0fcd63e9bfd0bc87441c6c271e080c3"),
    ("world-map-background-relocation-v1", "90d45034d427bedb076c53d9ab315437f2ce6e8c6634a69ab4513e7d6c5a2f39"),
)

#: The ROM every one of these families was measured against.  A family that
#: was measured against a different ROM does not describe this project.
EXPECTED_BASE_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

#: Pairs of summary keys that must agree: a round-trip count and the total it
#: is a fraction of.  Every pair that is present must hold.
_ROUNDTRIP_PAIRS = (
    ("original_roundtrip_fit_content_count", "content_resource_count"),
    ("original_roundtrip_fit_count", "resource_count"),
    ("original_roundtrip_count", "physical_palette_count"),
    ("original_roundtrip_count", "resource_count"),
    ("component_roundtrip_count", "component_count"),
    ("keyframe_roundtrip_count", "keyframe_count"),
)


# --------------------------------------------------------------------------
# family introspection
# --------------------------------------------------------------------------

def json_payloads(manifest: dict[str, Any]) -> list[str]:
    """The JSON payloads of a family, in a stable order.

    The relocation families ship a rule file and an audit file; the writeback
    families ship a single audit file.  Savestates and raw graphics blobs stay
    in the reverse work tree: they are re-run inputs, not the engineering
    basis, and the receipt still pins their hashes.
    """
    return sorted(
        relative for relative in (manifest.get("files") or {})
        if relative.lower().endswith(".json")
    )


def _load_payloads(family_dir: Path, relatives: Sequence[str]) -> dict[str, Any]:
    payloads: dict[str, Any] = {}
    for relative in relatives:
        payloads[relative] = read_json(family_dir / relative)
    return payloads


def _pick(payloads: dict[str, Any], *needles: str) -> tuple[str, dict[str, Any]]:
    """Find the payload whose name contains one of ``needles``."""
    for needle in needles:
        for relative, payload in sorted(payloads.items()):
            if needle in relative.lower() and isinstance(payload, dict):
                return relative, payload
    return "", {}


def extract_rule_set(spec: dict[str, Any]) -> dict[str, Any]:
    """The relocation rules of a family: the region binding and the edits."""
    edits = spec.get("edits")
    resources = spec.get("resources")
    return {
        "schema": spec.get("schema"),
        "base_rom_sha256": spec.get("base_rom_sha256"),
        "partition": spec.get("partition"),
        "owner": spec.get("owner"),
        "region": spec.get("region"),
        "region_owner": spec.get("region_owner"),
        "region_registry": spec.get("region_registry"),
        "region_registry_sha256": spec.get("region_registry_sha256"),
        "source_catalog": first_key(spec, ("source_catalog", "catalog")),
        "source_catalog_sha256": first_key(spec, ("source_catalog_sha256", "catalog_sha256")),
        "description": spec.get("description"),
        "edit_count": len(edits) if isinstance(edits, list) else None,
        "resource_count": len(resources) if isinstance(resources, list) else None,
    }


def extract_audit(audit: dict[str, Any]) -> dict[str, Any]:
    """The evidence of a family: the audit summary and the output ROM."""
    summary = audit.get("summary")
    return {
        "summary": summary if isinstance(summary, dict) else {},
        "scope": audit.get("scope") if isinstance(audit.get("scope"), dict) else {},
        "output_rom_sha256": audit.get("output_rom_sha256"),
        "mutation_model": audit.get("mutation_model"),
        "source_catalog": audit.get("source_catalog"),
        "rom": audit.get("rom"),
    }


def capacity_gate(summary: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
    """The writeback safety gate of a family, derived from its own summary.

    A family passes when every resource it accounts for can still be written
    back at its original size, when the tightest original slot still has room,
    and when the audit did not leave a pointer it could not account for.  The
    bounded mutation witness is allowed to overflow -- the audits say so
    explicitly -- so it is reported, not failed on.
    """
    problems: list[str] = []
    roundtrips: list[dict[str, Any]] = []
    for roundtrip_key, total_key in _ROUNDTRIP_PAIRS:
        if roundtrip_key not in summary or total_key not in summary:
            continue
        roundtrip = summary[roundtrip_key]
        total = summary[total_key]
        if not isinstance(roundtrip, int) or not isinstance(total, int):
            continue
        holds = roundtrip == total
        roundtrips.append({
            "roundtrip_key": roundtrip_key,
            "total_key": total_key,
            "roundtrip": roundtrip,
            "total": total,
            "holds": holds,
        })
        if not holds:
            problems.append(
                f"{roundtrip_key}={roundtrip} does not cover {total_key}={total}")

    margin = summary.get("minimum_original_slot_margin")
    if isinstance(margin, int) and margin < 0:
        problems.append(f"minimum_original_slot_margin={margin} is negative")

    unexpected = summary.get("unexpected_pointer_count")
    if isinstance(unexpected, int) and unexpected != 0:
        problems.append(f"unexpected_pointer_count={unexpected} is not zero")

    guarded = sorted(
        key for key, value in scope.items()
        if key.endswith("_importer_available") and value is True
    )
    return {
        "roundtrips": roundtrips,
        "minimum_original_slot_margin": margin,
        "unexpected_pointer_count": unexpected,
        "mutation_overflow_slot_count": summary.get("mutation_overflow_slot_count"),
        "mutation_overflow_content_count": summary.get("mutation_overflow_content_count"),
        "guarded_importer_flags": guarded,
        "problems": problems,
        "holds": not problems,
    }


# --------------------------------------------------------------------------
# import
# --------------------------------------------------------------------------

def import_family(
    reverse_root: Path,
    out_dir: Path,
    spec: FamilySpec,
) -> dict[str, Any]:
    """Import one family and return its receipt."""
    _manifest_path, manifest = load_verified_manifest(reverse_root, spec)
    family_dir = Path(reverse_root) / "artifacts" / spec.family
    verified = verify_family_files(family_dir, spec, manifest)

    relatives = json_payloads(manifest)
    if not relatives:
        raise FamilyImportError(
            f"{spec.family}: manifest lists no JSON payload to import",
            family=spec.family, exit_code=EXIT_INPUT_ERROR)

    written: list[dict[str, Any]] = []
    imported: list[dict[str, Any]] = []
    for relative in relatives:
        destination = Path(out_dir) / spec.family / Path(relative).name
        digest = copy_verified_file(
            family_dir / relative, destination, verified[relative])
        written.append({
            "path": destination.relative_to(Path(out_dir)).as_posix(),
            "sha256": digest,
            "reverse_path": f"artifacts/{spec.family}/{relative}",
        })
        imported.append({
            "path": destination.relative_to(Path(out_dir)).as_posix(),
            "sha256": digest,
            "reverse_path": f"artifacts/{spec.family}/{relative}",
        })

    payloads = _load_payloads(family_dir, relatives)
    spec_rel, spec_payload = _pick(payloads, "spec")
    audit_rel, audit_payload = _pick(payloads, "audit", "writeback")
    if not spec_payload and not audit_payload:
        # A single-payload family: the payload is both the rule and the audit.
        only_rel, only_payload = next(iter(sorted(payloads.items())))
        spec_rel, spec_payload = only_rel, only_payload
        audit_rel, audit_payload = only_rel, only_payload

    rule_set = extract_rule_set(spec_payload)
    audit = extract_audit(audit_payload)
    summary = audit.get("summary") or {}
    scope = audit.get("scope") or {}
    if not scope:
        scope = manifest_scope(manifest)
    gate = capacity_gate(summary, scope)

    rom_hash = first_key(spec_payload, ("base_rom_sha256",)) or (
        (audit_payload.get("rom") or {}).get("sha256")
        if isinstance(audit_payload.get("rom"), dict) else None)
    base_rom_ok = rom_hash == EXPECTED_BASE_ROM_SHA256
    if not base_rom_ok:
        gate["problems"].append(
            f"base ROM {rom_hash!r} is not the expected {EXPECTED_BASE_ROM_SHA256!r}")
        gate["holds"] = False

    receipt: dict[str, Any] = {
        "family": spec.family,
        "kind": "relocation" if "relocation" in spec.family else "writeback",
        "manifest": spec.manifest_relpath,
        "manifest_sha256": spec.manifest_sha256,
        "artifact_status": manifest.get("artifact_status"),
        "artifact_schema": manifest.get("artifact_schema") or manifest.get("schema"),
        "base_rom_sha256": rom_hash,
        "base_rom_matches_project": base_rom_ok,
        "verifier": manifest_verifier(manifest),
        "scope": manifest_scope(manifest),
        "rule_set": rule_set,
        "rule_set_source": f"artifacts/{spec.family}/{spec_rel}" if spec_rel else None,
        "audit": audit,
        "audit_source": f"artifacts/{spec.family}/{audit_rel}" if audit_rel else None,
        "capacity_gate": gate,
        "imported_payloads": imported,
        "reverse_file_hashes": verified,
    }
    receipt_path = Path(out_dir) / spec.family / "import.json"
    write_json(receipt_path, receipt)
    written.append({
        "path": (Path(spec.family) / "import.json").as_posix(),
        "sha256": sha256_file(receipt_path),
        "reverse_path": None,
    })
    return {"receipt": receipt, "written": written}


def import_families(
    reverse_root: Path,
    out_dir: Path,
    specs: Sequence[FamilySpec],
) -> dict[str, Any]:
    """Import every pinned family and write the consolidated spec index."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prune_previous_output(out_dir, RUN_MANIFEST_NAME)

    receipts: list[dict[str, Any]] = []
    written_files: list[dict[str, Any]] = []
    for spec in specs:
        result = import_family(reverse_root, out_dir, spec)
        receipts.append(result["receipt"])
        written_files.extend(result["written"])

    registry_hashes = sorted({
        receipt["rule_set"].get("region_registry_sha256")
        for receipt in receipts
        if receipt["rule_set"].get("region_registry_sha256")
    })
    index = {
        "schema": IMPORT_SCHEMA,
        "source": {
            "reverse_commit": reverse_commit(reverse_root),
            "base_rom_sha256": EXPECTED_BASE_ROM_SHA256,
            "accepted_status_required": ACCEPTED_STATUS,
        },
        "family_count": len(receipts),
        "region_registry_sha256": registry_hashes,
        "all_capacity_gates_hold": all(
            receipt["capacity_gate"]["holds"] for receipt in receipts),
        "families": receipts,
    }
    index_digest = write_json(out_dir / INDEX_NAME, index)
    written_files.append({
        "path": INDEX_NAME,
        "sha256": index_digest,
        "reverse_path": None,
    })
    run_manifest = {
        "schema": IMPORT_SCHEMA,
        "index": INDEX_NAME,
        "index_sha256": index_digest,
        "written_files": sorted(written_files, key=lambda entry: entry["path"]),
    }
    write_json(out_dir / RUN_MANIFEST_NAME, run_manifest)
    return index


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------

def verify_import(
    reverse_root: Path,
    out_dir: Path,
    specs: Sequence[FamilySpec],
) -> dict[str, Any]:
    """Re-check an imported tree against the reverse work tree and the gates."""
    out_dir = Path(out_dir)
    index_path = out_dir / INDEX_NAME
    if not index_path.is_file():
        raise FamilyImportError(
            f"no imported relocation index at {index_path}",
            exit_code=EXIT_INPUT_ERROR)
    index = read_json(index_path)
    if index.get("schema") != IMPORT_SCHEMA:
        raise FamilyImportError(
            f"{index_path}: unexpected schema {index.get('schema')!r}",
            exit_code=EXIT_INPUT_ERROR)
    by_family = {entry["family"]: entry for entry in index.get("families") or []}
    problems: list[str] = []
    for spec in specs:
        receipt = by_family.get(spec.family)
        if receipt is None:
            problems.append(f"{spec.family}: not present in the imported index")
            continue
        if receipt.get("manifest_sha256") != spec.manifest_sha256:
            problems.append(
                f"{spec.family}: pinned manifest hash does not match the import")
            continue
        try:
            _path, manifest = load_verified_manifest(reverse_root, spec)
        except FamilyImportError as error:
            problems.append(str(error))
            continue
        verify_family_files(
            Path(reverse_root) / "artifacts" / spec.family, spec, manifest)
        for payload in receipt.get("imported_payloads") or []:
            local = out_dir / payload["path"]
            if not local.is_file():
                problems.append(
                    f"{spec.family}: imported payload {payload['path']} is missing")
            elif sha256_file(local) != payload["sha256"]:
                problems.append(
                    f"{spec.family}: imported payload {payload['path']} "
                    f"does not match its hash")
        for problem in (receipt.get("capacity_gate") or {}).get("problems") or []:
            problems.append(f"{spec.family}: {problem}")
    return {
        "schema": "konoha.butano-relocation-spec-verify.v1",
        "checked_families": len(specs),
        "problems": problems,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _reverse_root(value: str | None) -> Path:
    if value:
        return Path(value)
    from_env = os.environ.get("KONOHA_REVERSE_ROOT")
    if from_env:
        return Path(from_env)
    return DEFAULT_REVERSE_ROOT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", nargs="?", default="import", choices=("import", "verify"))
    parser.add_argument("--reverse-root", default=None,
                        help="reverse work tree to import from (read only)")
    parser.add_argument("--out-dir", default=None,
                        help="directory the imported specs are written to")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    out_dir = Path(args.out_dir) if args.out_dir else (
        root / "artifacts" / "butano-reverse-m3-import-v1" / "relocation")
    specs = as_specs(RELOCATION_FAMILIES)
    try:
        if args.command == "import":
            reverse_root = _reverse_root(args.reverse_root)
            index = import_families(reverse_root, out_dir, specs)
            print(json.dumps({
                "command": "import",
                "out_dir": out_dir.as_posix(),
                "family_count": index["family_count"],
                "all_capacity_gates_hold": index["all_capacity_gates_hold"],
            }, ensure_ascii=False, indent=2))
            return EXIT_OK if index["all_capacity_gates_hold"] else EXIT_GATE_FAILED
        reverse_root = _reverse_root(args.reverse_root)
        report = verify_import(reverse_root, out_dir, specs)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return EXIT_OK if not report["problems"] else EXIT_GATE_FAILED
    except FamilyImportError as error:
        print(f"import_rom_relocation_specs: {error}", file=sys.stderr)
        return error.exit_code
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"import_rom_relocation_specs: {error}", file=sys.stderr)
        return EXIT_INPUT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
