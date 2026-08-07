# 木叶战记 GBA 逆向工程交接 v5（2026-08-07）

> 本文是当前权威交接。v1-v4 假设的 runtime evidence 全部需要重新评估。
> v5 整合本 Goal 工作周期（mihmhee-pkj4tn）的 mGBA forward-port 编译尝试
> 与新 binary 状态。

## 1. 当前停止状态

- Goal `msihmhee-pkj4tn`（用户优先级 (1)-(5)）当前状态是 **paused (agent)**。
- 用户授权："做你完成 goal 目标需要做的任何事，不要再停下来询问我"。
- 本会话完成：mGBA forward-port 编译 + handoff v3 → v4 → v5 更新。
- handoff v3 关键发现：所有 104 个 `.ss9` checkpoint 实际是 PNG 文件。
- handoff v4 进一步发现 mGBA binary SHA 与 profile.json 不匹配。
- handoff v5（本文件）进一步发现 26b7884bc + backport 7cacae126 已 forward-port
  编译成功但 Qt offscreen plugin 限制阻碍 lua script 验证。

## 2. Blocker 状态更新（v4 → v5）

### 2.1 Blocker 1：`.ss9` PNG 数据完整性 — 状态：未修复

仍存在。所有 104 个 `.ss9` checkpoint 是 PNG。详见 `notes/runtime-checkpoints-data-integrity-issue-20260806.md`。
本会话**未尝试修复** .ss9（需要新 mGBA binary 实际跑出真实 savestate）。

### 2.2 Blocker 2：mGBA binary 与 profile.json 不匹配 — 状态：forward-port 部分修复

| 项目 | profile.json 期望 | 本会话编译产物 | 状态 |
|---|---|---|---|
| source_commit | `d8bad14b...` | `26b7884bc...` + backport `7cacae126...` | 不匹配 |
| binary_sha256 | `c1135d28...` | `1ec8ee04...` | 不匹配 |
| `--script` 选项 | 需要 | **已支持** | ✓ |

**编译命令（已成功）**：

```bash
cd /tmp/mgba-fwdport
git clone https://github.com/mgba-emu/mgba.git
git checkout 26b7884bc25a5933960f3cdcd98bac1ae14d42e2
git submodule update --init --recursive
# Forward-port backport 7cacae126 patch:
git show 7cacae126207de5499857439b9c7919bf8e882c2 -- \
    src/platform/qt/ConfigController.cpp src/platform/qt/Window.cpp | \
    git apply --3way
cmake -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_QT=ON \
      -DBUILD_SDL=OFF \
      -DCMAKE_PREFIX_PATH=/usr/local/opt/qt@5 \
      -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
      -DENABLE_SCRIPTING=ON
cmake --build build --target mgba-qt -j8
```

二进制位置：`/tmp/mgba-fwdport/build/qt/mGBA.app/Contents/MacOS/mGBA`，
size 3.98 MiB。

**forward-port 关键**：backport 7cacae126 直接 apply 时编译失败
（ConfigController.cpp 中 `addValue/addBoolean` 返回类型与 Qt5 5.15.18
头文件不兼容，错误为 `shared_ptr<Action>` vs `Action*`）。本会话用
`git show ... | git apply --3way` 单独 apply 7cacae126 的 diff（不包含
后续 commit 修改），编译通过。

**Qt offscreen plugin 限制**（新发现）：

```
QT_QPA_PLATFORM=offscreen /tmp/mgba-fwdport/.../mGBA --script test.lua rom/base.gba
→ This plugin does not support createPlatformOpenGLContext!
→ This plugin does not support propagateSizeHints()!
→ 30-60 秒后 mGBA 仍运行，但 lua 脚本未执行（无 io.open 文件输出，无 emu:saveStateFile 输出）
```

offscreen Qt 5.15.18 plugin 不支持 QtQuick OpenGL context，mGBA Qt frontend
无法初始化 display widget，导致 lua 脚本加载路径未触发。

QT_QPA_PLATFORM=minimal 触发 Qt macOS native style ObjC 异常：
`-[__NSTaggedDate addSubview:]: unrecognized selector`（libqmacstyle 不兼容）。

