# Scenario 41 原 ROM 参考捕获 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 scenario 41 的 1:1 Butano 重建建立可复现、哈希固定的 GPU、业务状态、逐帧动画和音频参考包。

**Architecture:** 先扩展现有 mGBA save-state 解析器，使其离线读取完整 GBA 内存区域；再由 scenario 41 专用导出器把已验收 checkpoints 转成确定性 reference bundle。稳定边界来自 save-state，动态边界使用资源守卫下的 mGBA trace，二者最终由同一 manifest 关联。

**Tech Stack:** Python 3、mGBA 0.10.5 Qt script backport、Lua、PNG RGB8、JSON、SHA-256、unittest、`tools/run_guarded.py`。

## Global Constraints

- 原 ROM 必须为 SHA-256 `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
- save-state 只接受 mGBA GBA state version `0x01000000..0x01000007` 和严格 `0x61000` 解压长度。
- 区域映射固定为 I/O `0x04000000+0x400`、PRAM `0x05000000+0x400`、VRAM `0x06000000+0x18000`、OAM `0x07000000+0x400`、IWRAM `0x03000000+0x8000`、EWRAM `0x02000000+0x40000`。
- 所有重型运行使用 `tools/run_guarded.py` 与 `build/resource-guard/heavy.lock`；禁止宽泛进程清理。
- TDD 依次执行 RED、GREEN、REFACTOR；集成边界必须有会在 wiring 损坏时失败的测试。
- 不提交或推送，除非用户另行授权。

---

### Task 1: 完整映射 mGBA save-state 的 GBA 内存区域

**Files:**
- Modify: `tools/inspect_mgba_savestate.py`
- Modify: `tests/test_inspect_mgba_savestate.py`

**Interfaces:**
- Consumes: `load_gba_state(path) -> GbaState`
- Produces: `GbaState.read_memory(address: int, size: int) -> bytes` 对六个硬件区域的严格只读映射

- [x] **Step 1: 写失败测试**

在 `fixture_savestate()` 的序列化 state 中分别写入：

```python
regions = {
    0x04000000: (0x00400, b"IO!!"),
    0x05000000: (0x00800, b"PRAM"),
    0x07000000: (0x00C00, b"OAM!"),
    0x06000000: (0x01000, b"VRAM"),
    0x03000000: (0x19000, b"IRAM"),
    0x02000000: (0x21000, b"WRAM"),
}
```

测试每个地址能读回 marker，并断言跨区域尾部、负 size 与未映射 ROM 地址失败。

- [x] **Step 2: 运行 RED**

Run:

```sh
python3 -m unittest tests.test_inspect_mgba_savestate.InspectMgbaSavestateTests.test_maps_all_serialized_gba_memory_regions -v
```

Expected: I/O、PRAM、VRAM、OAM 读取抛出 `unsupported or out-of-range`。

- [x] **Step 3: 最小实现区域表**

把 `read_memory()` 的区域表改为：

```python
regions = (
    (0x04000000, 0x00400, 0x00400),
    (0x05000000, 0x00400, 0x00800),
    (0x07000000, 0x00400, 0x00C00),
    (0x06000000, 0x18000, 0x01000),
    (0x03000000, 0x08000, 0x19000),
    (0x02000000, 0x40000, 0x21000),
)
```

保持边界检查和错误文案，不允许切片静默截断。

- [x] **Step 4: 运行 GREEN 与现有 persistence 回归**

Run:

```sh
python3 -m unittest tests.test_inspect_mgba_savestate tests.test_scenario41_completion_persistence tests.test_scenario41_turn1_complete_persistence -v
```

Expected: 全部通过。

---

### Task 2: 导出确定性 scenario 41 稳定边界 reference bundle

**Files:**
- Create: `tools/butano/export_scenario_41_reference.py`
- Create: `tests/test_butano_scenario_41_reference.py`
- Create: `artifacts/scenario-41-reference-v1/manifest.json`
- Create: `artifacts/scenario-41-reference-v1/<boundary>/{io,pram,oam,vram,iwram,ewram}.bin`

**Interfaces:**
- Consumes: `rom/base.gba` 与固定 checkpoint 表
- Produces: `export_reference(rom: Path, output_dir: Path) -> dict[str, object]`
- Boundary names: `player-turn`、`first-movedone-facing`、`first-turn-technique-menu`、
  `turn-1-complete`、`victory`、`postbattle`

- [x] **Step 1: 写缺失导出器的 RED 测试**

测试通过文件路径导入模块，在两个临时目录调用 `export_reference()`，断言：

```python
self.assertEqual(first_manifest, second_manifest)
self.assertEqual(first_manifest["rom_sha256"], EXPECTED_ROM_SHA256)
self.assertEqual(set(first_manifest["boundaries"]), set(EXPECTED_CHECKPOINTS))
self.assertEqual(first_manifest["boundaries"]["player-turn"]["screen"]["width"], 240)
self.assertEqual(first_manifest["boundaries"]["player-turn"]["screen"]["height"], 160)
```

并逐区域检查长度、SHA-256 和实际文件一致。复制一份篡改 ROM/checkpoint 后必须在产生任何 bundle 文件前失败。

- [x] **Step 2: 运行 RED**

Run:

```sh
python3 -m unittest tests.test_butano_scenario_41_reference -v
```

Expected: `tools/butano/export_scenario_41_reference.py` 不存在。

- [x] **Step 3: 实现固定来源和原子导出**

模块固定 checkpoint 路径与 SHA-256，使用 `load_gba_state()` 和
`png_screen_fingerprint()`。每个 boundary 导出六个 region，并记录：来源 hash、
screen fingerprint、region size/hash、`0x02026804+8` battle control、
`0x0200A880+8` action fields、task 2 resume、单位池 hash。manifest 使用
`json.dumps(..., indent=2, sort_keys=True) + "\n"`。

先写入同级临时目录，全部校验后 rename 到尚不存在的目标；已有目标必须失败，不能覆盖。

- [x] **Step 4: 运行 GREEN 并物化 reference bundle**

Run:

```sh
python3 -m unittest tests.test_butano_scenario_41_reference -v
python3 tools/butano/export_scenario_41_reference.py --rom rom/base.gba --output artifacts/scenario-41-reference-v1
```

Expected: 测试通过，manifest 覆盖六个稳定边界；其中术菜单画面的 RGB SHA-256 必须为
`17644dae174acd0e26b9b004f3e8a03b9fd9a43b523cb3dff40f978b4f9b6eef`。

---

### Task 3: 解码显示寄存器和 OAM，建立逐层资产清单

**Files:**
- Create: `tools/butano/analyze_scenario_41_gpu.py`
- Create: `tests/test_butano_scenario_41_gpu.py`
- Create: `artifacts/scenario-41-reference-v1/gpu-analysis.json`

**Interfaces:**
- Consumes: reference bundle 的 `io.bin`、`pram.bin`、`oam.bin`、`vram.bin`
- Produces: `analyze_boundary(path: Path) -> dict[str, object]`

- [x] **Step 1: 写显示模式与 OAM RED 测试**

合成 DISPCNT/BGxCNT/scroll/window/blend 和三个 OAM entry，断言 mode、启用 BG/OBJ、
char/screen base、priority、scroll、window、blend、sprite x/y/shape/size/tile/palette/flip
被精确解码；disabled OAM 不进入 active 列表。

- [x] **Step 2: 运行 RED 后实现解码器**

Run:

```sh
python3 -m unittest tests.test_butano_scenario_41_gpu -v
```

实现只读 decoder，不渲染、不猜资源语义。所有保留/非法 mode 值失败关闭。

- [x] **Step 3: 对六个真实边界生成分析并做一致性测试**

测试真实分析包含 240×160 screen hash、至少一个启用 BG 和活动 OBJ，并且同一 boundary
重复分析 JSON 字节一致。输出 `gpu-analysis.json`，记录每个资源范围的 SHA-256 和引用者。

- [x] **Step 4: 离线重建六个稳定边界黄金帧**

先以合成 Mode 0 BG/OBJ/window/blend 写像素级失败测试，再从各 boundary 的 I/O、PRAM、
OAM、VRAM 合成 240×160 RGB8。六个输出必须匹配 checkpoint 内 normalized RGB SHA-256；若
序列化时点的单份寄存器不足以解释画面，必须记录具体 raster-time 缺口，不得以原截图
回填。

---

### Task 4: 捕获动态动画、输入和音频 trace

**Files:**
- Create: `tools/butano/mgba_scenario_41_reference_trace.lua`
- Create: `tools/butano/capture_scenario_41_reference.py`
- Create: `tests/test_butano_scenario_41_reference_trace.py`
- Create: `notes/scenario-41-one-to-one-reference-20260722.md`

**Interfaces:**
- Consumes: 固定 checkpoint、显式输入计划、mGBA manifest/binary hash
- Produces: 唯一 run 目录中的逐帧 PNG、frame manifest、GPU snapshot、cue trace、左右声道 PCM、最终 state 和 guard summary

- [ ] **Step 1: 写 Lua 安全与计划契约 RED 测试**

测试要求环境变量、固定 checkpoint hash、显式按键 down/up、最大帧、每帧截图命名、
GPU/audio dump、audit、done marker；禁止 `os.exit`、`os.execute`、`io.popen`、动态加载。

- [ ] **Step 2: 实现最小 player-turn 零输入周期 trace**

从 `scenario-41-player-turn.ss9` 捕获完整 64 帧周期，每帧截图并在 0/63 帧导出六个区域；
done marker 最后写入。经 `tools/run_guarded.py` 运行并记录 ROM/state/binary/script hash。

- [ ] **Step 3: 扩展到每个交互与动画区间**

按 checkpoint ledger 的单输入边连续捕获：选择、移动、菜单、朝向、防御、教程对白、
敌方阶段、技能、受击、胜利、结果和战后交接。每个区间独立 run ID，并由 manifest 的
input/output state hash 串成闭合链。

- [ ] **Step 4: 捕获 audio wrapper 与输出采样**

复用现有 controlled audio probe，仅在已固定可见事件边界记录 cue ID、调用 PC、frame、
player/track 生命周期和 PCM。静态候选名不得进入 expected cue。

---

### Task 5: 第一阶段验收与后续计划切换

**Files:**
- Modify: `docs/sequel-roadmap.md`
- Modify: `docs/butano-scenario-41-battle.md`
- Modify: `notes/scenario-41-one-to-one-reference-20260722.md`

**Interfaces:**
- Consumes: stable bundle、GPU analysis、dynamic frame/audio trace
- Produces: 场景/UI 资产计划、流程计划、动画计划、音频计划的权威输入

- [ ] **Step 1: 运行完整参考捕获测试**

Run:

```sh
python3 -m unittest tests.test_inspect_mgba_savestate tests.test_butano_scenario_41_reference tests.test_butano_scenario_41_gpu tests.test_butano_scenario_41_reference_trace -v
```

- [ ] **Step 2: 校验 manifest 与源证据**

逐项重算 ROM、checkpoint、region、screen、frame、PCM、guard 哈希；确认所有 mGBA run
completed/0、non-degraded、success-marker，且 owned process group 已清理。

- [ ] **Step 3: 更新路线图但保持 Goal active**

文档必须明确：参考捕获完成不等于 1:1 复刻完成；只有后续 Butano 输出通过相同逐帧、
状态和 PCM 比对，Goal 才可完成。
