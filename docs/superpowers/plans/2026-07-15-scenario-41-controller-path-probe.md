# Scenario 41 Controller Path Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建并运行一个行为透明的五点 observer，定位 scenario 41 白框后缀实际经过的 checked controller/action-dispatch call-site。

**Architecture:** Python builder 复用 `published_call_observer.py`，把五条已核对 Thumb BL 重定向到独立 96-byte wrapper，并把调用参数发布到共享 counter 下的五个 24-byte EWRAM record。现有浏览器 driver 只负责从 savestate 输入、截图和 `PROBE_MEMORY_DUMP`；Python decoder 离线解析 dump，不为 driver 增加新的成功出口。

**Tech Stack:** Python 3 `unittest`、现有 Thumb BL/observer 工具、Node 浏览器 driver、Windows `run_guarded.py`、mGBA savestate。

## Global Constraints

- 只复用 `published_call_observer.py` 的 `ObserverSite`、`assert_non_overlapping_sites()` 和 `patch_observer()`；不得复制 wrapper ABI。
- call-site/target 必须是设计文档列出的五组精确地址；错误 ROM、错误 BL、非零 cave、重叠范围全部 fail closed。
- counter=`0x0203F040`，records=`0x0203F060/80/A0/C0/E0`，stubs=`0x0809E800/880/900/980/EA00`，record size=24，stub size=96。
- 不修改 `runtime-formation-probe.js` 的成功判定；使用现有 `PROBE_MEMORY_DUMP` 一次读取 `0x0203F040`、长度 `0xC0`。
- 所有浏览器/mGBA 运行串行经过 `run_guarded.py`；最多四轮，每轮峰值预算 700 MiB，并保存 Job Object/raw exit/peak。
- 使用现有 savestate 直接进入边界，不重复从标题或主菜单导航。
- 任意 hit 只定位 checked call-site，不证明玩家控制；Task 5 在 evaluator 门禁通过前保持 `not-proven`。

---

### Task 1: 五点 builder 与离线 decoder

**Files:**
- Create: `tools/build_controller_path_runtime_probe.py`
- Create: `tools/decode_controller_path_runtime_probe.py`
- Create: `tests/test_build_controller_path_runtime_probe.py`
- Create: `tests/test_decode_controller_path_runtime_probe.py`

**Interfaces:**
- Consumes: `published_call_observer.ObserverSite`, `assert_non_overlapping_sites`, `patch_observer` and immutable `rom/base.gba` SHA-1 `26f60795fa5e63b4f0264b84e453beffd56b9f7d`.
- Produces: `build_probe(base: bytes, verify_sha1: bool = True) -> bytes`, `decode_dump(data: bytes) -> dict`, CLI builder and JSON decoder.

- [x] **Step 1: Write builder RED tests**

Add tests that assert the exact immutable layout:

```python
EXPECTED = (
    (0x08073946, 0x0806F718, 0x0809E800, 0x0203F060, b"PCO1", 1),
    (0x08073A16, 0x08067158, 0x0809E880, 0x0203F080, b"AC01", 2),
    (0x08073A2E, 0x08067158, 0x0809E900, 0x0203F0A0, b"AC02", 3),
    (0x08073A3E, 0x08067158, 0x0809E980, 0x0203F0C0, b"AC03", 4),
    (0x08073A4A, 0x08067158, 0x0809EA00, 0x0203F0E0, b"AC04", 5),
)

def test_sites_match_checked_layout(self):
    self.assertEqual(EXPECTED, tuple(
        (s.hook, s.original, s.stub, s.scratch,
         s.magic.to_bytes(4, "little"), s.event_code)
        for s in probe.OBSERVER_SITES
    ))
```

Also require tests for exact base bytes/decoded targets, five patched BLs only, five zero caves, stub literals/event codes, pairwise record/stub/call-site non-overlap, wrong SHA-1, one corrupted call-site, and one nonzero cave.

- [x] **Step 2: Run builder tests and verify RED**

Run:

```powershell
python -m unittest tests.test_build_controller_path_runtime_probe -v
```

Expected: FAIL because `tools.build_controller_path_runtime_probe` does not exist.

- [x] **Step 3: Implement the minimal builder**

Define immutable sites and reuse the shared patcher:

```python
BASE_SHA1 = "26f60795fa5e63b4f0264b84e453beffd56b9f7d"
EVENT_COUNTER = 0x0203F040
STUB_SIZE = 96
OBSERVER_SITES = (
    ObserverSite("player-select", 0x08073946, 0x0806F718, 0x0809E800,
                 0x0203F060, int.from_bytes(b"PCO1", "little"), 1),
    ObserverSite("action-1", 0x08073A16, 0x08067158, 0x0809E880,
                 0x0203F080, int.from_bytes(b"AC01", "little"), 2),
    ObserverSite("action-2", 0x08073A2E, 0x08067158, 0x0809E900,
                 0x0203F0A0, int.from_bytes(b"AC02", "little"), 3),
    ObserverSite("action-3", 0x08073A3E, 0x08067158, 0x0809E980,
                 0x0203F0C0, int.from_bytes(b"AC03", "little"), 4),
    ObserverSite("action-4", 0x08073A4A, 0x08067158, 0x0809EA00,
                 0x0203F0E0, int.from_bytes(b"AC04", "little"), 5),
)

def build_probe(base: bytes, *, verify_sha1: bool = True) -> bytes:
    if verify_sha1 and hashlib.sha1(base).hexdigest() != BASE_SHA1:
        raise ValueError("controller-path probe requires the immutable base ROM")
    assert_non_overlapping_sites(OBSERVER_SITES, EVENT_COUNTER, 4, STUB_SIZE)
    rom = bytearray(base)
    for site in OBSERVER_SITES:
        patch_observer(rom, site, EVENT_COUNTER, STUB_SIZE)
    return bytes(rom)
```

The CLI accepts `base_rom output_rom`, creates only the parent directory, writes the ROM, and prints SHA-256.

- [x] **Step 4: Write decoder RED tests**

Tests must construct one `0xC0`-byte dump whose base address is `0x0203F040`, encode five records at offsets `0x20/40/60/80/A0`, and assert:

```python
decoded = decoder.decode_dump(bytes(dump))
self.assertEqual(9, decoded["event_counter"])
self.assertEqual([1, 4], [r["event_code"] for r in decoded["fresh_records"]])
self.assertEqual("0x00000008", decoded["records"][0]["sequence"])
```

Add short dump, wrong magic, event-code/magic mismatch, stale zero record and uint32 fields tests. Wrong/zero records remain decoded diagnostics but never appear in `fresh_records`.

- [x] **Step 5: Run decoder tests and verify RED**

Run:

```powershell
python -m unittest tests.test_decode_controller_path_runtime_probe -v
```

Expected: FAIL because `tools.decode_controller_path_runtime_probe` does not exist.

- [x] **Step 6: Implement the minimal decoder**

Decode shared ABI fields using `struct.unpack_from` and emit JSON-safe values:

```python
def decode_record(data: bytes, offset: int, site: ObserverSite) -> dict:
    magic, hits, arg0, arg1, arg2, sequence, event = struct.unpack_from("<IIIHHII", data, offset)
    valid = magic == site.magic and event == site.event_code and hits > 0 and sequence > 0
    return {
        "name": site.name,
        "magic": f"0x{magic:08X}",
        "hit_count": hits,
        "argument0": f"0x{arg0:08X}",
        "argument1": arg1,
        "argument2": arg2,
        "sequence": f"0x{sequence:08X}",
        "event_code": event,
        "valid": valid,
    }
```

`decode_dump()` requires exactly `0xC0` bytes, decodes the counter at offset 0 and records using `site.scratch - 0x0203F040`, sorts valid records by uint32 sequence for diagnostics, and returns `event_counter`, `records`, and `fresh_records`. The CLI accepts `dump.bin output.json`.

- [x] **Step 7: Run GREEN, build ROM and verify confined diff**

Run:

```powershell
python -m unittest tests.test_published_call_observer tests.test_build_controller_path_runtime_probe tests.test_decode_controller_path_runtime_probe -v
python tools/build_controller_path_runtime_probe.py rom/base.gba build/scenario-41-controller-path.gba
python -c "from pathlib import Path; from tools.build_controller_path_runtime_probe import build_probe; base=Path('rom/base.gba').read_bytes(); out=Path('build/scenario-41-controller-path.gba').read_bytes(); assert out==build_probe(base)"
git diff --check
```

Expected: all tests PASS; rebuilt ROM is byte-identical; builder output differs only at five 4-byte BL call-sites and five 96-byte stub ranges.

- [x] **Step 8: Commit and push the probe**

```powershell
git add tools/build_controller_path_runtime_probe.py tools/decode_controller_path_runtime_probe.py tests/test_build_controller_path_runtime_probe.py tests/test_decode_controller_path_runtime_probe.py
git commit -m "feat(re): trace scenario 41 controller path"
git push origin task/units-character-definitions
```