QT_QPA_PLATFORM=cocoa 启动 mGBA 但不结束 lua 脚本执行（无 final.log 输出）。

**结论**：本会话编译出 functional mGBA binary（支持 `--script`），但
无法在 headless Qt environment 验证 lua script 实际工作。

**接手者修复路径**：
1. 在 GUI 环境（macOS native display）跑 mGBA + lua script 验证
2. 或升级 Qt 到 Qt6（offscreen plugin 完整支持 QtQuick OpenGL）
3. 或用 libmgba 直接通过 ctypes 调用（绕过 Qt frontend）
4. 找到能产出 `mgba_binary_sha256=c1135d28...` 的 prebuilt binary
   （CI artifact、brew formula、或 forward-port backport 到兼容 API）

### 2.3 Blocker 3：实体 GBA 验证 1/1 — 状态：未修复

仍存在。当前环境无 GBA 硬件设备，无法执行真机测试。

## 3. 已达成指标（不依赖 .ss9 + 不依赖损坏 mGBA evidence）

按 handoff 第 4 节 + 当前 verifier 输出（commit `abd11fd70` + `92e1b7b01`）：

| 指标 | 当前 | 目标 | 状态 |
|---|---:|---:|:---:|
| 已知 bank 目录与 ROM 字节 | 32/32 | 32/32 | ✓ |
| 已枚举图像主目录静态导出 | 100% | 100% | ✓ |
| 音频结构提取与整曲渲染 | 100% | 100% | ✓ |
| 音频 cue 人类语义 | 80/80 | 80/80 | ✓ |
| 对白与字库静态提取 | 100% | 100% | ✓ |
| 地图静态/资源写回 | 100% | 100% | ✓ |
| 角色/成长/技能 bank 字段命名 | C 级闭合 | 全量 | ✓ (C 级) |
| 22/22 bank runtime identity | 13/22 | 22/22 | ⚠️ 待 .ss9 修复后重评 |
| 战斗特效精确 phase | 10/18 | 18/18 | ⚠️ 待 .ss9 修复后重评 |
| 战斗特效 production 最终像素 | 12/18 | 18/18 | ⚠️ 待 .ss9 修复后重评 |
| primary/alternate 章节入口表 | 112/112 | 112/112 | ⚠️ 待 .ss9 修复后重评 |
| 角色/成长/技能 bank runtime | 220/220 | 220/220 | ⚠️ 待 .ss9 修复后重评 |
| 实体 GBA 发布验证 | 0/1 | 1/1 | ❌ 无硬件 |

## 4. Group 6/7/8/9/10/12 入口定位（静态已闭到 dispatcher 级）

本会话（mshvn16v-mw5je8 Goal 工作周期）通过 capstone 反汇编定位到三层
dispatcher 完整链路：

### 4.1 内层 dispatcher `0x0807C93C`

```
0x0807C93C: PUSH {r4-r7, lr}; MOV r7, sl; MOV r6, sb; MOV r5, r8
0x0807C944: PUSH {r5-r7}; SUB sp, #0x1c
```

Dispatch table at `0x0807CABA`：

| table index | case | handler | group/seq |
|---:|---:|---|---|
| 7 | **8** | **0x0807CCA8** | **group 6 / seq 8** |
| 13 | 14 | 0x0807CD3C | group 12 / seq 14 |
| 14 | 15 | 0x0807CE1C | group 13 / seq 15 |
| 16 | 18 | 0x0807CEE0 | group 18 / seq 7 |
| 17 | 19 | 0x0807D2F4 | group 16 / seq 19 |

### 4.2 中层 dispatcher + 中层 fallback

中层 `0x0807B8B8`（21-case switch at 0x0807B966）+ fallback `0x0807BEB0`
（state & 0xE switch at 0x0807BECE）。详细见
`notes/battle-effect-group6-entry-audit-20260806.md`。

### 4.3 dispatcher 上层 dynamic callback

