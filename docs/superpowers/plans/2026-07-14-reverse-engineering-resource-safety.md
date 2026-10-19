# Reverse-Engineering Resource Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unbounded whole-ROM Capstone path with a constant-memory Thumb scanner and ensure every project-owned heavy task runs under one cross-platform lock, admission check, RSS monitor, timeout, and owned-process isolation boundary.

**Architecture:** A pure `thumb_branch` module owns ARMv4T direct-branch encoding and scanning, while compatibility callers delegate to it. A separate `project_resource_guard` library owns locking, resource admission, monitoring, summaries, and process isolation; `run_guarded.py` exposes it to Python and Node-heavy workflows without scanning or killing unrelated processes.

**Tech Stack:** Python 3 standard library (`argparse`, `ctypes`, `dataclasses`, `fcntl`/`msvcrt`, `json`, `subprocess`, `threading`), Node.js 25 tests for runtime progress wiring, existing `unittest` suite.

## Global Constraints

- All functional changes use red-green-refactor TDD; no production code is written before its covering test fails for the intended reason.
- The scanner must not call Capstone for whole-ROM discovery; Capstone remains only in bounded disassembly.
- GBA ARM7TDMI support is Thumb BL plus 16-bit unconditional B. BLX immediate is not part of the compatibility contract.
- `start` and `end` are aligned GBA addresses, `end` is exclusive, and a four-byte BL must fit completely inside the requested range.
- Static scanning results are candidates until bounded disassembly, code-range evidence, or runtime evidence confirms them.
- One shared non-blocking `heavy` lock covers both static heavy tasks and Chromium runtime probes; lock contention exits with code 75 before launching a child.
- Defaults are exactly: 1024 MiB minimum available physical memory, 1536 MiB maximum owned process-tree RSS, 600 seconds wall timeout, 60 seconds idle timeout, 1 second RSS sampling, and 5 seconds termination grace.
- The guard may terminate only its own child process group or Job Object. It must never use `pkill`, `killall`, `taskkill /IM`, or any process-name-based cleanup.
- Missing resource-monitor or isolation capability is fail-closed unless an explicit audited degradation flag is supplied; degraded protection is recorded in the JSON summary.
- Each stage is committed and pushed to `origin/task/units-character-definitions` after its focused and integration tests pass.

---

### Task 1: Constant-memory Thumb direct-branch scanner

**Files:**
- Create: `tools/thumb_branch.py`
- Create: `tests/test_thumb_branch.py`

**Interfaces:**
- Consumes: raw ROM bytes and aligned GBA addresses.
- Produces: `ThumbBranch`, `encode_thumb_bl`, `decode_thumb_bl`, `decode_thumb_b`, `iter_thumb_direct_branches`, and `find_thumb_branches` exactly as specified below.

- [ ] **Step 1: Write the failing unit tests**

Create `tests/test_thumb_branch.py` with focused fixtures. The test file must include these concrete assertions:

```python
import struct
import unittest

from tools.thumb_branch import (
    ThumbBranch,
    decode_thumb_b,
    decode_thumb_bl,
    encode_thumb_bl,
    find_thumb_branches,
    iter_thumb_direct_branches,
)


class ThumbBranchTests(unittest.TestCase):
    def test_bl_round_trips_forward_and_backward(self):
        for source, target in ((0x08000100, 0x08012340), (0x08012340, 0x08000100)):
            first, second = struct.unpack("<HH", encode_thumb_bl(source, target))
            self.assertEqual(decode_thumb_bl(source, first, second), target)

    def test_bl_rejects_odd_and_out_of_range_targets(self):
        with self.assertRaisesRegex(ValueError, "halfword aligned"):
            encode_thumb_bl(0x08000100, 0x08000103)
        with self.assertRaisesRegex(ValueError, "outside ARMv4T range"):
            encode_thumb_bl(0x08000000, 0x08800004)

    def test_decoders_reject_non_direct_branch_encodings(self):
        self.assertIsNone(decode_thumb_bl(0x08000000, 0xE000, 0xF800))
        self.assertIsNone(decode_thumb_b(0x08000000, 0xD001))

    def test_unconditional_b_decodes_positive_and_negative_displacements(self):
        self.assertEqual(decode_thumb_b(0x08000100, 0xE001), 0x08000106)
        self.assertEqual(decode_thumb_b(0x08000100, 0xE7FD), 0x080000FE)

    def test_scan_obeys_exclusive_range_and_requires_complete_bl(self):
        base = 0x08000000
        blob = bytearray(16)
        blob[4:8] = encode_thumb_bl(base + 4, base + 14)
        blob[8:10] = struct.pack("<H", 0xE001)
        branches = list(iter_thumb_direct_branches(bytes(blob), rom_base=base, start=base + 4, end=base + 10))
        self.assertEqual(
            branches,
            [
                ThumbBranch(base + 4, base + 14, "bl", "#0x0800000e"),
                ThumbBranch(base + 8, base + 14, "b", "#0x0800000e"),
            ],
        )
        self.assertEqual(list(iter_thumb_direct_branches(bytes(blob), rom_base=base, start=base + 4, end=base + 6)), [])

    def test_scan_validates_address_mapping_and_alignment(self):
        blob = bytes(8)
        for kwargs, message in (
            ({"start": 0x08000001}, "halfword aligned"),
            ({"end": 0x08000009}, "mapped ROM range"),
            ({"start": 0x08000006, "end": 0x08000004}, "start must not exceed end"),
        ):
            with self.assertRaisesRegex(ValueError, message):
                list(iter_thumb_direct_branches(blob, rom_base=0x08000000, **kwargs))

    def test_find_filters_by_exact_target(self):
        base = 0x09000000
        blob = encode_thumb_bl(base, base + 8) + encode_thumb_bl(base + 4, base)
        self.assertEqual(
            [branch.address for branch in find_thumb_branches(blob, base + 8, rom_base=base)],
            [base],
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
python -m unittest tests.test_thumb_branch -v
```

Expected: import failure for missing `tools.thumb_branch`, proving the new API is not already present.

- [ ] **Step 3: Implement the minimal scanner**

Create `tools/thumb_branch.py` with this public structure and algorithm:

```python
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class ThumbBranch:
    address: int
    target: int
    mnemonic: str
    op_str: str


def encode_thumb_bl(callsite: int, target: int) -> bytes:
    displacement = target - (callsite + 4)
    if displacement & 1:
        raise ValueError("Thumb BL target must be halfword aligned")
    if not -(1 << 22) <= displacement < (1 << 22):
        raise ValueError("Thumb BL target is outside ARMv4T range")
    encoded = displacement & 0x7FFFFF
    return struct.pack(
        "<HH",
        0xF000 | ((encoded >> 12) & 0x7FF),
        0xF800 | ((encoded >> 1) & 0x7FF),
    )


def decode_thumb_bl(callsite: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return callsite + 4 + displacement


def decode_thumb_b(callsite: int, halfword: int) -> int | None:
    if halfword & 0xF800 != 0xE000:
        return None
    displacement = (halfword & 0x7FF) << 1
    if displacement & 0x800:
        displacement -= 0x1000
    return callsite + 4 + displacement


def _validated_offsets(data: bytes, rom_base: int, start: int | None, end: int | None) -> tuple[int, int]:
    mapped_end = rom_base + len(data)
    start = rom_base if start is None else start
    end = mapped_end if end is None else end
    if start > end:
        raise ValueError("start must not exceed end")
    if start < rom_base or end > mapped_end:
        raise ValueError("start/end must be inside the mapped ROM range")
    if (start | end | rom_base) & 1:
        raise ValueError("ROM base and scan bounds must be halfword aligned")
    return start - rom_base, end - rom_base


def iter_thumb_direct_branches(data: bytes, *, rom_base: int, start: int | None = None, end: int | None = None) -> Iterator[ThumbBranch]:
    start_offset, end_offset = _validated_offsets(data, rom_base, start, end)
    for offset in range(start_offset, end_offset, 2):
        address = rom_base + offset
        halfword = struct.unpack_from("<H", data, offset)[0]
        if offset + 4 <= end_offset:
            second = struct.unpack_from("<H", data, offset + 2)[0]
            target = decode_thumb_bl(address, halfword, second)
            if target is not None:
                yield ThumbBranch(address, target, "bl", f"#0x{target:08x}")
                continue
        target = decode_thumb_b(address, halfword)
        if target is not None:
            yield ThumbBranch(address, target, "b", f"#0x{target:08x}")


def find_thumb_branches(data: bytes, target: int, *, rom_base: int, start: int | None = None, end: int | None = None) -> list[ThumbBranch]:
    return [branch for branch in iter_thumb_direct_branches(data, rom_base=rom_base, start=start, end=end) if branch.target == target]
```

