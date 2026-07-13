#!/usr/bin/env python3
"""
mGBA headless watchpoint debugger.

Launches mgba-qt (or mgba-sdl) under Xvfb, feeds the built-in CLI debugger
commands via stdin, parses structured output, and produces JSON logs.

Supports five modes:
  --mode watch   Set hardware watchpoints, continue until hit (best for rare writes)
  --mode diff    Frame-by-frame, diff memory each frame (best for frequent writes)
  --mode snapshot Just advance N frames and dump memory (no watchpoints)
  --mode probe   Break at a ROM PC, then read ROM/WRAM in the stopped context
  --mode audio   Capture chronological MP2K FIFO chunks from a controlled ROM

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

  # Stop in the map loader, then capture the selected map row and unit WRAM
  python3 tools/mgba-headless-snapshot.py \\
    --rom rom/base.gba \\
    --mode probe \\
    --breakpoint 0x08068FF0 \\
    --read 0x0853D910:32 \\
    --read 0x02024290:64 \\
    --frames 0 \\
    --output notes/map-position-probe.json
"""

import argparse
import hashlib
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

RE_BREAKPOINT_HIT = re.compile(r"Hit breakpoint (\d+) at 0x([0-9A-Fa-f]+)")

RE_MEMORY_LINE = re.compile(r"(0x[0-9A-Fa-f]+):\s+((?:[0-9A-Fa-f]{8}\s*)+)")

MP2K_MAGIC = 0x68736D53
SOUND_MAIN_RETURN = 0x0809AABA
SOUND_INFO = 0x03006570
SOUND_INFO_HEADER_SIZE = 0x50
SOUND_INFO_SIZE = 0x350
DIRECT_RIGHT = SOUND_INFO + 0x350
DIRECT_LEFT = SOUND_INFO + 0x980
CGB_STATE = 0x030075B0
CGB_STATE_SIZE = 0x100
PLAYER_STATE = 0x030076B0
PLAYER_STATE_SIZE = 0x110
CGB_IO = 0x04000060
CGB_IO_SIZE = 0x30
BUFFER_FRAMES = 264
PCM_RING_CHUNKS = 6


def find_mgba():
    """Prefer SDL version (works with SDL_VIDEODRIVER=dummy, no Xvfb needed)."""
    explicit = os.environ.get("MGBA_BIN")
    if explicit and os.path.isfile(explicit) and os.access(explicit, os.X_OK):
        return explicit
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


def build_mgba_command(mgba_bin, rom_path, savestate=None):
    """Build the mGBA debugger command line.

    mGBA loads savestates through the native -t/--savestate option, not through
    the CLI debugger stdin. Keep it before the ROM filename so mGBA's getopt
    parser consumes it as an emulator option.
    """
    cmd = [mgba_bin, "-d", "-C", "mute=1", "-C", "volume=0"]
    if savestate:
        cmd.extend(["--savestate", savestate])
    cmd.append(rom_path)
    return cmd


def build_mgba_env(mgba_bin, env_extra=None):
    env = os.environ.copy()
    env["SDL_VIDEODRIVER"] = "dummy"
    env["SDL_AUDIODRIVER"] = "dummy"
    if "qt" in os.path.basename(mgba_bin).lower():
        env.setdefault("DISPLAY", XVFB_DISPLAY)
    if env_extra:
        env.update(env_extra)
    return env


def run_mgba_commands(mgba_bin, rom_path, commands, env_extra=None, timeout=60, savestate=None):
    """Run mGBA debugger with given commands, return raw output."""
    env = build_mgba_env(mgba_bin, env_extra)

    script = "\n".join(commands) + "\n"
    cmd = build_mgba_command(mgba_bin, rom_path, savestate)

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


def build_probe_commands(breakpoint_addr, reads, frames=0):
    """Build one deterministic execution-breakpoint/read command sequence."""
    commands = ["frame"] * frames
    commands.extend([f"b 0x{breakpoint_addr:08X}", "continue", "status"])
    for addr, size in reads:
        commands.extend(build_mem_read_commands(addr, size))
    commands.append("quit")
    return commands


