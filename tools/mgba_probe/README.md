# mgba_probe — 无头 mGBA 宿主（按键注入 + savestate）

本目录提供一个**无头**的 mGBA 宿主，用来给本仓库的逆向工作提供**动态证据**：
它是目前唯一能在本机上**注入按键**并**造出可用 savestate** 的工具。

没有改 mGBA 源码：所有扩展都挂在 mGBA 自带的 CLI 调试器
（`struct CLIDebuggerSystem::commands`）上。

---

## 1. 组成

| 文件 | 作用 |
|---|---|
| `host_main.c` | 宿主源码（C，MSVC） |
| `build.py` | 构建脚本：先确保 mGBA 静态库存在，再编译/链接宿主 |
| `probe_client.py` | Python 客户端：按命令驱动宿主，输出结构化 JSON |
| `CMakeLists.txt` | （可选）把宿主挂进 mGBA 自己的 CMake 工程，见 §5 |

外部依赖（不在本仓库内）：

- mGBA 源码 `D:/Shell/toolchain/mgba-dev`（可用 `$KONOHA_MGBA_SRC` 覆盖），
  **必须检出到钉死的提交**
  `d8bad14b4540f9114246c0281d74985cf81adc68`
  —— 这正是项目自己在 `tools/macos_mgba_toolchain_profile.py` 里钉的那个 mGBA，
  它的 **GBA 存档版本是 `0x0000000A`**，与 Butano 重制线既有的 `.ss9` 一致
  （格式与 BIOS 都对上）；`build.py` 会校验 HEAD，不符就**失败关闭**。
- mGBA 构建树 `D:/Shell/toolchain/mgba-build-d8bad14b`（`$KONOHA_MGBA_BUILD`）
- Lua 5.4 静态库 `D:/Shell/toolchain/lua-5.4.7-build/lua54.lib`（`$KONOHA_LUA_LIB`），
  由 `tools/build_lua_lib.ps1` 从源码编出
- MSVC Build Tools 2022 + 便携 CMake 3.31.7

---

## 2. 构建

```powershell
python tools/mgba_probe/build.py              # 宿主（必要时先建 mGBA 静态库）
python tools/mgba_probe/build.py --rebuild-mgba   # 强制重建 mGBA 静态库
```

产物：`build/mgba-probe/mgba-probe.exe`
（同时产出 `build/mgba-probe/mgba-probe.map`，用于把崩溃地址翻译成函数名）。

`build.py` 会**从 CMake 生成的 `mgba.vcxproj` 里读出 mGBA 静态库实际使用的
预处理宏**再传给 `cl.exe`。这一步不是多余的：`struct mCore` 内嵌
`#ifdef ENABLE_DEBUGGERS` 成员，宏不一致会让宿主与库的 ABI 不同
（指纹由 `abi_probe.c` 实测得出，见 `notes/mgba-probe-build-20261020.md`）。
`host_main.c` 里另有 `_Static_assert` 指纹，宏一旦漂移就是**编译错误**
而不是运行期崩溃。

> **`LIBMGBA_ONLY` 不能用**：新版 mGBA 里它会连带关掉
> `ENABLE_DEBUGGERS` / `USE_LUA` / `USE_PNG` / `USE_ZLIB`，
> 而探针需要调试器（断点）、脚本引擎和 PNG 截图。
> 改为逐个关掉图形前端（`BUILD_QT=OFF` / `BUILD_SDL=OFF`）。

---

## 3. 用法

### 3.1 直接驱动（stdin/stdout）

```powershell
build\mgba-probe\mgba-probe.exe rom\base.gba
```

宿主启动后打印 `READY`，之后每读一行就执行一条调试器命令，输出写到 stdout，
阶段轨迹写到 stderr。

### 3.2 Python 客户端（结构化 JSON）

```powershell
python tools/mgba_probe/probe_client.py --rom rom/base.gba --script run.txt
python tools/mgba_probe/probe_client.py --rom rom/base.gba \
    --cmd "frames 30 0x000" --cmd "dump 0x02026804 8" --cmd "save build/tmp.ss9"
```

脚本文件一行一条命令，空行和 `#` 开头的行会被忽略。客户端在每条命令后追加一个
`echo` 哨兵，据此把输出准确归属到命令，输出形如：

