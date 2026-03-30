#!/usr/bin/env python3
"""
mGBA headless watchpoint debugger.

Launches mgba-qt (or mgba-sdl) under Xvfb, feeds the built-in CLI debugger
commands via stdin, parses structured output, and produces JSON logs.

Supports two modes:
  --mode watch   Set hardware watchpoints, continue until hit (best for rare writes)
  --mode diff    Frame-by-frame, diff memory each frame (best for frequent writes)
  --mode snapshot Just advance N frames and dump memory (no watchpoints)

Usage:
  # Watchpoint mode - stops at each write to target address
  python3 tools/mgba-headless-snapshot.py \\
    --rom rom/experiment-00076d.gba \\
    --mode watch \\
    --watch 0x0200A900 \\
    --max-hits 5 \\
    --output notes/watch-run.json

  # Diff mode - advance frame by frame, detect changes in memory region
  python3 tools/mgba-headless-snapshot.py \\
    --rom rom/experiment-00076d.gba \\
    --mode diff \\
    --diff-region 0x0200A900:0x150 \\
    --frames 20 \\
    --output notes/diff-run.json

  # Snapshot mode - just dump memory after N frames
  python3 tools/mgba-headless-snapshot.py \\
    --rom rom/experiment-00076d.gba \\
    --mode snapshot \\
    --dump 0x0200A900:256 \\
    --frames 10 \\
    --output notes/snapshot.json
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

MGBA_QT = "/usr/games/mgba-qt"
MGBA_SDL = "/usr/games/mgba"
XVFB = "Xvfb"
XVFB_DISPLAY = ":47"

RE_REGISTER_BLOCK = re.compile(
    r"\s*r0:\s*([0-9A-F]+)\s+r1:\s*([0-9A-F]+)\s+r2:\s*([0-9A-F]+)\s+r3:\s*([0-9A-F]+)\s*\n"
    r"\s*r4:\s*([0-9A-F]+)\s+r5:\s*([0-9A-F]+)\s+r6:\s*([0-9A-F]+)\s+r7:\s*([0-9A-F]+)\s*\n"
    r"\s*r8:\s*([0-9A-F]+)\s+r9:\s*([0-9A-F]+)\s+r10:\s*([0-9A-F]+)\s+r11:\s*([0-9A-F]+)\s*\n"
    r"\s*r12:\s*([0-9A-F]+)\s+r13:\s*([0-9A-F]+)\s+r14:\s*([0-9A-F]+)\s+r15:\s*([0-9A-F]+)\s*\n"
    r"\s*cpsr:\s*([0-9A-F]+)\s+\[([^\]]*)\]\s*\n"
    r"\s*Cycle:\s*(\d+)\s*\n"
    r"\s*([0-9A-F]+):\s+([0-9A-F]+)\s+(.*)"
)

RE_WATCHPOINT_HIT = re.compile(
    r"Hit watchpoint (\d+) at 0x([0-9A-F]+): \(new value = 0x([0-9A-F]+), old value = 0x([0-9A-F]+)\)"
)

RE_MEMORY_LINE = re.compile(r"(0x[0-9A-Fa-f]+):\s+((?:[0-9A-Fa-f]{8}\s*)+)")


def find_mgba():
    """Prefer SDL version (works with SDL_VIDEODRIVER=dummy, no Xvfb needed)."""
    for path in [MGBA_SDL, MGBA_QT]:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    for name in ["mgba", "mgba-qt"]:
        found = shutil.which(name)
        if found:
            return found
    return None


def start_xvfb():
    """Only needed for Qt version. Returns None if not needed."""
    mgba = find_mgba()
    if mgba and "sdl" not in mgba.lower() and mgba != MGBA_SDL:
        proc = subprocess.Popen(
            [XVFB, XVFB_DISPLAY, "-screen", "0", "640x480x16"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)
        if proc.poll() is not None:
            raise RuntimeError(f"Xvfb failed to start (exit code {proc.returncode})")
        return proc
    return None


def run_mgba_commands(mgba_bin, rom_path, commands, env_extra=None, timeout=60):
    """Run mGBA debugger with given commands, return raw output."""
    env = os.environ.copy()
    env["SDL_VIDEODRIVER"] = "dummy"
    env["SDL_AUDIODRIVER"] = "dummy"
    if env_extra:
        env.update(env_extra)

    script = "\n".join(commands) + "\n"
    cmd = [mgba_bin, "-d", "-C", "mute=1", "-C", "volume=0", rom_path]

    proc = subprocess.run(
        cmd, input=script, capture_output=True, text=True,
        timeout=timeout, env=env,
    )
    return proc.stdout, proc.stderr


def build_mem_read_commands(base_addr, size):
    """Build a list of x/4 commands to read 'size' bytes starting at base_addr.
    
    The mGBA debugger only supports x/1, x/2, x/4 (each reads exactly 1 unit).
    To read larger regions, we issue x/4 at successive 16-byte addresses.
    Returns list of command strings.
    """
    cmds = []
    addr = base_addr
    end = base_addr + size
    while addr < end:
        cmds.append(f"x/4 0x{addr:08X}")
        addr += 16  # x/4 reads 4 words = 16 bytes
    return cmds


def parse_mem_block(raw, addr_hex):
    """Parse a single x/4 memory dump line for the given address."""
    addr_key = addr_hex.lower()
    for m in RE_MEMORY_LINE.finditer(raw):
        if m.group(1).lower() == addr_key:
            return [int(w, 16) for w in m.group(2).strip().split()]
    return None


def parse_mem_region(raw, base_addr, size):
    """Parse multiple sequential x/4 dumps into a contiguous byte list."""
    result = []
    addr = base_addr
    end = base_addr + size
    while addr < end:
        addr_hex = f"0x{addr:08X}"
        words = parse_mem_block(raw, addr_hex)
        if words is None:
            result.extend([0] * 4)
        else:
            result.extend(words)
        addr += 16
    return result


def parse_registers(raw):
    """Extract last register state from output."""
    blocks = RE_REGISTER_BLOCK.findall(raw)
    if not blocks:
        return None
    b = blocks[-1]
    return {
        "r0": f"0x{b[0]}", "r1": f"0x{b[1]}", "r2": f"0x{b[2]}", "r3": f"0x{b[3]}",
        "r4": f"0x{b[4]}", "r5": f"0x{b[5]}", "r6": f"0x{b[6]}", "r7": f"0x{b[7]}",
        "r8": f"0x{b[8]}", "r9": f"0x{b[9]}", "r10": f"0x{b[10]}", "r11": f"0x{b[11]}",
        "r12": f"0x{b[12]}", "sp": f"0x{b[13]}", "lr": f"0x{b[14]}", "pc": f"0x{b[15]}",
        "cpsr": f"0x{b[16]}", "flags": b[17],
        "cycle": int(b[18]),
    }


def parse_watchpoint_hits(raw):
    """Parse watchpoint hits and extract register state at each hit."""
    hits = []
    lines = raw.split("\n")
    
    for i, line in enumerate(lines):
        m = RE_WATCHPOINT_HIT.search(line)
        if not m:
            continue
        wp_id, addr, new_val, old_val = m.groups()
        hit = {
            "id": int(wp_id),
            "address": f"0x{addr}",
            "new_value": f"0x{new_val}",
            "old_value": f"0x{old_val}",
        }
        
        # Try to find the register block right after this hit (6 lines of registers + disasm)
        block_text = "\n".join(lines[i+1:i+8])
        reg_match = RE_REGISTER_BLOCK.search(block_text)
        if reg_match:
            b = reg_match.groups()
            hit["pc"] = f"0x{b[15]}"
            hit["lr"] = f"0x{b[14]}"
            hit["sp"] = f"0x{b[13]}"
            hit["cycle"] = int(b[18])
        
        hits.append(hit)
    return hits


def parse_memory_words(raw, addr_hex):
    """Extract memory dump for a specific address from output."""
    addr_key = addr_hex.lower()
    for m in RE_MEMORY_LINE.finditer(raw):
        if m.group(1).lower() == addr_key:
            return [int(w, 16) for w in m.group(2).strip().split()]
    return None


def mode_watch(rom, watch_addr, max_hits, frames_advance, per_hit_timeout, savestate):
    """Watchpoint mode: set watchpoint, continue until hit, repeat."""
    mgba = find_mgba()
    if not mgba:
        return {"error": "No mGBA binary found"}

    hits = []
    total_frames_advanced = 0

    # Build initial commands: advance frames, set watchpoint, continue
    cmds = []
    for _ in range(frames_advance):
        cmds.append("frame")
    cmds.append(f"watch/w 0x{watch_addr:08X}")
    cmds.append("continue")
    cmds.append("status")

    # Run first batch
    env = os.environ.copy()
    env["SDL_VIDEODRIVER"] = "dummy"
    env["SDL_AUDIODRIVER"] = "dummy"

    script = "\n".join(cmds) + "\n"

    proc = subprocess.run(
        [mgba, "-d", "-C", "mute=1", "-C", "volume=0", rom],
        input=script, capture_output=True, text=True,
        timeout=per_hit_timeout, env=env,
    )

    output = proc.stdout
    wp_hits = parse_watchpoint_hits(output)
    reg_state = parse_registers(output)

    for h in wp_hits:
        h["frame_number"] = total_frames_advanced + frames_advance
        hits.append(h)

    return {
        "mode": "watch",
        "watch_address": f"0x{watch_addr:08X}",
        "hits": hits,
        "final_registers": reg_state,
        "raw_output": output,
    }


def mode_diff(rom, region_addr, region_size, num_frames, savestate):
    """Diff mode: advance frame by frame, track memory changes."""
    mgba = find_mgba()
    if not mgba:
        return {"error": "No mGBA binary found"}

    addr_hex = f"0x{region_addr:08X}"

    snapshots = []
    changes = []
    prev_words = None

    # Build commands: for each frame, read memory then advance
    cmds = []
    for f in range(num_frames + 1):
        cmds.extend(build_mem_read_commands(region_addr, region_size))
        if f < num_frames:
            cmds.append("frame")
    cmds.append("quit")

    env = os.environ.copy()
    env["SDL_VIDEODRIVER"] = "dummy"
    env["SDL_AUDIODRIVER"] = "dummy"

    script = "\n".join(cmds) + "\n"

    proc = subprocess.run(
        [mgba, "-d", "-C", "mute=1", "-C", "volume=0", rom],
        input=script, capture_output=True, text=True,
        timeout=60 + num_frames * 5, env=env,
    )

    output = proc.stdout

    # Parse all memory dumps - collect x/4 lines per frame
    lines = output.split("\n")
    frame_dumps = []
    current_frame = []
    
    # Walk through output looking for x/4 memory lines between frame commands
    for line in lines:
        m = RE_MEMORY_LINE.match(line.strip())
        if m and m.group(1).lower() == addr_hex.lower():
            words = [int(w, 16) for w in m.group(2).strip().split()]
            current_frame.extend(words)
            # Check if we've collected enough words for a full region
            needed_words = region_size // 4
            if len(current_frame) >= needed_words:
                frame_dumps.append(current_frame[:needed_words])
                current_frame = []

    # Build snapshots and detect changes
    for i, words in enumerate(frame_dumps):
        frame_num = i
        snapshots.append({
            "frame": frame_num,
            "address": addr_hex,
            "words": [f"0x{w:08X}" for w in words],
        })

        if prev_words is not None and words != prev_words:
            changed_offsets = []
            for j in range(min(len(words), len(prev_words))):
                if words[j] != prev_words[j]:
                    changed_offsets.append({
                        "offset": f"0x{j * 4:04X}",
                        "byte_address": f"0x{region_addr + j * 4:08X}",
                        "old": f"0x{prev_words[j]:08X}",
                        "new": f"0x{words[j]:08X}",
                    })
            changes.append({
                "frame": frame_num,
                "changed_words": len(changed_offsets),
                "details": changed_offsets[:50],  # Limit detail
            })
        prev_words = words

    return {
        "mode": "diff",
        "region": {"address": addr_hex, "size": region_size},
        "frames_requested": num_frames,
        "snapshots_count": len(snapshots),
        "snapshots": snapshots,
        "changes": changes,
        "total_change_events": len(changes),
    }


def mode_snapshot(rom, dumps, frames, savestate):
    """Snapshot mode: advance N frames, dump memory."""
    mgba = find_mgba()
    if not mgba:
        return {"error": "No mGBA binary found"}

    cmds = []
    for _ in range(frames):
        cmds.append("frame")
    cmds.append("status")
    # Use x/4 at successive 16-byte offsets for each dump region
    for addr, size in dumps:
        cmds.extend(build_mem_read_commands(addr, size))
    cmds.append("quit")

    env = os.environ.copy()
    env["SDL_VIDEODRIVER"] = "dummy"
    env["SDL_AUDIODRIVER"] = "dummy"

    script = "\n".join(cmds) + "\n"

    proc = subprocess.run(
        [mgba, "-d", "-C", "mute=1", "-C", "volume=0", rom],
        input=script, capture_output=True, text=True,
        timeout=60 + frames, env=env,
    )

    output = proc.stdout
    reg_state = parse_registers(output)

    mem_dumps = []
    for addr, size in dumps:
        addr_hex = f"0x{addr:08X}"
        words = parse_mem_region(output, addr, size)
        mem_dumps.append({
            "address": addr_hex,
            "size": size,
            "words": [f"0x{w:08X}" for w in words],
        })

    return {
        "mode": "snapshot",
        "frames_advanced": frames,
        "registers": reg_state,
        "memory_dumps": mem_dumps,
    }


def main():
    parser = argparse.ArgumentParser(description="mGBA headless watchpoint debugger")
    parser.add_argument("--rom", required=True, help="Path to GBA ROM file")
    parser.add_argument("--mode", choices=["watch", "diff", "snapshot"], default="snapshot",
                        help="Operation mode (default: snapshot)")
    parser.add_argument("--watch", type=str, default=None,
                        help="Watchpoint address for watch mode (hex)")
    parser.add_argument("--max-hits", type=int, default=10,
                        help="Max watchpoint hits to capture (watch mode)")
    parser.add_argument("--diff-region", type=str, default=None,
                        help="Region for diff mode: ADDRESS:SIZE (hex)")
    parser.add_argument("--dump", action="append", default=[],
                        help="Memory dump spec: ADDRESS:SIZE (hex)")
    parser.add_argument("--frames", type=int, default=5,
                        help="Number of frames to advance")
    parser.add_argument("--savestate", default=None, help="Savestate file")
    parser.add_argument("--output", default=None, help="Output JSON file")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout seconds")
    parser.add_argument("--per-hit-timeout", type=int, default=30,
                        help="Timeout per watchpoint hit (watch mode)")

    args = parser.parse_args()

    if not os.path.isfile(args.rom):
        print(f"ERROR: ROM not found: {args.rom}", file=sys.stderr)
        sys.exit(1)

    xvfb_proc = None
    try:
        xvfb_proc = start_xvfb()

        if args.mode == "watch":
            if not args.watch:
                print("ERROR: --watch required for watch mode", file=sys.stderr)
                sys.exit(1)
            addr = int(args.watch, 16)
            result = mode_watch(
                args.rom, addr, args.max_hits, args.frames,
                args.per_hit_timeout, args.savestate,
            )

        elif args.mode == "diff":
            if not args.diff_region:
                print("ERROR: --diff-region required for diff mode", file=sys.stderr)
                sys.exit(1)
            parts = args.diff_region.split(":")
            region_addr = int(parts[0], 16)
            region_size = int(parts[1], 16) if parts[1].startswith("0x") else int(parts[1])
            result = mode_diff(
                args.rom, region_addr, region_size, args.frames, args.savestate,
            )

        else:  # snapshot
            dumps = []
            for spec in args.dump:
                parts = spec.split(":")
                addr = int(parts[0], 16)
                size = int(parts[1], 16) if parts[1].startswith("0x") else int(parts[1])
                dumps.append((addr, size))
            result = mode_snapshot(args.rom, dumps, args.frames, args.savestate)

        json_str = json.dumps(result, indent=2, ensure_ascii=False)

        if args.output:
            with open(args.output, "w") as f:
                f.write(json_str)
            print(f"Output written to {args.output}")
            if "hits" in result:
                print(f"  {len(result['hits'])} watchpoint hits")
            if "changes" in result:
                print(f"  {result['total_change_events']} change events")
            if "memory_dumps" in result:
                print(f"  {len(result['memory_dumps'])} memory dumps")
        else:
            print(json_str)

    finally:
        if xvfb_proc:
            xvfb_proc.terminate()
            try:
                xvfb_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                xvfb_proc.kill()


if __name__ == "__main__":
    main()
