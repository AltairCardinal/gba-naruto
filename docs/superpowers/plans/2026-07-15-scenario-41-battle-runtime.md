---
change: close-scenario-41-battle-runtime
design-doc: docs/superpowers/specs/2026-07-15-scenario-41-battle-runtime-design.md
design-addendum: docs/superpowers/specs/2026-07-15-scenario-41-prebattle-to-controller-design.md
base-ref: 9352dcadaa7f4650a65ae575286a2dd264b7b1ef
---

# Scenario 41 玩家控制、胜利与 Postbattle 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从自然 scenario 41 “开始任务”边界建立可复放快照阶梯，并以新鲜运行时地址证据证明玩家控制、MOVEDONE、胜利结果和 `0xF400` postbattle。

**Architecture:** macOS Intel 上严格 mGBA 0.10.5 Lua runner 负责低内存零输入复放与单键分段快照；浏览器模拟器仅保留已存在的实例内输入/历史证据路径；Windows mGBA 负责严格归属的 GDB breakpoint/寄存器/只读内存；小型分阶段 observer ROM 使用共享 published-call 协议记录自然控制链。每个结论由 checkpoint 基线后的新鲜事件、场景/单位/屏幕状态、base-ROM control 和资源守卫摘要共同验收。

**Tech Stack:** Python 3 `unittest`、mGBA 0.10.5 Lua、ARMv4T Thumb 机器码、Node.js `node:test`、Playwright/mGBA WASM driver、Windows mGBA 0.10.5 GDB RSP、项目 `run_guarded.py`/POSIX process group/Windows Job Object、OpenSpec/Comet。

## Global Constraints

- 所有功能变化必须执行红—绿—重构；集成点必须有 wiring 失败时会失败的测试。
- 不使用 `SendInput`、焦点抢占、Qt `PostMessage` 或 KEYINPUT write-watch 作为正式输入证据。
- 所有 Chromium、mGBA 和高开销静态命令通过同一个 `tools/run_guarded.py` heavy lock；只清理本次 owned process tree。
- mGBA 单个 GDB memory packet 最大 256 bytes；任一分块失败使整个逻辑读取失败。
- 快照只有在来源、ROM/状态 SHA-256、零输入稳定性、前台画面和关键 WRAM 一致时才进入 `artifacts/runtime-checkpoints/`。
- prebattle 后的 Down/A 必须拆成独立 single-input run；每个中间 candidate 先零输入复验，未通过时禁止下一键。
- strict battle arrival、已越过 hook 的零 scratch、savestate 携带旧 magic 或清单外自动输入均不得证明玩家控制。
- 本 change 不证明 EXP、level 2、训练点或 levels record，不改变任何 bank verification 状态。
- 每个可独立证据阶段创建范围明确的本地 commit 并记录 commit hash；临时 ROM/PNG/GDB 日志保留在忽略的 `build/`。

---

### Task 1: 可追溯 checkpoint ledger 与候选状态验收

**Files:**
- Create: `tools/runtime_checkpoint_ledger.py`
- Create: `tests/test_runtime_checkpoint_ledger.py`
- Create: `artifacts/runtime-checkpoints/scenario-41-checkpoints.json`
- Modify: `artifacts/runtime-checkpoints/README.md`

**Interfaces:**
- Consumes: repository-relative checkpoint/ROM paths and SHA-256 values.
- Produces: `sha256_file(path: Path) -> str`, `validate_record(record: dict[str, object], root: Path) -> list[str]`, `validate_ledger(payload: dict[str, object], root: Path) -> list[str]`, CLI exit 0/1.

- [x] **Step 1: Write failing schema, hash and boundary tests**

```python
class RuntimeCheckpointLedgerTests(unittest.TestCase):
    def test_accepts_a_traced_stable_pre_hook_checkpoint(self):
        state = self.root / "state.ss9"
        rom = self.root / "base.gba"
        state.write_bytes(b"state")
        rom.write_bytes(b"rom")
        record = {
            "name": "scenario-41-start-row",
            "status": "accepted",
            "path": "state.ss9",
            "sha256": hashlib.sha256(b"state").hexdigest(),
            "rom": "base.gba",
            "rom_sha256": hashlib.sha256(b"rom").hexdigest(),
            "parent": "tutorial-ui-save",
            "inputs": ["Down", "Down"],
            "screen": "scenario-41-start-row",
            "stable_zero_input": True,
            "before_hooks": ["0x08073946", "0x080739D8"],
            "allowed_evidence": ["player-control"],
        }
        self.assertEqual(validate_record(record, self.root), [])

    def test_rejects_wrong_hash_unknown_parent_and_crossed_hook(self):
        payload = self.make_ledger()
        payload["checkpoints"][0]["sha256"] = "0" * 64
        payload["checkpoints"][1]["parent"] = "missing"
        payload["checkpoints"][1]["before_hooks"] = []
        errors = validate_ledger(payload, self.root)
        self.assertTrue(any("sha256" in error for error in errors))
        self.assertTrue(any("parent" in error for error in errors))
        self.assertTrue(any("player-control" in error for error in errors))
```

- [x] **Step 2: Run the focused test and verify RED**

Run: `python -m unittest tests.test_runtime_checkpoint_ledger -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'tools.runtime_checkpoint_ledger'`.

- [x] **Step 3: Implement the minimal ledger validator**

```python
REQUIRED_FIELDS = {
    "name", "status", "path", "sha256", "rom", "rom_sha256",
    "parent", "inputs", "screen", "stable_zero_input",
    "before_hooks", "allowed_evidence",
}

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def validate_record(record: dict[str, object], root: Path) -> list[str]:
    errors = [f"missing field: {name}" for name in sorted(REQUIRED_FIELDS - record.keys())]
    if errors:
        return errors
    state = root / str(record["path"])
    rom = root / str(record["rom"])
    if record["status"] == "accepted":
        if not state.is_file() or sha256_file(state) != record["sha256"]:
            errors.append(f"checkpoint sha256 mismatch: {record['name']}")
        if not rom.is_file() or sha256_file(rom) != record["rom_sha256"]:
            errors.append(f"ROM sha256 mismatch: {record['name']}")
    if record["status"] == "accepted" and record["stable_zero_input"] is not True:
        errors.append(f"accepted checkpoint is not stable: {record['name']}")
    return errors
```

`validate_ledger` additionally enforces unique names, parent-before-child ordering, existing parents, valid 64-character SHA-256 metadata for every status, and that every `allowed_evidence` hook is listed in `before_hooks` for `player-control`, `movedone`, `victory`, and `postbattle`. Only `accepted` records require the referenced state and ROM to exist in the checkout and match their hashes; `candidate` and `rejected` records may retain an unavailable `build/` source path plus its previously measured hash.

- [x] **Step 4: Run tests and refactor GREEN**

Run: `python -m unittest tests.test_runtime_checkpoint_ledger -v`

Expected: all checkpoint ledger tests PASS.

- [x] **Step 5: Add the initial scenario 41 ledger**

Record the tracked `tutorial-ui-save.sav` as the accepted root and `build/natural-s41-menu-index2.ss9` as `candidate`. Use its actual SHA-256 `e5039f21675dde00f3bc78e7dad08bf7cbd4ce8bff2944ea108a92bbf25b9e81`; do not copy it into `artifacts/` until Task 5 proves zero-input stability and UI identity. Add a rejected entry explaining that `natural-s41-start-prompt.ss9` is actually the team/equipment page.

Run: `python tools/runtime_checkpoint_ledger.py artifacts/runtime-checkpoints/scenario-41-checkpoints.json`

Expected: exit 0 with `accepted=1 candidate=1 rejected=1 errors=0`.

- [x] **Step 6: Commit and push the checkpoint ledger**

```powershell
git add tools/runtime_checkpoint_ledger.py tests/test_runtime_checkpoint_ledger.py artifacts/runtime-checkpoints/scenario-41-checkpoints.json artifacts/runtime-checkpoints/README.md openspec/changes/close-scenario-41-battle-runtime/tasks.md
git commit -m "feat(re): validate scenario 41 checkpoint lineage"
git push origin task/units-character-definitions
```

---

### Task 2: 可复用 published-call observer 与玩家双 hook

**Files:**
- Create: `tools/published_call_observer.py`
- Create: `tests/test_published_call_observer.py`
- Create: `tests/thumb_observer_machine.py`
- Modify: `tools/build_player_control_runtime_probe.py`
- Modify: `tests/test_build_player_control_runtime_probe.py`

**Interfaces:**
- Consumes: immutable base ROM and checked Thumb BL sites.
- Produces: `ObserverSite`, `build_observer_stub(site, event_counter, stub_size) -> bytes`, `patch_observer(rom, site, event_counter, stub_size) -> None`.
- Record layout: `magic:u32, hit_count:u32, arg0:u32, arg1:u16, arg2:u16, sequence:u32, event_code:u32` (24 bytes).

- [x] **Step 1: Write RED tests for ABI, ranges and publish ordering**

