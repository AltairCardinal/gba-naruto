"""The provable pixel floor of the residual, **for the current ROM**.

    python tools/s49_z3_bound/z3bound.py --walk build/s49-z3-bound/walk \
        --out build/s49-z3-bound/bound.json

The algorithm is the pairing stream's (``tools/s49_pairing/pair.py``), reused
**read-only**:

    For every one of the 25 canonical beats, take **every** frame of that
    beat on the original side and **every** frame of the remake's recording,
    compute the battlefield residual of each pair, and keep the smallest.
    The sum over the 25 beats is the floor.

Why the sum is a lower bound
----------------------------
The judgment bench's residual of a beat is the residual of **one** original
frame against **one** remake frame.  Any walk changes *which* pair is used,
never how the residual of a pair is measured.  So for beat ``b``::

    residual(b) >= min { residual(o, r) : o in beat b, r in the remake recording }

for every possible walk, and the ``min`` is taken over a **superset** of the
pairs a walk can realise (the same remake frame may serve several beats).
A relaxation can only lower the optimum, therefore::

    total residual >= sum over the 25 beats of that minimum.

The floor is therefore a number that **no** pairing of these two recordings
can beat -- the residual of the battle-14 walk cannot be driven to zero.

This tool adds three things on top of the inherited algorithm:

* it names the **arg-min** pair of every beat, so the floor can be audited
  frame by frame;
* it cross-checks the audited implementation against
  ``pair.beat_floor`` and refuses to publish a number that disagrees;
* it writes the **sha256 of both ROMs** and of every recorded frame, so the
  number cannot be read without its measurement context.

The receipt carries **no wall clock time**, so two runs over the same
recording are byte identical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from s49_fidelity_report.pixels import diff_mask  # noqa: E402
from s49_pairing import pair as pair_module  # noqa: E402
from s49_pairing import pairing_report  # noqa: E402

FIELD_AREA = pair_module.FIELD_AREA  # (0, 0, 240, 128) -- the battlefield

PROOF = (
    "For every canonical beat b the bench's residual is the residual of one "
    "original frame against one remake frame.  min over all (frame of b) x "
    "(frame of the remake recording) of the battlefield residual is therefore "
    "<= the residual of every pairing of that beat, and the minimum is taken "
    "over a superset of the pairs a walk can realise (the same remake frame "
    "may serve several beats), so it is <= the residual of every walk.  "
    "Summing over the 25 beats gives a lower bound that no walk built on "
    "these two recordings can go below."
)


def write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frames_digest(directory: pathlib.Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(directory.glob("step-*.png")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def read_receipt(directory: pathlib.Path) -> dict:
    path = directory / "receipt.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def audited_floor(original_dir: pathlib.Path, remake_dir: pathlib.Path,
                  beats: int, per_beat: int) -> dict:
    """The inherited algorithm, with the arg-min pair of every beat kept.

    The loops are the ones of ``pair.beat_floor`` (same frames, same
    de-duplication of the remake frames, same ``diff_mask`` and the same
    field area); only the bookkeeping differs.
    """
    from PIL import Image

    original_files = sorted(original_dir.glob("step-*.png"))
    remake_files = sorted(remake_dir.glob("step-*.png"))
    if not original_files or not remake_files:
        raise SystemExit("ERR the dense walk is missing")

    remake_unique: dict[bytes, tuple[str, object]] = {}
    for path in remake_files:
        with Image.open(path) as handle:
            image = handle.convert("RGB")
        digest = image.crop(FIELD_AREA).tobytes()
        remake_unique.setdefault(digest, (path.name, image))

    original_images = {}
    for path in original_files:
        with Image.open(path) as handle:
            original_images[path.name] = handle.convert("RGB")

    canonical = [original_files[0]] + [original_files[per_beat * k]
                                       for k in range(1, beats + 1)]
    rows = []
    total_floor = 0
    total_canonical = 0
    for index, frame in enumerate(canonical):
        if index == 0:
            members = original_files[0:1]
        else:
            members = original_files[per_beat * (index - 1) + 1:
                                     per_beat * index + 1]
        best = None
        best_member = None
        best_remake = None
        canonical_px = None
        canonical_remake = None
        for member in members:
            image = original_images[member.name]
            for remake_name, other in remake_unique.values():
                count, _ = diff_mask(image, other, FIELD_AREA)
                if best is None or count < best:
                    best = count
                    best_member = member.name
                    best_remake = remake_name
            if member.name == frame.name:
                for remake_name, other in remake_unique.values():
                    count, _ = diff_mask(image, other, FIELD_AREA)
                    if canonical_px is None or count < canonical_px:
                        canonical_px = count
                        canonical_remake = remake_name
        total_floor += best
        total_canonical += canonical_px
        rows.append({"beat": index, "canonical": frame.name,
                     "canonical_px": canonical_px,
                     "canonical_remake": canonical_remake,
                     "floor_px": best, "floor_member": best_member,
                     "floor_remake": best_remake})
    return {"remake_frames": len(remake_files),
            "remake_distinct": len(remake_unique),
            "per_beat": per_beat,
            "canonical_sum": total_canonical,
            "floor_sum": total_floor,
            "rows": rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--walk", type=pathlib.Path,
                        default=REPO / "build" / "s49-z3-bound" / "walk")
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "s49-z3-bound" / "bound.json")
    parser.add_argument("--beats", type=int, default=24)
    parser.add_argument("--label", default="")
    parser.add_argument("--walk-id", default=None,
                        help="stable identifier written into the receipt instead "
                             "of the walk path, so that two independent runs of "
                             "the same recording compare byte for byte")
    parser.add_argument("--no-cross-check", action="store_true",
                        help="skip the run of the inherited pair.beat_floor")
    args = parser.parse_args(argv)

    original_dir = args.walk / "dense-original"
    remake_dir = args.walk / "dense-remake"
    for required in (original_dir, remake_dir):
        if not required.is_dir():
            raise SystemExit(f"ERR missing the dense walk: {required}")

    per_beat = pairing_report.beat_stride(original_dir)
    floor = audited_floor(original_dir, remake_dir, args.beats, per_beat)

    cross_check = None
    if not args.no_cross_check:
        inherited = pair_module.beat_floor(original_dir, remake_dir,
                                           args.beats, per_beat)
        cross_check = {
            "inherited_floor_sum": inherited["floor_sum"],
            "inherited_canonical_sum": inherited["canonical_sum"],
            "agrees": (inherited["floor_sum"] == floor["floor_sum"]
                       and inherited["canonical_sum"] == floor["canonical_sum"]),
        }
        if not cross_check["agrees"]:
            raise SystemExit(
                f"ERR the audited floor {floor['floor_sum']} disagrees with "
                f"pair.beat_floor {inherited['floor_sum']}")

    original_receipt = read_receipt(original_dir)
    remake_receipt = read_receipt(remake_dir)
    document = {
        "schema": "konoha.s49-z3.pixel-floor/1",
        "label": args.label,
        "walk": args.walk_id if args.walk_id else str(args.walk),
        "roms": {
            "original": {
                # The **name**, not the path: the path depends on where the
                # recording lives, the sha256 is the measurement's identity.
                # The full path is in the walk's own receipt.json.
                "file": pathlib.Path(
                    original_receipt.get("rom", "")).name,
                "sha256": original_receipt.get("rom_sha256"),
            },
            "remake": {
                "file": pathlib.Path(
                    remake_receipt.get("rom", "")).name,
                "sha256": remake_receipt.get("rom_sha256"),
            },
        },
        "frames": {
            "original": {"count": len(list(original_dir.glob("step-*.png"))),
                         "sha256": frames_digest(original_dir)},
            "remake": {"count": len(list(remake_dir.glob("step-*.png"))),
                       "sha256": frames_digest(remake_dir)},
        },
        "field_area": list(FIELD_AREA),
        "proof": PROOF,
        "floor_sum": floor["floor_sum"],
        "canonical_sum": floor["canonical_sum"],
        "remake_distinct": floor["remake_distinct"],
        "per_beat": floor["per_beat"],
        "beats": args.beats,
        "cross_check": cross_check,
        "rows": floor["rows"],
    }
    write_text(args.out, json.dumps(document, ensure_ascii=False, indent=1) + "\n")

    print(f"walk            : {args.walk}")
    print(f"original ROM    : {document['roms']['original']['sha256']}")
    print(f"remake ROM      : {document['roms']['remake']['sha256']}")
    print(f"remake frames   : {floor['remake_frames']} "
          f"({floor['remake_distinct']} distinct in the field area)")
    print(f"floor sum       : {floor['floor_sum']}")
    print(f"canonical sum   : {floor['canonical_sum']}")
    if cross_check:
        print(f"cross check     : pair.beat_floor floor_sum="
              f"{cross_check['inherited_floor_sum']} agrees={cross_check['agrees']}")
    print(f"wrote           : {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