### Task 2: Guarded runtime A/B 与持久结论

**Files:**
- Create: `artifacts/runtime-checkpoints/scenario-41-controller-path-evidence.json`
- Create: `notes/scenario-41-controller-path-runtime-20260715.md`
- Modify: `notes/scenario-41-player-control-runtime-20260715.md`
- Modify: `docs/sequel-roadmap.md`
- Modify: `docs/reverse-engineering-handoff-20260711.md`

**Interfaces:**
- Consumes: `build/scenario-41-controller-path.gba`, `decode_dump(data)`, `artifacts/runtime-checkpoints/actionable-move-grid.ss9`, `build/task5-after-start-a.ss9`.
- Produces: checked call-site hit ordering or a bounded `not-proven` result, with exact commands/hashes/input audits/guard data.

- [ ] **Step 1: Run resource and hash preflight**

Record available physical memory, heavy-lock availability, project-owned PID tree and port 2345; require no owned residue before launch. Recompute SHA-256 for ROM and both checkpoints. Abort the run if available memory is below the existing guard threshold or a project owner/listener remains.

- [ ] **Step 2: Run the actionable zero-input baseline**

Use the diagnostic ROM and existing actionable savestate with empty tail and every automatic input disabled. Set `PROBE_MEMORY_DUMP=build/controller-path-positive-zero.bin`, `PROBE_MEMORY_ADDRESS=0x0203F040`, and `PROBE_MEMORY_LENGTH=192`, then run through `run_guarded.py`.

Expected: stable actionable battle diagnostics, empty input audit, and a complete immutable baseline dump. A valid record in this single dump is only `valid_records`, never fresh evidence.

- [ ] **Step 3: Run the actionable positive control**

Use the same ROM/checkpoint. Set `PROBE_MEMORY_DUMP=build/controller-path-positive.bin`, disable adaptive/settle automatic input, and use the exact explicit tail `KeyX,ArrowDown,ArrowDown,KeyZ,KeyZ`. Run through `run_guarded.py`, then call `compare controller-path-positive-zero.bin controller-path-positive.bin`.

Expected: at least one valid `AC01..AC04` fresh record and no automatic input. If no action record is fresh, persist `positive-control-not-proven` and stop without running scenario 41.

- [ ] **Step 4: Run scenario 41 zero-input baseline**

From `build/task5-after-start-a.ss9`, use the same ROM with empty tail, all automatic input disabled, and dump `build/controller-path-s41-zero.bin`.

Expected: stable battle 41/36x44/Naruto+Iruka boundary, empty audit, and records usable only as immutable baseline. Old nonzero magic from savestate must not count as fresh.

- [ ] **Step 5: Run scenario 41 independent single A**

From the same checkpoint, use exactly one explicit `KeyZ/A`, automatic input disabled, and dump `build/controller-path-s41-a.bin`. Compare each final record with the zero-input baseline by hit count and uint32 sequence.

Expected: either a bounded ordered list of fresh checked events, or all-five `not-proven`. Do not add another key or another run after the defined stop condition.

- [ ] **Step 6: Persist evidence and update durable memory**

Write compact JSON with exact command/env provenance, ROM/checkpoint/result/screenshot/dump/guard hashes, input audit, baseline/final records, sequence ordering, raw guard reason/exit/peak and postcheck provenance. The note records attempts, learned call-site boundary, key addresses and rejected hypotheses. Update the player-control note, handoff and roadmap without claiming player control unless the existing Task 4 evaluator later passes.

- [ ] **Step 7: Verify, independently review, commit and push**

Run:

```powershell
python -m unittest tests.test_published_call_observer tests.test_build_controller_path_runtime_probe tests.test_decode_controller_path_runtime_probe -v
python tools/runtime_checkpoint_ledger.py artifacts/runtime-checkpoints/scenario-41-checkpoints.json
openspec validate close-scenario-41-battle-runtime --type change --strict --json --no-interactive
git diff --check
```

Expected: all commands PASS; resource summaries are non-degraded and no project-owned residue remains. A fresh reviewer must approve call-site bytes, input audit, dump freshness and claim boundaries before checkoff.

```powershell
git add artifacts/runtime-checkpoints/scenario-41-controller-path-evidence.json notes/scenario-41-controller-path-runtime-20260715.md notes/scenario-41-player-control-runtime-20260715.md docs/sequel-roadmap.md docs/reverse-engineering-handoff-20260711.md
git commit -m "docs(re): record scenario 41 controller path"
git push origin task/units-character-definitions
```