```python
class PublishedCallObserverTests(unittest.TestCase):
    def test_layouts_do_not_overlap(self):
        sites = [PLAYER_CONTROL_SITE, CURRENT_UNIT_SITE]
        self.assertEqual(assert_non_overlapping_sites(sites, EVENT_COUNTER, 4), None)

    def test_second_hook_and_cave_must_match(self):
        base = bytearray((ROOT / "rom/base.gba").read_bytes())
        base[CURRENT_UNIT_HOOK - ROM_BASE] ^= 1
        with self.assertRaisesRegex(ValueError, "current-unit call-site"):
            build_probe(bytes(base), verify_sha1=False)
        base = bytearray((ROOT / "rom/base.gba").read_bytes())
        base[CURRENT_UNIT_STUB - ROM_BASE] = 1
        with self.assertRaisesRegex(ValueError, "current-unit stub region"):
            build_probe(bytes(base), verify_sha1=False)

    def test_published_record_contains_fresh_shared_sequence(self):
        state = execute_stub(
            build_observer_stub(PLAYER_CONTROL_SITE, EVENT_COUNTER, STUB_SIZE),
            registers={"r0": 9, "r1": 0, "r2": 1, "r3": 0x33, "r4": 0x44},
            memory={EVENT_COUNTER: 6},
        )
        self.assertEqual(state.read_u32(SCRATCH + 4), 1)
        self.assertEqual(state.read_u32(SCRATCH + 16), 7)
        self.assertEqual(state.read_u32(SCRATCH + 20), PLAYER_CONTROL_EVENT)
        self.assertEqual(state.read_u32(SCRATCH), MAGIC)
        self.assertEqual(state.registers["r3"], 0x33)
        self.assertEqual(state.registers["r4"], 0x44)
```

Implement `tests/thumb_observer_machine.py` as a deterministic instruction-state interpreter scoped to the emitted Thumb subset. It must execute the generated stub and verify r0-r4, SP and LR restoration rather than only byte equality.

- [x] **Step 2: Run focused tests and verify RED**

Run: `python -m unittest tests.test_published_call_observer tests.test_build_player_control_runtime_probe -v`

Expected: FAIL because `published_call_observer` and the 24-byte sequence/event layout do not exist.

- [x] **Step 3: Implement the shared observer builder**

```python
@dataclass(frozen=True)
class ObserverSite:
    name: str
    hook: int
    original: int
    stub: int
    scratch: int
    magic: int
    event_code: int

def patch_observer(rom: bytearray, site: ObserverSite, event_counter: int, stub_size: int) -> None:
    hook_offset = site.hook - ROM_BASE
    stub_offset = site.stub - ROM_BASE
    expected = encode_thumb_bl(site.hook, site.original)
    if rom[hook_offset:hook_offset + 4] != expected:
        raise ValueError(f"{site.name} call-site bytes do not match")
    if any(rom[stub_offset:stub_offset + stub_size]):
        raise ValueError(f"{site.name} stub region is not zero-filled")
    stub = build_observer_stub(site, event_counter, stub_size)
    rom[stub_offset:stub_offset + stub_size] = stub
    rom[hook_offset:hook_offset + 4] = encode_thumb_bl(site.hook, site.stub)
```

Use dynamic literal fixups as in `build_skill_relation_runtime_probe.py`. The wrapper invalidates magic, increments hit count, stores arguments, increments the shared event counter, stores sequence/event code, publishes magic last, restores r0-r4/SP, and tail-branches through r12 to `original|1` without nested calls.

Use `EVENT_COUNTER=0x0203F040`, current-unit scratch `0x0203F060`, player-control scratch `0x0203F080`, stubs `0x0809E800` and `0x0809E880`, and `STUB_SIZE=96`. Build-time range tests must prove these do not overlap.

- [x] **Step 4: Refactor the player builder onto the shared API and run GREEN**

Run: `python -m unittest tests.test_published_call_observer tests.test_build_player_control_runtime_probe -v`

Expected: all observer/builder tests PASS, including execution-level register/SP/LR equivalence.

- [x] **Step 5: Build and byte-audit the diagnostic ROM**

```powershell
python tools/build_player_control_runtime_probe.py rom/base.gba build/scenario-41-player-control.gba
python -m unittest tests.test_published_call_observer tests.test_build_player_control_runtime_probe -v
```

Expected: builder prints a SHA-256; confined-diff test proves only two checked BL sites and two zero-filled caves changed.

- [x] **Step 6: Commit and push the shared observer**

```powershell
git add tools/published_call_observer.py tools/build_player_control_runtime_probe.py tests/thumb_observer_machine.py tests/test_published_call_observer.py tests/test_build_player_control_runtime_probe.py openspec/changes/close-scenario-41-battle-runtime/tasks.md
git commit -m "feat(re): publish ordered player control events"
git push origin task/units-character-definitions
```

---

### Task 3: 严格归属的 Windows mGBA GDB 探针

**Files:**
- Modify: `tools/mgba_gdb_probe.py`
- Modify: `tests/test_mgba_gdb_probe.py`
- Modify: `tools/README.md`
- Modify: `notes/macos-intel-runtime-preflight-20260715.md`

**Interfaces:**
- Consumes: mGBA executable, ROM, optional savestate, one stop point and read regions.
- Produces: `parse_stop_reply(payload: str) -> StopReply`, `ensure_port_available(host, port)`, `verify_rom_fingerprint(client, rom)`, and success/error JSON with hashes and strict stop evidence.

- [x] **Step 1: Write RED tests for session ownership and strict stop validation**

```python
def test_port_conflict_fails_before_launcher(self):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    with self.assertRaisesRegex(RuntimeError, "already in use"):
        ensure_port_available("127.0.0.1", listener.getsockname()[1])

def test_stop_reply_requires_target_pc(self):
    stop = parse_stop_reply("T05thread:1;")
    with self.assertRaisesRegex(RuntimeError, "expected PC"):
        validate_breakpoint_stop(stop, {"pc": 0x08070000}, 0x08073946)

def test_cleanup_never_sends_remote_kill(self):
    client = Mock()
    process = Mock()
    close_owned_session(client, process)
    self.assertNotIn(call("k"), client.command.call_args_list)
    process.terminate.assert_called_once()

def test_rom_fingerprint_rejects_wrong_endpoint(self):
    client = Mock()
    client.read_memory.return_value = b"wrong"
    with self.assertRaisesRegex(RuntimeError, "ROM fingerprint"):
        verify_rom_fingerprint(client, self.rom_path)
```

Add fake-RSP cases for ACK/NACK retransmit, checksum mismatch, `S05`, `T05`, `W00`, wrong PC, 600-byte chunking, one `E06` subchunk, and bounded stdout/stderr draining.

- [x] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_mgba_gdb_probe -v`

Expected: FAIL because ownership/stop/fingerprint functions are absent and cleanup still sends `k`.

- [x] **Step 3: Implement minimal strict session behavior**

```python
@dataclass(frozen=True)
class StopReply:
    kind: str
    signal: int | None
    exit_code: int | None
    fields: dict[str, str]
    raw: str

def validate_breakpoint_stop(stop: StopReply, registers: dict[str, int], expected: int) -> None:
    if stop.kind not in {"signal", "trap"} or stop.signal != 5:
        raise RuntimeError(f"unexpected GDB stop: {stop.raw}")
    actual = registers["pc"] & ~1
    accepted = {expected & ~1, (expected + 2) & ~1}
    if actual not in accepted:
        raise RuntimeError(f"breakpoint stopped at 0x{actual:08X}; expected PC 0x{expected:08X}")
```

Before `Popen`, bind-test the port. After connecting, read deterministic ROM windows including `0x08000000` and the requested stop point bytes and compare to the ROM file. Remove `--key`, window enumeration, `PostMessage`, KEYINPUT watch claims and `client.command("k")`. Drain child output continuously into bounded tails, then terminate only the owned `Popen` child; outer `run_guarded.py` owns the full tree.

- [x] **Step 4: Add hashes and actionable failure JSON**

Success and failure results include `outcome`, emulator path/SHA-256/version, ROM path/SHA-256, savestate path/SHA-256, command, port, raw stop, expected/actual PC, registers, read regions and capped child output tails. Failure writing must survive cleanup errors.

- [x] **Step 5: Run unit/fake-server GREEN**

Run: `python -m unittest tests.test_mgba_gdb_probe -v`

Expected: all tests PASS with no Windows input tests remaining.

- [x] **Step 6: Run a guarded native smoke at a known reachable boundary**

```powershell
python tools/run_guarded.py --summary build/resource-guard/mgba-strict-smoke.json -- python tools/mgba_gdb_probe.py --mgba C:\Users\feeli\.cache\codex-tools\mgba\0.10.5\mGBA-0.10.5-win64\mGBA.exe --rom rom/base.gba --savestate artifacts/runtime-checkpoints/actionable-move-grid.ss9 --breakpoint 0x080732B4 --read 0x02026804:8 --read 0x020240C0:256 --output build/mgba-strict-smoke.json
```

Expected: either a verified target stop with matching PC/ROM fingerprint or an explicit bounded `not-proven` timeout; in both cases guard reports `windows-job-object`, owns one process tree, and leaves no mGBA child. A timeout does not block the tool commit if fake-RSP and prior known-stop smoke are green, but must be recorded as runtime-route evidence rather than success.

- [x] **Step 7: Commit and push**

```powershell
git add tools/mgba_gdb_probe.py tests/test_mgba_gdb_probe.py tools/README.md openspec/changes/close-scenario-41-battle-runtime/tasks.md
git commit -m "fix(re): bind mGBA evidence to owned GDB sessions"
git push origin task/units-character-definitions
```

---

### Task 4: Player-control decoder、baseline 与证据 evaluator

**Files:**
- Create: `play/_scripts/scenario-41-runtime-evidence.js`
- Create: `play/_scripts/scenario-41-runtime-evidence.test.js`
- Modify: `play/_scripts/runtime-formation-probe.js`
- Modify: `play/_scripts/runtime-formation-probe.test.js`

**Interfaces:**
- Consumes: 24-byte observer records, checkpoint-time baselines, battle/map/unit/screen diagnostics and explicit input audit.
- Produces: `decodePublishedCall(bytes, expectedMagic)`, `evaluatePlayerControlEvidence(input)`, driver field `playerControlEvidence`.

- [x] **Step 1: Write decoder/evaluator RED tests**

```javascript
test('accepts only a fresh ordered player-control chain', () => {
  const result = evaluatePlayerControlEvidence({
    baseline: { player: call(0, 0), current: call(0, 0) },
    final: { player: call(1, 4, { argument0: 1 }), current: call(1, 5, { argument0: 1 }) },
    battleId: 41,
    mapLoaded: true,
    screenState: 'battle-map',
    controlledCharacterId: 1,
    explicitInputs: ['KeyZ'],
    automaticInputs: [],
  });
  assert.equal(result.verified, true);
});