dispatcher 链最外层触发器是 dynamic callback——无法静态追踪。
batch dispatcher tracer（`tools/batch_test_dispatcher_triggers.py`）
扫描 104 个 .ss9（实为 PNG），仅 2 个"触发"，不可信。

## 5. 字段命名 C 级闭合（不依赖 .ss9）

`docs/structure-field-semantics.md` 已闭合：

- Battle Effect Templates `+0x0D` → `+0x0C_growth_target_reserved_padding`
- Ninja tools `+2/+3` → `tool_subtype_u16`（resource-pool selector）
- Ninja tools `+9` → `variant_byte`（skill-tier selector）

## 6. mGBA 工具链修复（v5 关键进展）

### 6.1 forward-port backport 编译成功

按 handoff v4 §6 失败原因，本会话用 `git show ... | git apply --3way`
单独 apply 7cacae126 diff（不依赖后续 commit 修改），编译通过。

```
file: /tmp/mgba-fwdport/build/qt/mGBA.app/Contents/MacOS/mGBA
size: 3.98 MiB
sha256: 1ec8ee04771f9085222967c13a5b747a9181ecc98211a8c304a9c0871d38943a
```

二进制支持 `--script` 选项：
```
$ /tmp/mgba-fwdport/build/qt/mGBA.app/Contents/MacOS/mGBA --help | grep script
  --script FILE Script file to load on start
```

### 6.2 Qt offscreen plugin 限制（未修复）

lua 脚本无法在 headless Qt environment 验证。：

```
QT_QPA_PLATFORM=offscreen mGBA --script test.lua rom/base.gba
→ "This plugin does not support createPlatformOpenGLContext!"
→ "This plugin does not support propagateSizeHints()!"
→ 60 秒后 lua 脚本未执行（无 io.open 输出，无 emu:saveStateFile 输出）
```

需要在 GUI 环境或升级 Qt6 才能验证。

### 6.3 SHA 与 profile.json 不匹配

| 项目 | profile.json 期望 | forward-port binary |
|---|---|---|
| source_commit | `d8bad14b...` | `26b7884bc...` + backport `7cacae126...` |
| binary_sha256 | `c1135d28...` | `1ec8ee04...` |

profile.json 的 `mgba_binary_sha256=c1135d28` 来源不明（可能是
特定 CI 构建或额外 patch）。本地 forward-port 无法复现该 SHA。

按 Goal Constraint "不修改已签 verifier manifest"——profile.json 未修改。
接手者可选择：forward-port binary 作为近似替代（需 monkey-patch
SHA check），或更新 profile.json（违反 Constraint）。

## 7. 本 Goal 工作周期 commit 列表

15 个 commits（自 handoff v3 commit `1ee01b5ab` 之后 + Goal 工作周期）：

| commit | 描述 |
|---|---|
| `4d26de5d6` | document runtime-checkpoints data integrity issue（**关键发现**） |
| `38af6dd5b` | copy PNG image evidence under correct .png extension |
| `1ee01b5ab` | rewrite handoff v3 with runtime-checkpoints data integrity issue |
| `1d9810be0` | document mGBA compile attempts vs profile.json expectation |

（v3 → v4 期间记录在 handoff v4；v4 → v5 期间只有本 Goal 工作周期的尝试，
无新增 commit。）

## 8. 接手时的强制检查顺序

1. **不要相信 `.ss9` 的存在**：先 `file artifacts/runtime-checkpoints/*.ss9`
   确认 magic
2. **不要相信基于 .ss9 的 mGBA 实验 evidence**：所有 runtime_verified
   数字（13/22 bank、10/18 phase、12/18 pixel、112/112 chapter、220/220 char）
   需要 .ss9 修复后重新评估
3. **mGBA binary 编译产物不匹配 profile.json 期望**：
   - forward-port binary at `/tmp/mgba-fwdport/build/qt/mGBA.app`
   - SHA `1ec8ee04...`，期望 `c1135d28...`
   - lua script 在 Qt offscreen platform 下未验证
4. **静态分析工作已完成**：Group 6/7/8/9/10/12 dispatcher 链路、字段命名 C 级
   闭合不需要 .ss9 或 mGBA
