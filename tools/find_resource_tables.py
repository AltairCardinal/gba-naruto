#!/usr/bin/env python3
"""Scan GBA ROM for structured resource tables.

Targets:
  1. units — character stats table (HP/atk/def/speed per unit)
  2. skills — skill data (damage/cost/effect per skill)
  3. story_beats — dialogue/story flow table
  4. audio_files — BGM/SFX pointer table
  5. unit_positions — initial battle positions

Strategy:
  - Find pointer tables (arrays of u32 GBA pointers)
  - Find structured data tables (regular stride, plausible values)
  - Cross-reference with known addresses from import_battle_config.py
"""
from __future__ import annotations

import struct
import json
import sys
from pathlib import Path
from collections import Counter, defaultdict

ROM_BASE = 0x08000000
ROM_PATH = Path("/root/gba-naruto/火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba")

def read_u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]

def read_u16(buf: bytes, off: int) -> int:
    return struct.unpack_from("<H", buf, off)[0]

def is_arm_ptr(val: int) -> bool:
    """Check if a value looks like a GBA ROM pointer."""
    return ROM_BASE <= val < ROM_BASE + 0x02000000

def find_pointer_tables(buf: bytes, min_entries: int = 4, max_stride: int = 4) -> list[dict]:
    """Find arrays of consecutive aligned u32 pointers into ROM."""
    results = []
    n = len(buf)
    
    # Look for runs of consecutive u32 values that are all valid ROM pointers
    for stride in [4]:  # Most pointer tables are u32 aligned
        i = 0
        while i < n - 3:
            # Check if this could be start of a pointer table
            if not is_arm_ptr(read_u32(buf, i)):
                i += 4
                continue
            
            # Count consecutive pointers
            start = i
            count = 0
            while i < n - 3 and is_arm_ptr(read_u32(buf, i)):
                count += 1
                i += 4
            
            if count >= min_entries:
                targets = [read_u32(buf, start + j * 4) - ROM_BASE for j in range(count)]
                # Check if targets are sorted (common for tables)
                is_sorted = all(targets[j] <= targets[j+1] for j in range(len(targets)-1))
                # Check if targets are monotonically increasing (text pointers)
                is_monotonic = all(targets[j] < targets[j+1] for j in range(len(targets)-1))
                
                results.append({
                    "offset": start,
                    "count": count,
                    "size": count * 4,
                    "targets": [hex(t) for t in targets[:16]],
                    "sorted": is_sorted,
                    "monotonic": is_monotonic,
                    "target_range": f"0x{min(targets):06X}-0x{max(targets):06X}",
                })
    
    return results

def find_struct_tables(buf: bytes, stride: int, min_entries: int = 4) -> list[dict]:
    """Find tables with regular stride where entries have plausible stat values."""
    results = []
    n = len(buf)
    
    for offset in range(0, n - stride * min_entries, 4):
        # Check if this region has regular structure
        entries = []
        for i in range(min_entries):
            entry_off = offset + i * stride
            if entry_off + stride > n:
                break
            entries.append(buf[entry_off:entry_off + stride])
        
        if len(entries) < min_entries:
            continue
        
        # For unit stats: look for u16 values in range 1-999 (HP/atk/def)
        if stride >= 8:
            plausible = True
            for entry in entries:
                # Check first few u16 values
                for j in range(0, min(stride, 8), 2):
                    val = read_u16(entry, j)
                    if val > 999 and val != 0xFFFF:
                        plausible = False
                        break
                if not plausible:
                    break
            
            if plausible:
                # Verify the pattern continues
                continued = 0
                for i in range(min_entries, min(min_entries + 10, 100)):
                    entry_off = offset + i * stride
                    if entry_off + stride > n:
                        break
                    continued += 1
                
                if continued >= 2:
                    results.append({
                        "offset": hex(offset),
                        "stride": stride,
                        "sample_entries": len(entries) + continued,
                        "first_entry_hex": entries[0].hex(),
                        "second_entry_hex": entries[1].hex(),
                    })
    
    return results