During implementation, preserve the exact public names and dataclass field order above. If a test exposes an arithmetic error, correct the algorithm rather than weakening the assertions.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
python -m unittest tests.test_thumb_branch -v
```

Expected: all `ThumbBranchTests` pass with zero failures.

- [ ] **Step 5: Refactor and re-run**

Remove duplicated sign-extension expressions only if doing so keeps the public interface unchanged. Re-run the focused test command and `git diff --check`.

- [ ] **Step 6: Commit and push**

```powershell
git add tools/thumb_branch.py tests/test_thumb_branch.py
git commit -m "fix(re): add constant-memory Thumb branch scanner"
git push origin task/units-character-definitions
```

---

### Task 2: Replace unsafe scan and migrate compatible consumers

**Files:**
- Modify: `tools/find_thumb_calls.py`
- Modify: `tools/extract_audio_cue_calls.py`
- Modify: `tools/build_save_state_runtime_probe.py`
- Modify: `tools/disasm_thumb.py`
- Modify: `tools/README.md`
- Create: `tests/test_find_thumb_calls.py`
- Create: `tests/test_disasm_thumb.py`
- Modify: `tests/test_extract_audio_cue_calls.py`

**Interfaces:**
- Consumes: Task 1 public `thumb_branch` API.
- Produces: Capstone-free `find_thumb_calls.scan_calls`, backward-compatible `encode_thumb_bl` imports, and truly bounded file reads.

- [ ] **Step 1: Write failing compatibility and safety tests**

Create `tests/test_find_thumb_calls.py` to:

```python
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.find_thumb_calls import scan_calls
from tools.thumb_branch import encode_thumb_bl


