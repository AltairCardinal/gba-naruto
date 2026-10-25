#!/usr/bin/env python3
"""Shared plumbing for the S49 logic-state checks.

The five rule measurers of the remake tree
(``D:\\Shell\\Github\\gba-naruto-butano\\tools\\butano\\measure_s49_rule_*.py``)
were written on macOS and read their evidence out of
``artifacts/s49-fidelity-20261019-v1/``.  The PNG frames in that artifact were
removed by the 2026-10-19 cleanup; only the JSON receipts survived.  The
receipts keep one thing that matters: the ``image_sha256`` of every recorded
frame and the exact recording recipe.

This module gives the checks in this directory a single place to point at

* the **remake tree** (read-only reference: the measurers, the ROM, the
  content banks and the visual catalog),
* the **local evidence root** (``build/s49-logic``), where this stream
  re-records the original and the remake with the headless mGBA probe, and
* the **receipt directory**, where every check drops a JSON receipt.

Two rules apply to every check written here:

1. A check never trusts a prose note.  It measures, and the measurement is
   written to a receipt.
2. A check that cannot be decided on this machine says so
   (``无法判定``) and names the missing input.  It never guesses.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: The master repository (this file lives in ``tools/s49_logic_checks``).
MASTER_ROOT = Path(__file__).resolve().parents[2]

#: The remake tree.  Read-only for this stream.
REMAKE_ROOT = Path(
    os.environ.get("S49_REMAKE_ROOT", r"D:\Shell\Github\gba-naruto-butano")
).resolve()

#: Where this stream records and reads its local evidence.
EVIDENCE_ROOT = Path(
    os.environ.get(
        "S49_EVIDENCE_ROOT", str(MASTER_ROOT / "build" / "s49-logic")
    )
).resolve()

#: The receipts every check writes.
RECEIPTS = EVIDENCE_ROOT / "receipts"

#: The region table the remake tree's measurers use.
REGION_TABLE = REMAKE_ROOT / "tools" / "butano" / "s49_regions.json"

#: The original ROM under study.  Pinned everywhere in the project.
ORIGINAL_ROM = REMAKE_ROOT / "rom" / "base.gba"
ORIGINAL_ROM_SHA256 = (
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
)

#: The battle 14 entry savestate both sides start from.
BATTLE14_STATE = (
    REMAKE_ROOT / "artifacts" / "runtime-checkpoints"
    / "scenario-49-battle-14-entry.ss9"
)
BATTLE14_STATE_SHA256 = (
    "a3628723ac595f41b87d329f49d5422a7b9b397a8491379abb8c9620568a0aa1"
)

#: The local recordings this stream produces.
ORIGINAL_WALK = EVIDENCE_ROOT / "original-walk"
REMAKE_WALK = EVIDENCE_ROOT / "remake-walk"
IDLE_SWEEP = EVIDENCE_ROOT / "original-idle-sweep"
ROSTER_POOL = EVIDENCE_ROOT / "roster-pool"
FIELD_FRAME = EVIDENCE_ROOT / "field-frame"
LONG_WALK = EVIDENCE_ROOT / "original-walk-long"
STEP23_FRAMES = EVIDENCE_ROOT / "field-frame-step23"
PALETTE_PROBE = EVIDENCE_ROOT / "palette-probe"

#: The macOS artifacts this stream compares against (read-only).
MACOS_ROOT = (
    REMAKE_ROOT / "artifacts" / "s49-fidelity-20261019-v1"
)
MACOS_ORIGINAL_WALK = MACOS_ROOT / "walk-original-a24"
MACOS_REMAKE_WALK = MACOS_ROOT / "walk-remake-dd-a30-banner2"
MACOS_IDLE_SWEEP = MACOS_ROOT / "original-idle-sweep"
MACOS_FIELD_FRAME = REMAKE_ROOT / "artifacts" / "s49-original-field-frame-v1"
MACOS_ROSTER = REMAKE_ROOT / "artifacts" / "s49-original-battle14-roster-v1"
MACOS_PAIR_RECEIPTS = MACOS_ROOT / "region-diff-banner2"
MACOS_DIMMED_PALETTE = (
    REMAKE_ROOT / "artifacts" / "s49-original-gpu-20261020-v2"
    / "dimmed-palette-receipt.json"
)

#: The three verdicts a check may reach.
PASS = "通过"
FAIL = "未通过"
UNDECIDED = "无法判定"

#: Exit codes for :func:`main` style scripts.
EXIT_OK = 0
EXIT_FAIL = 1
EXIT_INPUT_ERROR = 2
EXIT_UNDECIDED = 3


class CheckInputError(RuntimeError):
    """An input is missing or unusable; the check cannot even start."""


@dataclass
class Item:
    """One judged line of a check."""

    name: str
    status: str
    basis: str
    original: Any = None
    remake: Any = None
    delta: Any = None
    missing: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "status": self.status,
            "basis": self.basis,
            "original": self.original,
            "remake": self.remake,
            "delta": self.delta,
        }
        if self.missing:
            payload["missing"] = self.missing
        return payload


@dataclass
class Check:
    """A named check with its judged lines."""

    name: str
    title: str
    source: str
    items: list[Item] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add(
        self,
        name: str,
        status: str,
        basis: str,
        original: Any = None,
        remake: Any = None,
        delta: Any = None,
        missing: str | None = None,
    ) -> None:
        self.items.append(
            Item(name, status, basis, original, remake, delta, missing)
        )

    def verdict(self) -> str:
        if any(item.status == FAIL for item in self.items):
            return FAIL
        if any(item.status == UNDECIDED for item in self.items):
            return UNDECIDED
        return PASS

    def exit_code(self) -> int:
        verdict = self.verdict()
        if verdict == FAIL:
            return EXIT_FAIL
        if verdict == UNDECIDED:
            return EXIT_UNDECIDED
        return EXIT_OK

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "konoha.s49-logic-check.v1",
            "name": self.name,
            "title": self.title,
            "source": self.source,
            "verdict": self.verdict(),
            "items": [item.to_dict() for item in self.items],
            "notes": list(self.notes),
        }

    def write(self, directory: Path = RECEIPTS) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.name}.json"
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return path

    def render(self) -> str:
        lines = [f"[{self.verdict()}] {self.name} -- {self.title}"]
        for item in self.items:
            mark = {PASS: "绿", FAIL: "红", UNDECIDED: "灰"}.get(item.status, "?")
            lines.append(f"  {mark} {item.name}")
            lines.append(f"      依据: {item.basis}")
            if item.original is not None or item.remake is not None:
                lines.append(
                    f"      原版: {item.original}   重制: {item.remake}"
                    f"   差异: {item.delta}"
                )
            if item.missing:
                lines.append(f"      缺什么: {item.missing}")
        return "\n".join(lines)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pixel_sha256(path: Path) -> str:
    """SHA-256 over the *decoded RGB pixels* of a PNG.

    The macOS recordings and the local recordings use different PNG encoders,
    so the file bytes differ even when the picture is identical.  The picture
    is what the rule is about, so the checks pin the pixels.
    """

    from PIL import Image

    image = Image.open(Path(path)).convert("RGB")
    return sha256_bytes(image.tobytes())


def load_image(path: Path):
    from PIL import Image

    path = Path(path)
    if not path.is_file():
        raise CheckInputError(f"missing evidence frame: {path}")
    image = Image.open(path).convert("RGB")
    if image.size != (240, 160):
        raise CheckInputError(
            f"{path} is {image.size}, not a 240x160 GBA frame"
        )
    return image


def difference_pixels(left, right) -> int:
    """Count the pixels that differ, ignoring the magnitude of the change."""

    from PIL import ImageChops

    difference = ImageChops.difference(left, right)
    bands = difference.split()
    peak = ImageChops.lighter(
        ImageChops.lighter(bands[0], bands[1]),
        bands[2],
    )
    return sum(
        count for value, count in enumerate(peak.histogram()) if value
    )


def region_table() -> dict[str, list[int]]:
    if not REGION_TABLE.is_file():
        raise CheckInputError(f"missing the region table: {REGION_TABLE}")
    payload = json.loads(REGION_TABLE.read_text(encoding="utf-8"))
    return payload.get("regions", {})


def region(name: str) -> tuple[int, int, int, int]:
    regions = region_table()
    box = regions.get(name)
    if not box:
        raise CheckInputError(f"{REGION_TABLE} has no {name} region")
    return tuple(int(value) for value in box)  # type: ignore[return-value]


def read_json(path: Path) -> Any:
    path = Path(path)
    if not path.is_file():
        raise CheckInputError(f"missing input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def macos_steps(walk: Path = MACOS_ORIGINAL_WALK) -> dict[str, dict[str, Any]]:
    """The macOS recording receipt: per step image and savestate hashes."""

    payload = read_json(walk / "steps.json")
    return {step["image"]: step for step in payload.get("steps", [])}


def walk_frames(directory: Path, pattern: str = "step-*.png") -> list[Path]:
    """The recorded frames of one walk, in recording order."""

    frames = sorted(Path(directory).glob(pattern))
    if not frames:
        raise CheckInputError(f"no frames in {directory} ({pattern})")
    return frames


#: The battlefield area.  The bottom 32 rows are the HUD, not the map.
FIELD_AREA = (0, 0, 240, 128)

#: The status bar band.
STATUS_BAR = (0, 144, 240, 160)

#: The blue channel a colour needs to count as part of the cyan move range
#: overlay.
CYAN_MIN_BLUE = 150


def overlay_statistics(grid, plain) -> dict[str, Any]:
    """Measure the overlay that turns ``plain`` into ``grid``.

    This is the original measurer's algorithm
    (``measure_s49_rule_move_grid.py``) with the local recordings: the
    battlefield area, the cyan filter, and the "one base colour, several
    overlay colours" count that decides whether the overlay is a dither mask
    or one flat tint.
    """

    grid_px = grid.load()
    plain_px = plain.load()
    x0, y0, x1, y1 = FIELD_AREA

    pairs: dict[tuple[tuple[int, int, int], tuple[int, int, int]], int] = {}
    for y in range(y0, y1):
        for x in range(x0, x1):
            base = plain_px[x, y]
            tinted = grid_px[x, y]
            if base == tinted:
                continue
            pairs[(base, tinted)] = pairs.get((base, tinted), 0) + 1

    if not pairs:
        return {
            "changed_pixels": 0,
            "distinct_base_to_overlay_pairs": 0,
            "distinct_overlay_colours": 0,
            "cyan_overlay_colours": 0,
            "cyan_pairs": 0,
            "bases_with_several_cyan_overlays": 0,
            "cyan_pixels": 0,
        }

    overlays = {tinted for (_base, tinted) in pairs}
    cyans = {colour for colour in overlays if colour[2] >= CYAN_MIN_BLUE}
    cyan_pairs = {
        (base, overlay): count
        for (base, overlay), count in pairs.items()
        if overlay in cyans
    }
    bases_with_several_cyan_overlays = {
        base
        for (base, _overlay) in cyan_pairs
        if len(
            {
                other
                for (other_base, other) in cyan_pairs
                if other_base == base
            }
        )
        > 1
    }
    return {
        "changed_pixels": sum(pairs.values()),
        "distinct_base_to_overlay_pairs": len(pairs),
        "distinct_overlay_colours": len(overlays),
        "cyan_overlay_colours": len(cyans),
        "cyan_pairs": len(cyan_pairs),
        "bases_with_several_cyan_overlays": len(
            bases_with_several_cyan_overlays
        ),
        "cyan_pixels": sum(cyan_pairs.values()),
    }


def overlay_cells(grid, plain, cell: int = 8) -> list[tuple[int, int]]:
    """The cells the grid frame paints cyan that the plain frame does not.

    This is the *locator* for the move range screen: the original paints the
    reachable cells with a cyan overlay, so the screen with the most such
    cells is the move range screen, whichever step it happens to be.
    """

    grid_px = grid.load()
    plain_px = plain.load()
    x0, y0, x1, y1 = FIELD_AREA
    cells: list[tuple[int, int]] = []
    for top in range(y0, y1 - cell + 1, cell):
        for left in range(x0, x1 - cell + 1, cell):
            grid_cyan = 0
            plain_cyan = 0
            for y in range(top, top + cell):
                for x in range(left, left + cell):
                    colour = grid_px[x, y]
                    if colour[2] >= CYAN_MIN_BLUE and colour[1] >= 120:
                        grid_cyan += 1
                    colour = plain_px[x, y]
                    if colour[2] >= CYAN_MIN_BLUE and colour[1] >= 120:
                        plain_cyan += 1
            if grid_cyan >= (cell * cell) // 2 and plain_cyan < (cell * cell) // 2:
                cells.append((left, top))
    return cells


def largest_connected_region(cells: list[tuple[int, int]]) -> int:
    """The size of the largest 4-connected region of cells.

    The move range overlay is a **field**: the reachable cells form one
    connected block.  Cyan text on a menu screen is scattered, so the
    connected region separates the move range screen from a screen change.
    """

    if not cells:
        return 0
    remaining = set(cells)
    best = 0
    while remaining:
        seed = remaining.pop()
        stack = [seed]
        size = 1
        while stack:
            left, top = stack.pop()
            for neighbour in (
                (left - 8, top), (left + 8, top), (left, top - 8),
                (left, top + 8),
            ):
                if neighbour in remaining:
                    remaining.discard(neighbour)
                    stack.append(neighbour)
                    size += 1
        best = max(best, size)
    return best


#: The colour of the original's dialogue panel.  A screen that carries it is
#: a dialogue or menu screen, never the move range screen.
DIALOGUE_PANEL = (231, 247, 214)


def find_overlay_pair(
    frames: list[Path]
) -> tuple[int, int, dict[str, Any]] | None:
    """Locate the move range frame pair inside one walk.

    Returns ``(grid_index, plain_index, statistics)`` or ``None``.  The pair
    is the adjacent pair whose first frame paints the largest **connected**
    cyan overlay field that the second frame does not -- and whose first
    frame is a battlefield frame (no dialogue panel), because the dialogue
    and menu screens also contain cyan, but as text rather than as a field.
    """

    best: tuple[int, int, dict[str, Any]] | None = None
    best_size = 0
    for index in range(len(frames) - 1):
        grid = load_image(frames[index])
        plain = load_image(frames[index + 1])
        pixels = grid.load()
        panel = sum(
            1 for y in range(FIELD_AREA[1], FIELD_AREA[3])
            for x in range(FIELD_AREA[0], FIELD_AREA[2])
            if pixels[x, y] == DIALOGUE_PANEL
        )
        if panel:
            continue
        size = largest_connected_region(overlay_cells(grid, plain))
        if size > best_size:
            best_size = size
            best = (index, index + 1, overlay_statistics(grid, plain))
    if best is None or best_size <= 0:
        return None
    return best


def classify_status_bar(image, box: tuple[int, int, int, int] = STATUS_BAR
                        ) -> dict[str, int]:
    """Count the two state inks in the status bar band."""

    x0, y0, x1, y1 = box
    pixels = image.load()
    end = 0
    standby = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            colour = pixels[x, y]
            if colour == END_INK:
                end += 1
            elif colour == STANDBY_INK:
                standby += 1
    return {"end_ink_pixels": end, "standby_ink_pixels": standby}


#: The two state inks of the original's status bar.
END_INK = (231, 24, 0)
STANDBY_INK = (115, 33, 255)


def main_common(parser) -> None:
    """Add the shared path arguments to an argument parser."""

    parser.add_argument(
        "--remake-root", default=str(REMAKE_ROOT),
        help="the remake tree (read-only reference)",
    )
    parser.add_argument(
        "--evidence-root", default=str(EVIDENCE_ROOT),
        help="where the local recordings live",
    )
