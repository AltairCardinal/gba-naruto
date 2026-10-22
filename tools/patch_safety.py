"""Reusable safety checks for ROM byte patches.

The gate deliberately reasons about the immutable base ROM.  A patch must not
derive its precondition from a buffer already modified by an earlier patch.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PatchSpan:
    patch_id: str
    start: int
    data: bytes
    patch_class: str
    merge_group: str | None = None

    @property
    def end(self) -> int:
        return self.start + len(self.data)


class PatchSafetyGate:
    """Validate bounds, base preconditions, and overlapping writes."""

    VALID_CLASSES = {"game_effective", "audit"}

    def __init__(self, base_rom: bytes):
        self.base_rom = base_rom
        self._spans: list[PatchSpan] = []

    def register(self, patch: dict, *, patch_class: str) -> dict[str, object]:
        if patch_class not in self.VALID_CLASSES:
            raise ValueError(f"invalid patch class {patch_class!r}")
        patch_id = str(patch.get("id", "<unnamed>"))
        start = int(patch["offset"])
        after = bytes.fromhex(patch["after_hex"])
        end = start + len(after)
        if start < 0 or end > len(self.base_rom):
            raise ValueError(
                f"patch {patch_id} range 0x{start:X}..0x{end:X} is outside ROM "
                f"(size 0x{len(self.base_rom):X})"
            )
        if not after:
            raise ValueError(f"patch {patch_id} has an empty write range")

        before_hex = patch.get("before_hex")
        if patch_class == "game_effective":
            if before_hex is None:
                raise ValueError(f"game-effective patch {patch_id} has no before_hex")
            before = bytes.fromhex(before_hex)
            if len(before) != len(after):
                raise ValueError(
                    f"patch {patch_id} changes length in place: "
                    f"before={len(before)} after={len(after)}"
                )
            actual = self.base_rom[start : start + len(before)]
            if actual != before:
                raise ValueError(
                    f"patch {patch_id} base-ROM mismatch at 0x{start:X}: "
                    f"expected {before.hex()} got {actual.hex()}"
                )

        span = PatchSpan(
            patch_id, start, after, patch_class, patch.get("merge_group")
        )
        identical_to: list[str] = []
        for prior in self._spans:
            overlap_start = max(span.start, prior.start)
            overlap_end = min(span.end, prior.end)
            if overlap_start >= overlap_end:
                continue
            new_bytes = span.data[overlap_start - span.start : overlap_end - span.start]
            old_bytes = prior.data[overlap_start - prior.start : overlap_end - prior.start]
            # Identical writes are naturally idempotent and need no declaration.
            if new_bytes == old_bytes:
                if (
                    span.start == prior.start
                    and span.end == prior.end
                    and span.patch_class == prior.patch_class
                ):
                    identical_to.append(prior.patch_id)
                continue
            # A merge declaration documents why patches share a range; it is
            # never permission for different bytes to win by application
            # order.  Conflicting bytes always indicate an ambiguous build.
            merge_note = (
                f" (merge_group={span.merge_group!r} still conflicts)"
                if span.merge_group is not None
                and span.merge_group == prior.merge_group
                else ""
            )
            raise ValueError(
                f"conflicting patch overlap at 0x{overlap_start:X}..0x{overlap_end:X}: "
                f"{prior.patch_id} ({prior.patch_class}) vs "
                f"{span.patch_id} ({span.patch_class}){merge_note}"
            )
        self._spans.append(span)
        return {
            "overlap_disposition": "idempotent_duplicate" if identical_to else "unique",
            "duplicate_of": identical_to,
        }


def with_base_precondition(base_rom: bytes, patch: dict) -> dict:
    """Return a copy whose before_hex comes only from the immutable base ROM."""
    start = int(patch["offset"])
    after = bytes.fromhex(patch["after_hex"])
    end = start + len(after)
    if start < 0 or end > len(base_rom):
        raise ValueError(f"patch range 0x{start:X}..0x{end:X} is outside base ROM")
    return {**patch, "before_hex": base_rom[start:end].hex()}
