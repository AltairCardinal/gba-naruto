#!/usr/bin/env python3
"""Export the two hash-bound Mode-3 boot framebuffers from the base ROM."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import uuid
from typing import Any

from PIL import Image


ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "rom-boot-framebuffers-v1"
FRAME_SPECS = (
    {
        "id": "boot-frame-a",
        "range": (0x5BA000, 0x5CCC00),
        "sha256": "68403b4d80800603aee5340b21fce0e95b59bece8d52edc82e3c97206ea320d1",
        "source_bin": "boot-frame-a.bin",
        "preview_png": "boot-frame-a.png",
    },
    {
        "id": "boot-frame-b",
        "range": (0x5CCE00, 0x5DFA00),
        "sha256": "f76aa2f65fa186390ec0625f9a0b8a0668455c8454c4ac1e0b522f4bbde38412",
        "source_bin": "boot-frame-b.bin",
        "preview_png": "boot-frame-b.png",
    },
)
ROUTINE_SPECS = (
    {
        "id": "boot-display-a",
        "start": 0x5CCC00,
        "source_offset": 0x5BA000,
        "terminal_target": 0x085DFA00,
        "code_sha256": "9e7b9abc901897288a32f4ddce07a4544e83f872a9a847378d7392c54af096d8",
        "literal_pool_sha256": "f8e223cf0bce0cb8af3018716240bb7d05f93748e8b011a546fb540bc67b5f89",
        "routine_sha256": "fc822696f80ed25edc2f3ee86f7646f8bf96e96b20a5e00fcc8c05ccefbb65ba",
    },
    {
        "id": "boot-display-b",
        "start": 0x5DFA00,
        "source_offset": 0x5CCE00,
        "terminal_target": 0x080000C8,
        "code_sha256": "3415db365bc258197c5665c1ce24b296fee80fb5ba983abbc5d9ad0341681e2f",
        "literal_pool_sha256": "8df20a3734d89bffe9e12f69f36baabc8d636ed052957e7adedc30e5fafad564",
        "routine_sha256": "35cfd378a3bec78899031ad6edf170a02dc9940cadd9b716990be086fee2ba3f",
    },
)
PADDING_RANGE = (0x5CCDEC, 0x5CCE00)
PADDING_SHA256 = "9a8dcd3f9ff7aa3114e141f03c12989d363ea81fd74c02eea63c5f41489cb17a"
STARTUP_CLAIM_SPECS = (
    ("reset-vector", (0x000000, 0x000004), "arm_code", "e3de0a6864e3119f5ccb28524e580cd769e44efefd06ba6c0bf7c2807bfd3a16"),
    ("gba-header", (0x000004, 0x0000C0), "gba_header", "bb4d92a4e61881dd4c18cb08b8b3de870832e234e58a4f36d6c533922fdf83bb"),
    ("display-handoff", (0x0000C0, 0x0000C4), "arm_code", "7c761439b51713afbe41659f76634b199c8a9a284f02cf0dbeea0896a44d6fe7"),
    ("arm-bootstrap", (0x0000C8, 0x0000F4), "arm_code", "90eace5ce45f29f48f27f66696728fc50d37ea6f62b4fff9d80556cf013fdff7"),
    ("arm-bootstrap-literals", (0x0000F4, 0x000104), "literal_pool", "6d087001a1c6b73ef334e65f00390bfed550fbec64cb21d90b4e843667cf5986"),
    ("arm-irq-callback", (0x000104, 0x000244), "arm_code", "d1f17c7955af78b297a5bb5d8222377ba9e6a125c59354255b1aaaa0cd86f1f8"),
    ("arm-irq-literals", (0x000244, 0x00024C), "literal_pool", "a9c21a365a1fa53e8fa21284fafbd7c8514ff14ac9ff4298ef24fb054cb9aca0"),
)
SCOPE = {
    "static_reset_chain_verified": True,
    "startup_header_verified": True,
    "bootstrap_irq_chain_verified": True,
    "unreferenced_boot_gap_semantically_classified": False,
    "mode3_dma_route_verified": True,
    "raw_bgr555_decode_verified": True,
    "final_screen_rgb_with_blending_verified": False,
    "framebuffer_writeback_verified": False,
    "mgba_runtime_replay_verified": False,
    "physical_gba_verified": False,
    "all_boot_paths_complete": False,
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _addr(value: int) -> str:
    return f"0x{value:08X}"


def _u32(rom: bytes, file_offset: int) -> int:
    if file_offset < 0 or file_offset + 4 > len(rom):
        raise ValueError(f"u32 offset 0x{file_offset:X} escapes ROM")
    return struct.unpack_from("<I", rom, file_offset)[0]


def _arm_branch_target(rom: bytes, file_offset: int) -> int:
    word = _u32(rom, file_offset)
    if word & 0x0F000000 != 0x0A000000:
        raise ValueError(f"ARM B missing at 0x{file_offset:X}")
    displacement = (word & 0x00FFFFFF) << 2
    if displacement & 0x02000000:
        displacement -= 0x04000000
    return ROM_BASE + file_offset + 8 + displacement


def _arm_literal(rom: bytes, file_offset: int, destination: int) -> tuple[int, int]:
    word = _u32(rom, file_offset)
    if word & 0x0F7F0000 != 0x051F0000 or (word >> 12) & 0xF != destination:
        raise ValueError(f"ARM PC-relative LDR missing at 0x{file_offset:X}")
    address = ROM_BASE + file_offset + 8
    immediate = word & 0xFFF
    literal_address = address + immediate if word & 0x00800000 else address - immediate
    return literal_address, _u32(rom, literal_address - ROM_BASE)


def _require_word(rom: bytes, file_offset: int, expected: int, label: str) -> None:
    if _u32(rom, file_offset) != expected:
        raise ValueError(f"{label} changed at 0x{file_offset:X}")


def _startup_chain(rom: bytes) -> dict[str, Any]:
    for identifier, (start, end), _, expected_sha256 in STARTUP_CLAIM_SPECS:
        if _sha(rom[start:end]) != expected_sha256:
            raise ValueError(f"startup range {identifier} changed")

    header = rom[0x04:0xC0]
    title = rom[0xA0:0xAC]
    game_code = rom[0xAC:0xB0]
    maker_code = rom[0xB0:0xB2]
    if title != b"NARUTOKONOHA" or game_code != b"AUEJ" or maker_code != b"DA":
        raise ValueError("GBA header identity changed")
    if rom[0xB2] != 0x96:
        raise ValueError("GBA header fixed byte changed")
    complement = (-sum(rom[0xA0:0xBD]) - 0x19) & 0xFF
    if rom[0xBD] != complement:
        raise ValueError("GBA header complement check failed")

    reset_target = _arm_branch_target(rom, 0x00)
    display_target = _arm_branch_target(rom, 0xC0)
    if reset_target != 0x080000C0 or display_target != 0x085CCC04:
        raise ValueError("ARM reset/display handoff changed")
    if _arm_branch_target(rom, 0xF0) != 0x080000C0:
        raise ValueError("ARM bootstrap return loop changed")

    stack_literals = []
    for offset, destination, expected_value in (
        (0xC8, 13, 0x03007FA0),
        (0xD4, 13, 0x03007F00),
    ):
        literal_address, value = _arm_literal(rom, offset, destination)
        if value != expected_value:
            raise ValueError("ARM bootstrap stack literal changed")
        stack_literals.append(
            {"load": _addr(ROM_BASE + offset), "literal": _addr(literal_address), "value": _addr(value)}
        )

    irq_literal_address, irq_slot = _arm_literal(rom, 0xD8, 1)
    if irq_literal_address != 0x080000F4 or irq_slot != 0x03007FFC:
        raise ValueError("IRQ callback slot literal changed")
    _require_word(rom, 0xDC, 0xE28F0020, "IRQ callback address materialization")
    _require_word(rom, 0xE0, 0xE5810000, "IRQ callback slot store")
    callback = ROM_BASE + 0xDC + 8 + 0x20

    thumb_literal_address, thumb_target = _arm_literal(rom, 0xE4, 1)
    if thumb_literal_address != 0x080000F8 or thumb_target != 0x08060FAD:
        raise ValueError("Thumb handoff literal changed")
    _require_word(rom, 0xE8, 0xE1A0E00F, "Thumb handoff link setup")
    _require_word(rom, 0xEC, 0xE12FFF11, "Thumb handoff BX")

    irq_mask_literal_address, irq_mask = _arm_literal(rom, 0x1CC, 1)
    irq_table_literal_address, irq_table = _arm_literal(rom, 0x1F4, 1)
    if (irq_mask_literal_address, irq_mask) != (0x08000244, 0x00002006):
        raise ValueError("IRQ mask literal changed")
    if (irq_table_literal_address, irq_table) != (0x08000248, 0x03000014):
        raise ValueError("IRQ handler table literal changed")
    _require_word(rom, 0x208, 0xE12FFF10, "IRQ handler BX")
    _require_word(rom, 0x240, 0xE12FFF1E, "IRQ callback return")

    return {
        "header": {
            "range": [0x04, 0xC0],
            "sha256": _sha(header),
            "title": title.decode("ascii"),
            "game_code": game_code.decode("ascii"),
            "maker_code": maker_code.decode("ascii"),
            "fixed_byte": 0x96,
            "complement": complement,
            "complement_check_valid": True,
        },
        "reset_vector": {"address": "0x08000000", "target": _addr(reset_target)},
        "display_handoff": {"address": "0x080000C0", "target": _addr(display_target)},
        "stack_literals": stack_literals,
        "irq_install": {
            "slot_literal": _addr(irq_literal_address),
            "slot": _addr(irq_slot),
            "callback": _addr(callback),
        },
        "thumb_handoff": {
            "literal": _addr(thumb_literal_address),
            "target": _addr(thumb_target),
            "mode": "thumb",
        },
        "irq_callback": {
            "range": [0x104, 0x244],
            "mask_literal": _addr(irq_mask_literal_address),
            "mask": _addr(irq_mask),
            "handler_table_literal": _addr(irq_table_literal_address),
            "handler_table": _addr(irq_table),
            "return_instruction": "0x08000240",
        },
        "unclaimed_gap": [0xC4, 0xC8],
    }


def _rgb_bytes(raw: bytes) -> bytes:
    if len(raw) != 76_800:
        raise ValueError("Mode-3 framebuffer size changed")
    pixels = bytearray(240 * 160 * 3)
    for index, (color,) in enumerate(struct.iter_unpack("<H", raw)):
        if color & 0x8000:
            raise ValueError("Mode-3 framebuffer uses nonzero BGR555 bit 15")
        output = index * 3
        pixels[output] = (color & 0x1F) * 255 // 31
        pixels[output + 1] = ((color >> 5) & 0x1F) * 255 // 31
        pixels[output + 2] = ((color >> 10) & 0x1F) * 255 // 31
    return bytes(pixels)


def _implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha((root / "tools/export_rom_boot_framebuffers.py").read_bytes()),
        "verifier_sha256": _sha((root / "tools/verify_rom_boot_framebuffers.py").read_bytes()),
        "test_sha256": _sha((root / "tests/test_export_rom_boot_framebuffers.py").read_bytes()),
    }


def _claim(identifier: str, value: tuple[int, int], semantic_class: str, rom: bytes) -> dict[str, Any]:
    start, end = value
    return {
        "id": identifier,
        "range": [start, end],
        "size": end - start,
        "semantic_class": semantic_class,
        "sha256": _sha(rom[start:end]),
    }


def _routine(spec: dict[str, Any]) -> dict[str, Any]:
    start = spec["start"]
    source = ROM_BASE + spec["source_offset"]
    return {
        "id": spec["id"],
        "range": [start, start + 0x1EC],
        "gba_range": [_addr(ROM_BASE + start), _addr(ROM_BASE + start + 0x1EC)],
        "code_range": [start, start + 0x140],
        "literal_pool_range": [start + 0x140, start + 0x1EC],
        "code_sha256": spec["code_sha256"],
        "literal_pool_sha256": spec["literal_pool_sha256"],
        "routine_sha256": spec["routine_sha256"],
        "dma": {
            "channel": "DMA3",
            "source": _addr(source),
            "source_register": "0x040000D4",
            "destination": "0x06000000",
            "destination_register": "0x040000D8",
            "control": "0x84004B00",
            "control_register": "0x040000DC",
            "byte_count": 76_800,
        },
        "display": {
            "register": "0x04000000",
            "value": "0x00000403",
            "decoded": "mode3_bgr555_bg2",
        },
        "blend": {
            "register": "0x04000050",
            "values": ["0x000004C4", "0x00000484"],
        },
        "vcount_poll": {"register": "0x04000006", "scanline": 160},
        "terminal_target": _addr(spec["terminal_target"]),
    }


def _build_manifest(root: Path, artifact_dir: Path, rom: bytes) -> dict[str, Any]:
    startup_chain = _startup_chain(rom)
    framebuffers = []
    for spec in FRAME_SPECS:
        start, end = spec["range"]
        raw = rom[start:end]
        if _sha(raw) != spec["sha256"]:
            raise ValueError(f"{spec['id']} ROM hash changed")
        source_path = artifact_dir / spec["source_bin"]
        source_path.write_bytes(raw)
        preview_path = artifact_dir / spec["preview_png"]
        Image.frombytes("RGB", (240, 160), _rgb_bytes(raw)).save(
            preview_path,
            format="PNG",
            optimize=False,
            compress_level=9,
        )
        framebuffers.append(
            {
                "id": spec["id"],
                "range": [start, end],
                "gba_range": [_addr(ROM_BASE + start), _addr(ROM_BASE + end)],
                "size": end - start,
                "sha256": spec["sha256"],
                "dimensions": [240, 160],
                "pixel_count": 38_400,
                "pixel_storage": "mode3_bgr555_le",
                "all_bit15_clear": True,
                "source_bin": spec["source_bin"],
                "source_bin_sha256": _sha(source_path.read_bytes()),
                "preview_png": spec["preview_png"],
                "preview_png_sha256": _sha(preview_path.read_bytes()),
            }
        )
    claims = [
        *(
            _claim(identifier, value, semantic_class, rom)
            for identifier, value, semantic_class, _ in STARTUP_CLAIM_SPECS
        ),
        _claim("boot-frame-a", FRAME_SPECS[0]["range"], "boot_mode3_framebuffer_bgr555", rom),
        _claim("boot-display-a-code", (0x5CCC00, 0x5CCD40), "arm_code", rom),
        _claim("boot-display-a-literals", (0x5CCD40, 0x5CCDEC), "literal_pool", rom),
        _claim("boot-framebuffer-alignment", PADDING_RANGE, "alignment_ff", rom),
        _claim("boot-frame-b", FRAME_SPECS[1]["range"], "boot_mode3_framebuffer_bgr555", rom),
        _claim("boot-display-b-code", (0x5DFA00, 0x5DFB40), "arm_code", rom),
        _claim("boot-display-b-literals", (0x5DFB40, 0x5DFBEC), "literal_pool", rom),
    ]
    padding = rom[slice(*PADDING_RANGE)]
    if padding != b"\xFF" * 20 or _sha(padding) != PADDING_SHA256:
        raise ValueError("boot framebuffer alignment padding changed")
    if sum(item["size"] for item in claims) != 155_188:
        raise ValueError("boot framebuffer byte denominator changed")
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "summary": {
            "claim_count": 14,
            "byte_count": 155_188,
            "startup_claim_count": 7,
            "startup_byte_count": 584,
            "framebuffer_count": 2,
            "pixels_per_framebuffer": 38_400,
            "arm_routine_count": 2,
        },
        "claims": claims,
        "framebuffers": framebuffers,
        "arm_routines": [_routine(spec) for spec in ROUTINE_SPECS],
        "padding": {
            "range": list(PADDING_RANGE),
            "size": 20,
            "fill_byte": 255,
            "sha256": PADDING_SHA256,
            "allocatable_free_space": False,
        },
        "startup_chain": startup_chain,
        "boot_chain": {
            "reset_vector": startup_chain["reset_vector"],
            "header_handoff": startup_chain["display_handoff"],
            "targets": ["0x085CCC04", "0x085DFA00", "0x080000C8"],
        },
        "scope": SCOPE,
        "implementation": _implementation(root),
    }


def _validate_output_dir(root: Path, output_dir: Path) -> Path:
    root = Path(root).resolve(strict=True)
    requested = Path(output_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    if requested.is_symlink():
        raise ValueError("boot output directory must not be a symlink")
    target = requested.resolve(strict=False)
    if target == root or target in root.parents:
        raise ValueError("boot output cannot be repository root or ancestor")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("boot output is not a directory")
    members = list(target.iterdir())
    if not members:
        return target
    expected = {
        "manifest.json",
        *(spec["source_bin"] for spec in FRAME_SPECS),
        *(spec["preview_png"] for spec in FRAME_SPECS),
    }
    if (
        any(member.is_symlink() or not member.is_file() for member in members)
        or {member.name for member in members} != expected
    ):
        raise ValueError("existing directory is not a replaceable boot artifact")
    try:
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        framebuffers = manifest["framebuffers"]
    except (OSError, KeyError, json.JSONDecodeError, TypeError) as error:
        raise ValueError("existing directory is not a replaceable boot artifact") from error
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("rom", {}).get("sha256") != ROM_SHA256
        or len(framebuffers) != len(FRAME_SPECS)
    ):
        raise ValueError("existing directory is not a replaceable boot artifact")
    expected_by_id = {spec["id"]: spec for spec in FRAME_SPECS}
    for record in framebuffers:
        spec = expected_by_id.get(record.get("id"))
        if spec is None:
            raise ValueError("existing directory is not a replaceable boot artifact")
        for name_key, hash_key in (
            ("source_bin", "source_bin_sha256"),
            ("preview_png", "preview_png_sha256"),
        ):
            name = record.get(name_key)
            if name != spec[name_key] or _sha((target / name).read_bytes()) != record.get(
                hash_key
            ):
                raise ValueError("existing directory is not a replaceable boot artifact")
    return target


def _replace_output_dir(output_dir: Path, temporary: Path) -> None:
    backup: Path | None = None
    try:
        if output_dir.exists():
            backup = output_dir.with_name(
                f".{output_dir.name}.backup-{uuid.uuid4().hex}"
            )
            os.replace(output_dir, backup)
        os.replace(temporary, output_dir)
    except Exception:
        if backup is not None and backup.exists() and not output_dir.exists():
            os.replace(backup, output_dir)
        raise
    else:
        if backup is not None:
            shutil.rmtree(backup)


def export_rom_boot_framebuffers(root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output_dir = _validate_output_dir(root, output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    rom = (root / ROM_PATH).read_bytes()
    if len(rom) != 6_291_456 or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    temporary = Path(tempfile.mkdtemp(prefix=".boot-framebuffers-", dir=output_dir.parent))
    try:
        manifest = _build_manifest(root, temporary, rom)
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _replace_output_dir(output_dir, temporary)
        return manifest
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/rom-boot-framebuffers-v1"),
    )
    args = parser.parse_args()
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = args.root / output_dir
    manifest = export_rom_boot_framebuffers(args.root, output_dir)
    print(json.dumps(manifest["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
