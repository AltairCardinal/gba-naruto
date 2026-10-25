# 本机工具链（2026-10-23 实测落地）

**目标**：让 Butano 重制线与逆向线的工作**在这台 Windows 机器上能跑**，
并且**录制时不弹窗、不出声**。

**结论**：两个硬约束**都满足，且是由构造保证的、不是靠配置碰运气**——
探针只链接 libmgba 的 **core**（`BUILD_QT=OFF` / `BUILD_SDL=OFF`），
二进制里**没有 USER32 / winmm / avrt / SDL / OpenAL 任何一个导入**，
所以它**在物理上不可能**开窗或开音频设备。

---

## 0. 一览

| 能力 | 状态 | 怎么用 |
|---|---|---|
| **构建 Butano ROM** | ✅ **已跑通**（devkitARM 在 WSL 里） | 见 §2 |
| **无窗口无声录制** | ✅ 可用，且可证明 | `tools/mgba_probe/verify_headless_recording.py` |
| **跑 mGBA Lua 脚本** | ✅ 可用（本次新打通） | 探针新增 `script <path>` 命令 |
| **PNG 截图 / 内存 dump / 存档** | ✅ 可用 | 探针既有命令 + 本次补上 PNG 支持 |
| **构建→录制端到端** | ✅ **已跑通**（见 §2.2） | 重制 ROM 在无窗口探针里正确渲染出中文标题画面 |
| **消费重制线已有的 `.ss9`** | ✅ **已解决**（见 §4） | 升级到钉死的 mGBA 提交后，存档格式与 BIOS 全部对上 |

---

## 1. 探针（本机录制底座）

`tools/mgba_probe/host_main.c` + `build/mgba-probe/mgba-probe.exe`
（由 `tools/mgba_probe/build.py` 构建，mGBA 源码在 `D:\Shell\toolchain\mgba-0.10.5`）。

### 命令表

| 命令 | 作用 |
|---|---|
| `key <mask>` / `keyoff` | 设置 / 释放按键（GBA KEYINPUT 位掩码） |
| `frames <n> <mask>` | 按住某键跑 n 帧后释放 |
| `run <n>` | 跑 n 帧，**不改动按键状态**（用来观察 KEYINPUT） |
| `cont [n]` | 跑到断点命中（默认 600 帧上限） |
| `dump <addr> <len>` | 十六进制 dump 任意地址（VRAM / PRAM / OAM / EWRAM） |
| `poke <addr> <val>` / `poke16` | 往内存写值 |
| `save <path>` / `load <path>` | 存 / 读存档（**本探针自己实现的路径版**，mGBA 自带的只认数字槽位） |
| `shot <path>` | **PNG 截图**（本次补上 PNG 支持后才真的能写 PNG） |
| `rawshot <path>` | 原始 RGBA 帧（240×160，无损、无需 PNG） |
| **`script <path>`** | **本次新增：加载 Lua 脚本**，`callbacks:add("frame", …)` 每帧触发 |
| `echo <token>` | 客户端哨兵 |

### 为什么它天然无窗口无声

* 构建参数 `-DLIBMGBA_ONLY=ON -DBUILD_QT=OFF -DBUILD_SDL=OFF`
  ⇒ 进程里**没有图形前端，也没有音频后端**。
* `emu:screenshot()` 走 `mCoreTakeScreenshotVF()`，**写文件**，不呈现任何东西。
* 证据（`verify_headless_recording.py` 实跑输出）：

```
probe imports: api-ms-win-crt-*.dll, kernel32.dll, ole32.dll, shell32.dll,
               shlwapi.dll, vcruntime140.dll
windows owned by the probe during the recording: none
recorded frame: 240x160, 5861 bytes
OK: the recording chain is headless and silent.
```

⇒ 导入表里**没有** `user32.dll`（开窗）、`winmm.dll` / `avrt.dll` /
`dsound.dll` / `sdl2.dll` / `openal32.dll` / `xaudio2_9.dll`（发声）。
⇒ 录制期间枚举该进程的全部顶层窗口：**一个都没有**。

### 复跑

```powershell
python tools/mgba_probe/build.py --rebuild-mgba   # 重建 mGBA 静态库 + 探针
python tools/mgba_probe/verify_headless_recording.py   # 无窗口无声门禁
```

---

## 2. 构建 Butano ROM（WSL）

| 项 | 值 |
|---|---|
| devkitARM | `/opt/devkitpro/devkitARM`，`arm-none-eabi-gcc 15.2.0` |
| GNU Make / Python | 4.3 / 3.12.3 |
| 位置 | `D:\Shell\Github\gba-naruto-butano\butano-sequel` |