def parse_probe_output(raw, breakpoint_addr, reads):
    """Turn debugger output into evidence tied to an actual breakpoint hit."""
    matches = list(RE_BREAKPOINT_HIT.finditer(raw))
    hit = matches[-1] if matches else None
    memory_reads = []
    for addr, size in reads:
        words = parse_mem_region(raw, addr, size)
        word_count = (size + 3) // 4
        memory_reads.append({
            "address": f"0x{addr:08X}",
            "size": size,
            "words": [f"0x{word:08X}" for word in words[:word_count]],
        })
    return {
        "mode": "probe",
        "breakpoint": f"0x{breakpoint_addr:08X}",
        "hit": hit is not None,
        "hit_pc": f"0x{int(hit.group(2), 16):08X}" if hit else None,
        "breakpoint_id": int(hit.group(1)) if hit else None,
        "registers": parse_registers(raw) if hit else None,
        "memory_reads": memory_reads if hit else [],
    }


def audio_chunk_index(invocation):
    """Return the physical FIFO chunk for a clean controlled dispatch."""
    if invocation < 0:
        raise ValueError("audio invocation must be non-negative")
    return invocation % PCM_RING_CHUNKS


def build_audio_capture_commands(invocations):
    if invocations <= 0:
        raise ValueError("audio invocation count must be positive")
    commands = [f"b 0x{SOUND_MAIN_RETURN:08X}"]
    for invocation in range(invocations):
        chunk = audio_chunk_index(invocation)
        commands.extend(("continue", "status"))
        commands.extend(build_mem_read_commands(SOUND_INFO, SOUND_INFO_SIZE))
        commands.extend(build_mem_read_commands(CGB_STATE, CGB_STATE_SIZE))
        commands.extend(build_mem_read_commands(PLAYER_STATE, PLAYER_STATE_SIZE))
        commands.extend(build_mem_read_commands(
            DIRECT_RIGHT + chunk * BUFFER_FRAMES, BUFFER_FRAMES,
        ))
        commands.extend(build_mem_read_commands(
            DIRECT_LEFT + chunk * BUFFER_FRAMES, BUFFER_FRAMES,
        ))
        commands.extend(build_mem_read_commands(CGB_IO, CGB_IO_SIZE))
    commands.append("quit")
    return commands


def _parse_region_bytes(raw, base_addr, size):
    data = bytearray()
    for addr in range(base_addr, base_addr + size, 16):
        words = parse_mem_block(raw, f"0x{addr:08X}")
        if words is None:
            raise ValueError(f"missing mGBA memory row at 0x{addr:08X}")
        for word in words:
            data.extend(word.to_bytes(4, "little"))
    return bytes(data[:size])


def _audio_hit_segments(raw):
    matches = [
        match for match in RE_BREAKPOINT_HIT.finditer(raw)
        if int(match.group(2), 16) == SOUND_MAIN_RETURN
    ]
    return [
        raw[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(raw)]
        for index, match in enumerate(matches)
    ]


