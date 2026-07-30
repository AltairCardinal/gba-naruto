"""Reusable safety checks for ROM byte patches.

The gate deliberately reasons about the immutable base ROM.  A patch must not
derive its precondition from a buffer already modified by an earlier patch.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rom_layout import RomLayout


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

    VALID_CLASSES = {"game_effective", "allocation", "audit"}

    def __init__(self, base_rom: bytes, *, layout: "RomLayout | None" = None):
        self.base_rom = base_rom
        self.layout = layout
        self._spans: list[PatchSpan] = []

    def register(self, patch: dict, *, patch_class: str) -> dict[str, object]:
        if patch_class not in self.VALID_CLASSES:
            raise ValueError(f"invalid patch class {patch_class!r}")
        patch_id = str(patch.get("id", "<unnamed>"))
        start = int(patch["offset"])
        after = bytes.fromhex(patch["after_hex"])
        end = start + len(after)
        if start < 0:
            raise ValueError(
                f"patch {patch_id} range 0x{start:X}..0x{end:X} is outside ROM "
                f"(size 0x{len(self.base_rom):X})"
            )
        if not after:
            raise ValueError(f"patch {patch_id} has an empty write range")

        allocation_result: dict[str, object] = {}
        requires_partition = patch_class == "allocation" or (
            patch_class == "audit" and self.layout is not None
        )
        if requires_partition:
            if self.layout is None:
                raise ValueError(
                    f"allocation patch {patch_id} has no declared ROM layout"
                )
            allocation = patch.get("allocation")
            if not isinstance(allocation, dict):
                raise ValueError(
                    f"allocation patch {patch_id} has no allocation declaration"
                )
            partition_id = str(allocation.get("partition", ""))
            owner = str(allocation.get("owner", ""))
            partition = self.layout.allocation_partition(
                partition_id,
                owner,
                start,
                end,
            )
            if patch_class == "audit" and partition.origin != "base_ff":
                raise ValueError(
                    f"audit patch {patch_id} requires a base_ff partition"
                )
            allocation_result = {
                "allocation_partition": partition.id,
                "allocation_owner": partition.owner,
            }
        elif end > len(self.base_rom):
            if self.layout is not None and end <= self.layout.target_rom_size:
                raise ValueError(
                    f"patch {patch_id} writes outside the immutable base ROM; "
                    "expanded writes require an allocation declaration"
                )
            raise ValueError(
                f"patch {patch_id} range 0x{start:X}..0x{end:X} is outside ROM "
                f"(size 0x{len(self.base_rom):X})"
            )

        before_hex = patch.get("before_hex")
        if patch_class in {"game_effective", "allocation"}:
            if before_hex is None:
                raise ValueError(f"{patch_class} patch {patch_id} has no before_hex")
            before = bytes.fromhex(before_hex)
            if len(before) != len(after):
                raise ValueError(
                    f"patch {patch_id} changes length in place: "
                    f"before={len(before)} after={len(after)}"
                )
            if patch_class == "allocation":
                actual = self.layout.expanded_base()[start : start + len(before)]
            else:
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
            **allocation_result,
        }


def with_base_precondition(base_rom: bytes, patch: dict) -> dict:
    """Return a copy whose before_hex comes only from the immutable base ROM."""
    start = int(patch["offset"])
    after = bytes.fromhex(patch["after_hex"])
    end = start + len(after)
    if start < 0 or end > len(base_rom):
        raise ValueError(f"patch range 0x{start:X}..0x{end:X} is outside base ROM")
    return {**patch, "before_hex": base_rom[start:end].hex()}