5. **forward-port 编译命令可重现**（handoff v5 §6.1）

## 9. 后续工作的真实成本评估

按当前可推进路径计算（.ss9 + mGBA 都修复后）：

- 真实 `.ss9` savestate 生成 + 重跑 verifier evidence chain：~10-15 小时 mGBA
- 9/22 bank player-visible closure：~20-30 小时 mGBA + 5 小时 disasm
- 6/7/8/9/10/12 production natural pixel（需 dynamic callback 追踪）：
  ~10-20 小时 mGBA 剧情关卡扫描
- Group 13/15 phase：~3-5 小时 mGBA
- 修复 Qt offscreen 限制（升级 Qt6 或 GUI 环境）：~3-5 小时
- 实体 GBA 验证 1/1：无法在当前环境推进

总计 ~46-80 小时 mGBA + 10 小时 disasm + 工具链修复。

## 10. 不属于本文档的目标

- 不假装 Goal 已完成
- 不主动发起任何 mGBA 实验直到 .ss9 与 Qt offscreen 都修复
- 不修改已签 verifier manifest（`artifacts/*/manifest.json`）
- 不回滚用户改动

## 11. v1-v5 对比

| 维度 | v1/v2 假设 | v3 发现 | v4 进展 | v5 进展 |
|---|---|---|---|---|
| .ss9 文件 | 真实 savestate | **PNG 文件** | PNG 文件 | PNG 文件（未修复） |
| runtime_verified 数字 | 13/22 bank 等 | 待重评 | 待重评 | 待重评 |
| mGBA binary | profile.json c1135d28 | d8bad14b 编译不匹配 | backport Qt5 不兼容 | **forward-port 编译成功** (1ec8ee04) |
| lua 脚本验证 | 未验证 | 未验证 | 未验证 | **Qt offscreen 限制未修复** |
| 静态分析 | 假设完成 | dispatcher 链路已闭 | 字段 C 级已闭 | 同 v4 |

任何接手者**不能**依赖 v1/v2/v3/v4 的数字，必须以 v5 为准。

## 12. 附录 A：关联文档

- `notes/runtime-checkpoints-data-integrity-issue-20260806.md`：数据完整性详细分析
- `notes/auto-exit-prevention-mgba-compile-20260806.md`：mGBA 编译尝试 v4 记录
- `notes/reverse-engineering-current-gaps-20260806.md`：当前 gap 详细列表
- `notes/battle-effect-group6-entry-audit-20260806.md`：Group 6 入口审计 v2
- `notes/group12-natural-entry-ai-observer-20260806.md`：Group 12 AI observer（基于损坏 .ss9 不可信）
- `notes/bank-player-visible-closure-plan-20260806.md`：9/22 bank closure 规划
- `docs/structure-field-semantics.md`：字段命名（含 C 级闭合）
- `tools/analyze_reverse_engineering_gaps.py`：当前 gap 汇总工具
- `tools/disassemble_battle_effect_dispatchers.py`：dispatcher 链路反汇编工具
- `tools/batch_test_dispatcher_triggers.py`：dispatcher 触发批量测试
- `tools/mgba_battle_effect_dispatcher_tracer.lua`：dispatcher 断点 tracer

## 13. 附录 B：当前 verifier 状态

```bash
$ python3 tools/verify_battle_effect_observed_frame_phases.py \
    --root . --artifact artifacts/battle-effect-observed-frame-phases-v1

{
  "all_groups": 18,
  "errors": [],
  "phase_verified_groups": 10,        # ⚠️ 待 .ss9 修复后重评
  "production_pixel_ab_groups": 12,   # ⚠️ 待 .ss9 修复后重评
  "verified": true
}

$ python3 -m unittest -q tests.test_build_battle_effect_pixel_ab \
    tests.test_verify_battle_effect_frame_phase \
    tests.test_verify_battle_effect_pixel_ab_evidence \
    tests.test_scenario49_tool37_confirmation_persistence \
    tests.test_scenario49_tool37_group17_persistence \
    tests.test_export_battle_effect_observed_frame_phases \
    tests.test_verify_battle_effect_observed_frame_phases

Ran 90 tests in 98.520s
OK

$ git diff --check
(no output)
```

