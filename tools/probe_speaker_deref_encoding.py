"""Disassemble the patched reader windows and compare the two candidate
deref encodings.

0x5849 (bytes 49 58) : Thumb-1 LDR (register) T1  -> ldr r1, [r1, r1]  == *(r1 + r1*1)
0x6809 (bytes 09 68) : Thumb-1 LDR (immediate) T1 -> ldr r1, [r1, #0]  == *(r1)
"""
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from capstone_loader import load_capstone  # noqa: E402

cs = load_capstone()
md = cs.Cs(cs.CS_ARCH_ARM, cs.CS_MODE_THUMB)
md.detail = False


def dis(data, addr, count=None):
    out = []
    for insn in md.disasm(data, addr):
        out.append(f"  0x{insn.address:08X}: {insn.bytes.hex(' '):<12} {insn.mnemonic} {insn.op_str}")
        if count and len(out) >= count:
            break
    return out


print("=== candidate encodings ===")
for hexs, addr in (("4958", 0x08097A12), ("0968", 0x08097A12)):
    data = bytes.fromhex(hexs)
    print(f"bytes {hexs} @0x{addr:08X}:")
    for line in dis(data, addr):
        print(line)

print()
print("=== BASE ROM window 0x08097A0C..0x08097A20 ===")
base = (REPO / "rom" / "base.gba").read_bytes()
for line in dis(base[0x97A0C:0x97A20], 0x08097A0C):
    print(line)

print()
print("=== TEST ROM window 0x08097A0C..0x08097A20 ===")
test = (REPO / "build" / "speaker-test.gba").read_bytes()
for line in dis(test[0x97A0C:0x97A20], 0x08097A0C):
    print(line)

print()
print("=== TEST ROM window 0x08097A20..0x08097A40 (op 0x0E second name) ===")
for line in dis(test[0x97A20:0x97A40], 0x08097A20):
    print(line)

print()
print("=== TEST ROM: every patched window disassembly ===")
import json  # noqa: E402

data = json.loads((REPO / "tools" / "data" / "speaker_name_code_patches.json").read_text(encoding="utf-8"))
for p in data["patches"]:
    off = int(str(p["rom_offset"]), 0)
    before = bytes.fromhex(p["before_hex"])
    after = bytes.fromhex(p["after_hex"])
    print(f"--- reader {p['reader']} {p['site']} @0x{off + 0x08000000:08X} ({len(before)} B) ---")
    print("  BEFORE:")
    for line in dis(before, off + 0x08000000):
        print("   ", line)
    print("  AFTER:")
    for line in dis(after, off + 0x08000000):
        print("   ", line)