test('rejects stale, reversed and automatic-input samples', () => {
  assert.equal(evaluatePlayerControlEvidence(staleSample()).reason, 'player-observer-not-fresh');
  assert.equal(evaluatePlayerControlEvidence(reversedSample()).reason, 'observer-order-invalid');
  assert.equal(evaluatePlayerControlEvidence(autoConfirmSample()).reason, 'unlisted-input-used');
});
```

Add a wiring test that injects a fake `readGbaBytes` and proves both the post-checkpoint baseline and plan/settle diagnostics read exactly 24 bytes from `0x0203F060` and `0x0203F080`. Source regex count is not sufficient.

- [x] **Step 2: Run Node tests and verify RED**

Run: `node --test play/_scripts/scenario-41-runtime-evidence.test.js play/_scripts/runtime-formation-probe.test.js`

Expected: FAIL because the evidence module and baseline wiring do not exist.

- [x] **Step 3: Implement the pure evidence module**

```javascript
function decodePublishedCall(bytes, expectedMagic) {
  const data = Buffer.from(bytes);
  if (data.length !== 24) throw new RangeError(`published call record must be 24 bytes, got ${data.length}`);
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
  return {
    rawHex: data.toString('hex'),
    magicValid: view.getUint32(0, true) === expectedMagic,
    hitCount: view.getUint32(4, true),
    argument0: view.getUint32(8, true),
    argument1: view.getUint16(12, true),
    argument2: view.getUint16(14, true),
    sequence: view.getUint32(16, true),
    eventCode: view.getUint32(20, true),
  };
}

function isFresh(after, before) {
  return after.magicValid && after.hitCount > before.hitCount && after.sequence > before.sequence;
}
```

`evaluatePlayerControlEvidence` checks fresh player/current events, sequence order, event codes, battle 41, nonzero map, foreground battle screen, controlled character/slot consistency and zero unlisted inputs. It returns `{verified, reason, checks}` without throwing on evidence failure.

- [x] **Step 4: Wire baseline and explicit-input audit**

Immediately after checkpoint load, read both observer records as immutable baselines. Record every `pressGbaKey` call as explicit or automatic. With `PROBE_EVIDENCE_MODE=player-control`, run the evaluator after each plan/settle diagnostic and stop only when it returns `verified`; settle with `PROBE_SETTLE_CONFIRM_EVERY=0` performs no input.

- [x] **Step 5: Run GREEN and full driver regression**

Run: `node --test play/_scripts/scenario-41-runtime-evidence.test.js play/_scripts/runtime-formation-probe.test.js`

Expected: all tests PASS; existing 39 runtime tests remain green plus new evaluator tests.

- [x] **Step 6: Commit and push the evidence wiring**

```powershell
git add play/_scripts/scenario-41-runtime-evidence.js play/_scripts/scenario-41-runtime-evidence.test.js play/_scripts/runtime-formation-probe.js play/_scripts/runtime-formation-probe.test.js openspec/changes/close-scenario-41-battle-runtime/tasks.md
git commit -m "feat(re): reject stale player-control runtime samples"
git push origin task/units-character-definitions
```

---

### Task 4.5: macOS Intel runtime 迁移前置

**Files:**
- Modify: `tools/project_resource_guard.py`
- Modify: `tests/test_project_resource_guard.py`
- Modify: `tests/test_run_guarded.py`
- Modify: `tools/README.md`
- Create: `notes/macos-intel-runtime-preflight-20260715.md`
- Modify: `openspec/changes/close-scenario-41-battle-runtime/tasks.md`

**Interfaces:**
- Consumes: 现有 `run_guarded.py` heavy lock、POSIX process-group 所有权、macOS `vm_stat` / `ps`、官方 mGBA `0.10.5` tag。
- Produces: Darwin 可用物理内存与 owned-tree RSS 监控、真实 CLI 集成测试、mGBA 0.10.5 x86_64 scripting 构建来源与资源摘要。

- [x] **Step 1: 以 TDD 验收 macOS 资源守卫与 mGBA 0.10.5 前置**

接管当前已归因到本 change 的 Darwin guard 在途 diff。核验已有 RED 证据确实分别来自 `unsupported on darwin`、缺失 `/proc` 和 CLI `protection-failure/125`；运行 GREEN 及完整 guard 回归。记录官方 tag/commit、独立缓存源码与构建路径、版本、架构、二进制 SHA-256、CLI `--script` 能力、配置/构建命令、峰值 RSS 和最终 owned-process 残留检查。更新工具文档，明确 macOS 使用 POSIX process group，不使用按进程名清理。

- [x] **Step 2: 提交迁移前置并同步 OpenSpec 任务**

仅提交上述代码、测试、文档与任务勾选，不提交忽略的 `build/` 诊断文件或外部 mGBA 构建目录。提交前运行 `git diff --check`、相关 Python 单元/集成测试和真实 guard smoke。

---

### Task 4.6: 严格 mGBA 0.10.5 脚本回移与零输入复放

**Files:**
- Create: `tools/patches/mgba-0.10.5-qt-script-cli.patch`
- Create: `tools/build_macos_mgba.py`
- Create: `tests/test_build_macos_mgba.py`
- Create: `tools/mgba_checkpoint_replay.lua`
- Create: `tools/run_macos_mgba_replay.py`
- Create: `tests/test_run_macos_mgba_replay.py`
- Modify: `tools/inspect_mgba_savestate.py`
- Modify: `tests/test_inspect_mgba_savestate.py`
- Modify: `tools/README.md`
- Create: `artifacts/runtime-checkpoints/scenario-41-prebattle-menu-evidence.json`
- Modify: `artifacts/runtime-checkpoints/scenario-41-checkpoints.json`
- Modify: `artifacts/runtime-checkpoints/README.md`
- Create: `notes/scenario-41-prebattle-menu-macos-20260715.md`
- Modify: `docs/sequel-roadmap.md`
- Modify: `openspec/changes/close-scenario-41-battle-runtime/tasks.md`

**Interfaces:**
- Consumes: clean mGBA `0.10.5` commit `26b7884bc25a5933960f3cdcd98bac1ae14d42e2`、上游 Qt `--script` commit `7cacae126207de5499857439b9c7919bf8e882c2`、base ROM、prebattle candidate、Task 4.5 Darwin guard。
- Produces: 明确标识的“mGBA 0.10.5 + Qt script backport” x86_64 二进制、参数化零输入 replay、frame-80 state/截图/audit、可离线验收的 prebattle menu evidence 与 accepted ledger 记录。

- [x] **Step 1: 以 TDD 固化两文件 Qt `--script` 回移与受控构建**

版本化保存上游 `7cacae1` 的原始两文件 patch。构建工具只接受 clean `0.10.5`/`26b7884...` 源码，在独立缓存副本先运行 `git apply --check` 再应用 patch；不得触碰 `/Users/altair/github/mgba-src` 的用户脏树。clone/configure/build/能力检查全部经同一个 heavy guard，记录 patch 与二进制 SHA-256、x86_64、CMake flags、峰值 RSS、退出码和 PGID 残留。RED/GREEN 必须覆盖错误 tag、dirty source、patch 不可应用、缺失 `--script`，并用一个真实 Lua sentinel 证明脚本能在 base ROM 启动后执行。

- [x] **Step 2: 以 TDD 实现参数化 frame-80 checkpoint replay**

Lua replay 从显式环境/配置读取输入 state、输出 state/截图/audit 和 capture frame；零输入模式必须生成 `inputs=[]`，不得调用 `emu:addKey`/`clearKey`，frame 80 保存后 `os.exit(0)`。Python runner 校验 ROM/state/binary/patch 哈希，强制 `QT_QPA_PLATFORM=offscreen`、heavy guard、wall/idle/RSS 上限与 owned PGID 清理；仅当 sentinel、audit、`.ss9`、截图、guard summary 全部存在且一致时返回 0。补重复 `--script` 执行顺序、缺失脚本、缺失产物、非零 child、超时和残留的失败测试与真实 ROM smoke。

- [x] **Step 3: 零输入验收 prebattle candidate 并固化快照证据**

在 base ROM 上从 `scenario-41-prebattle-menu-candidate.ss9` 零输入运行 80 帧。验收必须同时证明：截图仍为同一战前菜单；task 2 resume PC 为 `0x08067D02`；活动 unwind 为 `0x080885C1 → 0x08088F9F → 0x0808F92D` 且不含 `0x0808F957`；`[0x0202680C]=0`；ROM/state/emulator/patch 哈希正确；guard completed/0；最终 PGID/监听端口无残留。先以 TDD 扩展离线 inspector 生成这些字段。全部成立才把现有 candidate 记为 accepted 并更新 ledger/evidence/README/notes/roadmap；任一不成立则保持 not-proven，记录失败且不得继续 Down/A。

---

### Task 4.7: 从 accepted prebattle menu 分段进入 controller

设计边界见 `docs/superpowers/specs/2026-07-15-scenario-41-prebattle-to-controller-design.md`；
A 后动画稳定性补充见
`docs/superpowers/specs/2026-07-16-scenario-41-animated-snapshot-stability-design.md`。

**Files:**
- Create: `tools/mgba_single_input_replay.lua`
- Create: `tools/run_macos_mgba_single_input.py`
- Create: `tools/macos_mgba_runtime_residue.py`
- Create: `tools/mgba_zero_input_cycle_sample.lua`
- Create: `tools/analyze_mgba_zero_input_cycle.py`
- Create: `tests/test_run_macos_mgba_single_input.py`
- Create: `tests/test_macos_mgba_runtime_residue.py`
- Create: `tests/test_analyze_mgba_zero_input_cycle.py`
- Create when accepted: `artifacts/runtime-checkpoints/scenario-41-prebattle-down.ss9`
- Create: `artifacts/runtime-checkpoints/scenario-41-prebattle-down-evidence.json`
- Create when accepted: `artifacts/runtime-checkpoints/scenario-41-pre-controller-after-a.ss9`
- Create when accepted: `artifacts/runtime-checkpoints/scenario-41-pre-controller-after-a-evidence.json`
- Create when reached: `artifacts/runtime-checkpoints/scenario-41-controller-entry.ss9`
- Create when reached: `artifacts/runtime-checkpoints/scenario-41-controller-entry-evidence.json`
- Create: `notes/scenario-41-prebattle-to-controller-macos-20260715.md`
- Modify: `artifacts/runtime-checkpoints/scenario-41-checkpoints.json`
- Modify: `artifacts/runtime-checkpoints/README.md`
- Modify: `tools/README.md`
- Modify: `docs/sequel-roadmap.md`
- Modify: `openspec/changes/close-scenario-41-battle-runtime/tasks.md`

**Interfaces:**
- Consumes: accepted `scenario-41-prebattle-menu-candidate.ss9`; strict mGBA 0.10.5 manifest/binary/patch; `run_macos_mgba_replay` provenance/path/guard helpers; offline savestate inspector.
- Produces: `validate_single_input(key: str, down_frame: int, up_frame: int, capture_frame: int) -> None`, shared read-only `probe_runtime_residue(pgid: int) -> dict[str, object]`, `select_exact_period(baseline_rgb_sha256: str, frame_hashes: Mapping[int, str]) -> int | None`, fixed single-input/cycle-sampler Lua contracts, guarded state/PNG/audit/sentinel output, accepted Down/post-A snapshots only after zero-input stability, and optionally a controller-entry checkpoint.
- Global stop gate: A is forbidden until Down candidate is accepted; player-control work is forbidden until raw `0x0808F957` is in the statically validated active unwind or a fresh entry observer proves `0x0808F952 → 0x080732B4`.

- [x] **Step 1: 以 TDD 实现独立 single-input native runner**

先写 `tests/test_run_macos_mgba_single_input.py`。RED 必须覆盖：

```python
def test_only_down_or_a_and_strict_frame_order():
    for key in ("B", "Up", "Down+A", ""):
        with self.assertRaises(ReplayError):
            validate_single_input(key, 5, 13, 80)
    for frames in ((13, 5, 80), (5, 5, 80), (5, 80, 80), (0, 13, 80)):
        with self.assertRaises(ReplayError):
            validate_single_input("Down", *frames)

