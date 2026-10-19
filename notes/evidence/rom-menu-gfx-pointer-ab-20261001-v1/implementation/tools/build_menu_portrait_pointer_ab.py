#!/usr/bin/env python3
"""Build an isolated menu record 1 gfx_ptr_0 A/B input pair."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_menu_portrait_pixel_ab import build_pair as build_parent
from tools.build_cutscene_obj_secondary_ptr_ab import _fresh_output, _sha, _write_json
from tools.build_mod import apply_patch
from tools.extract_tileset import lz77_decompress
from tools.image_resource_regions import ImageResourceRegions
from tools.patch_safety import PatchSafetyGate
from tools.rom_layout import RomLayout

SCHEMA = 'menu-portrait-gfx-pointer-ab-build-v1'
BANK_PATH = 'sequel/content/menu-ui/bank.json'
BANK_SHA = '8e9cf0a4289ff2701ad9643181532a6e8283177875b38d34d6eced5948a6cfe7'
PARENT_MANIFEST_SHA = '1b2ec1560b5492ef90c354646f44a5f9ba872384ae3e6831984030474811bd69'
PARENT_SHAS = {
    'baseline': '202301cc0bcb246269e200db3c5ced1aa3ec8e7547e2f21c26d81df5db95fc3a',
    'candidate': '26a08a91628c4fc511a796db27a29518c7303e8a7294665afbf21b99dce42311',
}
POINTER_OFFSET = 0x5A4E14
ROM_BASE = 0x08000000


def build_pair(root, output):
    root = Path(root).resolve(strict=True)
    output = _fresh_output(output)
    bank_bytes = (root / BANK_PATH).read_bytes()
    if _sha(bank_bytes) != BANK_SHA:
        raise ValueError('menu bank identity mismatch')
    bank = json.loads(bank_bytes)
    field_names = [row['name'] for row in bank['entry_format']['fields']]
    if (bank['entry_count'] != 63 or bank['entry_size'] != 40
            or bank['table_offset'] + 40 != POINTER_OFFSET or field_names[0] != 'gfx_ptr_0'):
        raise ValueError('menu bank field binding mismatch')
    base = (root / 'rom/base.gba').read_bytes()
    with tempfile.TemporaryDirectory() as directory:
        parent_dir = Path(directory) / 'parent'
        parent = build_parent(root, parent_dir)
        parents = {name: (parent_dir / f'{name}/{name}.gba').read_bytes() for name in PARENT_SHAS}
        if (_sha((parent_dir / 'build-manifest.json').read_bytes()) != PARENT_MANIFEST_SHA
                or any(_sha(data) != PARENT_SHAS[name] for name, data in parents.items())):
            raise ValueError('menu parent identity mismatch')
    original = parents['baseline']
    layout = RomLayout.from_path(root / 'sequel/rom-layout.json', base)
    regions = ImageResourceRegions.from_path(root / 'sequel/image-resource-regions.json', layout)
    region = regions.require('menu-portraits', 'menu_portrait_resources')
    allocations = [r for r in parent['variants']['baseline']['patch_ledger'] if r['kind'] == 'allocation']
    gate = PatchSafetyGate(base, layout=layout, image_regions=regions)
    for row in allocations:
        offset, size = row['offset'], row['size']
        gate.register({'id': row['id'], 'offset': offset, 'before_hex': (b'\xFF' * size).hex(),
                       'after_hex': original[offset:offset + size].hex(), 'allocation': row['allocation']},
                      patch_class='allocation')
    end = max(r['offset'] + r['size'] for r in allocations)
    allocation_offset = (end + region.alignment - 1) & -region.alignment
    if allocation_offset != 0xA80D6C:
        raise ValueError('menu parent allocation boundary changed')
    encoded = parents['candidate'][0xA80000:0xA80000 + 3306]
    before = lz77_decompress(original, 0xA80000)
    after = lz77_decompress(parents['candidate'], 0xA80000)
    if (len(before) != 6400 or len(after) != 6400
            or [i for i, (a, b) in enumerate(zip(before, after, strict=True)) if a != b] != [5184]
            or (before[5184], after[5184]) != (52, 14)):
        raise ValueError('menu graphics donor isolation mismatch')
    allocation = {'id': 'menu-record1-gfx-ptr0-donor', 'type': 'bytes', 'offset': allocation_offset,
                  'before_hex': (b'\xFF' * len(encoded)).hex(), 'after_hex': encoded.hex(),
                  'allocation': {'partition': 'sequel-image-assets', 'owner': 'sequel_image_assets',
                                 'region': region.id, 'region_owner': region.owner}}
    shared = bytearray(original)
    apply_patch(shared, allocation, gate=gate)
    baseline = bytes(shared)
    before_pointer = struct.unpack_from('<I', baseline, POINTER_OFFSET)[0]
    after_pointer = ROM_BASE + allocation_offset
    redirect = {'id': 'menu-record1-gfx-ptr0-redirect', 'type': 'bytes', 'offset': POINTER_OFFSET,
                'before_hex': baseline[POINTER_OFFSET:POINTER_OFFSET + 4].hex(),
                'after_hex': struct.pack('<I', after_pointer).hex()}
    candidate_buffer = bytearray(baseline)
    apply_patch(candidate_buffer, redirect, gate=PatchSafetyGate(baseline))
    candidate = bytes(candidate_buffer)
    differences = [i for i, (a, b) in enumerate(zip(baseline, candidate, strict=True)) if a != b]
    if differences != [POINTER_OFFSET, POINTER_OFFSET + 1]:
        raise ValueError('menu pointer edit is not isolated')
    output.mkdir(parents=True, exist_ok=True)
    variants = {}
    for name, payload in [('baseline', baseline), ('candidate', candidate)]:
        folder = output / name
        folder.mkdir()
        path = folder / f'{name}.gba'
        path.write_bytes(payload)
        variants[name] = {'rom_path': path.relative_to(output).as_posix(),
                          'rom_sha256': _sha(payload), 'rom_size': len(payload)}
    manifest = {'schema': SCHEMA, 'source_rom_sha256': _sha(base), 'bank_sha256': BANK_SHA,
                'parent_manifest_sha256': PARENT_MANIFEST_SHA, 'parent_rom_sha256': PARENT_SHAS,
                'edit': {'record_id': '1', 'variant': 0, 'field': 'gfx_ptr_0', 'resource_id': 0,
                         'offset': POINTER_OFFSET, 'before_pointer': before_pointer, 'after_pointer': after_pointer},
                'allocation': {'offset': allocation_offset, 'size': len(encoded), 'region': region.id,
                               'region_owner': region.owner, 'encoded_sha256': _sha(encoded),
                               'decompressed_sha256': _sha(after), 'shared_by_both_variants': True,
                               'stream_byte_offset': 5184, 'before_index': 52, 'after_index': 14},
                'isolation': {'changed_rom_offsets': differences, 'other_bytes_equal': True},
                'variants': variants, 'runtime_verified': False}
    _write_json(output / 'build-manifest.json', manifest)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(build_pair(args.root, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
