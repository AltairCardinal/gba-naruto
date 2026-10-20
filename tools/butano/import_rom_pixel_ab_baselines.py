#!/usr/bin/env python3
"""Import the accepted pixel-A/B families as local 1:1 acceptance baselines.

The reverse work tree already holds 32 closed pixel-A/B families: for each one
the original ROM was run twice, once untouched and once with a single byte
edited, and the two frames were compared pixel by pixel.  Those families are
the closest thing this project has to a ground-truth rendering of the
original: the *baseline* frame is what the original ROM drew, and the recorded
pixel difference is the proof that the channel leading to it is editable.

Until now every one of those families sat at ``doc`` status in
``tools/measure_butano_reverse_gap.py``: mentioned in prose, never consumed.
This importer turns them into something the remake can actually be checked
against:

* the baseline frames are copied into the remake tree, so the acceptance
  baseline is local and does not depend on another work tree at build time;
* the evidence payload is copied next to them, so every claim about the
  baseline keeps its own provenance;
* an import receipt records the manifest hash, the verifier command, the
  applicability boundary, the recorded pixel expectation and the local
  anchors -- the local files that correspond to the reverse-side inputs.

``compare`` is the re-runnable acceptance entry point: it diffs a candidate
frame against an imported baseline with the same no-tolerance, per-channel
maximum rule the rest of the tree uses, and exits non-zero when the frames
differ.

Every import is hash-pinned.  The manifest SHA-256 of each family is listed
below, re-read from the reverse work tree at run time and checked; a family
whose manifest moved, vanished, lost its ``accepted`` status or whose bytes
no longer match its own manifest is a hard failure naming that family, never
a silent skip.

Usage::

    python3 tools/butano/import_rom_pixel_ab_baselines.py import \\
        --reverse-root /Users/altair/github/gba-naruto-reverse \\
        --out-dir artifacts/butano-reverse-m3-import-v1/pixel-ab

    python3 tools/butano/import_rom_pixel_ab_baselines.py verify \\
        --reverse-root /Users/altair/github/gba-naruto-reverse \\
        --out-dir artifacts/butano-reverse-m3-import-v1/pixel-ab

    python3 tools/butano/import_rom_pixel_ab_baselines.py compare \\
        --out-dir artifacts/butano-reverse-m3-import-v1/pixel-ab \\
        --family battle-effect-group1-pixel-ab-v1 \\
        --candidate butano-sequel/build/frame90.png
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

if __package__ in (None, ""):  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.butano.import_rom_reverse_families import (
    ACCEPTED_STATUS,
    DEFAULT_REVERSE_ROOT,
    EXIT_BASELINE_MISSING,
    EXIT_GATE_FAILED,
    EXIT_INPUT_ERROR,
    EXIT_OK,
    FamilyImportError,
    FamilySpec,
    as_specs,
    copy_verified_file,
    dig,
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

try:  # pragma: no cover - Pillow is a hard dependency of the compare path
    from PIL import Image, ImageChops
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment]
    ImageChops = None  # type: ignore[assignment]

IMPORT_SCHEMA = "konoha.butano-pixel-ab-baseline-import.v1"
INDEX_NAME = "baselines.json"
RUN_MANIFEST_NAME = "import-manifest.json"

#: The accepted pixel-A/B families, pinned by the SHA-256 of their manifest.
#: Each entry is the data the importer consumes: it reads that manifest, checks
#: the hash against the pin, and imports the files the manifest lists.
PIXEL_AB_FAMILIES: tuple[tuple[str, str], ...] = (
    ("battle-effect-group03-controlled-pixel-ab-v1", "cb8e62f8de2bca8e550b0cc5704965c93d1f5d0b9d8d4f5f9c7d867502308729"),
    ("battle-effect-group03-natural-pixel-ab-v1", "1d443078e52355b11b7324e82b11fda4e115c24e92301d3fd92515c2980e3c10"),
    ("battle-effect-group06-controlled-pixel-ab-v1", "45512206443c21500a670d7aea8ebd0c2f5678aeed096cddf0730786edbac30b"),
    ("battle-effect-group07-controlled-pixel-ab-v1", "25c6823fec18cdd32681a8a9a004378362eb11018850206d8440724fd98815f8"),
    ("battle-effect-group08-controlled-pixel-ab-v1", "192b608f0e3d4fb92fbe2d3fcfc8dae755253790d7c579bc24a25469bc996738"),
    ("battle-effect-group09-controlled-pixel-ab-v1", "59d743e6ee65ed6efc0e86cf0716065ba04d1a1c512fbe1d1bdf39f7a98ebaac"),
    ("battle-effect-group1-pixel-ab-v1", "9921f8060278ebe9227def7fa1917ce78bcc020e09d2e4e3b9ba59a23d272506"),
    ("battle-effect-group10-controlled-pixel-ab-v1", "384ec82bd668d7ebe330c650ed0dc93ab42d7d0b65e119973fce5d8b133d9ed1"),
    ("battle-effect-group11-pixel-ab-v1", "b955b67eb1174d1dc33e74874e12ac952b609fc34ca33c0b060e6210a3338c53"),
    ("battle-effect-group12-controlled-pixel-ab-v1", "440606b9f367e3bfff873e436fd7afa1f29a915204ec2be1de4845de676e571f"),
    ("battle-effect-group13-pixel-ab-v1", "41e7c9af6cee5e8008085c8cbf73c36ecd4a1b37316b5ad92e83f4af7c2111b5"),
    ("battle-effect-group14-pixel-ab-v1", "74261b05f61b160dcbdd181eb94db56fdb6d3457716d19258394f4b6e2da2e75"),
    ("battle-effect-group15-pixel-ab-v1", "4417d160289a72acb1d981c49063acaca9c51a498755ed95efbccdf5a36a1c6b"),
    ("battle-effect-group16-pixel-ab-v1", "393eee18bcecc2b1ddf6afa75fa325878ee528942b28c5db1ab4d5beeddb294f"),
    ("battle-effect-group17-pixel-ab-v1", "22763a552782012c368a31554ed6d90861f4a86d1035c97317838de63f22cb68"),
    ("battle-effect-group18-controlled-pixel-ab-v1", "2bf6f491a1e24d0befec303cd7ba0a8a2087946ccf25b1c0ecf704caa86256e1"),
    ("battle-effect-group18-natural-pixel-ab-v1", "b74cc6e135bbb9cd3ac60e6cfe119cc3a43e75a9f28de36d676e49099f38a4b6"),
    ("battle-effect-group2-pixel-ab-v1", "a0be99cd55c092c96f355d9a9a2efc8e08b102ec5cb864463c826f30b19462b4"),
    ("battle-effect-group4-pixel-ab-v1", "d88126122731f83b31ee06731afb33ea4b9641e3b3a33d2e639ff0358f288c34"),
    ("battle-effect-group5-pixel-ab-v1", "74c4afb1cb0d5079236d61d09adc7778d9009b6d2eb25e1f59003c7bcce672d0"),
    ("battle-encounters-story-visual-pixel-ab-v1", "6fc7148a5ec464142ac42d058751238bb0779f7e7f5fc4e7834bbd4dcc018c63"),
    ("character-battle-graphics-pixel-ab-v1", "8dc56720ded15ca9e39d7cc75b2e941969ad020289c7cc2c4ffcc7fe73052a1c"),
    ("cutscene-obj-id1-pixel-ab-v1", "c31638348f1f72a9a96e5fa13865974c83420e9afd55d096d1ff7455ee51052c"),
    ("data-table-b-message0-pointer-pixel-ab-v1", "fc0310e3f40d493ac0502d27bf2490817659999e32fa5bcade639f0699a50e9b"),
    ("map-events-e4-handler-pixel-ab-v1", "35f337be0534a1b93e9acc927eac35b981f4380bec99aed79d5abbb354912e48"),
    ("map-sprites-definition-id1-pixel-ab-v1", "0175f0ee8ec2184e1c3a15bd192e55d99fc4e5487fdc426209d7fe758d03ab06"),
    ("map41-primary-layout-pixel-ab-v1", "56dedcd21904cc65b1e3582894128a5b62fab02bbb9f1c9830b456e0d4a11d25"),
    ("menu-portrait-pixel-ab-v1", "c09b4784e18db4177cc44a089501ccea29699a666bcf969555ba331d916d91ae"),
    ("motion-effect-parameter-pixel-ab-v1", "3741e9465acc813e881493c3c91bef2101e879d6b565ecbc8e01e98b902b9abd"),
    ("residual-wram-tilemap-pixel-ab-v1", "46dba8f095d1fa2f07afbd6ac9f4405a5315f5ccc050f5fb1187502fd3088c2c"),
    ("tile-asset-descriptor2-pixel-ab-v1", "cceaa7a92507ac99fc0e9fc2abe40ba65426d4de5de03af671619510a3f1d5aa"),
    ("world-map-page0-pixel-ab-v1", "fef4ec504187bf0f3a36862bf9a067317124e02091f1317320504041da53bea7"),
)

#: Keys that carry a changed-pixel count, in preference order.
_COUNT_KEYS = (
    "changed_pixel_count",
    "differing_pixel_count",
    "different_pixel_count",
    "pixel_change_count",
    "count",
)

#: Keys that carry a changed-pixel bounding box, in preference order.
_BBOX_KEYS = (
    "bbox_inclusive",
    "screen_bbox",
    "pixel_change_bbox",
    "difference_bbox",
    "bbox",
)

#: Keys that carry a list of changed pixels, in preference order.
_PIXEL_LIST_KEYS = ("differing_pixels", "pixel_changes", "changes")

#: Local directories searched for anchors when deciding whether a family has a
#: landing point in this tree.
_ANCHOR_ROOTS = ("artifacts", "butano-sequel")

#: The reverse work tree's own top-level directories.  A path under any other
#: top directory (``build/``, ``runs/``) is relative to a family-local archive
#: rather than to the reverse work tree, and is not an input of this project.
_REVERSE_TREE_ROOTS = (
    "artifacts", "sequel", "tools", "tests", "notes", "docs", "rom",
)


# --------------------------------------------------------------------------
# family introspection
# --------------------------------------------------------------------------

def baseline_images(manifest: dict[str, Any]) -> list[str]:
    """The baseline frames of a family: every PNG whose path says ``baseline``.

    The families are not uniform -- some keep ``baseline.png`` at the root,
    others keep ``raw/baseline/frame90.png`` -- but every one of them names
    the untouched original run "baseline" and the edited run "candidate".
    """
    files = manifest.get("files") or {}
    return sorted(
        relative for relative in files
        if relative.lower().endswith(".png") and "baseline" in relative.lower()
    )


def evidence_relpath(manifest: dict[str, Any]) -> str | None:
    """The evidence payload of a family.

    Most families declare it as ``payload_file``; the ones that ship a
    ``raw.tar`` keep a single ``evidence.json`` at the family root instead.
    """
    payload = manifest.get("payload_file")
    if isinstance(payload, str) and payload:
        return payload
    candidates = sorted(
        relative for relative in (manifest.get("files") or {})
        if relative.lower().endswith(".json")
    )
    if len(candidates) == 1:
        return candidates[0]
    roots = [c for c in candidates if "/" not in c]
    return roots[0] if len(roots) == 1 else None


def _iter_dicts(payload: Any, prefix: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], dict[str, Any]]]:
    """Walk a JSON payload, yielding ``(path, dict)`` in a stable order."""
    if isinstance(payload, dict):
        yield prefix, payload
        for key in sorted(payload):
            child = payload[key]
            if isinstance(child, (dict, list)):
                yield from _iter_dicts(child, prefix + (key,))
    elif isinstance(payload, list):
        for index, child in enumerate(payload):
            if isinstance(child, (dict, list)):
                yield from _iter_dicts(child, prefix + (str(index),))


def _count_from(block: dict[str, Any]) -> int | None:
    value = first_key(block, _COUNT_KEYS)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    for key in _PIXEL_LIST_KEYS:
        listed = block.get(key)
        if isinstance(listed, list):
            return len(listed)
    return None


def _bbox_from(block: dict[str, Any]) -> list[int] | None:
    value = first_key(block, _BBOX_KEYS)
    if isinstance(value, list) and len(value) == 4 and all(
            isinstance(item, int) and not isinstance(item, bool) for item in value):
        return list(value)
    for key in _PIXEL_LIST_KEYS:
        listed = block.get(key)
        if not isinstance(listed, list) or not listed:
            continue
        if isinstance(listed[0], dict):
            nested = _bbox_from(listed[0])
            if nested is not None:
                return nested
            points = [
                (item["x"], item["y"]) for item in listed
                if isinstance(item, dict)
                and isinstance(item.get("x"), int) and isinstance(item.get("y"), int)
            ]
            if points:
                xs = [point[0] for point in points]
                ys = [point[1] for point in points]
                return [min(xs), min(ys), max(xs) + 1, max(ys) + 1]
    return None


def extract_expectation(evidence: Any) -> dict[str, Any]:
    """Pull the recorded pixel expectation out of an evidence payload.

    The payloads are not uniform, so the block is found by looking for the
    deepest dict that carries a changed-pixel count and a bounding box.  The
    path that was used is reported, so the number is always traceable to the
    payload it came from.
    """
    best: dict[str, Any] = {}
    best_score = -1
    for path, block in _iter_dicts(evidence):
        count = _count_from(block)
        bbox = _bbox_from(block)
        if count is None and bbox is None:
            continue
        score = (1 if count is not None else 0) + (1 if bbox is not None else 0)
        if score > best_score:
            best_score = score
            best = {
                "source_path": ".".join(path),
                "changed_pixel_count": count,
                "bbox": bbox,
            }
    baseline_digest = None
    candidate_digest = None
    for _path, block in _iter_dicts(evidence):
        if baseline_digest is None:
            value = first_key(block, ("baseline_rgb_sha256", "baseline_rgb"))
            if isinstance(value, str):
                baseline_digest = value
        if candidate_digest is None:
            value = first_key(block, ("candidate_rgb_sha256", "candidate_rgb"))
            if isinstance(value, str):
                candidate_digest = value
    best["baseline_rgb_sha256"] = baseline_digest
    best["candidate_rgb_sha256"] = candidate_digest
    # The reverse side records an inclusive bounding box; the comparison
    # entry point below reports PIL's exclusive box.  Both conventions are
    # stated so the two numbers are not read as a disagreement.
    best["bbox_convention"] = "inclusive"
    return best


# --------------------------------------------------------------------------
# local anchor search
# --------------------------------------------------------------------------

def _collect_reverse_paths(payload: Any) -> list[str]:
    """Every repo-relative path mentioned anywhere in a payload.

    Only path-shaped strings count: a prose sentence that happens to contain
    a slash is not an input, and treating it as one would report a family as
    missing an input it never had.
    """
    found: set[str] = set()

    def looks_like_path(value: str) -> bool:
        if value.startswith(("/", "http")) or " " in value:
            return False
        segments = value.split("/")
        if len(segments) < 2 or any(not segment for segment in segments):
            return False
        if segments[0] not in _REVERSE_TREE_ROOTS:
            return False
        return all(
            segment.replace(".", "").replace("-", "").replace("_", "").isalnum()
            for segment in segments
        )

    def walk(node: Any) -> None:
        if isinstance(node, str):
            if "/" in node and looks_like_path(node):
                found.add(node)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return sorted(found)


#: File names that carry no identity: thousands of artifacts in this tree are
#: called ``manifest.json``.  Matching on one of them would credit a family
#: with an anchor it does not have.
_GENERIC_STEMS = frozenset({
    "manifest", "index", "sentinel", "audit", "guard-summary",
    "build-manifest", "spec", "profile", "summary", "report", "config",
    "state", "final", "input", "output", "result", "results", "data",
})


def _local_file_index(root: Path) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Index the local tree by relative path and by file stem.

    Both are needed: a reverse-side input that names a local file by path is
    anchored by that path, and one that names a checkpoint by file name is
    anchored by the stem.
    """
    by_path: dict[str, list[str]] = {}
    by_stem: dict[str, list[str]] = {}
    for base in _ANCHOR_ROOTS:
        base_dir = Path(root) / base
        if not base_dir.is_dir():
            continue
        for path in base_dir.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(Path(root)).as_posix()
            by_path.setdefault(relative, []).append(relative)
            by_stem.setdefault(path.stem, []).append(relative)
    return by_path, by_stem