def test_payload_has_one_explicit_event_and_no_automatic_inputs():
    payload = {
        "evidence_mode": "single-input",
        "zero_input_verified": False,
        "inputs": [{"key": "Down", "down_frame": 5, "up_frame": 13, "hold_frames": 8}],
        "automatic_inputs": [],
        "recovery_inputs": [],
        "frame": 80,
        "capture_frame": 80,
    }
    validate_single_input_payload(payload, key="Down", down_frame=5, up_frame=13, capture_frame=80)
    self.assertEqual(payload["inputs"], [{"key": "Down", "down_frame": 5, "up_frame": 13, "hold_frames": 8}])
    self.assertEqual(payload["automatic_inputs"], [])
    self.assertEqual(payload["recovery_inputs"], [])
    self.assertFalse(payload["zero_input_verified"])

def test_residue_rejects_owned_pgid_or_mgba_listener():
    with self.assertRaises(RuntimeResidueError):
        validate_runtime_residue(20050, "22 20050 mGBA\n", "", lsof_exit_code=1)
    with self.assertRaises(RuntimeResidueError):
        validate_runtime_residue(20050, "", "p22\ncmGBA\nn*:2345\n", lsof_exit_code=0)
```

静态 Lua contract 还必须证明只有一次 `emu:addKey`/`clearKey`，只映射
`C.GBA_KEY.DOWN/A`，没有循环补键、adaptive/recovery/settle 输入。运行 focused test，确认因模块/函数缺失而 RED。

最小 GREEN 使用独立 `tools/run_macos_mgba_single_input.py`，只 import/reuse
`ReplayError`、`sha256_file`、`canonical_input`、`validate_output_paths`、
`prepare_fresh_output`、`validate_expected_hash`、`validate_build_manifest`、
`emulator_command`、`guarded_command`、`validate_guard_summary`、`read_ps_snapshot` 与
`validate_owned_pgid_clean`。禁止 `--pre-script` 和 custom Lua；固定 `QT_QPA_PLATFORM=offscreen`、
heavy lock、4096 MiB admission、1536 MiB RSS、fresh output、post-run rehash、staged `.sav`
隔离及 exact PGID/listener clean。把 `accept_prebattle_candidate.py` 已验证的只读 `ps`/`lsof`
逻辑抽到 `macos_mgba_runtime_residue.py` 并保持兼容 import，禁止按进程名 kill。现有
zero-input runner/Lua 及其 SHA 不得修改。

Run:

```bash
python3 -m unittest tests.test_run_macos_mgba_single_input tests.test_run_macos_mgba_replay tests.test_run_guarded -v
```

Expected: PASS；1 个既有 Windows-only test 可 skip。

- [x] **Step 2: guarded 单 Down 捕获 candidate，不发送 A**

从 accepted prebattle menu 运行固定 `Down`、frames `5/13/80`。输出使用 fresh 目录
`build/scenario-41-prebattle-down-20260715/`，并记录 binary/manifest/patch/ROM/input state/Lua
SHA、唯一 input event、state/PNG/audit/sentinel/guard、peak RSS、PGID 与 listener。命令必须显式给出
accepted input hash `b7badf1c7988f01614b92a46bcd54322d7693d120c4cdd671f0a3f56a4db7078`；
运行前后 `rom/base.sav` 必须不存在。

Run:

```bash
python3 tools/run_macos_mgba_single_input.py \
  --binary /Users/altair/.cache/codex-tools/mgba/0.10.5-script-backport-build-fix1-20260715/qt/mGBA.app/Contents/MacOS/mGBA \
  --build-manifest /Users/altair/.cache/codex-tools/mgba/0.10.5-script-backport-manifest-fix1-20260715.json \
  --expected-build-manifest-sha256 9da6779d7c1ac3140e512b233f98abe754c4f11f3fbc8157af147e014661cc4d \
  --expected-binary-sha256 20859087582ad16942f37e70ea973a09671b320aa0936aa72e43e9915b1ed408 \
  --rom rom/base.gba --expected-rom-sha256 1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b \
  --state artifacts/runtime-checkpoints/scenario-41-prebattle-menu-candidate.ss9 \
  --expected-state-sha256 b7badf1c7988f01614b92a46bcd54322d7693d120c4cdd671f0a3f56a4db7078 \
  --key Down --down-frame 5 --up-frame 13 --capture-frame 80 \
  --staged-rom build/scenario-41-prebattle-down-20260715/staged-base.gba \
  --output-state build/scenario-41-prebattle-down-20260715/after-down.ss9 \
  --output-png build/scenario-41-prebattle-down-20260715/after-down.png \
  --audit build/scenario-41-prebattle-down-20260715/audit.json \
  --sentinel build/scenario-41-prebattle-down-20260715/sentinel.json \
  --guard-summary build/scenario-41-prebattle-down-20260715/guard-summary.json
