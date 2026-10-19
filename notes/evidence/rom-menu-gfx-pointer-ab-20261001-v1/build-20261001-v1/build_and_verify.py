import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

root = Path.cwd().resolve()
sys.path.insert(0, str(root))
from tools.verify_menu_portrait_pixel_ab_evidence import _catalog_contract, _portrait, _rebuild_rom
from tools.verify_menu_portrait_writeback_audit import _encode_lz77
from tools.verify_cutscene_obj_primary_ptr_ab import _lz77

run = root / 'build/experiments/active/menu-portrait-pointer-ab/build-20261001-v1'
sha = lambda value: hashlib.sha256(value).hexdigest()
repeat = '--verify-only' in sys.argv
if not repeat:
    with (run / 'build.stdout').open('w') as out, (run / 'build.stderr').open('w') as err:
        process = subprocess.run([sys.executable, 'tools/build_menu_portrait_pointer_ab.py', '--root', str(root),
                                  '--output', str(run / 'build')], cwd=root, stdout=out, stderr=err)
    assert process.returncode == 0
manifest = json.loads((run / 'build.stdout').read_text())
assert manifest == json.loads((run / 'build/build-manifest.json').read_text())
base = (root / 'rom/base.gba').read_bytes()
_, palette = _catalog_contract(root, base)
stream, source_palette = _portrait(root / 'artifacts/menu-portraits-v1/portrait_01_variant_0.png', palette)
parent = _rebuild_rom(base, stream, source_palette)
assert sha(parent) == '202301cc0bcb246269e200db3c5ced1aa3ec8e7547e2f21c26d81df5db95fc3a'
authored = bytearray(stream)
authored[5184] = 14
encoded = _encode_lz77(bytes(authored))
assert len(encoded) == 3306
assert parent[0xA80D6C:0xA81A56] == b'\xFF' * 3306
baseline = bytearray(parent)
baseline[0xA80D6C:0xA81A56] = encoded
candidate = bytearray(baseline)
struct.pack_into('<I', candidate, 0x5A4E14, 0x08A80D6C)
rows = {}
for name, expected in [('baseline', baseline), ('candidate', candidate)]:
    actual = (run / f'build/{name}/{name}.gba').read_bytes()
    assert actual == bytes(expected)
    assert sha(actual) == manifest['variants'][name]['rom_sha256']
    assert _lz77(actual, int.from_bytes(actual[0x5A4E14:0x5A4E18], 'little')) == (stream if name == 'baseline' else bytes(authored))
    rows[name] = {'sha256': sha(actual), 'size': len(actual)}
assert manifest['allocation']['encoded_sha256'] == sha(encoded)
assert manifest['allocation']['decompressed_sha256'] == sha(bytes(authored))
assert manifest['runtime_verified'] is False
result = {'verified': True, 'method': 'independent source portrait packing/LZ77 plus raw pointer ROM reconstruction',
          'allocation_offset': 0xA80D6C, 'allocation_end': 0xA81A56, 'allocation_size': 3306,
          'encoded_sha256': sha(encoded), 'decoded_sha256': sha(bytes(authored)),
          'roms': rows, 'pointer_rom_offsets': [0x5A4E14, 0x5A4E15], 'runtime_verified': False}
(run / ('independent-build-repeated.json' if repeat else 'independent-build.json')).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print(json.dumps(result, sort_keys=True))