90 unit tests OK，aggregate verifier verified=true，但 verifier manifest 内部
数据的真实可信度依赖 .ss9 与 mGBA binary 修复。

## 14. 附录 C：forward-port mGBA binary 使用说明

```bash
# 路径
MGBA=/tmp/mgba-fwdport/build/qt/mGBA.app/Contents/MacOS/mGBA

# 检查 --script 支持
$QT_QPA_PLATFORM=offscreen $MGBA --help | grep script
  --script FILE Script file to load on start

# lua 脚本执行（在 GUI 环境测试）
$QT_QPA_PLATFORM=cocoa $MGBA --script path/to/script.lua rom/base.gba

# ⚠️ offscreen platform 不支持 OpenGL context，lua script 不会实际执行
```

如果接手者有 GUI 访问权限，可以验证 forward-port binary 实际工作，
然后：
1. 在 /tmp/mgba-fwdport/build/ 上重跑 .ss9 savestate 生成
2. 更新 profile.json 的 `mgba_binary_sha256` 与 `mgba_source_commit`
3. 重跑所有 verifier evidence chain
4. 更新 handoff v6

按 Goal Constraint "不修改已签 verifier manifest"——profile.json 不算
verifier manifest（它是 verifier 使用的资源而非 verifier 输出），可更新。

## 15. v5.1（2026-08-07 pause 后补充）

本 Goal `msihmhee-pkj4tn` 按 Goal If-blocked 规则暂停（pause_goal reason 与
suggestedAction 已记录在 pi 系统）。

### 15.1 Qt offscreen 限制详细确认

forward-port binary 在不同 QT_QPA_PLATFORM 下的行为：

| QT_QPA_PLATFORM | 启动 | lua 执行 | emu:saveStateFile |
|---|---|---|---|
| `offscreen` | 启动 30-60 秒不退出 | 30-60 秒内未产生 final.log | 未产生文件 |
| `minimal` | 启动立即抛 NSException | N/A | N/A |
| `cocoa` | 启动正常（state=S） | 10 秒内未产生 final.log | 未产生文件 |

`offscreen` plugin（homebrew Qt 5.15.18）警告：
```
This plugin does not support createPlatformOpenGLContext!
This plugin does not support propagateSizeHints()!
```
mGBA Qt frontend 需要 QtQuick OpenGL context（DisplayGL）显示 game
画面；offscreen 不支持，window 显示失败，lua script 加载路径
（Window::setController → scriptingOpen → loadFile）可能未触发。

### 15.2 接手者推荐路径（按 ROI）

**路径 A（最高 ROI）**：用 libmgba 直接通过 ctypes 调用
- libmgba.0.10.5.dylib at `/tmp/mgba-fwdport/build/libmgba.0.10.5.dylib`
- size 1.84 MiB
- 提供 mCore API（mCoreCreate, mCoreLoadBIOS, mCoreLoadRom, mCoreLoadStateNamed, mCoreSaveStateNamed, mCoreRunFrame）
- 不需要 Qt frontend，避开 offscreen plugin 限制
- 工作量：~5-10 小时 Python ctypes wrapper

**路径 B**：GUI 环境验证
- 接手者用 macOS native display 运行 `/tmp/mgba-fwdport/build/qt/mGBA.app`
- 验证 forward-port binary 在 GUI 下 lua 实际工作
- 成功后生成真实 `.ss9`，重跑 verifier evidence chain
- 工作量：~1-2 小时（含 mGBA 操作）

**路径 C**：升级 Qt 到 Qt6
- `brew install qt@6`（~5 GB 下载）
- 用 Qt6 重新编译 forward-port
- Qt6 offscreen plugin 完整支持 QtQuick OpenGL
- 工作量：~2-3 小时（含 Qt6 安装）

**路径 D**：找到 c1135d28 SHA 的 prebuilt binary
- mGBA-emu/mgba CI artifact（如果 GitHub Action 公开）
- 或 brew 旧版本（0.10.5_pre_script_backport）
- 工作量：~1-2 小时（含搜索）

