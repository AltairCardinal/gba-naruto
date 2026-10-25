#!/usr/bin/env python3
"""Drive the headless mGBA probe and return structured JSON.

The probe (tools/mgba_probe/host_main.c) reads debugger commands from stdin
and writes their output to stdout.  Each command is terminated by an `echo`
sentinel so the client can attribute output to the right command even when a
command produces an arbitrary amount of text.

Usage:
    python tools/mgba_probe/probe_client.py --rom rom/base.gba --script run.txt
    python tools/mgba_probe/probe_client.py --rom rom/base.gba \
        --cmd "frames 30 0x000" --cmd "dump 0x02026804 8"

A script file holds one command per line; blank lines and lines starting
with '#' are ignored.

The JSON document has the shape:

    {
      "rom": "rom/base.gba",
      "exe": "build/mgba-probe/mgba-probe.exe",
      "exit_code": 0,
      "steps": [
        {"index": 0, "command": "frames 30 0x000", "ok": true,
         "output": ["OK frames 30 0x00000000"], "dump": null}
      ],
      "stderr": []
    }

A `dump` step additionally carries a "dump" object with the address, length
and the hex bytes that were read.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import queue
import subprocess
import sys
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEFAULT_EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"


def read_script(path: pathlib.Path) -> list[str]:
    commands = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        commands.append(line)
    return commands


def parse_dump(lines: list[str]) -> dict | None:
    """Extract the structured payload of a `dump` command."""
    for index, line in enumerate(lines):
        if not line.startswith("DUMP "):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        address = parts[1]
        length = int(parts[2])
        payload = []
        for follow in lines[index + 1:]:
            if follow == "ENDDUMP":
                break
            payload.append(follow)
        data = "".join(payload)
        return {
            "address": address,
            "length": length,
            "bytes": data,
            "values": [data[i:i + 2] for i in range(0, len(data), 2)],
        }
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", required=True, help="ROM to load")
    ap.add_argument("--bios", help="real GBA BIOS to use instead of mGBA's HLE one "
                                   "(needed to reproduce captures taken with a real BIOS)")
    ap.add_argument("--script", help="script file with one command per line")
    ap.add_argument("--cmd", action="append", default=[],
                    help="inline command (may be repeated)")
    ap.add_argument("--exe", default=str(DEFAULT_EXE),
                    help="path to mgba-probe.exe")
    ap.add_argument("--timeout", type=float, default=120.0,
                    help="seconds to wait for the probe")
    ap.add_argument("--out", help="write the JSON document to this file")
    args = ap.parse_args()

    commands: list[str] = []
    if args.script:
        commands += read_script(pathlib.Path(args.script))
    commands += args.cmd
    if not commands:
        print("ERR no commands given (use --script or --cmd)", file=sys.stderr)
        return 2

    exe = pathlib.Path(args.exe)
    if not exe.exists():
        print(f"ERR {exe} missing; run: python tools/mgba_probe/build.py",
              file=sys.stderr)
        return 2

    command = [str(exe), str(args.rom)]
    if args.bios:
        command += ["--bios", str(args.bios)]
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )

    stderr_lines: list[str] = []
    stderr_done = threading.Event()

    def drain_stderr() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            stderr_lines.append(line.rstrip("\r\n"))
        stderr_done.set()

    thread = threading.Thread(target=drain_stderr, daemon=True)
    thread.start()

    steps = []
    deadline = time.monotonic() + args.timeout
    assert proc.stdin is not None and proc.stdout is not None

    def read_line() -> str | None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("probe timed out")
        result: queue.Queue = queue.Queue()
        reader = threading.Thread(
            target=lambda: result.put(proc.stdout.readline()), daemon=True)
        reader.start()
        reader.join(remaining)
        if reader.is_alive():
            raise TimeoutError("probe timed out")
        line = result.get()
        return line if line else None

    try:
        # Skip the banner the host prints before it accepts commands.
        first = read_line()
        if first is not None and first.strip() != "READY":
            stderr_lines.append(f"banner: {first.rstrip()}")

        for index, command in enumerate(commands):
            sentinel = f"___PROBE_END_{index}___"
            try:
                proc.stdin.write(f"{command}\n")
                proc.stdin.write(f"echo {sentinel}\n")
                proc.stdin.flush()
            except (BrokenPipeError, OSError):
                stderr_lines.append(f"probe exited before command {index}")
                break
            output = []
            while True:
                line = read_line()
                if line is None:
                    break
                line = line.rstrip("\r\n")
                if line == sentinel:
                    break
                output.append(line)
            status = "ok"
            if any(line.startswith("ERR") for line in output):
                status = "error"
            steps.append({
                "index": index,
                "command": command,
                "status": status,
                "output": output,
                "dump": parse_dump(output),
            })
        try:
            proc.stdin.write("quit\n")
            proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
    except TimeoutError as exc:
        stderr_lines.append(str(exc))
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
        stderr_done.wait(timeout=5)

    document = {
        "rom": str(args.rom),
        "exe": str(exe),
        "exit_code": proc.returncode,
        "steps": steps,
        "stderr": stderr_lines,
    }
    payload = json.dumps(document, ensure_ascii=False, indent=2)
    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload + "\n")
        print(f"wrote {out}")
    else:
        print(payload)
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