def parse_audio_capture_output(raw, invocations):
    """Parse chronological FIFO/state reads after a clean controlled dispatch."""
    segments = _audio_hit_segments(raw)
    if len(segments) < invocations:
        raise ValueError(
            f"expected {invocations} SoundMain hits, found {len(segments)}"
        )

    captures = []
    combined_pcm = bytearray()
    for invocation, segment in enumerate(segments[:invocations]):
        chunk = audio_chunk_index(invocation)
        sound_info = _parse_region_bytes(segment, SOUND_INFO, SOUND_INFO_SIZE)
        if int.from_bytes(sound_info[:4], "little") != MP2K_MAGIC:
            raise ValueError(
                f"SoundInfo magic does not match MP2K at invocation {invocation}"
            )
        cgb_state = _parse_region_bytes(segment, CGB_STATE, CGB_STATE_SIZE)
        player_state = _parse_region_bytes(segment, PLAYER_STATE, PLAYER_STATE_SIZE)
        right = _parse_region_bytes(
            segment, DIRECT_RIGHT + chunk * BUFFER_FRAMES, BUFFER_FRAMES
        )
        left = _parse_region_bytes(
            segment, DIRECT_LEFT + chunk * BUFFER_FRAMES, BUFFER_FRAMES
        )
        cgb_io = _parse_region_bytes(segment, CGB_IO, CGB_IO_SIZE)
        pcm = bytearray()
        for right_sample, left_sample in zip(right, left):
            pcm.extend((right_sample, left_sample))
        combined_pcm.extend(pcm)
        captures.append({
            "invocation": invocation,
            "chunk_index": chunk,
            "counter": sound_info[4],
            "sound_info_header_hex": sound_info[:SOUND_INFO_HEADER_SIZE].hex(),
            "direct_channels_hex": sound_info[SOUND_INFO_HEADER_SIZE:].hex(),
            "direct_channels_sha256": hashlib.sha256(
                sound_info[SOUND_INFO_HEADER_SIZE:]
            ).hexdigest(),
            "cgb_state_hex": cgb_state.hex(),
            "cgb_state_sha256": hashlib.sha256(cgb_state).hexdigest(),
            "player_state_hex": player_state.hex(),
            "player_state_sha256": hashlib.sha256(player_state).hexdigest(),
            "cgb_io_hex": cgb_io.hex(),
            "right_hex": right.hex(),
            "left_hex": left.hex(),
            "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
            "nonzero_frames": sum(
                right_sample != 0 or left_sample != 0
                for right_sample, left_sample in zip(right, left)
            ),
        })
    expected_counters = [0] + [
        PCM_RING_CHUNKS - (invocation - 1) % PCM_RING_CHUNKS
        for invocation in range(1, invocations)
    ]
    observed_counters = [capture["counter"] for capture in captures]
    return {
        "format": "gba-naruto-mgba-mp2k-capture-v1",
        "initial_counter": captures[0]["counter"],
        "invocation_count": invocations,
        "counter_sequence_valid": observed_counters == expected_counters,
        "combined_pcm_sha256": hashlib.sha256(combined_pcm).hexdigest(),
        "combined_nonzero_frames": sum(
            capture["nonzero_frames"] for capture in captures
        ),
        "captures": captures,
    }