class FindThumbCallsTests(unittest.TestCase):
    def test_scan_returns_legacy_tuple_shape_for_bl_and_b(self):
        base = 0x08000000
        with tempfile.TemporaryDirectory() as tmp:
            rom = Path(tmp) / "fixture.gba"
            rom.write_bytes(encode_thumb_bl(base, base + 8) + bytes.fromhex("00e00000"))
            self.assertEqual(scan_calls(rom, base + 8), [(base, "bl", "#0x08000008"), (base + 4, "b", "#0x08000008")])

    def test_scan_range_excludes_partial_bl(self):
        base = 0x08000000
        with tempfile.TemporaryDirectory() as tmp:
            rom = Path(tmp) / "fixture.gba"
            rom.write_bytes(encode_thumb_bl(base, base + 8) + bytes(4))
            self.assertEqual(scan_calls(rom, base + 8, start=base, end=base + 2), [])

    def test_cli_preserves_headers_and_accepts_range(self):
        base = 0x08000000
        with tempfile.TemporaryDirectory() as tmp:
            rom = Path(tmp) / "fixture.gba"
            rom.write_bytes(encode_thumb_bl(base, base + 8) + bytes(4))
            result = subprocess.run([sys.executable, "tools/find_thumb_calls.py", str(rom), hex(base + 8), "--start", hex(base), "--end", hex(base + 4)], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("matches=1", result.stdout)
            self.assertIn("0x08000000: bl", result.stdout)

    def test_module_does_not_import_capstone(self):
        with patch.dict(sys.modules, {"capstone": None, "capstone.arm": None}):
            __import__("tools.find_thumb_calls")
```

Create `tests/test_disasm_thumb.py` with a tracking file object or mocked `Path.open` that asserts `read_window()` performs `seek(start_off)` and `read(size)` and never calls `Path.read_bytes()`.

Extend `tests/test_extract_audio_cue_calls.py` with an assertion that the module's `encode_thumb_bl` remains the public scanner function or an exact compatible wrapper, and keep the existing real-ROM 290/278/12 inventory test unchanged.

- [ ] **Step 2: Run tests and verify RED for the intended reasons**

```powershell
python -m unittest tests.test_find_thumb_calls tests.test_disasm_thumb tests.test_extract_audio_cue_calls -v
```

Expected failures: old `scan_calls` has no range parameters and imports Capstone; `read_window` calls `read_bytes`; audio still owns duplicate encoding.

- [ ] **Step 3: Implement compatibility migration**

Make these exact changes:

```python
# tools/find_thumb_calls.py
from tools.thumb_branch import find_thumb_branches

def scan_calls(rom_path: Path, target: int, *, start: int | None = None, end: int | None = None) -> list[tuple[int, str, str]]:
    data = rom_path.read_bytes()
    return [(branch.address, branch.mnemonic, branch.op_str) for branch in find_thumb_branches(data, target, rom_base=ROM_BASE, start=start, end=end)]
```

Add `--start` and `--end` argparse options using `lambda value: int(value, 0)` and pass them to `scan_calls`. Delete every Capstone import and configuration from this file.

In `tools/extract_audio_cue_calls.py`, import `decode_thumb_bl` and `encode_thumb_bl` from `tools.thumb_branch` with the repository's existing script/module import fallback pattern; replace `_thumb_bl_target` calls with `decode_thumb_bl` and remove the duplicate implementation.

In `tools/build_save_state_runtime_probe.py`, import `encode_thumb_bl` from `tools.thumb_branch` with fallback and remove only the local duplicate. Keep the exported module name so existing imports continue working.

Implement bounded reading as:

```python
def read_window(rom_path: Path, gba_addr: int, before: int, size: int) -> tuple[int, bytes]:
    if before < 0 or size <= 0:
        raise ValueError("before must be non-negative and size must be positive")
    file_size = rom_path.stat().st_size
    mapped_end = ROM_BASE + file_size
    if not ROM_BASE <= gba_addr < mapped_end:
        raise ValueError("focus address is outside the ROM")
    start_addr = max(ROM_BASE, gba_addr - before)
    start_off = start_addr - ROM_BASE
    with rom_path.open("rb") as handle:
        handle.seek(start_off)
        return start_addr, handle.read(min(size, file_size - start_off))
```

Update `tools/README.md` to call results candidates, document `--start/--end`, state that BLX immediate is unsupported on ARMv4T, and remove the Capstone whole-ROM description.

- [ ] **Step 4: Run focused and real-ROM integration tests**

```powershell
python -m unittest tests.test_thumb_branch tests.test_find_thumb_calls tests.test_disasm_thumb tests.test_extract_audio_cue_calls tests.test_build_text_writer_trace_probe tests.test_build_numeric_writer_trace_probe tests.test_build_tilemap_writer_trace_probe -v
```

Expected: all tests pass; the true ROM call-site sets remain unchanged.

- [ ] **Step 5: Prove the unsafe dependency is gone**

```powershell
rg -n "capstone|md\.detail|md\.skipdata|md\.disasm" tools/find_thumb_calls.py
```

Expected: no matches. Run `git diff --check`.

- [ ] **Step 6: Commit and push**

```powershell
git add tools/find_thumb_calls.py tools/extract_audio_cue_calls.py tools/build_save_state_runtime_probe.py tools/disasm_thumb.py tools/README.md tests/test_find_thumb_calls.py tests/test_disasm_thumb.py tests/test_extract_audio_cue_calls.py
git commit -m "fix(re): remove unbounded Capstone call scan"
git push origin task/units-character-definitions
```

---

### Task 3: Shared lock, admission, monitoring, and summary core

**Files:**
- Create: `tools/project_resource_guard.py`
- Create: `tests/test_project_resource_guard.py`

**Interfaces:**
- Consumes: a command sequence, cwd, summary path, and immutable `GuardConfig`.
- Produces: `ProjectLock`, `MemorySnapshot`, `GuardConfig`, `GuardResult`, `available_physical_memory_mib`, and `run_guarded`.

- [ ] **Step 1: Write failing pure/core tests**

Create tests covering exact defaults and injected resource states:

```python
import json
import tempfile
import unittest
from pathlib import Path

from tools.project_resource_guard import GuardConfig, ProjectLock, run_guarded


class ProjectResourceGuardTests(unittest.TestCase):
    def test_defaults_match_resource_safety_spec(self):
        config = GuardConfig()
        self.assertEqual((config.min_available_mib, config.max_tree_rss_mib), (1024, 1536))
        self.assertEqual((config.wall_timeout_s, config.idle_timeout_s, config.sample_interval_s, config.grace_period_s), (600, 60, 1, 5))

    def test_second_heavy_lock_fails_fast_and_releases_after_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "heavy.lock"
            with ProjectLock(path, "heavy"):
                with self.assertRaisesRegex(BlockingIOError, "heavy resource lock is busy"):
                    with ProjectLock(path, "heavy"):
                        pass
            with ProjectLock(path, "heavy"):
                pass

    def test_admission_rejection_does_not_launch_child(self):
        launched = []
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "summary.json"
            result = run_guarded(["unused"], cwd=Path(tmp), summary_path=summary, config=GuardConfig(), memory_reader=lambda: 512, launcher=lambda *args, **kwargs: launched.append(args))
            self.assertEqual(result.reason, "admission-rejected")
            self.assertEqual(launched, [])
            self.assertEqual(json.loads(summary.read_text())["reason"], "admission-rejected")
```

Add fake-process tests that inject a clock, RSS reader, and launcher to exercise `completed`, `wall-timeout`, `idle-timeout`, `memory-limit`, `launch-error`, and child nonzero exit without sleeping for real time.

- [ ] **Step 2: Run tests and verify RED**

```powershell
python -m unittest tests.test_project_resource_guard -v
```

Expected: import failure for missing `project_resource_guard`.

- [ ] **Step 3: Implement immutable models and cross-platform lock**

Use these exact model fields:

```python
@dataclass(frozen=True)
class MemorySnapshot:
    available_physical_mib: float
    source: str


@dataclass(frozen=True)
class GuardConfig:
    min_available_mib: int = 1024
    max_tree_rss_mib: int = 1536
    wall_timeout_s: float = 600
    idle_timeout_s: float = 60
    sample_interval_s: float = 1
    grace_period_s: float = 5
    allow_degraded: bool = False

@dataclass(frozen=True)
class GuardResult:
    reason: str
    exit_code: int
    child_pid: int | None
    peak_tree_rss_mib: float
    protection_backend: str
    degraded: bool
```

`ProjectLock` opens a one-byte lock file and uses `fcntl.flock(... LOCK_EX | LOCK_NB)` on POSIX or `msvcrt.locking(... LK_NBLCK, 1)` on Windows. Translate platform lock contention into `BlockingIOError("heavy resource lock is busy")`; always unlock and close in `__exit__`.

Implement `available_physical_memory_mib() -> MemorySnapshot` with `/proc/meminfo` (`MemAvailable`) on Linux and `GlobalMemoryStatusEx` on Windows. Set `source` to `proc-meminfo` or `global-memory-status-ex`. Unsupported platforms raise `RuntimeError` unless `allow_degraded` is true.

Write summaries through a sibling temporary file followed by `Path.replace()` so partial JSON is never presented as a completed run.

- [ ] **Step 4: Implement the monitor loop against injected boundaries**

`run_guarded` must acquire the lock before admission, refuse low memory before launcher invocation, start one owned child, drain stdout/stderr while updating `last_progress`, sample process-tree RSS, and select exactly one terminal reason. Return child exit code for ordinary completion/nonzero child exit; use 75 for lock-busy and admission rejection; use 124 for timeouts and 125 for memory-limit/launch/protection failures.

Progress is any complete stdout/stderr line. Monitoring helpers accept injected launcher, memory reader, tree RSS reader, clock, and sleeper in tests; production defaults use standard-library implementations.

- [ ] **Step 5: Run focused tests and refactor**

```powershell
python -m unittest tests.test_project_resource_guard -v
git diff --check
```

Expected: all core tests pass with no real browser or large allocation.

- [ ] **Step 6: Commit and push**

```powershell
git add tools/project_resource_guard.py tests/test_project_resource_guard.py
git commit -m "feat(tools): add project heavy-task resource guard"
git push origin task/units-character-definitions
```

---

### Task 4: Owned process-tree isolation and guarded CLI

**Files:**
- Modify: `tools/project_resource_guard.py`
- Create: `tools/run_guarded.py`
- Modify: `tests/test_project_resource_guard.py`
- Create: `tests/test_run_guarded.py`

**Interfaces:**
- Consumes: Task 3 core models and monitor loop.
- Produces: POSIX process-group backend, Windows Job Object backend, and CLI contract `python tools/run_guarded.py [guard options] -- command ...`.

- [ ] **Step 1: Write failing subprocess isolation tests**

Use small helper commands based on `sys.executable -c`. Tests must prove:

1. a child plus grandchild are both gone after wall timeout;
2. an unrelated same-name Python sentinel launched outside the guard remains alive;
3. JSON contains `child_pid`, `peak_tree_rss_mib`, backend, command, cwd, timestamps, reason, and exit code;
4. invalid/no command is rejected by argparse;
5. two CLI instances share the same `heavy` lock and the second returns 75.

The sentinel test records its PID and checks `poll() is None` after the guarded tree exits, then terminates only that exact sentinel in test cleanup.

- [ ] **Step 2: Run integration tests and verify RED**

```powershell
python -m unittest tests.test_run_guarded -v
```

Expected: missing CLI/isolation backend failures.

- [ ] **Step 3: Implement POSIX owned process groups**

Launch with `start_new_session=True`. The backend stores the exact child PID. Graceful termination calls `os.killpg(child.pid, signal.SIGTERM)`; forced termination calls `SIGKILL` for the same group only. Tree RSS is the sum of `/proc/<pid>/statm` resident pages for descendants discovered from `/proc/<pid>/stat` parent IDs rooted at the stored child PID.

- [ ] **Step 4: Implement Windows Job Object ownership**

Using stdlib `ctypes`, create one Job Object per guarded run, set `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, assign the exact `Popen._handle` with `AssignProcessToJobObject`, and keep the Job handle alive until summary completion. Termination uses `TerminateJobObject(job, code)` only. Query job accounting or enumerate descendants rooted at the exact child PID for RSS; no process-name filters are permitted. If job creation, limit configuration, or assignment fails, terminate only the just-created child and return `protection-error` before normal monitoring.

- [ ] **Step 5: Implement the CLI**

`tools/run_guarded.py` parses exact defaults from `GuardConfig`, requires a `--summary` path, accepts `--lock-file` defaulting to `build/resource-guard/heavy.lock`, parses the child after `--`, calls `run_guarded`, prints the final summary as one JSON line, and exits with `GuardResult.exit_code`.

Add a static test that searches `tools/project_resource_guard.py` and `tools/run_guarded.py` and rejects `pkill`, `killall`, `taskkill /IM`, and process-name enumeration.

- [ ] **Step 6: Run cross-platform focused verification**

```powershell
python -m unittest tests.test_project_resource_guard tests.test_run_guarded -v
git diff --check
```

Expected: child/grandchild timeout cleanup passes while unrelated sentinel remains alive.

- [ ] **Step 7: Commit and push**

```powershell
git add tools/project_resource_guard.py tools/run_guarded.py tests/test_project_resource_guard.py tests/test_run_guarded.py
git commit -m "feat(tools): isolate guarded project process trees"
git push origin task/units-character-definitions
```

---

### Task 5: Chromium progress wiring, documentation, and full verification

**Files:**
- Modify: `play/_scripts/runtime-formation-probe.js`
- Modify: `play/_scripts/runtime-formation-probe.test.js`
- Modify: `play/_scripts/package.json`
- Modify: `tools/README.md`
- Modify: `docs/reverse-engineering-handoff-20260711.md`
- Modify: `docs/sequel-roadmap.md`
- Modify: `notes/memory-incident-root-cause-20260714.md`

**Interfaces:**
- Consumes: `tools/run_guarded.py` CLI and shared `heavy` lock.
- Produces: parseable runtime progress lines, one documented guarded probe entry, and durable verification evidence.

- [ ] **Step 1: Write the failing Node wiring test**

Export a pure `formatProgress(stage, details = {})` helper from `runtime-formation-probe.js`. Add tests that require each line to parse as:

```javascript
{
  type: 'resource-progress',
  stage: 'browser-launched',
  timestamp: '2026-07-14T00:00:00.000Z',
  details: {},
}
```

Inject the clock into the helper so the exact timestamp is testable. Add source wiring assertions for stages `browser-launched`, `page-loaded`, `core-ready`, `checkpoint-loaded`, `phase-start`, and `result-written`.

- [ ] **Step 2: Run Node tests and verify RED**

```powershell
node --test play/_scripts/runtime-formation-probe.test.js
```

Expected: missing `formatProgress` export and stage wiring.

- [ ] **Step 3: Implement progress and guarded npm entry**

Implement `formatProgress` as one JSON line and `emitProgress` as `console.log(formatProgress(...))`. Emit only at the six required boundaries; do not log memory contents or ROM data. Add package scripts:

```json
"scripts": {
  "test": "node --test runtime-formation-probe.test.js",
  "probe:guarded": "python ../../tools/run_guarded.py --summary ../../build/resource-guard/runtime-probe.json -- node runtime-formation-probe.js"
}
```

The shared lock is supplied by `run_guarded.py` default and cannot be disabled by npm arguments.

- [ ] **Step 4: Update durable documentation**

`tools/README.md` must show guarded invocations for heavy work, explain all default thresholds and exit codes, and prohibit process-name cleanup. Update handoff and roadmap resource sections from “document-only constraint” to the exact implemented guard/test commands without changing the bank distribution. Append the implementation and verification result to the incident note.

- [ ] **Step 5: Run focused verification**

```powershell
node --test play/_scripts/runtime-formation-probe.test.js
python -m unittest tests.test_thumb_branch tests.test_find_thumb_calls tests.test_disasm_thumb tests.test_project_resource_guard tests.test_run_guarded tests.test_extract_audio_cue_calls tests.test_build_text_writer_trace_probe tests.test_build_numeric_writer_trace_probe tests.test_build_tilemap_writer_trace_probe -v
```

Expected: all focused Python and Node tests pass.

- [ ] **Step 6: Run full verification and monitor memory**

Before and after each command, record system available memory and only project command lines/PIDs. Do not start a browser during this verification.

```powershell
python -m unittest discover -s tests -p "test_*.py"
node --test play/_scripts/runtime-formation-probe.test.js
python tools/audit_re_completion.py
git diff --check
```

Expected: Python suite and Node suite have zero failures; audit remains 32/32 with 13 runtime, 10 code, 9 disproved; no project-owned process exceeds guard thresholds; worktree contains only intended changes.

- [ ] **Step 7: Final code review**

Generate a review package from the pre-plan base commit through HEAD and dispatch the final reviewer. Resolve every Critical or Important finding with focused tests and re-review before committing the final task.

- [ ] **Step 8: Commit and push**

```powershell
git add play/_scripts/runtime-formation-probe.js play/_scripts/runtime-formation-probe.test.js play/_scripts/package.json tools/README.md docs/reverse-engineering-handoff-20260711.md docs/sequel-roadmap.md notes/memory-incident-root-cause-20260714.md
git commit -m "fix(re): enforce guarded reverse-engineering workflows"
git push origin task/units-character-definitions
```

## Completion gate

The memory-safety subproject is complete only when all five task commits exist remotely, the final full verification is fresh and green, the unsafe Capstone whole-ROM call is absent, scan and Chromium paths share one enforced lock, unrelated sentinel processes survive timeout tests, and the documentation contains the actual guarded commands. Passing only unit tests or documenting intended behavior is insufficient.

After this gate, resume the reverse-engineering roadmap at the transparent player-control observer for `0x08073946 -> 0x0806F718`; do not claim progress on MOVEDONE, victory, postbattle, or levels until their independent runtime gates are captured.