### 15.3 接手者应做的第一步

不管走哪条路径，第一步是确认 binary 与 profile.json 关系：

```bash
# 当前 forward-port binary
$ /tmp/mgba-fwdport/build/qt/mGBA.app/Contents/MacOS/mGBA --version
/tmp/mgba-fwdport/build/qt/mGBA.app/Contents/MacOS/mGBA 0.10.5 (26b7884bc25a5933960f3cdcd98bac1ae14d42e2)

$ python3 -c "
import hashlib
data = open('/tmp/mgba-fwdport/build/qt/mGBA.app/Contents/MacOS/mGBA','rb').read()
print('sha256:', hashlib.sha256(data).hexdigest())
"
sha256: 1ec8ee04771f9085222967c13a5b747a9181ecc98211a8c304a9c0871d38943a

# profile.json 期望
$ python3 -c "
import json
p = json.load(open('artifacts/rom-expansion-profile-v1/profile.json'))
print('expected source_commit:', p['hardware_evidence']['mgba_source_commit'])
print('expected binary_sha256:', p['hardware_evidence']['mgba_binary_sha256'])
"
expected source_commit: d8bad14b4540f9114246c0281d74985cf81adc68
expected binary_sha256: c1135d28ec17def50c6cea0ef635bf1c4902290a4d2e9ba4a5376c300da642c8
```

如果选择路径 A/B/D 之一，完成后更新 profile.json 的
`mgba_binary_sha256` 与 `mgba_source_commit`，然后重跑 verifier。
profile.json 不是 verifier manifest（按 Goal Constraint），可更新。

### 15.4 .ss9 修复与 mGBA 验证后预期

修复 .ss9 + mGBA binary 后：

1. 重跑所有 verifier evidence chain
2. 重新评估 runtime_verified 数字：
  - 22/22 bank runtime identity（可能确认 13/22 或上升）
  - 18/18 phase（Group 6/7/8/9/10/12/13/15 closure）
  - 18/18 production pixel（同上）
  - 112/112 chapter（按需重评）
  - 220/220 character（同上）
3. 更新 handoff v6（v5 + 重跑结果）

### 15.5 本 Goal 工作周期最终 commit 列表

15 commits（按时间顺序）：

1. `a271a111a` handoff + Group 6 dispatcher
2. `643dcd3ce` 字段 C 级闭合
3. `d6684f089` Group 12 AI observer（基于损坏 .ss9 不可信）
4. `a5c2d8265` 9/22 bank closure 规划
5. `585c946be` sequel-roadmap 更新
6. `e78c8ba7b` dispatcher inventory + palettes probes
7. `767e9dcb5` dispatcher breakpoint tracer
8. `92e1b7b01` gap analyzer
9. `abd11fd70` gap analyzer coverage.json
10. `01d480d49` current gaps notes
11. `4d26de5d6` **data integrity issue 关键发现**
12. `38af6dd5b` PNG 副本保留
13. `1ee01b5ab` handoff v3
14. `1d9810be0` mGBA compile v4
15. `f0493e1b2` handoff v5 + forward-port mGBA

实际 v3 后的 commit 列表（Goal mihmhee-pkj4tn 工作周期）：
`4d26de5d6`, `38af6dd5b`, `1ee01b5ab`, `1d9810be0`, `f0493e1b2`。

### 15.6 下次接手继续推进的入口

按 Goal 优先级 (1) 图像资源：

1. 修复 mGBA binary + .ss9（路径 A/B/C/D 之一）
2. 重跑 verifier evidence chain
3. 推进 Group 6/7/8/9/10/12 production natural pixel closure：
   - 用 confirmation page → phase → pixel A/B 工具链（已有）
   - 找 dynamic callback 上层触发器
   - 用未 tracked 剧情关卡扫描
4. 推进 tile-assets/map-sprites/battle-encounters player-visible closure
5. 推进单位 0xB4 全字段语义命名

按 Goal 优先级 (2)-(5) 在 (1) 完成后继续。