```

Expected: guard `completed/0`、non-degraded POSIX process group、`inputs` 恰为一个 Down。
人工查看 PNG，并用 `png_screen_fingerprint` 与离线 inspector 记录变化；此步只生成 build
candidate，不登记 accepted。若画面未变化、离开 prebattle、task context 无法受约束解释或任何
资源/来源门失败，记录 not-proven 并停止，不执行 Step 3/4。

- [x] **Step 3: 零输入复验 Down candidate 后才固化快照**

使用现有 `run_macos_mgba_replay.py --evidence-mode zero-input` 从 Down candidate 再运行 80 帧，
写入独立 fresh 目录。验收同时要求：candidate/replay normalized RGB pixels 相同；task 2
resume PC、显式 active-unwind slots 和 `[0x0202680C]` 相同；zero-input audit 为 `inputs=[]`；
所有 caller-known hash 正确；guard completed/0；PGID/listener clean。

Run（先从 Step 2 产物实算 hash，不能从文件名推断）：

```bash
DOWN_SHA256="$(shasum -a 256 build/scenario-41-prebattle-down-20260715/after-down.ss9 | awk '{print $1}')"
python3 tools/run_macos_mgba_replay.py \
  --binary /Users/altair/.cache/codex-tools/mgba/0.10.5-script-backport-build-fix1-20260715/qt/mGBA.app/Contents/MacOS/mGBA \
  --build-manifest /Users/altair/.cache/codex-tools/mgba/0.10.5-script-backport-manifest-fix1-20260715.json \
  --expected-build-manifest-sha256 9da6779d7c1ac3140e512b233f98abe754c4f11f3fbc8157af147e014661cc4d \
  --expected-binary-sha256 20859087582ad16942f37e70ea973a09671b320aa0936aa72e43e9915b1ed408 \
  --rom rom/base.gba --expected-rom-sha256 1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b \
  --state build/scenario-41-prebattle-down-20260715/after-down.ss9 \
  --expected-state-sha256 "$DOWN_SHA256" --capture-frame 80 --evidence-mode zero-input \
  --staged-rom build/scenario-41-prebattle-down-zero-20260715/staged-base.gba \
  --output-state build/scenario-41-prebattle-down-zero-20260715/frame80.ss9 \
  --output-png build/scenario-41-prebattle-down-zero-20260715/frame80.png \
  --audit build/scenario-41-prebattle-down-zero-20260715/audit.json \
  --sentinel build/scenario-41-prebattle-down-zero-20260715/sentinel.json \
  --guard-summary build/scenario-41-prebattle-down-zero-20260715/guard-summary.json
```

只有全部成立才复制为 `artifacts/runtime-checkpoints/scenario-41-prebattle-down.ss9`，将 ledger
状态设 accepted，并写 compact evidence/note/README/roadmap。若不成立，保留 build candidate
和失败 note，不复制、不登记 accepted，并停止 A。

- [x] **Step 4: 只从 accepted Down snapshot 发送单 A（按失败分支完成）**

输入必须是 Step 3 tracked snapshot 的实算 SHA；仍使用 frames `5/13/80`、唯一 A、fresh
目录与同一 provenance/guard 门。不得同轮附加第二个 A、方向键、B 或恢复输入。捕获后先离线
列出 task 2 SP/resume PC 与受约束的 return slots；再对该 candidate 做独立 zero-input 80-frame
复验。任一不稳定或无法解释即保持 not-proven 并停止。

Run:

```bash
DOWN_ACCEPTED_SHA256="$(shasum -a 256 artifacts/runtime-checkpoints/scenario-41-prebattle-down.ss9 | awk '{print $1}')"
python3 tools/run_macos_mgba_single_input.py \
  --binary /Users/altair/.cache/codex-tools/mgba/0.10.5-script-backport-build-fix1-20260715/qt/mGBA.app/Contents/MacOS/mGBA \
  --build-manifest /Users/altair/.cache/codex-tools/mgba/0.10.5-script-backport-manifest-fix1-20260715.json \
  --expected-build-manifest-sha256 9da6779d7c1ac3140e512b233f98abe754c4f11f3fbc8157af147e014661cc4d \
  --expected-binary-sha256 20859087582ad16942f37e70ea973a09671b320aa0936aa72e43e9915b1ed408 \
  --rom rom/base.gba --expected-rom-sha256 1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b \
  --state artifacts/runtime-checkpoints/scenario-41-prebattle-down.ss9 \
  --expected-state-sha256 "$DOWN_ACCEPTED_SHA256" \
  --key A --down-frame 5 --up-frame 13 --capture-frame 80 \
  --staged-rom build/scenario-41-controller-a-20260715/staged-base.gba \
  --output-state build/scenario-41-controller-a-20260715/after-a.ss9 \
  --output-png build/scenario-41-controller-a-20260715/after-a.png \
  --audit build/scenario-41-controller-a-20260715/audit.json \
  --sentinel build/scenario-41-controller-a-20260715/sentinel.json \
  --guard-summary build/scenario-41-controller-a-20260715/guard-summary.json
```

实际结果：唯一 A 与资源/来源门通过，但随后的独立 80-frame zero-input replay 与 candidate
存在 140 个 Naruto 动画像素差异；task 2、三个 static-BL-valid unwind slots 和
`[0x0202680C]` 一致。按原门槛保持 `not-proven`，未进入 Step 5。下一步只能执行已批准的
`docs/superpowers/specs/2026-07-16-scenario-41-animated-snapshot-stability-design.md`。

- [x] **Step 4A: 以 TDD 实现固定周期 sampler 与 exact 周期分析器**

先创建 `tests/test_analyze_mgba_zero_input_cycle.py`。RED 必须同时覆盖 Lua 静态契约和纯分析
逻辑：

```python
def test_selects_smallest_period_with_two_exact_recurrences():
    hashes = {frame: f"frame-{frame}" for frame in range(1, 601)}
    hashes[12] = hashes[24] = "baseline"
    hashes[18] = hashes[36] = "baseline"
    self.assertEqual(select_exact_period("baseline", hashes), 12)

def test_requires_complete_600_frames_and_rejects_late_or_single_match():
    complete = {frame: f"frame-{frame}" for frame in range(1, 601)}
    with self.assertRaisesRegex(CycleAnalysisError, "frames 1..600"):
        select_exact_period("baseline", {1: "baseline"})
    complete[301] = complete[600] = "baseline"
    self.assertIsNone(select_exact_period("baseline", complete))
    complete[40] = "baseline"
    self.assertIsNone(select_exact_period("baseline", complete))

def test_sampler_has_fixed_bound_progress_and_no_input_api():
    text = SAMPLER.read_text(encoding="utf-8")
    self.assertIn("max_frame == 600", text)
    self.assertIn('string.format("%s/frame-%04d.png"', text)
    self.assertIn("frame % 30 == 0", text)
    self.assertEqual(text.count("emu:screenshot"), 1)
    for forbidden in ("emu:addKey", "emu:clearKey", "emu:setKeys"):
        self.assertNotIn(forbidden, text)
```

Run RED:

```bash
python3 -m unittest tests.test_analyze_mgba_zero_input_cycle -v
```

Expected: FAIL because the module/Lua and `select_exact_period` do not exist.

Minimal GREEN in `tools/analyze_mgba_zero_input_cycle.py` must expose exactly:

```python
MAX_FRAME = 600
MAX_PERIOD = 300

class CycleAnalysisError(ValueError):
    pass

def select_exact_period(
    baseline_rgb_sha256: str, frame_hashes: Mapping[int, str]
) -> int | None:
    if set(frame_hashes) != set(range(1, MAX_FRAME + 1)):
        raise CycleAnalysisError("cycle sample must contain frames 1..600 exactly once")
    for period in range(1, MAX_PERIOD + 1):
        if (
            frame_hashes[period] == baseline_rgb_sha256
            and frame_hashes[period * 2] == baseline_rgb_sha256
        ):
            return period
    return None