```json
{
  "rom": "rom/base.gba",
  "exe": "build/mgba-probe/mgba-probe.exe",
  "exit_code": 0,
  "steps": [
    {"index": 0, "command": "dump 0x02026804 8", "status": "ok",
     "output": ["DUMP 02026804 8", "0000000000000000", "ENDDUMP"],
     "dump": {"address": "02026804", "length": 8,
              "bytes": "0000000000000000",
              "values": ["00", "00", "00", "00", "00", "00", "00", "00"]}}
  ],
  "stderr": ["[probe] open rom", "..."]
}
```

`--out <file>` 可把 JSON 写到文件。

---

## 4. 命令

宿主自带（额外于 mGBA）：

| 命令 | 说明 |
|---|---|
| `key <mask>` | 设置按键状态（保持） |
| `keyoff` | 释放全部按键 |
| `frames <count> <mask>` | 按键 → 跑 N 帧 → 释放按键 |
| `run <count>` | 跑 N 帧，**不改动**按键状态（用于观察按住时的 KEYINPUT） |
| `dump <addr> <len>` | 十六进制导出任意区域 |
| `save <path>` | 写 savestate 到文件 |
| `load <path>` | 从文件读 savestate |
| `poke <addr> <val>` / `poke16 <addr> <val>` | 往模拟地址空间写字节 / 半字 |
| `shot <path>` | 写当前帧的 **PNG** |
| `rawshot <path>` | 写当前帧的原始 **RGBA**（240×160，无损，不经 PNG） |
| `cont [budget]` | 跑到断点命中（默认 600 帧上限） |
| **`script <path>`** | **加载 Lua 脚本**；`callbacks:add("frame", …)` 每完成一帧触发一次（2026-10-23 新增） |
| `echo <token>` | 回显一个 token（客户端哨兵用） |

> `script` 需要宿主带 Lua 支持构建：`tools/build_lua_lib.ps1` 先把 Lua 5.4 编成
> 静态库，`build.py` 检测到它就加 `-DUSE_LUA=ON -DENABLE_SCRIPTING=ON`。
> 重制线的 Lua 探针脚本（如 `mgba_original_input_frame_sequence.lua`）
> **原样可用**，产物格式（`frame-*.png` / `*.ss9` / `audit.json`）一致。
> 详见 `docs/local-toolchain-20261023.md`。

### 无窗口、无声

宿主只链接 libmgba 的 **core**（`BUILD_QT=OFF` / `BUILD_SDL=OFF`），
**导入表里没有 USER32 / winmm / avrt / SDL / OpenAL** ⇒
进程在物理上不可能开窗或开音频设备；`emu:screenshot` 只写文件。
`python tools/mgba_probe/verify_headless_recording.py` 是这条性质的门禁：
它解析导入表、并在一次真实录制期间枚举该进程的全部顶层窗口。

mGBA 自带（经 `CLIDebuggerRunCommand`）：`status`、`b`/`break`、`c`/`continue`、
`x/1` `x/2` `x/4`、`w/1` `w/2` `w/4`、`r/1` `r/2` `r/4`、`watch`/`watch/r`/`watch/w`、
`next`、`print`/`print/x`、`disassemble`、`backtrace`、`frame`（GBA 平台）、
`listb`、`listw`、`reset`、`events`、`help`。

### 按键掩码

与 GBA KEYINPUT 位序一致，也是 `core->setKeys()` 期望的位序：

```
A=0x001  B=0x002  SELECT=0x004  START=0x008
RIGHT=0x010  LEFT=0x020  UP=0x040  DOWN=0x080
R=0x100  L=0x200
```

按住某键时，模拟内的 KEYINPUT（`0x04000130`，小端 16 位）读回
`0x03FF ^ mask`：例如按住 START → `F7 03`。

---

## 5. 可选：并入 mGBA 的 CMake 工程

`CMakeLists.txt` 让宿主作为 mGBA 自己的子工程构建，从而由 CMake 保证
宏与对象选择完全一致：

```powershell
cmake -S tools/mgba_probe -B build/mgba-probe/cmake -DCMAKE_BUILD_TYPE=Release
cmake --build build/mgba-probe/cmake --config Release
```

（`build.py` 目前走的是"用 mGBA 已生成的 vcxproj 读宏 + 直接 cl/link"的路径，
因为它复用已有的 `mgba-build` 静态库，更省时间。）

---

## 6. 已知限制

- 宿主不做画面识别（没有 OCR），只能靠内存/寄存器读数判断状态。
- mGBA 自带的 `save`/`load` 是**槽号**语义；本宿主用 `save <path>`/`load <path>`
  另开一套基于文件的存取（mGBA 的 `"*"` 参数格式解析不了路径）。
- 断点/单步是 mGBA CLI 的交互命令；脚本化"跑到断点停下"还需要在客户端侧补。