def find_audio_table(buf: bytes) -> list[dict]:
    """Look for audio-related pointer tables (Sappy/M4A format)."""
    results = []
    n = len(buf)
    
    # Sappy sound table signature: look for specific patterns
    # Common: song table pointer at offset 0x04 in Sappy header
    # Also: arrays of {instrument, sample_ptr} structs
    
    # Search for "Sappy" or music engine signatures
    sappy_offsets = []
    for i in range(n - 4):
        # Look for typical Sappy table patterns
        # A valid audio entry often has: u32 voicegroup_ptr, u32 tone_data_ptr
        if i + 8 <= n:
            v1 = read_u32(buf, i)
            v2 = read_u32(buf, i + 4)
            if is_arm_ptr(v1) and is_arm_ptr(v2):
                # Both are pointers - could be audio entry
                target1 = v1 - ROM_BASE
                target2 = v2 - ROM_BASE
                # Audio data tends to be in 0x00xxxx-0x3xxxxx range
                if target1 < 0x400000 and target2 < 0x400000:
                    sappy_offsets.append(i)
    
    return results

def scan_for_unit_stats(buf: bytes) -> list[dict]:
    """Specifically look for unit stat tables."""
    results = []
    n = len(buf)
    
    # Known unit IDs from import_battle_config.py:
    # 0x00=Naruto, 0x01=Sasuke, 0x02=Sakura, 0x03=Sai, 0x04=Kakashi, 0x05=Shikamaru
    # Typical stat table: {u16 hp, u16 atk, u16 def, u16 speed, ...} per unit
    
    # Strategy: look for tables where consecutive entries have different
    # but plausible stat distributions
    
    for stride in [16, 20, 24, 28, 32, 36, 40]:
        for offset in range(0, n - stride * 32, 4):
            # Try to interpret as stat table
            valid_entries = 0
            stats = []
            
            for unit_id in range(32):  # Up to 32 units
                entry_off = offset + unit_id * stride
                if entry_off + stride > n:
                    break
                
                # Read potential stats (first 8 bytes = 4 x u16)
                if stride >= 8:
                    vals = []
                    for j in range(0, min(stride, 12), 2):
                        vals.append(read_u16(buf, entry_off + j))
                    
                    # HP should be 1-999, atk/def/speed 1-255 typically
                    if all(0 < v < 1000 for v in vals[:4]):
                        valid_entries += 1
                        stats.append(vals)
                    else:
                        break
            
            # We expect ~20+ units with valid stats
            if valid_entries >= 20:
                results.append({
                    "offset": hex(offset),
                    "stride": stride,
                    "entries": valid_entries,
                    "sample_stats": stats[:5],
                })
    
    return results

def scan_for_skill_data(buf: bytes) -> list[dict]:
    """Look for skill/ability data tables."""
    results = []
    n = len(buf)
    
    # Skills typically: {u8 id, u8 type, u8 cost, u8 power, u8 accuracy, ...}
    # Look for compact tables with u8/u16 values
    
    for stride in [8, 12, 16, 20, 24]:
        for offset in range(0, n - stride * 32, 4):
            valid = 0
            for i in range(32):
                entry_off = offset + i * stride
                if entry_off + stride > n:
                    break
                
                # Check if first byte looks like an ID (0-255)
                # and subsequent bytes look like game values
                if stride >= 8:
                    b0 = buf[entry_off]
                    b1 = buf[entry_off + 1]
                    # Skill IDs usually start from 1, type field 0-15
                    if 0 < b0 < 128 and b1 < 16:
                        valid += 1
                    else:
                        break
            
            if valid >= 20:
                results.append({
                    "offset": hex(offset),
                    "stride": stride,
                    "entries": valid,
                    "sample": buf[offset:offset+stride*4].hex(),
                })
    
    return results

def find_battle_position_table(buf: bytes) -> list[dict]:
    """Look for battle unit position/initialization data."""
    results = []
    n = len(buf)
    
    # Battle positions are likely stored per-scenario
    # From import_battle_config.py: positions are x,y,team,u8 per unit
    # Scenario config is at 0x53D914+i*32, so positions might be nearby
    
    # Search around known battle config area
    search_regions = [
        (0x53D000, 0x540000, "near battle config"),
        (0x530000, 0x540000, "battle data region"),
    ]
    
    for start, end, region_name in search_regions:
        for offset in range(start, min(end, n - 256), 4):
            # Look for tables of {x, y, team, unit_id} tuples
            # x and y should be 0-63 (map coords), team 0-3, unit_id 0-63
            
            entries = []
            for i in range(25):  # MAX_UNITS = 25
                entry_off = offset + i * 4
                if entry_off + 4 > n:
                    break
                
                x = buf[entry_off]
                y = buf[entry_off + 1]
                team = buf[entry_off + 2]
                unit_id = buf[entry_off + 3]
                
                # Validate ranges
                if x < 64 and y < 64 and team < 4 and unit_id < 64:
                    entries.append({"x": x, "y": y, "team": team, "unit_id": unit_id})
                else:
                    break
            
            if len(entries) >= 4:  # At least 4 units
                results.append({
                    "offset": hex(offset),
                    "region": region_name,
                    "entries": len(entries),
                    "sample": entries[:5],
                })
    
    return results

