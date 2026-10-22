#!/usr/bin/env python3
"""Sample the original ROM's per-frame outline-colour counter in IWRAM.

The original ROM rewrites the 1 px unit outline colour every frame.  The
colour is a triangle wave driven by a 32-bit word in IWRAM at 0x03000078
(ROM literal 0x03000078 at 0x0806A7D4, read by the writer at 0x0806A7A0).
Two different ROM functions increment that word, so the *static* disassembly
cannot say which one runs during scenario 49, nor how often per frame.

This probe answers that dynamically: it samples the word once per emulated
frame, together with its two IWRAM neighbours and the four OBJ palette
banks' entry 15 (the outline slot the writer stores into), so the counter and
the colour it produces can be cross-checked in the same receipt.

It extends the pattern already used by ``tools/butano/capture_s49_gpu_state.py``
(mGBA Lua reads ``emu.memory[<region>]``; region names come from
``_GBAMemoryBlocks`` in mGBA's ``src/gba/core.c``).  The existing tool only
dumps one frame of PRAM/VRAM/OAM, which cannot answer a per-frame question,
so this is a separate tool rather than a flag on that one.

The probe is fail-closed:

* every input (ROM, savestate, mGBA binary, guard, the Lua source embedded
  below) is hashed into ``inputs.json`` before the run;
* the run fails when mGBA exits non-zero, when the done marker is missing,
  or when the number of sampled frames does not match the declared budget;
* the Lua source is written to a temporary file and its SHA-256 is recorded,
  so the exact bytes that ran are pinned in the receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.butano.capture_s49_advance import guard_command  # noqa: E402

DEFAULT_MGBA = ROOT / "build/macos-mgba/build/qt/mGBA.app/Contents/MacOS/mGBA"
GUARD = ROOT / "tools/run_guarded.py"

#: The counter word, as an offset inside mGBA's "iwram" domain.
COUNTER_OFFSET = 0x78
#: The two IWRAM words that bracket the counter, sampled for context.
NEIGHBOUR_OFFSETS = (0x74, 0x7C)
#: OBJ palette entry 15 (the outline slot) for the first four palette banks.
PRAM_OUTLINE_OFFSET = 0x21E
PRAM_BANKS_SAMPLED = 4

LUA_SOURCE = r"""
-- Sample the original ROM's per-frame outline-colour counter.
--
-- mGBA exposes each memory region to Lua as emu.memory[name] (there is no
-- "domains" sub-table) with readRange(offset, length) returning raw bytes.
-- The region names come from _GBAMemoryBlocks in mGBA's src/gba/core.c:
-- "wram" = EWRAM, "iwram" = IWRAM, "palette" = PRAM.
--
-- The absolute frame counter is emu:currentFrame() -- the binding is exported
-- under that name (mSCRIPT_DEFINE_STRUCT_METHOD_NAMED(mCore, currentFrame,
-- frameCounter) in mGBA's src/core/scripting.c), and emu:frameCounter() is
-- NOT a method: calling it aborts the callback.
--
-- The script samples once per emulated frame, then writes a JSON-lines
-- receipt and a done marker.  The surrounding guard watches for that marker
-- and stops the emulator, so the run ends on its own.

local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function write_text(path, payload)
	local output = assert(io.open(path, "w"))
	output:write(payload)
	output:close()
end

local output_dir = required_env("MGBA_IWRAM_COUNTER_OUTPUT_DIR")
local done_marker = required_env("MGBA_IWRAM_COUNTER_DONE_MARKER")
local frame_budget = tonumber(required_env("MGBA_IWRAM_COUNTER_FRAMES"))
local settle_frames = tonumber(required_env("MGBA_IWRAM_COUNTER_SETTLE_FRAMES"))
local input_state = os.getenv("MGBA_IWRAM_COUNTER_INPUT_STATE")

if input_state and input_state ~= "" then
	assert(emu:loadStateFile(input_state), "failed to load input state")
end

local iwram = emu.memory["iwram"]
assert(iwram, "memory domain not exposed: iwram")
local pram = emu.memory["palette"]
assert(pram, "memory domain not exposed: palette")

-- The helpers below take a raw byte string and decode it little-endian.
-- They index the string with Lua's 1-based string.byte, so a 4-byte IWRAM
-- word is bytes 1..4 -- reading a fifth byte would abort the callback.
local function u32_le(bytes)
	return bytes:byte(1)
		+ bytes:byte(2) * 256
		+ bytes:byte(3) * 65536
		+ bytes:byte(4) * 16777216
end

local function u16_le(bytes)
	return bytes:byte(1) + bytes:byte(2) * 256
end

local samples = {}
local frame = 0
local complete = false

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1
	if frame < settle_frames then
		return
	end

	local counter = u32_le(iwram:readRange(0x78, 4))
	local n74 = u32_le(iwram:readRange(0x74, 4))
	local n7c = u32_le(iwram:readRange(0x7c, 4))

	local outline = {}
	for bank = 0, 3 do
		outline[#outline + 1] = u16_le(
			pram:readRange(0x21E + bank * 32, 2))
	end

	local pc = emu:readRegister("pc")
	samples[#samples + 1] = string.format(
		'{"frame":%d,"abs_frame":%d,"counter":%d,"iwram_74":%d,"iwram_7c":%d,' ..
		'"pram15_bank0":%d,"pram15_bank1":%d,"pram15_bank2":%d,"pram15_bank3":%d,' ..
		'"pc":%d}',
		frame, emu:currentFrame(), counter, n74, n7c,
		outline[1], outline[2], outline[3], outline[4], pc)

	if frame >= settle_frames + frame_budget - 1 then
		write_text(output_dir .. "/samples.jsonl", table.concat(samples, "\n") .. "\n")
		write_text(done_marker, "ok\n")
		complete = true
	end
end)
"""


class CounterProbeError(RuntimeError):
    """The probe did not produce a complete, self-consistent sample set."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _resolve_inputs(
    state: Path | None, rom: Path, mgba: Path, frames: int, settle_frames: int
) -> dict[str, object]:
    for path, label in ((rom, "ROM"), (mgba, "mGBA")):
        if not Path(path).is_file():
            raise CounterProbeError(f"missing {label}: {path}")
    if state is not None and not Path(state).is_file():
        raise CounterProbeError(f"missing savestate: {state}")
    if not GUARD.is_file():
        raise CounterProbeError(f"missing guard: {GUARD}")
    if frames < 1:
        raise CounterProbeError("frame budget must be positive")
    if settle_frames < 1:
        raise CounterProbeError("settle frames must be positive")
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "schema": "konoha.mgba-iwram-counter-inputs.v1",
        "mode": "resume-from-state" if state is not None else "power-on-boot",
        "input_state": str(state) if state is not None else None,
        "input_state_sha256": sha256_file(Path(state)) if state is not None else None,
        "rom": str(rom),
        "rom_sha256": sha256_file(Path(rom)),
        "mgba": str(mgba),
        "mgba_sha256": sha256_file(Path(mgba)),
        "guard": str(GUARD),
        "guard_sha256": sha256_file(GUARD),
        "tool": str(Path(__file__).resolve()),
        "tool_sha256": sha256_file(Path(__file__).resolve()),
        "lua_source_sha256": sha256_text(LUA_SOURCE),
        "counter_offset_in_iwram": COUNTER_OFFSET,
        "neighbour_offsets_in_iwram": list(NEIGHBOUR_OFFSETS),
        "pram_outline_offset": PRAM_OUTLINE_OFFSET,
        "pram_banks_sampled": PRAM_BANKS_SAMPLED,
        "frame_budget": frames,
        "settle_frames": settle_frames,
    }