```bash
# WSL
cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel
source /opt/devkitpro/devkitarm.sh
export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano
make -j4
```

> ⚠️ **必须显式导出 `LIBBUTANOABS`。**
> `butano-sequel/Makefile` 用 `$(realpath $(LIBBUTANO))` 算绝对路径，
> 但 **GNU make 没有 `realpath` 函数**（那是 GNU make 4.x 也没有的），
> 于是 `LIBBUTANOABS` 展开成空串，`include /butano.mak` 直接失败。
> 这是**本机第一次构建就踩到的坑**，不是环境问题。

### 子模块

`third_party/butano` 与 `third_party/gba-wav-to-s3m-converter` 在本仓是**未初始化**的
（`git submodule status` 前缀 `-`）。
`butano` 仓库历史很大，**全量克隆在本机网络下极慢**（>30 分钟仍未落地），
改用**浅克隆**：

```powershell
git -C D:\Shell\gba-naruto-butano -c protocol.version=2 `
    submodule update --init --depth 1 third_party/butano
```

⇒ 实测 **~40 秒**完成，并检出到钉死的提交 `112a1827`。

> ⚠️ **新克隆的子模块会继承全局 `core.autocrlf=true`**
> （本机全局是 `true`，三个工作树都在**仓库级**改成了 `false`，
> 但新建的子模块不在其中）。
> ⇒ 克隆后必须补上，否则 Butano 源码会被写成 CRLF：
>
> ```powershell
> git -C D:\Shell\gba-naruto-butano\third_party\butano config core.autocrlf false
> git -C D:\Shell\gba-naruto-butano\third_party\butano config core.eol lf
> git -C D:\Shell\gba-naruto-butano\third_party\butano read-tree HEAD
> git -C D:\Shell\gba-naruto-butano\third_party\butano checkout-index -a -f
> ```
>
> （`read-tree` + `checkout-index -f` 这两步不能省：只改配置不重建索引，
> git 的 stat 缓存会让它跳过重写——这正是 `notes/windows-migration-20261020.md` §2 记的坑。）

### 2.2 端到端验证（构建 → 录制）

```
WSL: make → butano-sequel/butano-sequel.gba (10,613,284 B, 2026-10-23 21:40)
Windows: 探针跑 120 帧 → shot → 240x160 PNG
```

录下来的帧是**重制 ROM 的真实中文标题画面**
（「保护乡村 义不容辞 慎重出击！」+ 菜单 + 角色列表），不是黑屏。
⇒ **构建链与录制链在本机全部闭合。**

> 重制仓 `git status` 仍是 **0 变更**——构建产物被 `.gitignore` 挡住。

---

## 3. Lua 脚本支持（本次新打通）

### 做了什么

mGBA 0.10.5 的 Lua 引擎在 `src/script/engines/lua.c`，核心脚本层在 `src/script/`。
本机原来**没有**任何 Lua，也没有管理员权限装包 ⇒ **从源码编译**：

| 步骤 | 产物 |
|---|---|
| `tools/build_lua_lib.ps1`（MSVC，32 个 .c → `lib.exe`） | `D:\Shell\toolchain\lua-5.4.7-build\lua54.lib` + `lua-5.4.7\src` 头文件 |
| `tools/mgba_probe/build.py` | 探测 Lua 静态库存在就加 `-DUSE_LUA=ON -DENABLE_SCRIPTING=ON` |
| `tools/mgba_probe/host_main.c` | 新增 `script <path>` 命令 + 每帧触发 `frame` 回调 |

`tools/build_lua_lib.sh` 只是 WSL 包装（真正的编译在 PowerShell 里，因为工具链是 MSVC）。

### 踩到的三个 mGBA 0.10.5 缺陷（已在 `build.py` 里做成幂等补丁）

| # | 缺陷 | 现象 | 补丁 |
|---|---|---|---|
| 1 | `find_feature(USE_LUA "Lua" ${USE_LUA})` 把 `ON` 当版本号 | `find_package(Lua ON EXACT)` 被 CMake 拒绝 → 功能被**静默关闭** | 只在 `USE_LUA` 真的是版本号时才传版本 |
| 2 | `find_feature` 里判 `if(Lua_FOUND)`，但 CMake 的 FindLua 在函数作用域里只设 `LUA_FOUND` | 找到库了也判为「没找到」 | 同时判 `LUA_FOUND` / `Lua_FOUND` |
| 3 | `LIBMGBA_ONLY=ON` 会 `set(DISABLE_DEPS ON)`，于是 `find_feature` 直接 early-return，**并且** `USE_PNG`/`USE_ZLIB` 被强制关掉 | Lua 关掉；**`shot` 命令写不出 PNG**（`mCoreTakeScreenshotVF` 没有 PNG 支持） | 显式请求的特性不再被 `DISABLE_DEPS` 拦；PNG/ZLIB 显式请求时保留 |

> 缺陷 3 还顺带暴露了一件事：**在本机补上 PNG 支持之前，`shot` 命令其实写不出 PNG**
> （只有 `rawshot` 能用）。这解释了为什么历史脚本大多走 `rawshot` / VRAM dump 路线。

### 验证：重制线的 Lua 脚本原样可跑

用重制线**自己的**录制脚本 `tools/butano/mgba_original_input_frame_sequence.lua`、
**它自己的环境变量契约**、**它自己的产物格式**，在本机跑通：

```
audit.json / done.json   ← 与重制线的 payload 格式逐字段一致
frame-000.png … frame-007.png
restored.ss9 / final.ss9
```

`audit.json` 内容：

```json
{"status":"capture-complete","record_all":true,"input_state_sha256":"…",
 "key":"A","hold_frames":4,"input_after_frame":2,"frame_count":8}