```

`analyze_frame_directory(...)` 必须拒绝 symlink、缺帧、`frame-0001.png`..`frame-0600.png`
之外的 frame PNG，并复用 `tools.inspect_mgba_savestate.png_screen_fingerprint`，不得实现宽松
PNG decoder。CLI 必须验证 baseline PNG caller-known SHA、diagnostic audit 为
`script-order-diagnostic`/`inputs=[]`/`capture_frame=600`，且 `pre_scripts` 恰好绑定固定 sampler
路径与运行前 SHA；输出包含 600 个 frame RGB hash、baseline file/RGB hash、sampler/audit hash、
`period` 和 `status=cycle-found|not-proven` 的 JSON。

`tools/mgba_zero_input_cycle_sample.lua` 只读取 `MGBA_CYCLE_OUTPUT_DIR` 与
`MGBA_CYCLE_MAX_FRAME=600`，注册一个 frame callback，逐帧写
`frame-%04d.png`，每 30 帧 `print` 进度；不加载/保存 state、不退出、不发送输入，frame 600
的 state/audit/sentinel 仍由未修改的 `mgba_checkpoint_replay.lua` 负责。

Run GREEN/refactor:

```bash
python3 -m unittest tests.test_analyze_mgba_zero_input_cycle tests.test_run_macos_mgba_replay tests.test_run_macos_mgba_single_input -v
python3 -m py_compile tools/analyze_mgba_zero_input_cycle.py
git diff --check
```

Expected: PASS；既有 zero-input 与 single-input Lua/runner SHA 和行为不变。提交只包含新
sampler、analyzer、测试与必要的 `tools/README.md` 说明。

- [ ] **Step 4B: guarded 采样 600 个零输入动画帧并选择周期**

输入必须继续使用 Step 4 的单 A candidate，实算并核对 state SHA
`43f19bf7b80f900be6d34bd4da3bdfc4daf206bd78da1e6e68754071bb40f6e8` 与 baseline PNG file SHA
`efc787f7c8644b63145c3923553775697b99059ff88b003d8af9afc47d659f85`。fresh 目录必须不存在，
`rom/base.sav` 必须在前后均不存在：

```bash
test ! -e build/scenario-41-controller-a-cycle-sample-20260716
mkdir -p build/scenario-41-controller-a-cycle-sample-20260716/frames
SAMPLER_SHA256="$(shasum -a 256 tools/mgba_zero_input_cycle_sample.lua | awk '{print $1}')"
MGBA_CYCLE_OUTPUT_DIR="$PWD/build/scenario-41-controller-a-cycle-sample-20260716/frames" \
MGBA_CYCLE_MAX_FRAME=600 \
python3 tools/run_macos_mgba_replay.py \
  --binary /Users/altair/.cache/codex-tools/mgba/0.10.5-script-backport-build-fix1-20260715/qt/mGBA.app/Contents/MacOS/mGBA \
  --build-manifest /Users/altair/.cache/codex-tools/mgba/0.10.5-script-backport-manifest-fix1-20260715.json \
  --expected-build-manifest-sha256 9da6779d7c1ac3140e512b233f98abe754c4f11f3fbc8157af147e014661cc4d \
  --expected-binary-sha256 20859087582ad16942f37e70ea973a09671b320aa0936aa72e43e9915b1ed408 \
  --rom rom/base.gba --expected-rom-sha256 1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b \
  --state build/scenario-41-controller-a-20260715/after-a.ss9 \
  --expected-state-sha256 43f19bf7b80f900be6d34bd4da3bdfc4daf206bd78da1e6e68754071bb40f6e8 \
  --capture-frame 600 --evidence-mode script-order-diagnostic \
  --pre-script tools/mgba_zero_input_cycle_sample.lua \
  --staged-rom build/scenario-41-controller-a-cycle-sample-20260716/staged-base.gba \
  --output-state build/scenario-41-controller-a-cycle-sample-20260716/frame600.ss9 \
  --output-png build/scenario-41-controller-a-cycle-sample-20260716/frame600.png \
  --audit build/scenario-41-controller-a-cycle-sample-20260716/audit.json \
  --sentinel build/scenario-41-controller-a-cycle-sample-20260716/sentinel.json \
  --guard-summary build/scenario-41-controller-a-cycle-sample-20260716/guard-summary.json \
  --wall-timeout-s 300 --idle-timeout-s 60

python3 tools/analyze_mgba_zero_input_cycle.py \
  --baseline-png build/scenario-41-controller-a-20260715/after-a.png \
  --expected-baseline-png-sha256 efc787f7c8644b63145c3923553775697b99059ff88b003d8af9afc47d659f85 \
  --frame-dir build/scenario-41-controller-a-cycle-sample-20260716/frames \
  --audit build/scenario-41-controller-a-cycle-sample-20260716/audit.json \
  --sampler tools/mgba_zero_input_cycle_sample.lua \
  --expected-sampler-sha256 "$SAMPLER_SHA256" \
  --output build/scenario-41-controller-a-cycle-sample-20260716/cycle-analysis.json
```

Expected: exactly 600 PNGs, audit/sentinel identical before analyzer rewrite, guard `completed/0`, no
PGID/listener/base.sav residue, peak RSS recorded, and analysis returns the smallest exact period
`1 <= p <= 300` with `H[0]=H[p]=H[2p]`. No period is a valid bounded `not-proven` result：record it
and stop before Step 4C/5.

- [ ] **Step 4C: 用两段独立 p-frame zero-input replay 接纳或拒绝 A 后快照**

从 `cycle-analysis.json` 读取 `p`。第一段从原单 A candidate 运行 `p` 帧，第二段从第一段输出
state 再运行 `p` 帧；两段都使用现有 `run_macos_mgba_replay.py --evidence-mode zero-input`、
独立 fresh 目录、无 pre-script。禁止重用 Step 4 的旧 80-frame replay 充当其中一段。

验收必须同时满足：candidate、`png-p`、`png-2p` normalized RGB8 全屏像素 SHA 完全相同；
三个 state 的 task 2 resume PC、所有显式 static-BL-valid unwind slots 和 `[0x0202680C]` 相同；
两轮 audit 都是 `inputs=[]`/`pre_scripts=[]`/`zero_input_verified=true`；ROM/state/binary/
manifest/patch/Lua hash、guard、PGID/listener/base.sav 全通过。任何失败都持久记录
`not-proven` 并停止 Step 5。

全部通过时复制第一段输出为
`artifacts/runtime-checkpoints/scenario-41-pre-controller-after-a.ss9`，新增 compact evidence，
更新 ledger/README/note/roadmap。lineage 必须记录 accepted Down → 唯一 A → zero settle `p`；
`allowed_evidence=[]`，明确它不证明 controller entry/player control。提交不得包含 600 张 raw
PNG 或 fresh build 目录。

- [ ] **Step 5: 只按 controller 门槛接纳，不用画面分类替代**

controller acceptance 仅有两条合法路径：

1. 当前 task 2 active unwind 的显式栈槽包含 raw `0x0808F957`，且 base ROM 静态解码
   `0x0808F952 → 0x080732B4`；或
2. 独立 observer 在 post-load baseline 后 fresh 命中该 entry call。

`battle_id`、map、formation、白框或 battle-map 画面只能补充。门槛通过才固化
`scenario-41-controller-entry.ss9`；否则 compact evidence 记录 candidate/not-proven，明确没有
controller entry/player control，并停止 Task 6。

- [ ] **Step 6: 验证、独立审查并同步 OpenSpec**

Run:

```bash
python3 -m unittest tests.test_run_macos_mgba_single_input tests.test_run_macos_mgba_replay tests.test_inspect_mgba_savestate tests.test_runtime_checkpoint_ledger tests.test_run_guarded -v
python3 -m unittest tests.test_macos_mgba_runtime_residue tests.test_accept_prebattle_candidate -v
python3 tools/runtime_checkpoint_ledger.py artifacts/runtime-checkpoints/scenario-41-checkpoints.json
python3 -m py_compile tools/run_macos_mgba_single_input.py tools/inspect_mgba_savestate.py
git diff --check
```

Expected: tests/ledger/compile/diff PASS；所有运行目录记录 peak RSS 且无 owned PGID/listener；
`rom/base.sav` 不存在。thorough reviewer 必须检查 input 数量、zero-input 分段、活动 unwind、
snapshot lineage 与 not-proven 边界；通过后才勾选对应 plan/OpenSpec。

---

### Task 5: Canonical start checkpoint 历史运行（已执行，结果 not-proven）

**Files:**
- Persisted: `artifacts/runtime-checkpoints/scenario-41-start-row.ss9`
- Persisted: `artifacts/runtime-checkpoints/scenario-41-player-control-evidence.json`
- Persisted: `notes/scenario-41-player-control-runtime-20260715.md`
- Updated: `artifacts/runtime-checkpoints/scenario-41-checkpoints.json`
- Updated: `artifacts/runtime-checkpoints/README.md`
- Not produced: `artifacts/runtime-checkpoints/scenario-41-start-confirm.ss9`
- Not produced: `artifacts/runtime-checkpoints/scenario-41-player-turn.ss9`

**Interfaces:**
- Consumes: Task 1 ledger, Task 2 observer ROM, Task 4 evaluator, candidate `build/natural-s41-menu-index2.ss9`.
- Produces: accepted start-row、pre-controller negative checkpoint 与 compact `not-proven` evidence；没有 player-turn checkpoint。

- [x] **Step 1: Prove the candidate is stable before copying it（历史执行）**

Run two guarded zero-input replays on base ROM with `START_COUNT=0`, `ADVANCE_COUNT=0`, empty `TAIL_KEYS`, `SETTLE_CONFIRM_EVERY=0`, `ADAPTIVE_BACK=0`, `STOP_ON_MATCH=0`, `FORCE_SETTLE=1`. Both runs must show the same “开始任务” selected row, battle/map/formation absent, no observer samples and identical declared WRAM fields.

历史结果：compact evidence 记录两轮 UI/声明 WRAM 相同，tracked start-row 内嵌画面与 hash 可离线复核。raw build JSON/PNG 已不在仓库，guard 当时为 `child-exit/1` 且 residue/listener 未记录，因此只保留历史证据上限，不把它改写为当前可复核 PASS，也不重跑缺失 candidate。

- [x] **Step 2: Copy only the accepted checkpoint and update hashes（历史执行）**

```powershell
Copy-Item -LiteralPath build\natural-s41-menu-index2.ss9 -Destination artifacts\runtime-checkpoints\scenario-41-start-row.ss9
python tools/runtime_checkpoint_ledger.py artifacts/runtime-checkpoints/scenario-41-checkpoints.json
```

实际结果：`scenario-41-start-row` 已 accepted，SHA-256 为 `e5039f21675dde00f3bc78e7dad08bf7cbd4ce8bff2944ea108a92bbf25b9e81`。后续证据无法证明保存点位于两个 hook 之前，因此 ledger 保守使用 `before_hooks=[]`、`allowed_evidence=[]`。

- [x] **Step 3: Run one explicit A from start-row with the observer ROM（历史执行）**

```powershell
$env:PROBE_ROM='build/scenario-41-player-control.gba'
$env:PROBE_STATE_LOAD='artifacts/runtime-checkpoints/scenario-41-start-row.ss9'
$env:PROBE_SKIP_NEW_GAME='1'; $env:PROBE_START_COUNT='0'; $env:PROBE_ADVANCE_COUNT='0'
$env:PROBE_TAIL_KEYS='KeyZ'; $env:PROBE_TAIL_REPEAT='1'; $env:PROBE_ADAPTIVE_BACK='0'
$env:PROBE_SETTLE_CONFIRM_EVERY='0'; $env:PROBE_STOP_ON_MATCH='0'; $env:PROBE_FORCE_SETTLE='1'
$env:PROBE_EVIDENCE_MODE='player-control'; $env:PROBE_STATE_DUMP='build/scenario-41-after-start-a.ss9'
$env:PROBE_RESULT='build/scenario-41-after-start-a.json'; $env:PROBE_SCREENSHOT='build/scenario-41-after-start-a.png'
python tools/run_guarded.py --summary build/resource-guard/scenario-41-after-start-a.json -- node play/_scripts/runtime-formation-probe.js
```

If this run only opens “开始任务？”, verify the screenshot and absent hook, then copy the exported state to `scenario-41-start-confirm.ss9`, add it to the ledger, and rerun the same command from that state with exactly one A. Do not add a second A to the same plan.

历史结果：唯一 A 到达后来经 task 栈复核的 pre-controller lineup/deployment；没有追加第二 A，也没有 distinct start-confirm checkpoint。

- [x] **Step 4: Require a fresh player-control result and base control（按失败分支完成）**

Acceptance requires: `PCO1` and `PCU1` counts increase from post-load baselines; player sequence precedes current-unit sequence; arguments match the captured controllable slot/character/affiliation; battle ID 41, map and foreground battle screen agree; automatic input list is empty. Replay the same checkpoint/input on `rom/base.gba` and compare user-visible screen plus declared non-target WRAM.

If strict battle arrival occurs with zero fresh hit, persist it as `not-proven` and return to the earlier checkpoint; do not promote the evidence.

实际结果：observer/base 可见行为一致，但 `PCO1/PCU1` baseline/final 均为零；evaluator 为 `player-observer-not-fresh`，因此按计划持久化 `not-proven`。

- [x] **Step 5: Persist compact not-proven evidence；不创建 player-turn**

Copy only the accepted player-turn state, record all ROM/checkpoint hashes, input `KeyZ`, before/after observer records, controlled unit, screenshot hash, base-control comparison and guard peak in `scenario-41-player-control-evidence.json`. The note must list failed/misnamed checkpoints and explain why zero scratch after a crossed hook is inconclusive.

失败分支结果已写入 `scenario-41-player-control-evidence.json` 与调查 note；没有创建或接纳 `scenario-41-player-turn.ss9`。

- [x] **Step 6: Verify and commit historical not-proven result**

Run:

```powershell
python tools/runtime_checkpoint_ledger.py artifacts/runtime-checkpoints/scenario-41-checkpoints.json
python -m unittest tests.test_runtime_checkpoint_ledger tests.test_published_call_observer tests.test_build_player_control_runtime_probe tests.test_mgba_gdb_probe -v
node --test play/_scripts/scenario-41-runtime-evidence.test.js play/_scripts/runtime-formation-probe.test.js
git diff --check
```

历史提交为 `2bd9760`，provenance hardening 为 `ce67a8a`，task-context 收窄为 `4949a86`。旧 raw summaries 没有 durable residue/owned-tree/listener postcheck，因此不得补写该部分为 PASS；当前分支 push 状态也不在本计划中声称。

不再运行旧计划中的 player-turn `git add/push` 命令；该 checkpoint 从未通过门槛，也不存在。

---

### Task 6: 自然行动提交与 MOVEDONE checkpoint

**Files:**
- Create: `tools/build_action_submit_runtime_probe.py`
- Create: `tests/test_build_action_submit_runtime_probe.py`
- Extend: `play/_scripts/scenario-41-runtime-evidence.js`
- Extend: `play/_scripts/scenario-41-runtime-evidence.test.js`
- Create: `artifacts/runtime-checkpoints/scenario-41-turn-1-complete.ss9`
- Create: `artifacts/runtime-checkpoints/scenario-41-movedone-evidence.json`
- Create: `notes/scenario-41-movedone-runtime-20260715.md`
- Modify: `artifacts/runtime-checkpoints/scenario-41-checkpoints.json`
- Modify: `openspec/changes/close-scenario-41-battle-runtime/tasks.md`

**Interfaces:**
- Consumes: `published_call_observer`, player-turn checkpoint and explicit short input plans.
- Produces: two-site MOVEDONE observer for `0x0807443C` and `0x08074918`, `evaluateMovedoneEvidence`, accepted turn-1 checkpoint.

- [ ] **Step 1: Write builder/evaluator RED tests**

```python
def test_patches_both_checked_movedone_calls(self):
    probe = build_probe((ROOT / "rom/base.gba").read_bytes())
    self.assertEqual(decode_call(probe, 0x0807443C), 0x0809E800)
    self.assertEqual(decode_call(probe, 0x08074918), 0x0809E880)
    self.assertEqual(changed_ranges(probe), expected_checked_ranges())