def find_local_anchors(
    evidence: Any,
    by_path: dict[str, list[str]],
    by_stem: dict[str, list[str]],
) -> tuple[list[str], list[str]]:
    """Match the reverse-side inputs of a family against local files.

    Returns ``(anchors, unavailable)``: the local files that correspond to a
    reverse-side input, and the reverse-side inputs that have no local
    counterpart.  The match is exact -- same relative path, or same file name
    -- so a family is never credited with an anchor it does not have, and the
    second list is the honest "this has no landing point in this tree" signal.
    """
    anchors: set[str] = set()
    unavailable: set[str] = set()
    for reverse_path in _collect_reverse_paths(evidence):
        direct = by_path.get(reverse_path)
        if direct:
            anchors.update(direct)
            continue
        stem = Path(reverse_path).stem
        matches = by_stem.get(stem) if (
            len(stem) >= 8 and stem.lower() not in _GENERIC_STEMS) else None
        if matches:
            anchors.update(matches)
            continue
        unavailable.add(reverse_path)
    return sorted(anchors), sorted(unavailable)


# --------------------------------------------------------------------------
# import
# --------------------------------------------------------------------------

def import_family(
    reverse_root: Path,
    out_dir: Path,
    spec: FamilySpec,
    anchor_index: tuple[dict[str, list[str]], dict[str, list[str]]] | None = None,
) -> dict[str, Any]:
    """Import one family and return its receipt."""
    _manifest_path, manifest = load_verified_manifest(reverse_root, spec)
    family_dir = Path(reverse_root) / "artifacts" / spec.family
    verified = verify_family_files(family_dir, spec, manifest)

    baselines = baseline_images(manifest)
    if not baselines:
        raise FamilyImportError(
            f"{spec.family}: no baseline frame found among "
            f"{sorted(verified)}",
            family=spec.family, exit_code=EXIT_BASELINE_MISSING)

    written: list[dict[str, Any]] = []
    imported_baselines: list[dict[str, Any]] = []
    for relative in baselines:
        destination = Path(out_dir) / spec.family / "baseline" / Path(relative).name
        digest = copy_verified_file(
            family_dir / relative, destination, verified[relative])
        written.append({
            "path": destination.relative_to(Path(out_dir)).as_posix(),
            "sha256": digest,
            "reverse_path": f"artifacts/{spec.family}/{relative}",
        })
        imported_baselines.append({
            "path": destination.relative_to(Path(out_dir)).as_posix(),
            "sha256": digest,
            "reverse_path": f"artifacts/{spec.family}/{relative}",
            "size": _png_size(destination),
        })

    evidence_rel = evidence_relpath(manifest)
    evidence: Any = None
    evidence_entry: dict[str, Any] | None = None
    if evidence_rel is not None:
        evidence_digest = copy_verified_file(
            family_dir / evidence_rel,
            Path(out_dir) / spec.family / "evidence.json",
            verified[evidence_rel])
        written.append({
            "path": (Path(spec.family) / "evidence.json").as_posix(),
            "sha256": evidence_digest,
            "reverse_path": f"artifacts/{spec.family}/{evidence_rel}",
        })
        evidence = read_json(Path(out_dir) / spec.family / "evidence.json")
        evidence_entry = {
            "path": (Path(spec.family) / "evidence.json").as_posix(),
            "sha256": evidence_digest,
            "reverse_path": f"artifacts/{spec.family}/{evidence_rel}",
        }

    anchors: list[str] = []
    unavailable: list[str] = []
    if anchor_index is not None and evidence is not None:
        anchors, unavailable = find_local_anchors(evidence, *anchor_index)

    receipt: dict[str, Any] = {
        "family": spec.family,
        "manifest": spec.manifest_relpath,
        "manifest_sha256": spec.manifest_sha256,
        "artifact_status": manifest.get("artifact_status"),
        "artifact_schema": manifest.get("artifact_schema") or manifest.get("schema"),
        "base_rom_sha256": manifest.get("base_rom_sha256"),
        "verifier": manifest_verifier(manifest),
        "scope": manifest_scope(manifest),
        "baseline_images": imported_baselines,
        "evidence": evidence_entry,
        "expectation": extract_expectation(evidence) if evidence is not None else {},
        "local_anchors": anchors,
        "unavailable_local_inputs": unavailable,
        "applicability": (
            "local-anchor-found" if anchors
            else "no-local-anchor-in-this-tree"
        ),
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


def _png_size(path: Path) -> list[int] | None:
    if Image is None:
        return None
    try:
        with Image.open(path) as image:
            return [image.size[0], image.size[1]]
    except OSError:  # pragma: no cover - defensive
        return None


def import_families(
    reverse_root: Path,
    out_dir: Path,
    specs: Sequence[FamilySpec],
    root: Path | None = None,
) -> dict[str, Any]:
    """Import every pinned family and write the baseline index."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prune_previous_output(out_dir, RUN_MANIFEST_NAME)

    receipts: list[dict[str, Any]] = []
    written_files: list[dict[str, Any]] = []
    anchor_index = _local_file_index(Path(root)) if root is not None else None
    for spec in specs:
        result = import_family(reverse_root, out_dir, spec, anchor_index)
        receipts.append(result["receipt"])
        written_files.extend(result["written"])

    index = {
        "schema": IMPORT_SCHEMA,
        "source": {
            "reverse_commit": reverse_commit(reverse_root),
            "rom_sha256": _common_rom_sha256(receipts),
            "accepted_status_required": ACCEPTED_STATUS,
        },
        "family_count": len(receipts),
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
        "written_files": sorted(
            written_files, key=lambda entry: entry["path"]),
    }
    write_json(out_dir / RUN_MANIFEST_NAME, run_manifest)
    return index


def _common_rom_sha256(receipts: Sequence[dict[str, Any]]) -> str | None:
    values = {receipt.get("base_rom_sha256") for receipt in receipts}
    values.discard(None)
    if len(values) == 1:
        return next(iter(values))
    return None


# --------------------------------------------------------------------------
# verify / compare
# --------------------------------------------------------------------------

def verify_import(
    reverse_root: Path,
    out_dir: Path,
    specs: Sequence[FamilySpec],
) -> dict[str, Any]:
    """Re-check an imported tree against the reverse work tree."""
    out_dir = Path(out_dir)
    index_path = out_dir / INDEX_NAME
    if not index_path.is_file():
        raise FamilyImportError(
            f"no imported baseline index at {index_path}",
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
        for image in receipt.get("baseline_images") or []:
            local = out_dir / image["path"]
            if not local.is_file():
                problems.append(f"{spec.family}: imported baseline {image['path']} is missing")
            elif sha256_file(local) != image["sha256"]:
                problems.append(
                    f"{spec.family}: imported baseline {image['path']} does not match its hash")
    return {
        "schema": "konoha.butano-pixel-ab-baseline-verify.v1",
        "checked_families": len(specs),
        "problems": problems,
    }


def difference_mask(left: Any, right: Any) -> Any:
    """Binary mask of differing pixels, with no tolerance and no masking.

    The per-channel maximum is used rather than a luminance conversion: a
    luminance round-trip silently drops a one-step difference in a single
    channel, which would undercount instead of failing closed.
    """
    difference = ImageChops.difference(left, right)
    red, green, blue = difference.split()
    combined = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return combined.point(lambda value: 255 if value else 0, mode="L")


def compare_frames(baseline_path: Path, candidate_path: Path) -> dict[str, Any]:
    """Compare a candidate frame against an imported baseline frame."""
    if Image is None:  # pragma: no cover - defensive
        raise FamilyImportError(
            "Pillow is required for the frame comparison", exit_code=EXIT_INPUT_ERROR)
    baseline_path, candidate_path = Path(baseline_path), Path(candidate_path)
    for path in (baseline_path, candidate_path):
        if not path.is_file():
            raise FamilyImportError(
                f"missing frame: {path}", exit_code=EXIT_INPUT_ERROR)
    with Image.open(baseline_path) as baseline_image, \
            Image.open(candidate_path) as candidate_image:
        baseline = baseline_image.convert("RGB")
        candidate = candidate_image.convert("RGB")
        if baseline.size != candidate.size:
            raise FamilyImportError(
                f"frame size mismatch: baseline {baseline.size}, "
                f"candidate {candidate.size}", exit_code=EXIT_INPUT_ERROR)
        mask = difference_mask(baseline, candidate)
        bbox = mask.getbbox()
        different = mask.histogram()[255]
    return {
        "schema": "konoha.butano-pixel-ab-baseline-comparison.v1",
        "comparison": "no-tolerance-per-channel-maximum",
        "baseline": baseline_path.name,
        "candidate": candidate_path.name,
        "size": [baseline.size[0], baseline.size[1]],
        "different_pixels": different,
        "difference_bbox": list(bbox) if bbox is not None else None,
        "difference_bbox_convention": "exclusive",
        "identical": different == 0,
    }


def compare_against_import(
    out_dir: Path,
    family: str,
    candidate: Path,
    baseline_relpath: str | None = None,
) -> dict[str, Any]:
    """Compare a candidate frame against a family's imported baseline."""
    out_dir = Path(out_dir)
    index_path = out_dir / INDEX_NAME
    if not index_path.is_file():
        raise FamilyImportError(
            f"no imported baseline index at {index_path}", exit_code=EXIT_INPUT_ERROR)
    index = read_json(index_path)
    entry = next(
        (item for item in index.get("families") or [] if item.get("family") == family),
        None)
    if entry is None:
        raise FamilyImportError(
            f"{family}: not present in the imported baseline index",
            family=family, exit_code=EXIT_INPUT_ERROR)
    images = entry.get("baseline_images") or []
    if not images:
        raise FamilyImportError(
            f"{family}: imported without a baseline frame",
            family=family, exit_code=EXIT_BASELINE_MISSING)
    if baseline_relpath is None:
        chosen = images[0]
    else:
        chosen = next(
            (item for item in images if item["path"] == baseline_relpath
             or item.get("reverse_path") == baseline_relpath),
            None)
        if chosen is None:
            raise FamilyImportError(
                f"{family}: no baseline frame named {baseline_relpath!r}",
                family=family, exit_code=EXIT_BASELINE_MISSING)
    result = compare_frames(out_dir / chosen["path"], Path(candidate))
    result["family"] = family
    result["baseline_path"] = chosen["path"]
    return result


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
        "command", nargs="?", default="import",
        choices=("import", "verify", "compare"))
    parser.add_argument("--reverse-root", default=None,
                        help="reverse work tree to import from (read only)")
    parser.add_argument("--out-dir", default=None,
                        help="directory the imported baselines are written to")
    parser.add_argument("--root", default=None,
                        help="remake work tree root, used for the local anchor search")
    parser.add_argument("--family", default=None,
                        help="family to compare against")
    parser.add_argument("--candidate", default=None,
                        help="candidate frame to compare against the baseline")
    parser.add_argument("--baseline", default=None,
                        help="which baseline frame of the family to use")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[2]
    out_dir = Path(args.out_dir) if args.out_dir else (
        root / "artifacts" / "butano-reverse-m3-import-v1" / "pixel-ab")
    specs = as_specs(PIXEL_AB_FAMILIES)
    try:
        if args.command == "import":
            reverse_root = _reverse_root(args.reverse_root)
            index = import_families(reverse_root, out_dir, specs, root=root)
            print(json.dumps({
                "command": "import",
                "out_dir": out_dir.as_posix(),
                "family_count": index["family_count"],
            }, ensure_ascii=False, indent=2))
            return EXIT_OK
        if args.command == "verify":
            reverse_root = _reverse_root(args.reverse_root)
            report = verify_import(reverse_root, out_dir, specs)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return EXIT_OK if not report["problems"] else EXIT_GATE_FAILED
        if not args.family or not args.candidate:
            print("compare: --family and --candidate are required",
                  file=sys.stderr)
            return EXIT_INPUT_ERROR
        result = compare_against_import(
            out_dir, args.family, Path(args.candidate), args.baseline)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return EXIT_OK if result["identical"] else EXIT_GATE_FAILED
    except FamilyImportError as error:
        print(f"import_rom_pixel_ab_baselines: {error}", file=sys.stderr)
        return error.exit_code
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"import_rom_pixel_ab_baselines: {error}", file=sys.stderr)
        return EXIT_INPUT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
