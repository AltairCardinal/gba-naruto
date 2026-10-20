# mGBA C API 探针：能力清单与移植方案（2026-10-20）

**状态**: ⚠️ 知识面已完全吸收；**本机构建受阻**（无 C 工具链 / 无 mGBA 源码）
**来源**: `third_party/konoha-workshop/源码/tools/gba_probe.c`（MIT，只读知识库）
**关联**: `notes/external-konoha-workshop-gap-20261020.md` §P3-1、
`notes/windows-migration-20261020.md`（平台约束）、
`notes/runtime-state-entry-audit-20260710.md`（本仓库同类阻塞）

---

## 0. 为什么这条重要

本仓库长期被三件事卡住：

1. `notes/battle-config-format.md` 写的
   *"Blocked: mGBA headless debugger does not support key input injection"*；
2. `notes/runtime-verification-gates-20260710.md` 写的
   *"当前仓库没有有效战斗 savestate，现有 `.sav` 为擦除态，CLI 调试器不能注入按键"*；
3. 多数结构缺"原生判定定点"证据（我们只做到 L2 的 positions）。

第三方的 `gba_probe.c` **一次性覆盖了前两件事**。这是差集清单里
性价比最高的一项，值得单独记一份方案。

---

## 1. 探针的能力面（逐条读源码得出）

它不是一次性脚本，而是一个**通过 stdin 驱动的 REPL**，命令面如下：

| 命令 | 作用 | 对我们的意义 |
|---|---|---|
| `frames <N> <KEYMASK>` | `c->setKeys(c, mask)` 注入按键，跑 N 帧后释放 | **解决"不能注入按键"** |
| `shot <PATH>` | `mCoreTakeScreenshotVF` 截图 | OCR 验证的输入 |
| `dump <ADDR> <LEN> <PATH>` | `c->busRead8` 逐字节导出 ROM/WRAM/EWRAM/IO | 采集证据落盘 |
| `read <ADDR> <LEN>` | 同上，输出到 stdout | 快速探查 |
| `w8/w16/w32 <ADDR> <VAL>` | `c->busWrite*` 直接写内存 | **WRAM 作弊 / 状态注入** |
| `state <PATH>` | `c->saveState` 存 savestate | **解决"没有有效 savestate"** |
| `loadstate <PATH>` | `c->loadState` 读 savestate | 回到任意状态继续采 |
| `savecopy <PATH>` | `c->savedataClone` 克隆 SRAM | 存档不污染原档 |

**关键点**：`state` / `loadstate` 走的是 mGBA 自己的 `stateSize`/`saveState`，
与"擦除态 `.sav`"完全是两码事 —— 这才是我们缺的那份"带语境的战斗前状态"。

按键掩码是 GBA 标准位：

```
A=0x001  B=0x002  SELECT=0x004  START=0x008
RIGHT=0x010  LEFT=0x020  UP=0x040  DOWN=0x080
R=0x100  L=0x200
```

---

## 2. 移植方案

### 2.1 依赖

| 依赖 | 对方环境 | 本机现状 |
|---|---|---|
| mGBA 0.11 源码 + `libmgba` 核心库 | 有（`-DENABLE_DIRECTORIES`） | **无**：本机既无源码也无预编译库 |
| C 编译器 | `arm-none-eabi-gcc`（用于 ROM 侧代码）+ 宿主编译器（用于探针） | **无**：`arm-none-eabi-gcc` / `gcc` / `clang` / `cl` 均不在 PATH；无 VS 安装、无 MinGW/MSYS2 |
| mGBA 运行时采集链 | macOS dylib | **需重建**：Windows 版 mGBA（Qt，commit `d8bad14b`），见 `notes/windows-migration-20261020.md` |

> 探针**只需要 mGBA 的 core，不需要 Qt GUI** —— 它只用
> `<mgba/core/core.h>`、`mCoreFind` / `mCoreLoadFile` / `setKeys` /
> `runFrame` / `busRead8` / `saveState`。
> 这比重建整个 Qt 版轻得多，但仍需要一个 mGBA 源码 checkout 和宿主编译器。

### 2.2 建议步骤

1. **取源码**：拉 mGBA 0.11（或能提供 `mCore` 核心 API 的版本）到
   `third_party/mgba-src/`（或独立仓库，避免污染本仓库许可证边界）。
2. **只编 core**：用 CMake 关掉 Qt / SDL / FFmpeg：
   `cmake -DENABLE_QT=OFF -DENABLE_SDL=OFF -DENABLE_FFMPEG=OFF`
   产出一个最小 `libmgba`（Windows 需 MSVC 或 MinGW）。
3. **移植探针**：`gba_probe.c` 是单文件，逻辑与平台无关；
   需要改的只有 mGBA 0.11→目标版本的头文件/API 差异与
   `mCoreTakeScreenshotVF` 的文件头。
4. **接线到本仓库**：在 `tools/` 下新增 `tools/mgba_probe.py`（或
   `tools/mgba_c_probe/`）作为 Python 客户端，把 REPL 的 stdout 协议解析成
   结构化 JSON；证据落盘格式沿用现有 `build/mgba-*.json` 约定。
5. **验证**：先用 `frames` 走一遍新游戏开场，拿到第一份**真实 savestate**，
   再用它去解 P0-Step 4 的"章节流程入口"与"战斗配置"两个老问题。

### 2.3 验收标准

- 探针能在本机启动并加载 `rom/base.gba`；
- `frames 60 0x008`（START）能推进过标题画面 —— 这一步失败说明按键掩码或
  核心初始化不对；
- `state` 能存出可被 `loadstate` 读回的状态；
- 采集到的 WRAM 片段能与我们静态推导的地址对上
  （`0x02026804` 起的 battle_control、`0x020240C0 + n*468` 的单位槽）。