```

⇒ **重制线的 73 个 Lua 探针脚本在本机可用**（只要存档格式兼容，见 §4）。

---

## 4. mGBA 版本选择（2026-10-23 升级完成）

### 4.1 为什么不是 0.10.5、也不是当前 master

mGBA 的 GBA 存档格式版本定义在 `src/gba/serialize.c`：

```c
MGBA_EXPORT const uint32_t GBASavestateMagic   = 0x01000000;
MGBA_EXPORT const uint32_t GBASavestateVersion = 0x00000007;   /* 0.10.5 */
```

本机原来的 0.10.5 ⇒ 存档版本 `0x01000007`，
而重制线的 `.ss9` 是 **`0x0100000A`**，所以被拒绝
（`Invalid or too new savestate`），再加上 **BIOS 哈希不同**，双重不兼容。

版本历史（`git log -L` 实测）：

| 提交 | 日期 | 版本 |
|---|---|---|
| `c3f3d00` | 2025-04-12 | 0x00000008 |
| `c5cddc0` | | 0x00000009 |
| **`b6618c5`** | 2025-11-28 | **0x0000000A** |
| `01300f9` | | 0x0000000B（当前 master） |

⇒ **只有 `[b6618c5, 01300f9)` 这一段产出 0x0A 存档。**

### 4.2 选定：**钉死的提交 `d8bad14b4540f9114246c0281d74985cf81adc68`**

这不是挑出来的，是**项目自己钉死的那个**：
`tools/macos_mgba_toolchain_profile.py` 的 `CURRENT_MGBA_SOURCE_COMMIT`
（重制线用它建 macOS 版 mGBA）。实测该提交：

* GBA 存档版本 = **`0x0000000A`** ⇒ 与重制线既有 `.ss9` **完全一致**；
* HLE BIOS 与重制线一致 ⇒ **BIOS 哈希也对得上**；
* 2026-03-27 的提交（「Qt: Add missing ARM64 AppImage update option」）。

⇒ 选它的理由是**双向兼容**：
本机产出的存档（0x0A）重制线能读，重制线产出的存档本机能读。

**不选当前 master（0x0B）**：它虽然也能读 0x0A（mGBA 对旧存档只警告不拒绝），
但它**产出**的 0x0B 存档**重制线读不了** ⇒ 会造出新的单向兼容问题。

**不选 0.10.5**：读不了重制线既有证据。

### 4.3 升级代价：探针要跟着移植

0.10.5 → `d8bad14b` 之间 mGBA 做了 **debugger 重构**，
`struct CLIDebugger` 从「内含一个 `mDebugger`」变成「**是一个 `mDebuggerModule`**」，
`USE_DEBUGGERS` 选项也变成了 `ENABLE_DEBUGGERS`。
⇒ `tools/mgba_probe/host_main.c` 必须移植：

| 改动 | 内容 |
|---|---|
| ABI 指纹 | `sizeof(mCore)` 1648 → **1712**（`ENABLE_DEBUGGERS` 会加成员）；其余偏移不变。指纹由 `tools/mgba_probe/abi_probe.c` 重新实测 |
| 调试器生命周期 | `mDebuggerCreate(DEBUGGER_CLI, core)` → `mDebuggerInit` + `mDebuggerAttach` + `mDebuggerCreateModule(DEBUGGER_CLI, core)` + `mDebuggerAttachModule` |
| 帧推进 | `&g_cli->d` 不再是 `mDebugger*`，改用宿主自己持有的 `g_debugger` |
| 视频缓冲 | `color_t` → `mColor`（`mgba-util/image.h`）；`setVideoBuffer` 签名不变 |
| Lua 回调 | `mScriptContextTriggerCallback(ctx, "frame")` → 多了 `args` 参数，传 `NULL` |
| 构建参数 | **不能再用 `LIBMGBA_ONLY=ON`** —— 新版里它会连带关掉 `ENABLE_DEBUGGERS`/`USE_LUA`/`USE_PNG`/`USE_ZLIB`；改为逐个关掉图形前端 |

### 4.4 升级后的实测

```
# 重制线自己的存档，直接读
load  .../battle-effect-affine-runtime-v1/raw/state-0154.ss9   → OK load
frames 10 0x000                                                → OK frames 10
shot  ...                                                      → OK shot
（无 "Invalid or too new savestate"，无 BIOS 不匹配）

