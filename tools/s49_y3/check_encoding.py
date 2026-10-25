#!/usr/bin/env python3
"""Check the encoding of the files this stream wrote: LF only, no BOM."""
import pathlib

FILES = [
    r"D:\Github\gba-naruto\notes\s49-fidelity\Y3-overlay-zero.md",
    r"D:\Github\gba-naruto\tools\s49_overlay_align\compare_overlay_families.py",
    r"D:\Github\gba-naruto\tools\s49_fidelity_report\overlay.py",
    r"D:\Github\gba-naruto\tools\s49_y3\overlay_probe.py",
    r"D:\Github\gba-naruto\tools\s49_y3\remake_overlay_map.py",
    r"D:\Github\gba-naruto\tools\s49_y3\anchor_search.py",
    r"D:\Github\gba-naruto\tools\s49_y3\anchor_diff.py",
    r"D:\Github\gba-naruto\tools\s49_y3\window_scan.py",
    r"D:\Github\gba-naruto\tools\s49_y3\side_by_side.py",
    r"D:\Github\gba-naruto\tools\s49_y3\diff_breakdown.py",
    r"D:\Github\gba-naruto\tools\s49_y3\extract_anchor_vram.py",
    r"D:\Github\gba-naruto\tools\s49_y3\check_unit_ratchet.py",
    r"D:\Github\gba-naruto\tools\s49_y3\show_report.py",
    r"D:\Github\gba-naruto\tools\s49_y3\dump_frames.py",
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include"
       r"\konoha\battle_range_ui_style.h",
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include"
       r"\konoha\grid_pathfinder.h",
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\tests"
       r"\test_battle_range_ui_style.cpp",
]

bad = 0
for name in FILES:
    path = pathlib.Path(name)
    blob = path.read_bytes()
    bom = blob[:3] == b"\xef\xbb\xbf"
    crlf = blob.count(b"\r\n")
    lone_lf = blob.count(b"\n") - crlf
    flag = "OK " if not bom and crlf == 0 else "BAD"
    if flag == "BAD":
        bad += 1
    print(f"{flag} bom={bom!s:<5} crlf={crlf:<4} lf={lone_lf:<5} {name}")
print("files with a problem:", bad)
