#!/usr/bin/env python3
"""Import the shelf families whose manifests verify file by file.

``docs/butano-wiring-roadmap.md`` (W4) asks that the families sitting on the
shelf -- closed, carrying a payload, and consumed by nobody -- be wired in.
The pixel-A/B route (``import_rom_pixel_ab_baselines.py``) only fits families
that carry a baseline/candidate frame pair, and only three of the shelf
families have that shape.

This importer covers the other shape: a family whose manifest lists **every
file with its SHA-256**.  Importing it is therefore a *content equivalence*
acceptance -- the copied bytes must be the bytes the reverse side signed --
and the same is true for the payload the remake can now read locally.

Fifteen shelf families are **not** imported: their own manifest disagrees with
their own files (the recorded hash of, say, ``rom-fixed-pair-tables.json`` does
not match the file sitting next to it).  That is a defect in the reverse
side's promotion, not something this importer may paper over, so those
families are left on the shelf and reported.

Usage::

    python3 tools/butano/import_rom_shelf_families.py import \\
        --reverse-root /Users/altair/github/gba-naruto-reverse \\
        --out-dir artifacts/butano-reverse-m3-import-v1/shelf

    python3 tools/butano/import_rom_shelf_families.py verify \\
        --reverse-root /Users/altair/github/gba-naruto-reverse \\
        --out-dir artifacts/butano-reverse-m3-import-v1/shelf
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.butano.import_rom_reverse_families import (  # noqa: E402
    EXIT_FAMILY_FILE_MISMATCH,
    EXIT_GATE_FAILED,
    EXIT_HASH_MISMATCH,
    EXIT_INPUT_ERROR,
    EXIT_OK,
    EXIT_STATUS_REJECTED,
    FamilyImportError,
    FamilySpec,
    as_specs,
    copy_verified_file,
    load_verified_manifest,
    manifest_scope,
    manifest_verifier,
    reverse_commit,
    sha256_file,
    verify_family_files,
    write_json,
)

IMPORT_SCHEMA = "konoha.butano-shelf-family-import.v1"

#: The shelf families whose manifests verify file by file.  Each entry pins
#: the manifest's SHA-256, so the import fails closed when the reverse side
#: moves.
SHELF_FAMILIES: tuple[tuple[str, str], ...] = (
    ("battle-effect-frame-phase-group1-v1", "fadf6b9d541589b8bd758839de91c1433f81e81cdcc3d4f5ac2387cf02e79526"),
    ("battle-effect-frame-phase-group14-v1", "a862bd09bb7c8bd417c8b0651036a99357a2cd5bc7ce852d50dcff4c98e3a46d"),
    ("battle-effect-frame-phase-group16-natural-v1", "f211669fe29bbc391b87083eca66226e4a49220489d7cbd56dc71b33a831bb8e"),
    ("battle-effect-frame-phase-group17-natural-v1", "03b075b52d2e6ebbcbfe66f64c47bbea7d93cc2bff59d876de138356a96f0e91"),
    ("battle-effect-frame-phase-group18-natural-sequence-v1", "e87b9b6035334ec29bf420529d5f541d72f76b07f36328470845ef0718c3768e"),
    ("battle-effect-frame-phase-group2-v1", "0babb563f167448ec924eb7647aa948110b1d7bf02e1e8a6752a7a79c4e5d68c"),
    ("battle-effect-frame-phase-group3-natural-v1", "b4a0ace388f1af08e9699df4c6ff593c711ee923ead56197a85c09e313c17f5a"),
    ("battle-effect-frame-phase-group4-natural-v1", "53485b25271cb565828c0461818f996fc5708b6348e5f3df4fca647da0e85493"),
    ("battle-effect-frame-phase-group5-v1", "bac4d5c3cd7c4c31fb88fdf31856548e03206467e7bf33b1203ccf8a0477e086"),
    ("battle-effect-frame-phase-v1", "d42a325efb3498d43be7b22e0c070b43608d54265d3ba93db975bac2127362a5"),
    ("battle-effect-group12-ai-observer-v1", "ddd212d475192f5c3c94d75e662164beabdc8b5159a7bccbe8b7fae36fe579b8"),
    ("battle-effect-group13-natural-runtime-v1", "f3347c73888f33b7f8b753a91490dd524583710c268a220a712fad65324808e2"),
    ("battle-effect-group18-natural-checkpoint-v1", "779a8df2df1cb8d9ccf6674d8ac93897f653615f7770c80c449406fd6aecbd16"),
    ("battle-effect-runtime-oam-bindings-v1", "6e8b7a06038cc06ed39f78d3ea05beb102ae32cea53ddbcd78110364c154825b"),
    ("battle-effect-runtime-oam-task-bindings-v1", "bc00e8e41610b09b84637a80a0262ba2ef883aac7e7a8ccdd862f2fbd28000af"),
    ("battle-status-bars-v1", "d88242fa88213b96d8fe48430a0758a3bb79adf7dd6bb6d22e7d00da9711c0d0"),
    ("character-battle-visual-resource-matrix-v1", "41baf4a2f087723e1d51de2629e1065958bd1d7ddd655f3157dbb0de41966fdb"),
    ("character-runtime-oam-bindings-v1", "98d84e6ce9a75b9d47be3efc4e1d7a14924729b3605dfde6b65d4b370f3fdce6"),
    ("character-runtime-oam-task-bindings-v1", "df2fc83e3322c0584c9410f6b23c798e6dfd400f6a21377552395756152cddfc"),
    ("initializer-resource-pack-v1", "8fc7c3ea449b480c5065a97e70d0f6c5c0fa30a0dc3f942931f6be86264337a4"),
    ("lz77-palette-runtime-v1", "d363310303d8b51d0cc6f64014489297071882859c547694b3db91f7c11c52bf"),
    ("map41-visual-resource-matrix-v1", "196aa07481b9aeb75ebae59de9214bc8893eb9bc913e29f9441897cd7590ec42"),
    ("portrait-palette-producers-v1", "5714056ed70d0510727d7b612bc89e90b7d0159c68e9a743c6af4815a0ebd361"),
    ("residual-text-bg-tilemap-resource-ownership-v1", "a4db6c9ecfb5bf1d4a408630900a1d6b061f0a04aa30191479522904a71b8ccc"),
    ("residual-wram-crop-tilemap-runtime-v1", "9580db8094ea06cd249b22307c440aea46a01ec141df2d7418d2ec890598341e"),
    ("residual-wram-tilemap-abi-v1", "8f74053ffda705e0a1aac0c761bd561905afbb03d5203745ce6c54910a222412"),
    ("residual-wram-tilemap-resource-ownership-v1", "57e04df8c14ac9ee0b34a5102e42b1d9761e168343e3671b8e396fe938123ab5"),
    ("residual-wram-tilemap-runtime-v1", "1cde045d1fb0e06028760371514cfe2ac47e1623e1d9605a00489e763a460f5f"),
    ("residual-wram-tilemap-runtime-v2", "73eb055798b1c93a59d9fc6c9bab16525933d2ea9ccfab066fe4b70b6d65d1f7"),
    ("residual-wram-transformed-tilemap-runtime-v1", "eee86b030e588cc5f336a09c51f036064cedd94efa7fd83b043d0e5f2db181bc"),
    ("residual-wram-visual-metadata-abi-v2", "ba1c878911f5541007bacc0092e0da852ff6f991203b834e50d461b8188ef54e"),
    ("rom-alternate-dialogue-table-v1", "f7ded383f1c7334d714337768867496d083a85db051a69688fea121023f121b0"),
    ("rom-battle-sound-selector-v1", "eb30940a42f9d2c0e7ece5f18939eb4c0b1fbb06c9d51bc756ad853bc13d8807"),
    ("rom-cutscene-obj-source-ranges-v1", "a0e97ec43858a145a7c26dc71c5b89dfe8c4d9a5d6074ccad88c4ae56e03afd5"),
    ("rom-dialogue-text-inventory-v1", "0e8f3276ff5eac20c089299174abeac36b930fd71e368b16cc97e0cce22e4d7d"),
    ("rom-direct-cpuset-gpu-inventory-v1", "ed886e717b54b0ec78af5eb4941d677095286290a5ad2ed2a01b033f4520d246"),
    ("rom-direct-dma-gpu-inventory-v1", "84bc8f927047d7356e6779d6550d2ff74e342929da4b9228fc2c8102585324d1"),
    ("rom-expansion-profile-v1", "75a056e0d82b24af30e59a713910a3e5d6a9073bb28ee079409689eba92dc7cc"),
    ("rom-gpu-copy-queue-inventory-v1", "3a3f4d06f27560dfcf2674c13802e2fbcc551246e5de121b1f62747a09f32a95"),
    ("rom-menu-portrait-palette-inventory-v1", "8a8675c2724131a6caa9b956825d74280fa26fe99447470b3cc3810688e6f88b"),
    ("rom-pointer-lz77-graphics-v1", "17a93ff1f8779a0da50d8e7022adf9c9a7656811884b32db3db3e54f13fd495d"),
    ("rom-renderer-text-inventory-v1", "43b723061e4c5f8f82b50326a4e851bec722fb0f42c0782005ddc3c1a683ad04"),
    ("rom-selector-direct-source-records-v1", "094dbb593b2b8e09849ea795f4a09155598936cd3a1bc0b36e2eda6a413cf789"),
    ("rom-staged-gpu-copy-inventory-v1", "ff634185ab977d0f99c5eab0e893149ad9ac28fcecc2e0d2df70bf3ac30c0f39"),
    ("rom-u8-indexed-u16-pair-lookup-v1", "926c2df1b1154181b28dcb65369471f87cdb35c986ce9d0c15a942a3e6fef81a"),
    ("runtime-bg-composites-v1", "fdb681d5fb3f86784208803301d97602642d70f21e76ddaa04a36dd552efa098"),
    ("runtime-font-tile-provenance-v1", "ad74f08c107a5326dc75c003614fcaff6fe1b0218087da80781d3d2316780375"),
    ("runtime-layer-static-provenance-v1", "6a24b443bea94177c8a017a1099cfb343b4d61bed765f6a4d7400cf738a16704"),
    ("runtime-screen-composites-v1", "f31ca8e7e21de6b930fcdb487359e63e30b08b140e74c1e7791a1a3ec619624c"),
    ("scene-visual-composites-v1", "bfa901135f416e48ee5e646d88c1b6669ab8c36d4817b24f2e3664cf00be0da2"),
    ("scene-visual-transition-timelines-v1", "47952417ec6219866b3256d63a2136d0c9c98ad4cbdc0fe643641d97a3929514"),
    ("story-visual-resource-sources-v1", "6a6aebe1cc1b9a37b8651309d461550cb13d36e319b587a8dbf657ebcc1ea1cc"),
)

#: Shelf families whose own manifest disagrees with their own files.  They are
#: deliberately **not** imported: the reverse side's promotion is inconsistent
#: there, and an importer that copies them would hide the defect.
#: The name must **not** end in ``_FAMILIES``: the audit reader treats every
#: constant with that suffix as a ``(family, manifest sha256)`` table, and a
#: tuple of plain strings would fail to unpack.
SHELF_FAMILIES_NOT_IMPORTED: tuple[str, ...] = (
    "rom-animation-descriptor-pool-v2",
    "rom-boot-copy-sources-v1",
    "rom-bounded-index-u16-pair-table-v1",
    "rom-cfg-proven-roots-v14",
    "rom-directsound-pitch-lookup-v1",
    "rom-display-text-delta-v1",
    "rom-fixed-animation-descriptor-groups-v1",
    "rom-fixed-index-u8-tail-v1",
    "rom-fixed-pair-tables-v1",
    "rom-fixed-renderer-script-records-v1",
    "rom-low-script-delta-v1",
    "rom-psg-frequency-lookup-v1",
    "rom-renderer-records-delta-v1",
    "rom-renderer-script-pointer-pool-records-v1",
    "rom-u8-indexed-u8-triplet-lookup-v1",
)

INDEX_NAME = "families.json"


def import_families(
    reverse_root: Path,
    out_dir: Path,
    specs: tuple[FamilySpec, ...],
) -> dict[str, Any]:
    """Copy every manifest-listed file of every family, verifying as it goes."""
    families: list[dict[str, Any]] = []
    for spec in specs:
        manifest_path, manifest = load_verified_manifest(reverse_root, spec)
        family_dir = manifest_path.parent
        verified = verify_family_files(family_dir, spec, manifest)
        target = out_dir / spec.family
        target.mkdir(parents=True, exist_ok=True)
        for relative in sorted(verified):
            copy_verified_file(
                family_dir / relative,
                target / relative,
                verified[relative],
            )
        receipt = {
            "family": spec.family,
            "manifest_sha256": spec.manifest_sha256,
            "manifest_path": str(manifest_path),
            "file_count": len(verified),
            "files": verified,
            "verifier": manifest_verifier(manifest),
            "scope": manifest_scope(manifest),
            "acceptance": (
                "content equivalence: every copied file's SHA-256 equals the "
                "hash the reverse side's manifest records"
            ),
        }
        write_json(target / "import.json", receipt)
        families.append(receipt)
    return {
        "schema": IMPORT_SCHEMA,
        "reverse_root": str(reverse_root),
        "reverse_commit": reverse_commit(reverse_root),
        "family_count": len(families),
        "file_count": sum(family["file_count"] for family in families),
        "not_imported_inconsistent": list(SHELF_FAMILIES_NOT_IMPORTED),
        "families": families,
    }


def verify_families(
    reverse_root: Path,
    out_dir: Path,
    specs: tuple[FamilySpec, ...],
) -> dict[str, Any]:
    """Re-check the local copies against the reverse side's signed hashes."""
    problems: list[str] = []
    checked = 0
    for spec in specs:
        manifest_path, manifest = load_verified_manifest(reverse_root, spec)
        verified = verify_family_files(manifest_path.parent, spec, manifest)
        target = out_dir / spec.family
        for relative, expected in verified.items():
            local = target / relative
            if not local.is_file():
                problems.append(f"{spec.family}: {relative} is missing locally")
                continue
            actual = sha256_file(local)
            if actual != expected:
                problems.append(
                    f"{spec.family}: {relative} sha256 mismatch "
                    f"(expected {expected}, local {actual})"
                )
            checked += 1
    return {
        "schema": IMPORT_SCHEMA,
        "checked_files": checked,
        "families": len(specs),
        "problems": problems,
        "ok": not problems,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("import", "verify"))
    parser.add_argument(
        "--reverse-root",
        type=Path,
        default=Path("/Users/altair/github/gba-naruto-reverse"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("artifacts/butano-reverse-m3-import-v1/shelf"),
    )
    args = parser.parse_args(argv)

    reverse_root = args.reverse_root.resolve()
    out_dir = args.out_dir
    if not out_dir.is_absolute():
        out_dir = Path.cwd() / out_dir
    specs = as_specs(SHELF_FAMILIES)
    try:
        if args.command == "import":
            payload = import_families(reverse_root, out_dir, specs)
            out_dir.mkdir(parents=True, exist_ok=True)
            write_json(out_dir / INDEX_NAME, payload)
            print(
                json.dumps(
                    {
                        "family_count": payload["family_count"],
                        "file_count": payload["file_count"],
                        "not_imported_inconsistent": len(
                            payload["not_imported_inconsistent"]
                        ),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return EXIT_OK
        payload = verify_families(reverse_root, out_dir, specs)
        for problem in payload["problems"]:
            print(f"PROBLEM: {problem}", file=sys.stderr)
        print(
            json.dumps(
                {
                    "families": payload["families"],
                    "checked_files": payload["checked_files"],
                    "problems": len(payload["problems"]),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return EXIT_OK if payload["ok"] else EXIT_FAMILY_FILE_MISMATCH
    except FamilyImportError as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return error.exit_code or EXIT_INPUT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