# 重制线自己的 Lua 录制脚本 + 重制线自己的存档
mgba_original_input_frame_sequence.lua  →  frame-000..009.png + restored/final.ss9 + audit.json
（audit.json 与重制线契约逐字段一致）

# 新写出的存档再读回来
load .../final.ss9 → OK load（无告警）
```

⇒ **存档不兼容问题已消除，不需要靠「重录」来绕过。**
（用户已授权重录；本轮**没有**动用它——升级已经让旧证据直接可用，
重录会改变既有证据文件的身份，属于不必要的动作。）

---

## 5. 本次新增 / 修改的文件

| 文件 | 说明 |
|---|---|
| `tools/mgba_probe/build.py` | 加 Lua 支持 + 三个 mGBA 补丁 + 链接 PNG/ZLIB 静态库 |
| `tools/mgba_probe/host_main.c` | 新增 `script <path>` 命令；每帧触发 `frame` 回调 |
| `tools/mgba_probe/verify_headless_recording.py` | **无窗口无声门禁**（导入表 + 实时窗口枚举 + 产物校验） |
| `tools/build_lua_lib.ps1` | 从源码编译 Lua 5.4.7 静态库（MSVC） |
| `tools/build_lua_lib.sh` | WSL 包装（转发给 PowerShell） |
| `tools/probe_build_env.sh` | 环境探针（devkitARM / make / python / mGBA 能力） |

**仓外改动**（工具链目录，不在三个仓里，但必须记录）：

| 路径 | 改动 |
|---|---|
| `D:\Shell\toolchain\lua-5.4.7` | 新增（Lua 源码） |
| `D:\Shell\toolchain\lua-5.4.7-build` | 新增（`lua54.lib`） |
| `D:\Shell\toolchain\mgba-dev` | 新增（mGBA，钉在 `d8bad14b`） |
| `D:\Shell\toolchain\mgba-build-d8bad14b` | 新增（mGBA 构建产物，含 PNG / ZLIB / Lua / debugger） |
| `D:\Shell\toolchain\mgba-0.10.5` | 旧版本，保留未删 |
| `D:\Shell\toolchain\mgba-build` | 旧版本构建产物，保留未删 |
| `D:\Shell\toolchain\mgba-dev\CMakeLists.txt` | 补丁 1、3 |
| `D:\Shell\toolchain\mgba-dev\src\platform\cmake\FindFeature.cmake` | 补丁 2 |

> 补丁是**幂等**的，`build.py` 每次都重新检查并按需应用；
> 升级 mGBA 版本后可能需要重跑一次（脚本会提示）。
> `D:\Shell\toolchain\mgba-0.10.5` 那份也打过同样的补丁，保留是为了
> 「万一要回到 0.10.5 产出重制线读得懂的存档」这条退路仍然可用。

---

## 6. 下一步（按成本从低到高）

1. **换掉重制线的录制入口**：`capture_s49_pair.py` 现在钉的是
   `mgba --script <lua>`（macOS 路径）。改成调用本机探针
   （`script <path>` + 环境变量契约完全一致），
   录制链就在本机闭环、且**不需要 mGBA 的 Qt/SDL 前端**。
2. **确认重制线既有 `.ss9` 的可读性覆盖面**：本轮验证了
   `battle-effect-affine-runtime-v1` 的存档；其余 `.ss9` 应全量扫一遍
   （`tools/mgba_probe/probe_client.py --cmd "load <file>"` 批量）。
3. 按 `docs/butano-fidelity-roadmap.md` 的 P0.3 建**状态对拍台**
   （原版 recomp 侧逐帧状态导出 + 重制侧同口径导出 + 逐地址 diff）。
4. **P1.0 spike**：判定 Butano 引擎扛不扛得住 1:1 渲染/音频
   （BG 层位次 / 4bpp / 每帧调色板 / MP2K）。
