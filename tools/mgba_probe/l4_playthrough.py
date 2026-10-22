#!/usr/bin/env python3
"""L4 playthrough harness: drive the game through every story scene.

Why this tool exists
--------------------
The completion ladder's L4 level is *"55 场景 × 3 配置全流程打通并逐场留证"*.
Playing the 55 scenes by hand (or one boot per scene from the title screen)
is not reproducible and not checkable, so the harness needs a way to make the
game **dispatch an arbitrary scene** and then let that scene play normally.

The mechanism (proved on this ROM, see
``notes/evidence/l4-playthrough-20261021.md``):

* the story dispatcher ``0x0808F544`` takes the **scene number in r0**
  (L2 evidence: it was hit with r0 = 0x36 = 54 and the VM then received
  ``before_root[54]``);
* the 'next scene' path at ``0x0808F8DC`` reads that number as a byte from
  ``[r4 + 0x16]``, where r4 is the story flag block ``0x020311D4`` — so the
  byte lives at **0x020311EA**;
* therefore poking N into ``0x020311EA`` while the game is parked on
  ``0x0808F8DC`` makes the game dispatch scene N.  Measured: poking 40 made
  the VM entry receive r0 = 0x08031430 = ``before_root[40]``, exactly.

The harness therefore breaks on both addresses, pokes the next target scene
number, lets the scene play (B advances the dialogue), and records, per
scene: the VM script pointer the game actually ran, the scene byte, the
frame count, and a screenshot.  A scene only counts as *reached* when the
script pointer the VM received equals the root table entry for that scene —
the game can therefore not be fooled by a scene that merely "looked" right.

Usage:
    python tools/mgba_probe/l4_playthrough.py rom/base.gba --scenes 1-55 \
        --out build/l4
    python tools/mgba_probe/l4_playthrough.py rom/base.gba --scenes 1-3 --json build/l4.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import queue
import re
import struct
import subprocess
import sys
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

ROM_BASE = 0x08000000
STORY_STATE = 0x020311D4          # story flag block
SCENE_BYTE = STORY_STATE + 0x16   # 0x020311EA -- the scene number
NEXT_SCENE = 0x0808F8DC            # 'ldrb r0,[r4,#0x16]' in the next-scene path
VM_ENTRY = 0x080977B8              # story VM entry
BEFORE_ROOT = 0x060C74             # file offset of the before root table
AFTER_ROOT = 0x060D54              # file offset of the after root table

KEY_BITS = {
    "A": 0x001, "B": 0x002, "SELECT": 0x004, "START": 0x008,
    "RIGHT": 0x010, "LEFT": 0x020, "UP": 0x040, "DOWN": 0x080, "R": 0x100, "L": 0x200,
}
HIT_RE = re.compile(r"(?:Hit breakpoint|Hit watchpoint)\s+#?(\d+)\s+at\s+(0x[0-9a-fA-F]+)")


class Probe:
    """A live probe process with a command/response protocol."""

    def __init__(self, exe: pathlib.Path, rom: pathlib.Path, timeout: float = 900.0):
        self.proc = subprocess.Popen(
            [str(exe), str(rom)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        self.deadline = time.monotonic() + timeout
        self.stderr_lines: list[str] = []
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        self._read_line()  # banner

    def _drain_stderr(self) -> None:
        assert self.proc.stderr is not None
        for line in self.proc.stderr:
            self.stderr_lines.append(line.rstrip("\n"))

    def _read_line(self) -> str | None:
        assert self.proc.stdout is not None
        result: queue.Queue[str | None] = queue.Queue()
        reader = threading.Thread(target=lambda: result.put(self.proc.stdout.readline()),
                                 daemon=True)
        reader.start()
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("probe timed out")
        reader.join(timeout=remaining)
        if reader.is_alive():
            raise TimeoutError("probe timed out")
        line = result.get()
        return line if line else None

    def send(self, command: str) -> list[str]:
        assert self.proc.stdin is not None
        token = f"__end_{len(self.stderr_lines)}_{abs(hash(command)) % 9973}"
        self.proc.stdin.write(f"{command}\necho {token}\n")
        self.proc.stdin.flush()
        lines: list[str] = []
        while True:
            line = self._read_line()
            if line is None:
                raise EOFError("probe exited")
            line = line.rstrip("\r\n")
            if line.strip() == token:
                return lines
            lines.append(line)

    def registers(self) -> dict[str, int]:
        # mGBA prints `r0: 00000001` -- the value is hex *without* a 0x
        # prefix, so it must not be parsed as decimal.
        from tools.mgba_probe.runtime_probe import parse_status
        return parse_status(self.send("status"))

    def read_bytes(self, address: int, length: int) -> bytes:
        out = self.send(f"dump 0x{address:08X} {length}")
        payload: list[str] = []
        for line in out:
            line = line.strip()
            if line.startswith("DUMP"):
                continue
            if line.startswith("ENDDUMP"):
                break
            payload.append(line)
        try:
            return bytes.fromhex("".join(payload))
        except ValueError:
            return b""

    def close(self) -> None:
        try:
            self.send("quit")
        except Exception:
            pass
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            try:
                self.proc.wait(timeout=5)
            except Exception:
                pass


def write_png(path: pathlib.Path, rgba: bytes, width: int = 240, height: int = 160) -> None:
    """Minimal RGBA -> PNG writer (mGBA's own PNG support is not built in)."""
    import zlib

    raw = b"".join(b"\x00" + rgba[y * width * 4:(y + 1) * width * 4]
                   for y in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def capture(probe: Probe, path: pathlib.Path) -> str | None:
    """Save the probe's own rendered frame as a PNG."""
    import tempfile
    import os

    handle, raw_path = tempfile.mkstemp(suffix=".rgba")
    os.close(handle)
    try:
        probe.send(f"rawshot {raw_path}")
        data = pathlib.Path(raw_path).read_bytes()
        if len(data) < 240 * 160 * 4:
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        write_png(path, data[:240 * 160 * 4])
        return str(path)
    finally:
        try:
            os.unlink(raw_path)
        except OSError:
            pass


def arm(probe: Probe, address: int) -> int | None:
    for line in probe.send(f"b {address:#x}"):
        if "breakpoint #" in line:
            return int(line.split("#")[1].split()[0])
    return None


def rearm(probe: Probe, armed: dict[int, int]) -> None:
    """Re-arm every breakpoint.

    A breakpoint that fired stays armed, so the next `cont` reports the
    same address again and the game never moves.  The cycle is
    `delete <id>` -> re-`b <addr>`.
    """
    for address, ident in list(armed.items()):
        probe.send(f"delete {ident}")
        armed[address] = arm(probe, address) or 0


def root_pointers(rom: bytes) -> dict[int, int]:
    """scene number -> script pointer, for the before and after root tables.

    The tables are indexed by the scene number directly (word 0 is unused):
    ``before_root[54] = 0x08049E76`` is the L2-proved scene-54 script.
    """
    out: dict[int, int] = {}
    for base in (BEFORE_ROOT, AFTER_ROOT):
        for scene in range(1, 64):
            off = base + scene * 4
            if off + 4 > len(rom):
                break
            value = struct.unpack_from("<I", rom, off)[0]
            if ROM_BASE <= value < ROM_BASE + len(rom):
                out.setdefault(scene, value)
    return out


def parse_scenes(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("rom", nargs="?", default="rom/base.gba")
    parser.add_argument("--exe", type=pathlib.Path,
                        default=REPO / "build" / "mgba-probe" / "mgba-probe.exe")
    parser.add_argument("--scenes", default="1-55",
                        help="scene list, e.g. '1-55' or '1,2,5-9'")
    parser.add_argument("--boot-frames", type=int, default=1500)
    parser.add_argument("--nav", default="START:8,A:8,A:8,A:8,A:20",
                        help="press plan to reach the first scene dispatch")
    parser.add_argument("--play-frames", type=int, default=900,
                        help="frame budget for one scene to play out")
    parser.add_argument("--play-keys", default="A",
                        help="keys cycled while a scene plays (A advances the "
                             "dialogue; B opens the help panel in this game)")
    parser.add_argument("--settle-frames", type=int, default=120,
                        help="frames with no key held after a press; the game "
                             "only reacts to a press edge, so this window has "
                             "to be long enough (the L3 evidence used 120)")
    parser.add_argument("--gap-frames", type=int, default=6)
    parser.add_argument("--press-gap", type=int, default=2)
    parser.add_argument("--out", type=pathlib.Path, default=None,
                        help="directory for the per-scene screenshots")
    parser.add_argument("--json", type=pathlib.Path, default=None)
    args = parser.parse_args(argv)

    if not args.exe.exists():
        print(f"ERR {args.exe} missing; run: python tools/mgba_probe/build.py",
              file=sys.stderr)
        return 2
    rom_path = pathlib.Path(args.rom)
    if not rom_path.is_file():
        print(f"ERR ROM not found: {rom_path}", file=sys.stderr)
        return 2
    rom = rom_path.read_bytes()
    roots = root_pointers(rom)
    scenes = parse_scenes(args.scenes)

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    plan: list[tuple[str, int]] = []
    for item in args.nav.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            key, n = item.split(":", 1)
            plan.append((key.strip(), int(n)))
        else:
            plan.append((item, 8))

    def navigate(probe: Probe, armed: dict[int, int]) -> None:
        """Press the nav plan until the game sits on the scene dispatch.

        The core must be *parked* on `0x0808F8DC` when the scene byte is
        poked, so the navigation stops at the first breakpoint hit.
        """
        for key, frames in plan:
            out = probe.send(f"frames {frames} {KEY_BITS[key]:#05x}")
            hit = None
            for line in out:
                m = HIT_RE.search(line)
                if m:
                    hit = (int(m.group(1), 16), int(m.group(2), 16))
                    break
            if hit is None:
                out = probe.send(f"frames {args.settle_frames} 0x000")
                for line in out:
                    m = HIT_RE.search(line)
                    if m:
                        hit = (int(m.group(1), 16), int(m.group(2), 16))
                        break
            if hit:
                return

    def boot() -> tuple[Probe, dict[int, int]]:
        probe = Probe(args.exe, rom_path)
        probe.send(f"frames {args.boot_frames} 0x000")
        armed = {NEXT_SCENE: arm(probe, NEXT_SCENE) or 0,
                 VM_ENTRY: arm(probe, VM_ENTRY) or 0}
        return probe, armed

    results: list[dict] = []
    probe, armed = boot()
    print("armed: " + ", ".join(f"0x{a:08X}#{i}" for a, i in armed.items()))
    navigate(probe, armed)
    try:
        # --- the scene loop ----------------------------------------------
        #
        # One boot per scene: the harness dispatches the scene, lets it run
        # for a while (the dialogue really advances) and records the proof
        # that the game entered *that* scene -- the VM script pointer the
        # game itself used must equal the root table entry for the scene.
        # A per-scene boot keeps the evidence independent of whether the
        # scene ends on its own (some scenes wait for a choice or a battle).
        for index, scene in enumerate(scenes):
            if index:
                probe.close()
                probe, armed = boot()
                navigate(probe, armed)

            # 1. make the game dispatch this scene
            probe.send(f"poke 0x{SCENE_BYTE:08X} {scene}")
            probe.send("next")          # step past the ldrb so it reads the new byte
            out = probe.send("cont 1200")
            hit = None
            for line in out:
                m = HIT_RE.search(line)
                if m:
                    hit = (int(m.group(1), 16), int(m.group(2), 16))
                    break
            if hit is None:
                results.append({"scene": scene, "status": "no-dispatch"})
                print(f"scene {scene:3}: no dispatch")
                break
            regs = probe.registers()
            script = regs.get("r0", 0)
            expected = roots.get(scene)
            record = {
                "scene": scene,
                "status": "reached" if expected and script == expected else "mismatch",
                "script_pointer": f"0x{script:08X}",
                "expected": f"0x{expected:08X}" if expected else None,
                "scene_byte": f"0x{SCENE_BYTE:08X}",
                "hit_at": f"0x{hit[1]:08X}",
            }
            if args.out:
                args.out.mkdir(parents=True, exist_ok=True)
                record["screenshot"] = capture(
                    probe, args.out / f"scene-{scene:02d}.png")
            results.append(record)
            print(f"scene {scene:3}: {record['status']:<8} "
                  f"script={record['script_pointer']} expected={record['expected']} "
                  f"hit={record['hit_at']}")
            # the core is parked on the VM entry: step past it and re-arm
            probe.send("next")
            rearm(probe, armed)

            # 2. let the scene play out until the next dispatch
            #
            # The press recipe is the one the L3 evidence used: hold the key
            # for 8 frames, then release it for `settle_frames`.  The game
            # only reacts to a *press edge* (0x0300000E), so the release
            # window has to be long enough for the game to sample the key
            # as "newly pressed" and then as "not held".
            frames = 0
            next_seen = False
            keys = tuple(k.strip() for k in args.play_keys.split(",") if k.strip())
            turn = 0
            while frames < args.play_frames:
                key = keys[turn % len(keys)]
                turn += 1
                out = probe.send(f"frames 8 {KEY_BITS[key]:#05x}")
                frames += 8
                hit = None
                for line in out:
                    m = HIT_RE.search(line)
                    if m:
                        hit = (int(m.group(1), 16), int(m.group(2), 16))
                        break
                if hit is None:
                    probe.send(f"frames {args.settle_frames} 0x000")
                    frames += args.settle_frames
                    out = probe.send("cont 240")
                    for line in out:
                        m = HIT_RE.search(line)
                        if m:
                            hit = (int(m.group(1), 16), int(m.group(2), 16))
                            break
                if hit and hit[1] == NEXT_SCENE:
                    next_seen = True
                    break
                if hit:
                    print(f"    play: hit at 0x{hit[1]:08X} after {frames} frames")
                if hit and hit[1] == VM_ENTRY:
                    # the scene started another script segment: keep playing
                    record.setdefault("extra_vm_entries", 0)
                    record["extra_vm_entries"] += 1
                if hit:
                    probe.send("next")
                    rearm(probe, armed)
            record["play_frames"] = frames
            record["reached_next_dispatch"] = next_seen
            # Machine-checkable battle evidence: the battle control block
            # 0x02026804 and the 12-slot unit array at 0x020240C0 (stride
            # 0x1D4, character id at +0).  A non-empty unit array means a
            # battle was really set up for this scene.
            ctrl = probe.read_bytes(0x02026804, 8)
            record["battle_ctrl"] = ctrl.hex()
            units = 0
            for slot in range(12):
                unit = probe.read_bytes(0x020240C0 + slot * 0x1D4, 1)
                if unit and unit[0]:
                    units += 1
            record["battle_units"] = units
            record["battle_started"] = units > 0
            if args.out:
                record["screenshot_end"] = capture(
                    probe, args.out / f"scene-{scene:02d}-end.png")
            print(f"          play: {frames} frames, "
                  f"battle_ctrl={record['battle_ctrl']} "
                  f"units={record['battle_units']} "
                  f"battle_started={record['battle_started']} "
                  f"next_dispatch={record['reached_next_dispatch']}")
            # 3. re-arm (a breakpoint that fired stays armed and would fire again)
            for address, ident in list(armed.items()):
                probe.send(f"delete {ident}")
                armed[address] = arm(probe, address) or 0
    finally:
        probe.close()

    report = {
        "rom": str(rom_path),
        "scenes_requested": scenes,
        "scene_byte": f"0x{SCENE_BYTE:08X}",
        "results": results,
        "reached": sum(1 for r in results if r.get("status") == "reached"),
        "total": len(results),
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8", newline="\n")
    print(f"\nreached {report['reached']}/{report['total']} scene(s)")
    return 0 if report["reached"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