```

```javascript
test('MOVEDONE requires a fresh event and matching unit transition', () => {
  assert.equal(evaluateMovedoneEvidence({
    baseline: call(0, 0), final: call(1, 8),
    beforeUnit: { x: 4, y: 4, moved: false },
    afterUnit: { x: 4, y: 7, moved: true },
    explicitInputs: ['ArrowDown', 'ArrowDown', 'ArrowDown', 'KeyZ'],
    automaticInputs: [],
  }).verified, true);
});
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m unittest tests.test_build_action_submit_runtime_probe -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
node --test play/_scripts/scenario-41-runtime-evidence.test.js
```

Expected: both commands FAIL for missing builder/evaluator.

- [ ] **Step 3: Implement the minimal two-call observer and evaluator**

Use checked base calls `0x0807443C → 0x080722A8` and `0x08074918 → 0x080722A8`, independent slots/event codes and the shared wrapper API. `evaluateMovedoneEvidence` requires one fresh candidate event, explicit input only, same controlled unit identity, coordinate/state transition, and scenario 41.

- [ ] **Step 4: Run GREEN and build the ROM**

Run:

```powershell
python -m unittest tests.test_build_action_submit_runtime_probe tests.test_published_call_observer -v
node --test play/_scripts/scenario-41-runtime-evidence.test.js
python tools/build_action_submit_runtime_probe.py rom/base.gba build/scenario-41-action-submit.gba
```

Expected: all tests PASS; confined diff contains exactly two calls and two caves.

- [ ] **Step 5: Execute the first tutorial action in short explicit steps**

From `scenario-41-player-turn.ss9`, sample the actual controlled unit and target `(4,7)`. Send one direction/confirm at a time, export a candidate checkpoint at each stable tutorial prompt, and never use adaptive recovery. Complete direction and defense selections only when the preceding screenshot/WRAM boundary matches the tutorial state.

Acceptance requires fresh MOVEDONE at either checked call, matching controlled-unit before/after coordinates and action/round state, no automatic inputs, and a base-ROM control replay. Then accept `scenario-41-turn-1-complete.ss9` in the ledger.

- [ ] **Step 6: Persist, verify, and create a focused local commit**

Run all Task 6 Python/Node tests, ledger validation, `git diff --check`, and check the guard summary/memory. Persist the exact input list, event site, sequence, unit/round before-after and failed routes.

```powershell
git add tools/build_action_submit_runtime_probe.py tests/test_build_action_submit_runtime_probe.py play/_scripts/scenario-41-runtime-evidence.js play/_scripts/scenario-41-runtime-evidence.test.js artifacts/runtime-checkpoints/scenario-41-turn-1-complete.ss9 artifacts/runtime-checkpoints/scenario-41-movedone-evidence.json artifacts/runtime-checkpoints/scenario-41-checkpoints.json notes/scenario-41-movedone-runtime-20260715.md openspec/changes/close-scenario-41-battle-runtime/tasks.md
git commit -m "feat(re): prove scenario 41 MOVEDONE transition"
```

Record the resulting local commit hash in the stage evidence.

---

### Task 7: 胜负结果、battle exit 与 postbattle 闭环

**Files:**
- Create: `tools/build_battle_completion_runtime_probe.py`
- Create: `tests/test_build_battle_completion_runtime_probe.py`
- Extend: `play/_scripts/scenario-41-runtime-evidence.js`
- Extend: `play/_scripts/scenario-41-runtime-evidence.test.js`
- Create: `artifacts/runtime-checkpoints/scenario-41-victory.ss9`
- Create: `artifacts/runtime-checkpoints/scenario-41-postbattle.ss9`
- Create: `artifacts/runtime-checkpoints/scenario-41-completion-evidence.json`
- Create: `notes/scenario-41-completion-runtime-20260715.md`
- Modify: `artifacts/runtime-checkpoints/scenario-41-checkpoints.json`
- Modify: `openspec/changes/close-scenario-41-battle-runtime/tasks.md`

**Interfaces:**
- Consumes: turn-1 checkpoint, shared observer API and second-turn explicit input plan.
- Produces: completion observer/evaluator, victory and postbattle checkpoints.

- [ ] **Step 1: Write RED tests for the checked completion chain**

```python
SITES = {
    "outcome": (0x0807444E, 0x0807305C),
    "battle_exit": (0x08074458, 0x08074FDA),
    "postbattle": (0x080735C2, 0x08074EE6),
}