def scan_for_text_pointers(buf: bytes) -> list[dict]:
    """Find text/dialogue pointer tables (for story_beats)."""
    results = []
    n = len(buf)
    
    # Text pointer tables are arrays of u32 ROM pointers
    # They tend to be monotonically increasing
    # We already know one at 0x461CE8 (dialogue-bank.json)
    
    # Look for tables with 10+ entries pointing to text-like regions
    for i in range(0, n - 40, 4):
        if not is_arm_ptr(read_u32(buf, i)):
            continue
        
        count = 0
        targets = []
        while i + count * 4 + 4 <= n and is_arm_ptr(read_u32(buf, i + count * 4)):
            targets.append(read_u32(buf, i + count * 4) - ROM_BASE)
            count += 1
        
        if count >= 10:
            # Check if targets are monotonically increasing (text table)
            mono = all(targets[j] < targets[j+1] for j in range(len(targets)-1))
            if mono:
                # Check if targets point to regions with text-like bytes
                text_likely = 0
                for t in targets[:5]:
                    if t + 16 <= n:
                        sample = buf[t:t+16]
                        # Count non-zero, non-FF bytes
                        nz = sum(1 for b in sample if 0 < b < 0xFF)
                        if nz >= 8:
                            text_likely += 1
                
                if text_likely >= 3:
                    results.append({
                        "offset": hex(i),
                        "count": count,
                        "target_range": f"0x{min(targets):06X}-0x{max(targets):06X}",
                        "text_likely_score": text_likely,
                    })
    
    return results

def main():
    print(f"Loading ROM: {ROM_PATH}")
    buf = ROM_PATH.read_bytes()
    print(f"ROM size: {len(buf)} bytes ({len(buf)/1024/1024:.1f} MB)")
    
    print("\n=== Scanning for pointer tables ===")
    ptr_tables = find_pointer_tables(buf, min_entries=8)
    print(f"Found {len(ptr_tables)} pointer tables with 8+ entries")
    for pt in ptr_tables[:20]:
        print(f"  0x{pt['offset']:06X}: {pt['count']} entries, targets {pt['target_range']}, sorted={pt['sorted']}")
    
    print("\n=== Scanning for unit stat tables ===")
    unit_stats = scan_for_unit_stats(buf)
    print(f"Found {len(unit_stats)} candidate unit stat tables")
    for us in unit_stats[:10]:
        print(f"  {us['offset']}: stride={us['stride']}, entries={us['entries']}, sample={us['sample_stats'][:3]}")
    
    print("\n=== Scanning for skill data tables ===")
    skill_data = scan_for_skill_data(buf)
    print(f"Found {len(skill_data)} candidate skill tables")
    for sd in skill_data[:10]:
        print(f"  {sd['offset']}: stride={sd['stride']}, entries={sd['entries']}")
    
    print("\n=== Scanning for battle position tables ===")
    positions = find_battle_position_table(buf)
    print(f"Found {len(positions)} candidate position tables")
    for pos in positions[:10]:
        print(f"  {pos['offset']}: {pos['entries']} entries in {pos['region']}, sample={pos['sample'][:3]}")
    
    print("\n=== Scanning for text pointer tables ===")
    text_ptrs = scan_for_text_pointers(buf)
    print(f"Found {len(text_ptrs)} text pointer tables")
    for tp in text_ptrs[:20]:
        print(f"  {tp['offset']}: {tp['count']} entries, range {tp['target_range']}")
    
    # Save results
    report = {
        "pointer_tables": ptr_tables[:50],
        "unit_stat_candidates": unit_stats[:20],
        "skill_data_candidates": skill_data[:20],
        "battle_position_candidates": positions[:20],
        "text_pointer_tables": text_ptrs[:50],
    }
    
    out_path = Path("/root/gba-naruto/notes/resource-table-scan.json")
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nReport saved to {out_path}")

if __name__ == "__main__":
    main()