def _verify(out_dir: Path, frames: int) -> list[dict[str, object]]:
    samples_path = out_dir / "samples.jsonl"
    if not samples_path.is_file():
        raise CounterProbeError("probe did not write samples.jsonl")
    samples = []
    for number, line in enumerate(
        samples_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            samples.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise CounterProbeError(f"sample line {number} is not JSON: {error}") from error
    if len(samples) != frames:
        raise CounterProbeError(
            f"probe produced {len(samples)} samples, budget demanded {frames}"
        )
    return samples


def run(
    state: Path | None,
    rom: Path,
    out_dir: Path,
    frames: int,
    settle_frames: int,
    mgba: Path = DEFAULT_MGBA,
) -> dict[str, object]:
    inputs = _resolve_inputs(
        Path(state) if state is not None else None,
        Path(rom),
        Path(mgba),
        frames,
        settle_frames,
    )

    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise CounterProbeError(
            f"{out_dir} is not empty; each run needs its own directory so a "
            f"stale sample set can never be read as a fresh one"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "inputs.json").write_text(
        json.dumps(inputs, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    done_marker = out_dir / "done.json"
    environment = {
        "MGBA_IWRAM_COUNTER_OUTPUT_DIR": str(out_dir.resolve()),
        "MGBA_IWRAM_COUNTER_DONE_MARKER": str(done_marker.resolve()),
        "MGBA_IWRAM_COUNTER_FRAMES": str(frames),
        "MGBA_IWRAM_COUNTER_SETTLE_FRAMES": str(settle_frames),
    }
    if state is not None:
        environment["MGBA_IWRAM_COUNTER_INPUT_STATE"] = str(Path(state).resolve())

    scratch = Path(tempfile.mkdtemp(prefix="s49-iwram-counter-"))
    script = scratch / "probe.lua"
    script.write_text(LUA_SOURCE, encoding="utf-8")
    try:
        child = [str(mgba), "--script", str(script), str(rom)]
        completed = subprocess.run(
            guard_command(out_dir / "guard.json", done_marker, child),
            env={**os.environ, **environment},
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if completed.returncode != 0:
        raise CounterProbeError(
            f"guarded probe failed with exit {completed.returncode}: "
            f"{completed.stderr.strip()[:400]}"
        )
    if not done_marker.is_file():
        raise CounterProbeError("probe never wrote its done marker")
    samples = _verify(out_dir, frames)
    return {"inputs": inputs, "samples": samples, "out_dir": str(out_dir)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument(
        "--state",
        type=Path,
        default=None,
        help="savestate to resume from; omit for a power-on boot",
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=130)
    parser.add_argument("--settle-frames", type=int, default=2)
    parser.add_argument("--mgba", type=Path, default=DEFAULT_MGBA)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run(
            args.state,
            args.rom,
            args.out_dir,
            args.frames,
            args.settle_frames,
            args.mgba,
        )
    except CounterProbeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    samples = result["samples"]
    counters = [sample["counter"] for sample in samples]
    print(
        json.dumps(
            {
                "out_dir": result["out_dir"],
                "mode": result["inputs"]["mode"],
                "samples": len(samples),
                "counter_first": counters[0] if counters else None,
                "counter_last": counters[-1] if counters else None,
                "counter_deltas": sorted(
                    {
                        counters[index + 1] - counters[index]
                        for index in range(len(counters) - 1)
                    }
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