def test_completion_probe_patches_only_checked_calls_and_caves(self):
    base = (ROOT / "rom/base.gba").read_bytes()
    probe = build_probe(base)
    for name, (hook, original) in SITES.items():
        self.assertEqual(base[hook-ROM_BASE:hook-ROM_BASE+4], encode_thumb_bl(hook, original))
        self.assertNotEqual(probe[hook-ROM_BASE:hook-ROM_BASE+4], base[hook-ROM_BASE:hook-ROM_BASE+4])
    self.assertTrue(diff_is_confined(base, probe, SITES, STUB_RANGES))
```

```javascript
test('completion requires ordered outcome, result, exit and F400', () => {
  const evidence = evaluateBattleCompletionEvidence({
    baseline: completionBaseline(),
    final: completionEvents({ outcomeSequence: 10, exitSequence: 11, postbattleSequence: 12 }),
    resultBefore: 0,
    resultAfter: 1,
    predicatePc: 0x080777fe,
    resultWritePc: 0x08073068,
    controllerState: 0xf400,
    irukaAliveBefore: true,
    irukaAliveAfter: false,
    automaticInputs: [],
  });
  assert.equal(evidence.verified, true);
});
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m unittest tests.test_build_battle_completion_runtime_probe -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
node --test play/_scripts/scenario-41-runtime-evidence.test.js
```

Expected: FAIL because builder and completion evaluator are absent.

- [ ] **Step 3: Implement the three checked call observers**

Patch `0x0807444E → 0x0807305C`, `0x08074458 → 0x08074FDA`, and `0x080735C2 → 0x08074EE6` with independent slots and event codes. Preserve the static sub-chain in evidence metadata: `0x08073064 → 0x080777FE`, return/write instruction `0x08073068 → 0x02026807`.

The evaluator requires fresh ordered events, result transition from pending to victory, predicate/write PCs from strict GDB or checked static+observer correlation, Iruka valid-survival transition, battle exit and controller state `0xF400`. It must report the first missing gate rather than infer earlier events from postbattle.

- [ ] **Step 4: Run GREEN and build the completion ROM**

```powershell
python -m unittest tests.test_build_battle_completion_runtime_probe tests.test_published_call_observer -v
node --test play/_scripts/scenario-41-runtime-evidence.test.js
python tools/build_battle_completion_runtime_probe.py rom/base.gba build/scenario-41-completion.gba
```

Expected: all tests PASS and confined diff is exact.

- [ ] **Step 5: Complete the second tutorial turn naturally**

From `scenario-41-turn-1-complete.ss9`, move the actual controlled unit to `(4,10)` and end action using short explicit steps. Capture predicate/write/result, exit and postbattle separately. Save `scenario-41-victory.ss9` as soon as result is established, then `scenario-41-postbattle.ss9` only after `0xF400` is stable.

Run a base-ROM zero-input replay of postbattle and a base-ROM control of the same second-turn input. No WRAM result write, formation cheat or forced victory ROM is allowed.

- [ ] **Step 6: Persist evidence and update ledger**

The compact JSON records checkpoint/ROM hashes, explicit input steps, all event baselines/finals, predicate/write/exit/postbattle addresses, result byte, controller state, unit survival transition, screenshots/frame hashes, base controls and resource peaks. The note records every failed or ambiguous route.

- [ ] **Step 7: Verify and create a focused local commit**

Run all Task 7 tests, all earlier focused tests, ledger validation, native mGBA read-only replay of victory/postbattle, and `git diff --check`.

```powershell
git add tools/build_battle_completion_runtime_probe.py tests/test_build_battle_completion_runtime_probe.py play/_scripts/scenario-41-runtime-evidence.js play/_scripts/scenario-41-runtime-evidence.test.js artifacts/runtime-checkpoints/scenario-41-victory.ss9 artifacts/runtime-checkpoints/scenario-41-postbattle.ss9 artifacts/runtime-checkpoints/scenario-41-completion-evidence.json artifacts/runtime-checkpoints/scenario-41-checkpoints.json notes/scenario-41-completion-runtime-20260715.md openspec/changes/close-scenario-41-battle-runtime/tasks.md
git commit -m "feat(re): close scenario 41 victory and postbattle"
```

Record the resulting local commit hash in the stage evidence.

---

### Task 8: 文档、审计、临时产物清理与 Build 阶段验收

**Files:**
- Modify: `tools/README.md`
- Modify: `artifacts/runtime-checkpoints/README.md`
- Modify: `docs/reverse-engineering-handoff-20260711.md`
- Modify: `docs/sequel-roadmap.md`
- Modify: `notes/re-completion-audit.md`
- Modify: `notes/re-completion-audit.json`
- Modify: `openspec/changes/close-scenario-41-battle-runtime/tasks.md`
- Modify: `openspec/changes/close-scenario-41-battle-runtime/.comet.yaml`

**Interfaces:**
- Consumes: all accepted checkpoints, compact evidence, tests and guard summaries.
- Produces: consistent handoff/roadmap/audit boundary, all OpenSpec tasks checked, clean staged scope ready for Comet Verify.

- [ ] **Step 1: Update stable documentation from evidence only**

Document Windows mGBA 0.10.5 source/version/archive SHA-256 `B497A57C7D9093834DADC64F33A90F7C411439C21FDB8A0143255A45EA37563A`, source commit `26b7884bc25a5933960f3cdcd98bac1ae14d42e2`, executable path, strict GDB limitations, hybrid input route, checkpoint replay commands and exact failure semantics.

Handoff and roadmap must say player control/MOVEDONE/victory/postbattle are proven only if Task 5–7 evidence passed, while level/EXP/training/levels remain unproven and `levels=code_verified`. Recompute the bank distribution from the audit; do not hard-code an expected change because this change upgrades no bank.

- [ ] **Step 2: Run the full change verification set**

```powershell
python -m unittest tests.test_runtime_checkpoint_ledger tests.test_published_call_observer tests.test_build_player_control_runtime_probe tests.test_mgba_gdb_probe tests.test_build_action_submit_runtime_probe tests.test_build_battle_completion_runtime_probe tests.test_project_resource_guard tests.test_run_guarded -v
node --test play/_scripts/scenario-41-runtime-evidence.test.js play/_scripts/runtime-formation-probe.test.js
python tools/runtime_checkpoint_ledger.py artifacts/runtime-checkpoints/scenario-41-checkpoints.json
python tools/audit_re_completion.py
openspec validate close-scenario-41-battle-runtime --type change --strict --json --no-interactive
git diff --check
```

Expected: every required command exits 0; no required integration test is skipped; audit remains consistent with actual bank states.

- [ ] **Step 3: Review resources and clean only enumerated project artifacts**

Check system available memory and project-owned PID trees. Remove only temporary `build/` files created and enumerated by this change after their durable replacements/hashes exist. Never delete user files, broad directories, or terminate processes by name. Preserve guard summaries referenced by durable evidence or copy their compact fields into evidence first.

- [ ] **Step 4: Run thorough independent review**

Review batches:

1. GDB session ownership, stop semantics and exact-tree cleanup;
2. Thumb ABI, cave/scratch boundaries and control-ROM equivalence;
3. checkpoint lineage, explicit inputs and positive/negative evidence;
4. documentation, audit and levels boundary.

Critical findings must be fixed with RED/GREEN evidence. Accepted noncritical findings require a durable rationale in the completion note or commit body.

- [ ] **Step 5: Check every OpenSpec task and commit final Build state**

Mark each `openspec/.../tasks.md` item checked only after its exact evidence exists. Verify zero unchecked tasks with:

Run: `(Select-String -Path openspec\changes\close-scenario-41-battle-runtime\tasks.md -Pattern '^- \[ \]').Count`

Expected: `0`.

```powershell
git status --short
git add tools/README.md artifacts/runtime-checkpoints/README.md docs/reverse-engineering-handoff-20260711.md docs/sequel-roadmap.md notes/re-completion-audit.md notes/re-completion-audit.json notes/scenario-41-player-control-runtime-20260715.md notes/scenario-41-movedone-runtime-20260715.md notes/scenario-41-completion-runtime-20260715.md openspec/changes/close-scenario-41-battle-runtime
git diff --cached --check
git commit -m "docs(re): hand off scenario 41 runtime closure"
```

Record the resulting local commit hash before running the Comet build guard.

Before committing, inspect cached names and unstage any unrelated user or temporary build file. Then run the Comet build guard; only all-green output may transition the change to Verify.
