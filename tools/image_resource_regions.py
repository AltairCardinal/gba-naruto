"""Validate stable image-resource ownership inside one ROM layout partition."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.rom_layout import RomLayout, RomPartition


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as error:
            raise ValueError(f"{label} is not an integer") from error
    raise ValueError(f"{label} must be an integer")


def _power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


@dataclass(frozen=True)
class ImageResourceRegion:
    id: str
    owner: str
    start: int
    end: int
    alignment: int


class ImageResourceRegions:
    """Non-overlapping, gap-free suballocations of an expanded ROM partition."""

    def __init__(
        self,
        *,
        source: dict[str, Any],
        parent: RomPartition,
        regions: list[ImageResourceRegion],
    ):
        self.source = source
        self.parent = parent
        self.regions = tuple(regions)
        self._by_id = {region.id: region for region in regions}

    @classmethod
    def from_path(
        cls,
        path: Path,
        layout: RomLayout,
    ) -> "ImageResourceRegions":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("image resource registry must be an object")
        return cls.from_dict(payload, layout)

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
        layout: RomLayout,
    ) -> "ImageResourceRegions":
        if payload.get("version") != 1:
            raise ValueError("image resource registry version must be 1")
        parent_id = payload.get("parent_partition")
        parent_owner = payload.get("parent_owner")
        try:
            parent = next(
                partition
                for partition in layout.partitions
                if partition.id == parent_id
            )
        except StopIteration as error:
            raise ValueError("image resource parent partition is missing") from error
        if (
            parent.owner != parent_owner
            or parent.origin != "expanded_ff"
        ):
            raise ValueError("image resource parent partition contract mismatch")

        raw_regions = payload.get("regions")
        if not isinstance(raw_regions, list) or not raw_regions:
            raise ValueError("image resource regions must be a non-empty array")
        regions: list[ImageResourceRegion] = []
        seen: set[str] = set()
        for index, raw in enumerate(raw_regions):
            if not isinstance(raw, dict):
                raise ValueError(f"image resource region {index} must be an object")
            region_id = str(raw.get("id", "")).strip()
            owner = str(raw.get("owner", "")).strip()
            if not region_id or region_id in seen:
                raise ValueError("image resource region IDs must be unique")
            if not owner:
                raise ValueError(f"image resource region {region_id} has no owner")
            seen.add(region_id)
            start = _integer(raw.get("start"), f"{region_id}.start")
            end = _integer(raw.get("end"), f"{region_id}.end")
            alignment = _integer(
                raw.get("alignment", 1),
                f"{region_id}.alignment",
            )
            if not _power_of_two(alignment):
                raise ValueError(
                    f"image resource region {region_id} alignment is invalid"
                )
            if (
                start < parent.start
                or end <= start
                or end > parent.end
                or start % alignment
                or end % alignment
            ):
                raise ValueError(
                    f"image resource region {region_id} range is invalid"
                )
            regions.append(
                ImageResourceRegion(
                    id=region_id,
                    owner=owner,
                    start=start,
                    end=end,
                    alignment=alignment,
                )
            )

        regions.sort(key=lambda region: region.start)
        cursor = parent.start
        for region in regions:
            if region.start != cursor:
                raise ValueError(
                    "image resource regions must cover the parent without "
                    "gaps or overlaps"
                )
            cursor = region.end
        if cursor != parent.end:
            raise ValueError(
                "image resource regions must cover the parent without gaps"
            )
        return cls(source=payload, parent=parent, regions=regions)

    def require(self, region_id: str, owner: str) -> ImageResourceRegion:
        try:
            region = self._by_id[region_id]
        except KeyError as error:
            raise ValueError(
                f"unknown image resource region: {region_id}"
            ) from error
        if region.owner != owner:
            raise ValueError(
                f"image resource region {region_id} owner mismatch"
            )
        return region
