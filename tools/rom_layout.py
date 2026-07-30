"""Validated ROM capacity and allocation ownership.

The layout is deliberately separate from patch manifests.  A run of 0xFF
bytes is not allocation permission: every allocatable range must have a
stable partition ID, an owner, provenance, and a bounded cartridge profile.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as error:
            raise ValueError(f"{label} is not an integer: {value!r}") from error
    raise ValueError(f"{label} must be an integer")


def _power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


@dataclass(frozen=True)
class RomPartition:
    id: str
    owner: str
    start: int
    end: int
    origin: str
    alignment: int


class RomLayout:
    """Immutable, hash-pinned allocation registry for one base ROM."""

    VALID_ORIGINS = {"base_ff", "expanded_ff"}

    def __init__(
        self,
        *,
        source: dict[str, Any],
        base_rom: bytes,
        cartridge_profile: str,
        rom_base: int,
        max_rom_size: int,
        target_rom_size: int,
        fill_byte: int,
        partitions: list[RomPartition],
    ):
        self.source = source
        self.base_rom = base_rom
        self.cartridge_profile = cartridge_profile
        self.rom_base = rom_base
        self.max_rom_size = max_rom_size
        self.target_rom_size = target_rom_size
        self.fill_byte = fill_byte
        self.partitions = tuple(partitions)
        self._partitions_by_id = {item.id: item for item in partitions}

    @classmethod
    def from_path(cls, path: Path, base_rom: bytes) -> "RomLayout":
        return cls.from_dict(
            json.loads(path.read_text(encoding="utf-8")),
            base_rom,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any], base_rom: bytes) -> "RomLayout":
        if payload.get("version") != 1:
            raise ValueError("ROM layout version must be 1")

        base_spec = payload.get("base_rom")
        if not isinstance(base_spec, dict):
            raise ValueError("ROM layout base_rom must be an object")
        expected_size = _integer(base_spec.get("size"), "base_rom.size")
        if expected_size != len(base_rom):
            raise ValueError(
                f"ROM layout base size mismatch: expected 0x{expected_size:X} "
                f"got 0x{len(base_rom):X}"
            )
        expected_sha1 = str(base_spec.get("sha1", "")).lower()
        actual_sha1 = hashlib.sha1(base_rom).hexdigest()
        if expected_sha1 != actual_sha1:
            raise ValueError(
                f"ROM layout base SHA-1 mismatch: expected {expected_sha1} "
                f"got {actual_sha1}"
            )

        profile = payload.get("cartridge_profile")
        if not isinstance(profile, dict):
            raise ValueError("ROM layout cartridge_profile must be an object")
        profile_id = str(profile.get("id", "")).strip()
        if not profile_id:
            raise ValueError("ROM layout cartridge profile has no id")
        rom_base = _integer(profile.get("rom_base"), "cartridge_profile.rom_base")
        max_rom_size = _integer(
            profile.get("max_rom_size"),
            "cartridge_profile.max_rom_size",
        )
        target_rom_size = _integer(
            payload.get("target_rom_size"),
            "target_rom_size",
        )
        if target_rom_size < len(base_rom):
            raise ValueError(
                f"target ROM size 0x{target_rom_size:X} is smaller than "
                f"base ROM size 0x{len(base_rom):X}"
            )
        if target_rom_size > max_rom_size:
            raise ValueError(
                f"target ROM size 0x{target_rom_size:X} exceeds cartridge profile "
                f"maximum 0x{max_rom_size:X}"
            )
        if target_rom_size > len(base_rom) and not _power_of_two(target_rom_size):
            raise ValueError("expanded target ROM size must be a power of two")

        fill_byte = _integer(payload.get("fill_byte"), "fill_byte")
        if not 0 <= fill_byte <= 0xFF:
            raise ValueError("fill_byte must fit in one byte")

        raw_partitions = payload.get("partitions")
        if not isinstance(raw_partitions, list):
            raise ValueError("ROM layout partitions must be an array")
        partitions: list[RomPartition] = []
        seen_ids: set[str] = set()
        for index, raw in enumerate(raw_partitions):
            if not isinstance(raw, dict):
                raise ValueError(f"partition {index} must be an object")
            partition_id = str(raw.get("id", "")).strip()
            owner = str(raw.get("owner", "")).strip()
            if not partition_id or partition_id in seen_ids:
                raise ValueError(f"partition {index} has missing or duplicate id")
            if not owner:
                raise ValueError(f"partition {partition_id} has no owner")
            seen_ids.add(partition_id)
            start = _integer(raw.get("start"), f"partition {partition_id}.start")
            end = _integer(raw.get("end"), f"partition {partition_id}.end")
            alignment = _integer(
                raw.get("alignment", 1),
                f"partition {partition_id}.alignment",
            )
            origin = str(raw.get("origin", ""))
            if origin not in cls.VALID_ORIGINS:
                raise ValueError(
                    f"partition {partition_id} has invalid origin {origin!r}"
                )
            if start < 0 or end <= start or end > target_rom_size:
                raise ValueError(
                    f"partition {partition_id} range "
                    f"0x{start:X}..0x{end:X} is outside target ROM"
                )
            if not _power_of_two(alignment):
                raise ValueError(
                    f"partition {partition_id} alignment must be a power of two"
                )
            if start % alignment or end % alignment:
                raise ValueError(
                    f"partition {partition_id} range is not aligned to {alignment}"
                )
            if origin == "base_ff":
                if end > len(base_rom):
                    raise ValueError(
                        f"base_ff partition {partition_id} crosses the base ROM end"
                    )
                expected = bytes([fill_byte]) * (end - start)
                if base_rom[start:end] != expected:
                    raise ValueError(
                        f"base_ff partition {partition_id} is not filled with "
                        f"0x{fill_byte:02X}"
                    )
            elif start < len(base_rom):
                raise ValueError(
                    f"expanded_ff partition {partition_id} overlaps the base ROM"
                )
            partitions.append(
                RomPartition(
                    id=partition_id,
                    owner=owner,
                    start=start,
                    end=end,
                    origin=origin,
                    alignment=alignment,
                )
            )

        partitions.sort(key=lambda item: (item.start, item.end, item.id))
        for left, right in zip(partitions, partitions[1:]):
            if left.end > right.start:
                raise ValueError(
                    f"ROM layout partition overlap: {left.id} "
                    f"0x{left.start:X}..0x{left.end:X} vs {right.id} "
                    f"0x{right.start:X}..0x{right.end:X}"
                )

        return cls(
            source=payload,
            base_rom=base_rom,
            cartridge_profile=profile_id,
            rom_base=rom_base,
            max_rom_size=max_rom_size,
            target_rom_size=target_rom_size,
            fill_byte=fill_byte,
            partitions=partitions,
        )

    def expanded_base(self) -> bytes:
        return self.base_rom + bytes([self.fill_byte]) * (
            self.target_rom_size - len(self.base_rom)
        )

    def allocation_partition(
        self,
        partition_id: str,
        owner: str,
        start: int,
        end: int,
    ) -> RomPartition:
        partition = self._partitions_by_id.get(partition_id)
        if partition is None:
            raise ValueError(f"unknown ROM allocation partition {partition_id!r}")
        if owner != partition.owner:
            raise ValueError(
                f"ROM allocation owner {owner!r} does not match partition "
                f"{partition.id} owner {partition.owner!r}"
            )
        if start < partition.start or end > partition.end:
            raise ValueError(
                f"ROM allocation 0x{start:X}..0x{end:X} is outside partition "
                f"{partition.id} 0x{partition.start:X}..0x{partition.end:X}"
            )
        if start % partition.alignment:
            raise ValueError(
                f"ROM allocation at 0x{start:X} is not aligned to "
                f"{partition.alignment}"
            )
        return partition

    def require_exact_partition(
        self,
        partition_id: str,
        owner: str,
        start: int,
        end: int,
    ) -> RomPartition:
        partition = self.allocation_partition(
            partition_id,
            owner,
            start,
            end,
        )
        if start != partition.start or end != partition.end:
            raise ValueError(
                f"allocator 0x{start:X}..0x{end:X} must exactly match "
                f"partition {partition.id} "
                f"0x{partition.start:X}..0x{partition.end:X}"
            )
        return partition

    def report(self) -> dict[str, Any]:
        return {
            "base_rom_size": len(self.base_rom),
            "target_rom_size": self.target_rom_size,
            "fill_byte": self.fill_byte,
            "cartridge_profile": self.cartridge_profile,
            "rom_base": f"0x{self.rom_base:08X}",
            "max_rom_size": self.max_rom_size,
            "partitions": [
                {
                    "id": item.id,
                    "owner": item.owner,
                    "start": item.start,
                    "end": item.end,
                    "origin": item.origin,
                    "alignment": item.alignment,
                }
                for item in self.partitions
            ],
        }
