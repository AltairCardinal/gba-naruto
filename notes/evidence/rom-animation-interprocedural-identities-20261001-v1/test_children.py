from pathlib import Path
import struct
import unittest
from callee_effects import analyze


def bl(at,target):
    d=(target-at-4)&0x7fffff
    return struct.pack('<HH',0xf000|(d>>12),0xf800|((d>>1)&2047))


class ChildrenTests(unittest.TestCase):
    def fixture(self,parent=True):
        raw=bytearray(Path('rom/base.gba').read_bytes())
        parts={0x200:bytes.fromhex('0120'),0x202:bytes.fromhex('7047')}
        if parent:parts.update({0x100:bytes.fromhex('10b5'),0x102:bl(0x102,0x200),
                               0x106:bytes.fromhex('10bc'),0x108:bytes.fromhex('01bc'),0x10a:bytes.fromhex('0047')})
        for at,b in parts.items():raw[at:at+len(b)]=b
        rom=bytes(raw)
        return rom,set(parts)-{0x200,0x202},analyze(rom,0x200,{0x200,0x202})

    def test_verified_child_preserves_unsaved_gpr(self):
        rom,nodes,child=self.fixture()
        r=analyze(rom,0x100,nodes,conditional_frame=True,children={0x200:child})
        self.assertIn(5,r['preserved_registers'])
        self.assertTrue(r['return_identity_proven'])
        self.assertFalse(r['caller_stack_facts_preserved'])

    def test_forged_child_preservation_rejected(self):
        rom,nodes,child=self.fixture();child['preserved_registers'].append(0)
        with self.assertRaises(ValueError):analyze(rom,0x100,nodes,conditional_frame=True,children={0x200:child})

    def test_child_rom_drift_rejected(self):
        rom,nodes,child=self.fixture();raw=bytearray(rom);raw[0x200:0x202]=bytes.fromhex('0220')
        with self.assertRaises(ValueError):analyze(bytes(raw),0x100,nodes,conditional_frame=True,children={0x200:child})

    def test_bl_does_not_preserve_entry_lr_even_if_child_preserves_lr(self):
        rom,_,_=self.fixture(False);raw=bytearray(rom)
        raw[0x100:0x104]=bl(0x100,0x200);raw[0x104:0x106]=bytes.fromhex('7047')
        rom=bytes(raw);child=analyze(rom,0x200,{0x200,0x202})
        r=analyze(rom,0x100,{0x100,0x104},children={0x200:child})
        self.assertFalse(r['return_identity_proven'])

    def test_strict_parent_still_drops_unproved_child_memory_effects(self):
        rom,nodes,child=self.fixture()
        r=analyze(rom,0x100,nodes,children={0x200:child})
        self.assertFalse(r['return_identity_proven'])

    def test_self_dependent_contract_is_rejected(self):
        rom,nodes,child=self.fixture()
        child['root']=0x100
        with self.assertRaises(ValueError):analyze(rom,0x100,nodes,children={0x100:child})


if __name__ == '__main__':unittest.main(verbosity=2)
