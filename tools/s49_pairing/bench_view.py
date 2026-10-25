"""Build the judgment bench's view of the dense walk.

The bench reads two capture directories:

``capture-original``
    the canonical frames of the original's walk -- the frame at the end of
    each beat.  They are copied out of the dense recording under the *pinned
    baseline's* names, so the bench's rows keep their keys and the residual
    numbers stay comparable with the pinned baseline (the ratchet needs
    that).

``capture-remake``
    the remake's dense frames -- every beat end **and** every inner sample.
    The dense set is what makes "the same game moment" reachable: the two
    games do not reach the end of a beat at the same frame, and the remake's
    fade frames are only sampled by the inner stride (the coarse walk never
    caught them).

The canonical frames are picked by **file name**, not by index arithmetic:
the recorder writes the frame at the end of a beat as ``*-beat.png`` and the
frame before the first beat as ``*-base.png``.  An index formula would have
to know the capture stride and the settle length, and it silently picked the
wrong frames when the stride changed.

The bench's arg-min can only get better when it is given more frames, so the
residual of the new walk is bounded above by the residual of the old one.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from s49_pairing import walkspec  # noqa: E402


def write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def canonical_frames(directory: pathlib.Path) -> list[pathlib.Path]:
    """The beat-end frames of a dense recording, in beat order."""
    beats = sorted(directory.glob("step-*-beat.png"))
    bases = sorted(directory.glob("step-*-base.png"))
    if not bases:
        raise SystemExit(f"ERR no base frame in {directory}")
    if not beats:
        raise SystemExit(f"ERR no beat frames in {directory}")
    return bases + beats


def build(original_dir: pathlib.Path, remake_dir: pathlib.Path,
          work_dir: pathlib.Path, beats: int = walkspec.BEATS) -> dict:
    """Populate ``work_dir/capture-original`` and ``work_dir/capture-remake``."""
    for name in ("capture-original", "capture-remake"):
        target = work_dir / name
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)

    original_frames = canonical_frames(original_dir)
    remake_frames = sorted(remake_dir.glob("step-*.png"))
    if not remake_frames:
        raise SystemExit("ERR the dense walk is missing")

    # The original's canonical frames are the beat ends: the base plus one
    # frame per beat.  The pinned baseline has 25 of them (base + 24 beats).
    canonical = original_frames[:beats + 1]
    if len(canonical) != beats + 1:
        raise SystemExit(f"ERR the original walk has {len(canonical)} beat "
                         f"frames, {beats + 1} are needed")
    for index, frame in enumerate(canonical):
        name = ("step-00-base.png" if index == 0
                else f"step-{index:02d}-A.png")
        for suffix in (".png", ".ss9"):
            source = frame.with_suffix(suffix)
            if source.exists():
                shutil.copyfile(source,
                                work_dir / "capture-original" / (name[:-4] + suffix))

    for frame in remake_frames:
        for suffix in (".png", ".ss9"):
            source = frame.with_suffix(suffix)
            if source.exists():
                shutil.copyfile(source, work_dir / "capture-remake" / source.name)

    for name in ("capture-original", "capture-remake"):
        payload = json.dumps({
            "status": "capture-complete",
            "source": str(original_dir if name == "capture-original"
                          else remake_dir),
        }, ensure_ascii=False)
        write_text(work_dir / name / "done.json", payload + "\n")
        write_text(work_dir / name / "audit.json", payload + "\n")

    return {
        "work_dir": str(work_dir),
        "capture_original": len(canonical),
        "capture_remake": len(remake_frames),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--walk", type=pathlib.Path,
                    default=REPO / "build" / "s49-pairing" / "walk")
    ap.add_argument("--work-dir", type=pathlib.Path,
                    default=REPO / "build" / "s49-pairing" / "bench")
    ap.add_argument("--beats", type=int, default=walkspec.BEATS)
    args = ap.parse_args(argv)
    receipt = build(args.walk / "dense-original", args.walk / "dense-remake",
                    args.work_dir, args.beats)
    print(json.dumps(receipt, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
