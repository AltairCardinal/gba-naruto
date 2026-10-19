"""Independent halfword checks; only local shapes, not a full semantic proof."""
import hashlib
import json
import struct
from pathlib import Path

rom = Path('rom/base.gba').read_bytes()
assert hashlib.sha256(rom).hexdigest() == '1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'

def half(at):
    return struct.unpack_from('<H', rom, at)[0]

rows = []
for opcode, load, add, store, register in [
    (7, 0x67f2c, 0x67f4e, 0x67f50, 3),
    (7, 0x67f80, 0x67f82, 0x67f84, 5),
    (8, 0x68170, 0x68172, 0x68174, 6),
    (8, 0x68190, 0x68192, 0x68194, 0),
]:
    ldr, adds, str_ = half(load), half(add), half(store)
    assert ldr & 0xf800 == 0x9800 and (ldr >> 8) & 7 == register and ldr & 255 == 5
    assert adds & 0xf800 == 0x3000 and (adds >> 8) & 7 == register
    assert str_ & 0xf800 == 0x9000 and (str_ >> 8) & 7 == register and str_ & 255 == 5
    width = adds & 255
    assert width == (3 if opcode == 7 else 2)
    rows.append({'opcode': opcode, 'load': load, 'add': add, 'store': store,
                 'register': register, 'local_advance': width,
                 'intervening_control_flow_and_callees_closed': False})
for opcode, target in [(7, 0x675e4), (8, 0x68090)]:
    assert struct.unpack_from('<I', rom, 0x67180 + opcode * 4)[0] == 0x8000000 + target
print(json.dumps({'raw_local_shapes': rows, 'dispatch_cells_match': True,
                  'promotion_bytes': 0, 'complete_handler_semantics_proven': False}, sort_keys=True, indent=2))