def mode_audio(rom, sound_id, invocations, timeout):
    mgba = find_mgba()
    if not mgba:
        return {"error": "No mGBA binary found"}
    commands = build_audio_capture_commands(invocations)
    try:
        stdout, stderr = run_mgba_commands(
            mgba, rom, commands, timeout=timeout,
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or exc.output or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        timed_out = True
    try:
        result = parse_audio_capture_output(stdout, invocations)
    except ValueError as exc:
        result = {
            "format": "gba-naruto-mgba-mp2k-capture-v1",
            "error": str(exc),
            "soundmain_hits": len(_audio_hit_segments(stdout)),
        }
    result.update({
        "mode": "audio",
        "sound_id": sound_id,
        "rom": rom,
        "stderr": stderr,
        "timed_out": timed_out,
    })
    return result


def mode_probe(rom, breakpoint_addr, reads, frames, timeout, savestate=None):
    """Stop at a known PC and capture ROM/WRAM reads in the same process."""
    mgba = find_mgba()
    if not mgba:
        return {"error": "No mGBA binary found"}
    commands = build_probe_commands(breakpoint_addr, reads, frames)
    try:
        stdout, stderr = run_mgba_commands(
            mgba, rom, commands, timeout=timeout, savestate=savestate,
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or exc.output or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        timed_out = True
    result = parse_probe_output(stdout, breakpoint_addr, reads)
    result["savestate"] = savestate
    result["stderr"] = stderr
    result["timed_out"] = timed_out
    return result


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
    env = build_mgba_env(mgba)

    script = "\n".join(cmds) + "\n"

    proc = subprocess.run(
        build_mgba_command(mgba, rom, savestate),
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
        "savestate": savestate,
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

    env = build_mgba_env(mgba)

    script = "\n".join(cmds) + "\n"

    proc = subprocess.run(
        build_mgba_command(mgba, rom, savestate),
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
        "savestate": savestate,
        "frames_requested": num_frames,
        "snapshots_count": len(snapshots),
        "snapshots": snapshots,
        "changes": changes,
        "total_change_events": len(changes),
    }


def mode_snapshot(rom, dumps, frames, savestate, timeout=60):
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

    env = build_mgba_env(mgba)

    script = "\n".join(cmds) + "\n"

    try:
        proc = subprocess.run(
            build_mgba_command(mgba, rom, savestate),
            input=script, capture_output=True, text=True,
            timeout=timeout + frames, env=env,
        )
        output = proc.stdout
        stderr = proc.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or exc.output or ""
        stderr = exc.stderr or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        timed_out = True
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
        "savestate": savestate,
        "frames_advanced": frames,
        "registers": reg_state,
        "memory_dumps": mem_dumps,
        "stderr": stderr,
        "timed_out": timed_out,
    }


def main():
    parser = argparse.ArgumentParser(description="mGBA headless watchpoint debugger")
    parser.add_argument("--rom", required=True, help="Path to GBA ROM file")
    parser.add_argument("--mode", choices=["watch", "diff", "snapshot", "probe", "audio"], default="snapshot",
                        help="Operation mode (default: snapshot)")
    parser.add_argument("--watch", type=str, default=None,
                        help="Watchpoint address for watch mode (hex)")
    parser.add_argument("--max-hits", type=int, default=10,
                        help="Max watchpoint hits to capture (watch mode)")
    parser.add_argument("--diff-region", type=str, default=None,
                        help="Region for diff mode: ADDRESS:SIZE (hex)")
    parser.add_argument("--dump", action="append", default=[],
                        help="Memory dump spec: ADDRESS:SIZE (hex)")
    parser.add_argument("--read", action="append", default=[],
                        help="Probe read spec after PC hit: ADDRESS:SIZE")
    parser.add_argument("--breakpoint", default=None,
                        help="Execution address for probe mode (hex)")
    parser.add_argument("--frames", type=int, default=5,
                        help="Number of frames to advance")
    parser.add_argument("--savestate", default=None, help="Savestate file")
    parser.add_argument("--output", default=None, help="Output JSON file")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout seconds")
    parser.add_argument("--per-hit-timeout", type=int, default=30,
                        help="Timeout per watchpoint hit (watch mode)")
    parser.add_argument("--sound-id", type=lambda value: int(value, 0), default=None,
                        help="Controlled sound ID label for audio mode")
    parser.add_argument("--invocations", type=int, default=8,
                        help="SoundMain FIFO chunks to capture in audio mode")

    args = parser.parse_args()

    if not os.path.isfile(args.rom):
        print(f"ERROR: ROM not found: {args.rom}", file=sys.stderr)
        sys.exit(1)
    if args.savestate and not os.path.isfile(args.savestate):
        print(f"ERROR: savestate not found: {args.savestate}", file=sys.stderr)
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

        elif args.mode == "probe":
            if not args.breakpoint:
                print("ERROR: --breakpoint required for probe mode", file=sys.stderr)
                sys.exit(1)
            reads = []
            for spec in args.read:
                parts = spec.split(":")
                addr = int(parts[0], 16)
                size = int(parts[1], 16) if parts[1].startswith("0x") else int(parts[1])
                reads.append((addr, size))
            result = mode_probe(
                args.rom, int(args.breakpoint, 16), reads, args.frames, args.timeout,
                args.savestate,
            )

        elif args.mode == "audio":
            if args.sound_id is None:
                print("ERROR: --sound-id required for audio mode", file=sys.stderr)
                sys.exit(1)
            result = mode_audio(
                args.rom, args.sound_id, args.invocations, args.timeout,
            )

        else:  # snapshot
            dumps = []
            for spec in args.dump:
                parts = spec.split(":")
                addr = int(parts[0], 16)
                size = int(parts[1], 16) if parts[1].startswith("0x") else int(parts[1])
                dumps.append((addr, size))
            result = mode_snapshot(
                args.rom, dumps, args.frames, args.savestate,
                timeout=min(args.timeout, 60),
            )

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