---

## 3. 与我们已有工具的关系

| 我们的工具 | 与探针的关系 |
|---|---|
| `tools/mgba-headless-snapshot.py` | 走 mgba-sdl 命令行，**不能注入按键**；探针走 C API，可以 |
| `tools/mgba_newgame_walk.lua` 等 Lua 脚本 | 依赖 mGBA 自带脚本支持，能力受限于解释器；探针是直接调用 |
| `play/_scripts/runtime-formation-probe.js`（网页 WASM） | 已解决 positions 的 L2/L3，但**没有 PC/LR/断点**；探针两者都有 |
| `tools/mgba_gdb_probe.py` | GDB 协议路线，可与探针并存（探针做注入，GDB 做断点） |

**结论**：探针不是要替换现有工具，而是补上"注入按键 + 造 savestate"这两块
我们始终缺的能力。真正的前置是**本机工具链**，不是逆向工作本身。

---

## 4. 判定

- 差集清单 P3-1 的**知识部分已吸收**（本文件即为其在本仓库的落点）；
- **构建部分未完成**，阻塞在"本机无 mGBA 源码 + 无 C 编译器"；
- 建议作为**独立立项**推进：它同时解锁 P0-Step 4（章节流程入口）
  与本仓库所有 L2/L3 证据缺口，是当前逆向推进的关键路径。

---

## 5. 2026-10-20 晚：阻塞已解除，方案确定

### 5.1 环境探测结果

| 项 | 结果 |
|---|---|
| 网络 | ✅ 可用（GitHub API HTTP 200） |
| pip 的 mGBA 包 | ❌ 无 |
| 本机 mGBA 缓存 | ❌ 无 |
| mGBA 源码 | ✅ **已下载** `D:\Shell\toolchain\mgba-0.10.5`（0.10.5 源码包 13.7 MB） |
| C 编译器 | ✅ **已就位** `D:\Shell\toolchain\zig-x86_64-windows-0.17.0`（Zig 自带 clang，`zig cc` 即完整 C 编译器，单 zip 免安装） |

> 工具链刻意放在**仓库之外**（`D:\Shell\toolchain`），
> 避免把 100 MB 的编译器塞进仓库、也不污染 SHA-256 证据身份。

### 5.2 关键发现：不需要自己写 C 探针

mGBA 的 **CLI 调试器**（`src/debugger/cli-debugger.c`）已经提供本仓库
`tools/mgba-headless-snapshot.py` 所依赖的**全部**能力：
断点 `b`、读内存 `x/4`、写内存 `w/1`、看寄存器 `status`、
监视点 `watch/w`、单步 `next`、继续 `continue`、帧步进 `frame`。

**缺的只有按键注入。** 而核心 API 已经有：

```c
/* include/mgba/core/core.h */
void (*setKeys)(struct mCore*, uint32_t keys);
void (*addKeys)(struct mCore*, uint32_t keys);
void (*clearKeys)(struct mCore*, uint32_t keys);
```

CLI 调试器的命令表是 `static` 的（`src/debugger/cli-debugger.c:83`），
外部无法扩展，但**在自己的构建树里加一条命令只要几行**：

```c
{ "key", _setKey, "IS", "Press or release a key" },
```

回调里调用 `core->setKeys(core, mask)` 即可。

> 另一条路是 mGBA 的 Lua 脚本（`src/script/engines/lua.c`），
> Lua API 有 `emu:keyPress()`；但 0.10.5 **不自带 Lua 库**
> （`src/third-party/` 里只有 blip_buf / inih / libpng / lzma / sqlite3 / zlib），
> 需要外部 Lua。**加命令更省事。**

### 5.3 落地路径

1. 用 Zig cc 把 mGBA 编成静态库（源文件清单可从各 `CMakeLists.txt` 提取；
   注意 0.10.5 已改用 CMake、**没有 Makefile**，配置解析器是自带的 `inih`）；
2. 给 `cli-debugger.c` 打上 `key` 命令的补丁（补丁文件要入库，便于复现）；
3. 写一个**无头宿主**（`main.c`）：建 GBA core → 载入 ROM →
   建 `CLIDebugger` → 从 stdin 喂命令；
   core 需要的 video/audio 回调给空实现即可（不接 SDL、不接 Qt）；
4. 写 Python 客户端，把命令/输出封装成结构化 JSON，
   接到既有 `tools/mgba-headless-snapshot.py` 的工作流上。

### 5.4 做完之后能干什么

| 能力 | 解锁的仓库目标 |
|---|---|
| 按键注入 | 打通新游戏开场 → 首战 → 战后剧情的**确定性**导航 |
| 真实 savestate（core 的 `saveState`/`loadState`） | 解决"没有有效战斗 savestate"这个老问题 |
| 断点 + PC/LR | `notes/runtime-verification-gates-20260710.md` 要求的 **L2 原生定点**证据 |
| 内存读/写 | 观察战斗配置、任务文字、奖励表的**运行时消费** |

**这是从 L1 走到 L2/L3 的唯一通道。** 在此之前，所有新增的静态结论
（合成夹具、格式推导）都只能停在 L1。

### 5.5 仍需注意

- mGBA 的 `setKeys` 是**电平**语义：按键状态由调用方保持，
  所以需要"按下 → 跑 N 帧 → 释放 → 跑 N 帧"这类成对命令，
  不能只发一次 `setKeys`。
- GBA 按键掩码：`A=0x001 B=0x002 SELECT=0x004 START=0x008
  RIGHT=0x010 LEFT=0x020 UP=0x040 DOWN=0x080 R=0x100 L=0x200`。
- 无头宿主不需要 SDL/Qt，但要给出 `setVideoBuffer` 的缓冲，
  否则某些 core 路径会断言失败。
